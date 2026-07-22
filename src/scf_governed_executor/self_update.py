from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from .core import (
    AUTHORIZATION_FIELDS,
    EXECUTOR_VERSION,
    OPERATION_SCHEMA_VERSION,
    RESULT_SCHEMA_VERSION,
    TERMINAL_STATUSES,
    CommandSupervisor,
    ExecutorError,
    GuardError,
    ResultConflictError,
    SchemaError,
    TerminalProgress,
    base_result,
    canonical_json,
    capture_repository_state,
    command_record_dict,
    evaluate_repository_guards,
    operation_digest,
    result_destination,
    utc_now,
    write_result_exclusive,
)

from . import strict_validation


SELF_UPDATE_OPERATION_TYPE = "executor-self-update"
SELF_UPDATE_INPUT_FIELDS = {
    "current_executor_version",
    "replacement_executor_version",
    "operations",
    "validation_profile",
}
SELF_UPDATE_EXPECTED_FIELDS = {"files"}
SELF_UPDATE_VALIDATION_PROFILES = {"focused", "complete"}
SELF_UPDATE_ACTIONS = {"create", "replace", "delete"}
SELF_UPDATE_PROTECTED_PATHS = frozenset(
    {
        "scripts/governed-execute",
        "src/scf_governed_executor/__init__.py",
        "src/scf_governed_executor/__main__.py",
        "src/scf_governed_executor/core.py",
        "src/scf_governed_executor/errors.py",
        "src/scf_governed_executor/git_publication.py",
        "src/scf_governed_executor/issue_comments.py",
        "src/scf_governed_executor/local_files.py",
        "src/scf_governed_executor/lifecycle.py",
        "src/scf_governed_executor/runtime.py",
        "src/scf_governed_executor/self_update.py",
        "src/scf_governed_executor/validation.py",
        "tests/governed_executor/test_core.py",
        "tests/governed_executor/test_executor_self_update.py",
        "tests/governed_executor/test_issue_comments.py",
        "tests/governed_executor/test_independent_git_lifecycle.py",
        "tests/governed_executor/test_local_file_protection.py",
    }
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MODE = re.compile(r"^0[0-7]{3}$")
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class SelfUpdateError(ExecutorError):
    def __init__(
        self,
        message: str,
        *,
        evidence: Mapping[str, Any] | None = None,
        mutation_observed: bool = False,
        rollback_verified: bool = False,
    ) -> None:
        super().__init__(message)
        self.evidence = dict(evidence or {})
        self.mutation_observed = mutation_observed
        self.rollback_verified = rollback_verified


_STRICT = strict_validation.StrictValidator(SchemaError)


def _exact_fields(
    value: Mapping[str, Any],
    allowed: set[str] | frozenset[str],
    required: set[str] | frozenset[str],
    location: str,
) -> None:
    _STRICT.exact_fields(value, allowed, required, location)


def _object(value: Any, location: str) -> dict[str, Any]:
    return _STRICT.object(value, location)


def _string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise SchemaError(f"{location} must be a non-empty string")
    return value


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _validated_path(value: Any, location: str) -> str:
    path = _string(value, location)
    candidate = Path(path)
    if candidate.is_absolute() or path.startswith(("/", "\\")):
        raise SchemaError(f"{location} must be repository-relative")
    if any(part in ("", ".", "..") for part in candidate.parts):
        raise SchemaError(f"{location} is not normalized")
    if candidate.as_posix() != path:
        raise SchemaError(f"{location} must use normalized POSIX form")
    if path not in SELF_UPDATE_PROTECTED_PATHS:
        raise SchemaError(f"{location} is outside the self-update path inventory")
    return path


def _operation_fields(action: str) -> set[str]:
    common = {"action", "path", "mode"}
    if action == "create":
        return common | {"content", "content_sha256"}
    if action == "replace":
        return common | {"content", "content_sha256", "expected_sha256"}
    if action == "delete":
        return common | {"expected_sha256"}
    return common


def _validate_operations(
    operations: Any, expected_mutations: Any
) -> list[dict[str, Any]]:
    if not isinstance(operations, list) or not operations:
        raise SchemaError("inputs.operations must be a non-empty array")
    if len(operations) > len(SELF_UPDATE_PROTECTED_PATHS):
        raise SchemaError("inputs.operations exceeds protected path inventory")

    normalized: list[dict[str, Any]] = []
    expected_files: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(operations):
        location = f"inputs.operations[{index}]"
        item = _object(raw, location)
        action = item.get("action")
        if action not in SELF_UPDATE_ACTIONS:
            raise SchemaError(f"{location}.action is unsupported")
        fields = _operation_fields(action)
        _exact_fields(item, fields, fields, location)
        path = _validated_path(item["path"], f"{location}.path")
        if path in seen:
            raise SchemaError(f"duplicate self-update path: {path}")
        seen.add(path)

        mode = item["mode"]
        if not isinstance(mode, str) or not MODE.fullmatch(mode):
            raise SchemaError(f"{location}.mode has invalid form")

        expected_sha256 = item.get("expected_sha256")
        if action in {"replace", "delete"}:
            if not isinstance(expected_sha256, str) or not SHA256.fullmatch(
                expected_sha256
            ):
                raise SchemaError(
                    f"{location}.expected_sha256 must be lowercase SHA-256"
                )

        content = item.get("content")
        content_sha256 = item.get("content_sha256")
        if action in {"create", "replace"}:
            if not isinstance(content, str):
                raise SchemaError(f"{location}.content must be a string")
            if not isinstance(content_sha256, str) or not SHA256.fullmatch(
                content_sha256
            ):
                raise SchemaError(
                    f"{location}.content_sha256 must be lowercase SHA-256"
                )
            if _sha256_bytes(content.encode("utf-8")) != content_sha256:
                raise SchemaError(
                    f"{location}.content_sha256 does not match content"
                )

        normalized_item = dict(item)
        normalized_item["path"] = path
        normalized.append(normalized_item)
        expected_files.append(
            {
                "action": action,
                "path": path,
                "before_sha256": (
                    None if action == "create" else expected_sha256
                ),
                "after_sha256": (
                    None if action == "delete" else content_sha256
                ),
                "mode": mode,
            }
        )

    expected = _object(expected_mutations, "expected_mutations")
    _exact_fields(
        expected,
        SELF_UPDATE_EXPECTED_FIELDS,
        SELF_UPDATE_EXPECTED_FIELDS,
        "expected_mutations",
    )
    if expected["files"] != expected_files:
        raise SchemaError(
            "expected_mutations.files does not exactly match self-update operations"
        )
    return normalized


def load_self_update_operation(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SchemaError(f"cannot read operation: {exc}") from exc
    try:
        operation = json.loads(
            raw,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-standard JSON constant: {value}")
            ),
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise SchemaError(f"invalid operation JSON: {exc}") from exc

    operation = _object(operation, "operation")
    top_fields = {
        "schema_version",
        "operation_id",
        "operation_type",
        "executor_version",
        "operation_digest",
        "repository",
        "guards",
        "authorization",
        "inputs",
        "expected_mutations",
        "validation",
        "publication",
        "result",
    }
    _exact_fields(operation, top_fields, top_fields, "operation")
    if operation["schema_version"] != OPERATION_SCHEMA_VERSION:
        raise SchemaError("unsupported operation schema version")
    if operation["operation_type"] != SELF_UPDATE_OPERATION_TYPE:
        raise SchemaError("unsupported self-update operation type")
    if operation["executor_version"] != EXECUTOR_VERSION:
        raise SchemaError("incompatible running executor version")
    operation_id = operation["operation_id"]
    if not isinstance(operation_id, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}", operation_id
    ):
        raise SchemaError("operation_id has invalid form")
    digest = operation["operation_digest"]
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise SchemaError("operation_digest must be lowercase SHA-256")
    if digest != operation_digest(operation):
        raise SchemaError("operation digest mismatch")

    repository = _object(operation["repository"], "repository")
    _exact_fields(repository, {"root", "origin"}, {"root", "origin"}, "repository")
    _string(repository["root"], "repository.root")
    _string(repository["origin"], "repository.origin")

    guards = _object(operation["guards"], "guards")
    _exact_fields(guards, {"branch", "head", "clean"}, {"branch", "head", "clean"}, "guards")
    _string(guards["branch"], "guards.branch")
    if not isinstance(guards["head"], str) or not re.fullmatch(
        r"[0-9a-f]{40}", guards["head"]
    ):
        raise SchemaError("guards.head must be a lowercase full commit id")
    if guards["clean"] is not True:
        raise SchemaError("executor self-update requires a clean starting tree")

    authorization = _object(operation["authorization"], "authorization")
    _exact_fields(
        authorization,
        AUTHORIZATION_FIELDS,
        AUTHORIZATION_FIELDS,
        "authorization",
    )
    for key, value in authorization.items():
        if not isinstance(value, bool):
            raise SchemaError(f"authorization.{key} must be boolean")
    required = {"interrogate", "edit", "validate"}
    if not all(authorization[key] for key in required):
        raise SchemaError(
            "executor self-update requires interrogate, edit, and validate authorization"
        )
    forbidden = set(AUTHORIZATION_FIELDS) - required
    enabled = sorted(key for key in forbidden if authorization[key])
    if enabled:
        raise SchemaError(
            "operation broadens authorization: " + ", ".join(enabled)
        )

    inputs = _object(operation["inputs"], "inputs")
    _exact_fields(
        inputs,
        SELF_UPDATE_INPUT_FIELDS,
        SELF_UPDATE_INPUT_FIELDS,
        "inputs",
    )
    current_version = _string(
        inputs["current_executor_version"], "inputs.current_executor_version"
    )
    replacement_version = _string(
        inputs["replacement_executor_version"],
        "inputs.replacement_executor_version",
    )
    if not VERSION.fullmatch(current_version) or not VERSION.fullmatch(
        replacement_version
    ):
        raise SchemaError("executor versions must use MAJOR.MINOR.PATCH form")
    if current_version != EXECUTOR_VERSION:
        raise SchemaError("current executor version mismatch")
    if replacement_version == current_version:
        raise SchemaError("replacement executor version must differ")
    if inputs["validation_profile"] not in SELF_UPDATE_VALIDATION_PROFILES:
        raise SchemaError("unsupported self-update validation profile")
    operation["_normalized_operations"] = _validate_operations(
        inputs["operations"], operation["expected_mutations"]
    )

    if _object(operation["validation"], "validation"):
        raise SchemaError("validation must be empty; self-update owns validation")
    if _object(operation["publication"], "publication"):
        raise SchemaError("publication must be empty for executor self-update")

    result = _object(operation["result"], "result")
    _exact_fields(result, {"directory", "filename"}, {"directory", "filename"}, "result")
    _string(result["directory"], "result.directory")
    filename = _string(result["filename"], "result.filename")
    if not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{7,191}\.result\.json", filename
    ):
        raise SchemaError("result.filename has invalid form")
    return operation


def _target(root: Path, relative: str) -> Path:
    target = root.joinpath(*Path(relative).parts)
    try:
        target.resolve(strict=False).relative_to(root.resolve())
    except ValueError as exc:
        raise SelfUpdateError(f"path escapes repository: {relative}") from exc
    current = root
    for part in Path(relative).parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise SelfUpdateError(f"symlink ancestor is forbidden: {relative}")
    if target.is_symlink():
        raise SelfUpdateError(f"symlink target is forbidden: {relative}")
    return target


def _write_atomic(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.self-update-", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _capture_before(
    root: Path, operations: Sequence[Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    before: dict[str, dict[str, Any]] = {}
    for operation in operations:
        relative = operation["path"]
        target = _target(root, relative)
        action = operation["action"]
        if action == "create":
            if target.exists():
                raise SelfUpdateError(f"create refuses existing path: {relative}")
            before[relative] = {"exists": False, "content": None, "mode": None}
            continue
        if not target.is_file():
            raise SelfUpdateError(
                f"{action} requires an existing regular file: {relative}"
            )
        content = target.read_bytes()
        digest = _sha256_bytes(content)
        if digest != operation["expected_sha256"]:
            raise SelfUpdateError(f"source digest mismatch: {relative}")
        actual_mode = f"0{target.stat().st_mode & 0o777:03o}"
        if actual_mode != operation["mode"]:
            raise SelfUpdateError(f"source mode mismatch: {relative}")
        before[relative] = {
            "exists": True,
            "content": content,
            "mode": actual_mode,
            "sha256": digest,
        }
    return before


def _apply(
    root: Path, operations: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, operation in enumerate(operations):
        relative = operation["path"]
        target = _target(root, relative)
        action = operation["action"]
        if action == "delete":
            target.unlink()
            after_sha256 = None
            verified = not target.exists()
        else:
            data = operation["content"].encode("utf-8")
            _write_atomic(target, data, int(operation["mode"], 8))
            after_sha256 = _sha256_bytes(target.read_bytes())
            actual_mode = f"0{target.stat().st_mode & 0o777:03o}"
            verified = (
                after_sha256 == operation["content_sha256"]
                and actual_mode == operation["mode"]
            )
        record = {
            "index": index,
            "action": action,
            "path": relative,
            "expected_after_sha256": operation.get("content_sha256"),
            "after_sha256": after_sha256,
            "verified": verified,
        }
        records.append(record)
        if not verified:
            raise SelfUpdateError(
                f"read-after-write verification failed: {relative}",
                evidence={"file_operations": records},
                mutation_observed=True,
            )
    return records


def _restore(
    root: Path, before: Mapping[str, Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], bool]:
    records: list[dict[str, Any]] = []
    verified_all = True
    for relative, state in reversed(list(before.items())):
        target = _target(root, relative)
        try:
            if not state["exists"]:
                if target.exists():
                    target.unlink()
                verified = not target.exists()
                digest = None
            else:
                _write_atomic(
                    target,
                    state["content"],
                    int(state["mode"], 8),
                )
                digest = _sha256_bytes(target.read_bytes())
                actual_mode = f"0{target.stat().st_mode & 0o777:03o}"
                verified = (
                    digest == state["sha256"] and actual_mode == state["mode"]
                )
        except OSError as exc:
            verified = False
            digest = None
            records.append(
                {
                    "path": relative,
                    "verified": False,
                    "error": str(exc),
                }
            )
        else:
            records.append(
                {
                    "path": relative,
                    "verified": verified,
                    "sha256": digest,
                }
            )
        verified_all = verified_all and verified
    return records, verified_all



def _purge_bytecode(root: Path) -> list[str]:
    removed: list[str] = []
    for relative in (
        "src/scf_governed_executor/__pycache__",
        "tests/governed_executor/__pycache__",
    ):
        target = root / relative
        if target.exists():
            shutil.rmtree(target)
            removed.append(relative)
    return removed


def _status_paths(status: Sequence[str]) -> list[str]:
    return sorted(
        line[3:] if len(line) > 2 and line[2] == " " else line[2:]
        for line in status
    )

def _run_checked(
    supervisor: CommandSupervisor,
    command: Sequence[str],
    root: Path,
    *,
    phase: str,
    timeout: float,
) -> dict[str, Any]:
    record = supervisor.run(
        command,
        root,
        timeout_seconds=timeout,
        phase=phase,
    )
    result = command_record_dict(record)
    if record.exit_code != 0:
        raise SelfUpdateError(
            record.stderr.strip() or f"{phase} failed",
            evidence={"failed_command": result},
            mutation_observed=True,
        )
    return result


def _verification_operation(
    operation: Mapping[str, Any],
    root: Path,
    directory: Path,
) -> tuple[Path, Path]:
    replacement_version = operation["inputs"]["replacement_executor_version"]
    probe_result = directory / (
        operation["operation_id"] + ".replacement-probe.result.json"
    )
    probe_path = directory / (
        operation["operation_id"] + ".replacement-probe.operation.json"
    )
    probe = {
        "schema_version": OPERATION_SCHEMA_VERSION,
        "operation_id": operation["operation_id"] + ".replacement-probe",
        "operation_type": "repository-interrogation",
        "executor_version": replacement_version,
        "operation_digest": "",
        "repository": dict(operation["repository"]),
        "guards": {
            "branch": operation["guards"]["branch"],
            "head": operation["guards"]["head"],
            "clean": False,
        },
        "authorization": {
            key: key == "interrogate" for key in AUTHORIZATION_FIELDS
        },
        "inputs": {},
        "expected_mutations": {},
        "validation": {},
        "publication": {},
        "result": {
            "directory": str(directory),
            "filename": probe_result.name,
        },
    }
    probe["operation_digest"] = operation_digest(probe)
    with probe_path.open("x", encoding="utf-8") as handle:
        json.dump(probe, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return probe_path, probe_result


def execute_self_update(
    operation: Mapping[str, Any],
    operation_path: Path,
    progress: TerminalProgress | None = None,
) -> tuple[dict[str, Any], Path]:
    progress = progress or TerminalProgress()
    progress.phase(2, "evaluating repository and executor guards")
    result = base_result(operation)
    result["mutation"]["authorized"] = True
    result["self_update"] = {
        "running_executor_version": EXECUTOR_VERSION,
        "replacement_executor_version": operation["inputs"][
            "replacement_executor_version"
        ],
        "file_operations": [],
        "rollback": [],
        "rollback_verified": False,
        "replacement_probe": {},
    }
    supervisor = CommandSupervisor()
    repository_root = Path(operation["repository"]["root"]).expanduser().resolve()
    destination = result_destination(operation, repository_root)
    if destination.exists():
        raise ResultConflictError(f"result already exists: {destination}")

    root: Path | None = None
    before: dict[str, dict[str, Any]] = {}
    mutation_observed = False
    try:
        root, command_records, state = evaluate_repository_guards(
            operation, supervisor, progress
        )
        result["commands"].extend(command_records)
        result["starting_state"] = state
        if operation_path.is_relative_to(root):
            raise GuardError(
                "self-update operation description must be outside repository"
            )
        progress.check("repository identity and exact state verified")

        operations = operation["_normalized_operations"]
        before = _capture_before(root, operations)
        result["self_update"]["before"] = {
            path: {
                key: value
                for key, value in state.items()
                if key != "content"
            }
            for path, state in before.items()
        }
        progress.check("protected path inventory and source digests verified")

        progress.phase(3, "performing isolated executor replacement")
        result["mutation"]["attempted"] = True
        records = _apply(root, operations)
        mutation_observed = bool(records)
        result["mutation"]["observed"] = mutation_observed
        result["self_update"]["file_operations"] = records
        result["self_update"]["bytecode_removed_before_validation"] = (
            _purge_bytecode(root)
        )
        progress.check("replacement bytes and modes verified")

        profile = operation["inputs"]["validation_profile"]
        if profile == "focused":
            validation_command = [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests/governed_executor",
            ]
        else:
            validation_command = ["./scripts/validate"]
        result["commands"].append(
            _run_checked(
                supervisor,
                validation_command,
                root,
                phase="replacement validation",
                timeout=900.0,
            )
        )
        progress.check("replacement validation passed")

        with tempfile.TemporaryDirectory(
            prefix="scf-self-update-probe-",
            dir=destination.parent,
        ) as temporary:
            temporary_path = Path(temporary)
            probe_path, probe_result = _verification_operation(
                operation, root, temporary_path
            )
            probe_command = ["./scripts/governed-execute", str(probe_path)]
            result["commands"].append(
                _run_checked(
                    supervisor,
                    probe_command,
                    root,
                    phase="replacement executor probe",
                    timeout=120.0,
                )
            )
            if not probe_result.is_file():
                raise SelfUpdateError(
                    "replacement executor did not create probe result",
                    mutation_observed=True,
                )
            probe = json.loads(probe_result.read_text(encoding="utf-8"))
            if probe.get("executor_version") != operation["inputs"][
                "replacement_executor_version"
            ]:
                raise SelfUpdateError(
                    "replacement executor probe version mismatch",
                    mutation_observed=True,
                )
            if probe.get("terminal_status") != "local-mutation-completed":
                raise SelfUpdateError(
                    "replacement executor probe did not complete",
                    mutation_observed=True,
                )
            result["self_update"]["replacement_probe"] = {
                "executor_version": probe.get("executor_version"),
                "terminal_status": probe.get("terminal_status"),
                "operation_id": probe.get("operation_id"),
            }
        progress.check("replacement executor independently verified")

        progress.phase(4, "verifying resulting repository state")
        ending_commands, ending_state = capture_repository_state(root, supervisor)
        result["commands"].extend(ending_commands)
        result["ending_state"] = ending_state
        expected_paths = sorted(
            operation_item["path"]
            for operation_item in operation["_normalized_operations"]
        )
        observed_paths = _status_paths(ending_state["status"])
        if observed_paths != expected_paths:
            raise SelfUpdateError(
                "repository mutation escaped declared self-update inventory",
                evidence={
                    "expected_paths": expected_paths,
                    "observed_paths": observed_paths,
                },
                mutation_observed=True,
            )
        result["mutation"]["completed"] = True
        result["terminal_status"] = "local-mutation-completed"
        result["safest_next_interaction"] = (
            "Review self-update, validation, and replacement-probe evidence."
        )
    except GuardError as exc:
        result["terminal_status"] = "guard-failed"
        result["diagnostics"].append(str(exc))
    except (SelfUpdateError, OSError, ValueError, json.JSONDecodeError) as exc:
        result["diagnostics"].append(str(exc))
        result["mutation"]["observed"] = mutation_observed or getattr(
            exc, "mutation_observed", False
        )
        if isinstance(exc, SelfUpdateError) and exc.evidence:
            result["self_update"]["failure_evidence"] = exc.evidence
        if result["mutation"]["observed"] and root is not None and before:
            rollback, rollback_verified = _restore(root, before)
            result["self_update"]["rollback"] = rollback
            result["self_update"]["bytecode_removed_after_rollback"] = (
                _purge_bytecode(root)
            )
            rollback_commands, rollback_state = capture_repository_state(
                root, supervisor
            )
            result["commands"].extend(rollback_commands)
            result["self_update"]["rollback_state"] = rollback_state
            repository_restored = rollback_state["clean"]
            rollback_verified = rollback_verified and repository_restored
            result["self_update"]["rollback_verified"] = rollback_verified
            result["terminal_status"] = (
                "post-mutation-validation-failed"
                if rollback_verified
                else "partial-local-mutation"
            )
            result["safest_next_interaction"] = (
                "Review restored failure evidence before preparing a new operation."
                if rollback_verified
                else "Do not rerun. Repository may contain unresolved executor mutation."
            )
        else:
            result["terminal_status"] = "pre-mutation-failed"
        if root is not None:
            try:
                ending_commands, ending_state = capture_repository_state(
                    root, supervisor
                )
                result["commands"].extend(ending_commands)
                result["ending_state"] = ending_state
            except ExecutorError as state_exc:
                result["diagnostics"].append(
                    f"ending-state capture failed: {state_exc}"
                )
    finally:
        result["finished_at"] = utc_now()

    if result["terminal_status"] not in TERMINAL_STATUSES:
        raise ExecutorError("invalid terminal result status")
    progress.phase(5, "writing execution evidence")
    write_result_exclusive(destination, result)
    progress.check("result artifact created without overwrite")
    return result, destination


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print(
            "usage: ./scripts/governed-execute /path/to/operation.json",
            file=sys.stderr,
        )
        return 64

    operation_path = Path(args[0]).expanduser().resolve()
    destination: Path | None = None
    progress = TerminalProgress()
    try:
        print(f"Governed Executor {EXECUTOR_VERSION}", flush=True)
        progress.phase(1, "validating executor self-update description")
        operation = load_self_update_operation(operation_path)
        destination = result_destination(
            operation,
            Path(operation["repository"]["root"]).expanduser().resolve(),
        )
        progress.check("schema and authorization verified")
        progress.check("operation digest verified")
        progress.check("closed protected path inventory verified")
        print("", flush=True)
        print(f"Repository : {operation['repository']['root']}", flush=True)
        print(f"Revision   : {operation['guards']['head']}", flush=True)
        print(f"Operation  : {operation['operation_id']}", flush=True)
        print(f"Type       : {operation['operation_type']}", flush=True)
        print(f"Result     : {destination}", flush=True)
        print("", flush=True)

        result, destination = execute_self_update(
            operation, operation_path, progress
        )

        print("", flush=True)
        print("-" * 60, flush=True)
        print(f"STATUS: {result['terminal_status']}", flush=True)
        print("", flush=True)
        print("Result:", flush=True)
        print(f"  {destination}", flush=True)
        print("", flush=True)
        print("Next step:", flush=True)
        print(f"  {result['safest_next_interaction']}", flush=True)
        return 0 if result["terminal_status"] == "local-mutation-completed" else 1
    except ExecutorError as exc:
        print("", file=sys.stderr, flush=True)
        print("-" * 60, file=sys.stderr, flush=True)
        print("STATUS: executor-failed", file=sys.stderr, flush=True)
        print(f"Reason: {exc}", file=sys.stderr, flush=True)
        if destination is not None:
            print(f"Result: {destination}", file=sys.stderr, flush=True)
        return 1
