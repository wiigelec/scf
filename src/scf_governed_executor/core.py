from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

from .local_files import (
    LocalFileOperationError,
    apply_local_file_operations,
    validate_local_file_inputs,
)
from .git_publication import (
    GitPublicationError,
    publish_git_changes,
    validate_git_publication_inputs,
)
from .validation import (
    GovernedValidationError,
    run_governed_validation,
    validate_governed_validation_inputs,
)


EXECUTOR_VERSION = "0.1.0"
OPERATION_SCHEMA_VERSION = 1
RESULT_SCHEMA_VERSION = 1
TERMINAL_STATUSES = {
    "guard-failed",
    "pre-mutation-failed",
    "partial-local-mutation",
    "partial-remote-mutation",
    "post-mutation-validation-failed",
    "local-mutation-completed",
    "commit-completed",
    "publication-completed",
    "validation-completed",
}
SUPPORTED_OPERATION_TYPES = {
    "repository-interrogation",
    "local-file-operations",
    "git-publication",
    "governed-validation",
}
TOP_LEVEL_FIELDS = {
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
REPOSITORY_FIELDS = {"root", "origin"}
GUARD_FIELDS = {"branch", "head", "clean"}
AUTHORIZATION_FIELDS = {
    "interrogate",
    "edit",
    "validate",
    "stage",
    "commit",
    "push",
    "issue",
    "pull_request",
    "review",
    "merge",
    "close_issue",
}
RESULT_FIELDS = {"directory", "filename"}
SECRET_NAME = re.compile(
    r"(?:token|password|passwd|secret|private[_-]?key|credential|authorization)",
    re.IGNORECASE,
)
TOKEN_PATTERNS = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}"),
)


class ExecutorError(RuntimeError):
    """Base executor failure."""


class SchemaError(ExecutorError):
    """Operation schema failure."""


class GuardError(ExecutorError):
    """Repository guard failure."""


class ResultConflictError(ExecutorError):
    """Result output would overwrite an existing path."""


class CommandTimeoutError(ExecutorError):
    """Supervised command exceeded its timeout."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def operation_digest(operation: Mapping[str, Any]) -> str:
    body = dict(operation)
    body.pop("operation_digest", None)
    return hashlib.sha256(canonical_json(body)).hexdigest()


def _require_exact_fields(
    value: Mapping[str, Any],
    allowed: set[str],
    required: set[str],
    location: str,
) -> None:
    unknown = set(value) - allowed
    missing = required - set(value)
    if unknown:
        raise SchemaError(
            f"{location} contains unknown fields: {', '.join(sorted(unknown))}"
        )
    if missing:
        raise SchemaError(
            f"{location} is missing required fields: {', '.join(sorted(missing))}"
        )


def _require_object(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError(f"{location} must be an object")
    return value


def _require_bool_map(value: Any, fields: set[str], location: str) -> dict[str, bool]:
    obj = _require_object(value, location)
    _require_exact_fields(obj, fields, fields, location)
    for key, item in obj.items():
        if not isinstance(item, bool):
            raise SchemaError(f"{location}.{key} must be boolean")
    return obj


def load_operation(path: Path) -> dict[str, Any]:
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

    operation = _require_object(operation, "operation")
    _require_exact_fields(
        operation, TOP_LEVEL_FIELDS, TOP_LEVEL_FIELDS, "operation"
    )

    if operation["schema_version"] != OPERATION_SCHEMA_VERSION:
        raise SchemaError("unsupported operation schema version")
    if operation["executor_version"] != EXECUTOR_VERSION:
        raise SchemaError("incompatible executor version")
    if operation["operation_type"] not in SUPPORTED_OPERATION_TYPES:
        raise SchemaError("unsupported operation type")
    if not isinstance(operation["operation_id"], str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}", operation["operation_id"]
    ):
        raise SchemaError("operation_id has invalid form")
    if not isinstance(operation["operation_digest"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", operation["operation_digest"]
    ):
        raise SchemaError("operation_digest must be lowercase SHA-256")
    actual_digest = operation_digest(operation)
    if operation["operation_digest"] != actual_digest:
        raise SchemaError("operation digest mismatch")

    repository = _require_object(operation["repository"], "repository")
    _require_exact_fields(
        repository, REPOSITORY_FIELDS, REPOSITORY_FIELDS, "repository"
    )
    for key in REPOSITORY_FIELDS:
        if not isinstance(repository[key], str) or not repository[key]:
            raise SchemaError(f"repository.{key} must be a non-empty string")

    guards = _require_object(operation["guards"], "guards")
    _require_exact_fields(guards, GUARD_FIELDS, GUARD_FIELDS, "guards")
    if not isinstance(guards["branch"], str) or not guards["branch"]:
        raise SchemaError("guards.branch must be a non-empty string")
    if not isinstance(guards["head"], str) or not re.fullmatch(
        r"[0-9a-f]{40}", guards["head"]
    ):
        raise SchemaError("guards.head must be a lowercase full commit id")
    if not isinstance(guards["clean"], bool):
        raise SchemaError("guards.clean must be boolean")

    authorization = _require_bool_map(
        operation["authorization"], AUTHORIZATION_FIELDS, "authorization"
    )
    operation_type = operation["operation_type"]
    if operation_type == "repository-interrogation":
        if authorization["interrogate"] is not True:
            raise SchemaError("repository interrogation requires authorization")
        forbidden = set(AUTHORIZATION_FIELDS) - {"interrogate"}
        enabled_forbidden = sorted(key for key in forbidden if authorization[key])
        if enabled_forbidden:
            raise SchemaError(
                "operation broadens authorization: " + ", ".join(enabled_forbidden)
            )
        for field in ("inputs", "expected_mutations", "validation", "publication"):
            obj = _require_object(operation[field], field)
            if obj:
                raise SchemaError(
                    f"{field} must be empty for repository interrogation"
                )
    elif operation_type == "local-file-operations":
        if not authorization["interrogate"] or not authorization["edit"]:
            raise SchemaError(
                "local file operations require interrogate and edit authorization"
            )
        forbidden = set(AUTHORIZATION_FIELDS) - {"interrogate", "edit"}
        enabled_forbidden = sorted(key for key in forbidden if authorization[key])
        if enabled_forbidden:
            raise SchemaError(
                "operation broadens authorization: " + ", ".join(enabled_forbidden)
            )
        validate_local_file_inputs(
            operation["inputs"], operation["expected_mutations"]
        )
        for field in ("validation", "publication"):
            obj = _require_object(operation[field], field)
            if obj:
                raise SchemaError(
                    f"{field} must be empty for local file operations"
                )
    elif operation_type == "git-publication":
        required = {"interrogate", "stage", "commit"}
        if not all(authorization[field] for field in required):
            raise SchemaError(
                "git publication requires interrogate, stage, and commit authorization"
            )
        forbidden = set(AUTHORIZATION_FIELDS) - required - {"push"}
        enabled_forbidden = sorted(key for key in forbidden if authorization[key])
        if enabled_forbidden:
            raise SchemaError(
                "operation broadens authorization: " + ", ".join(enabled_forbidden)
            )
        validate_git_publication_inputs(
            operation["inputs"],
            operation["expected_mutations"],
            operation["publication"],
            push_authorized=authorization["push"],
        )
        validation = _require_object(operation["validation"], "validation")
        if validation:
            raise SchemaError("validation must be empty for git publication")
    else:
        required = {"interrogate", "validate"}
        if not all(authorization[field] for field in required):
            raise SchemaError(
                "governed validation requires interrogate and validate authorization"
            )
        forbidden = set(AUTHORIZATION_FIELDS) - required
        enabled_forbidden = sorted(key for key in forbidden if authorization[key])
        if enabled_forbidden:
            raise SchemaError(
                "operation broadens authorization: " + ", ".join(enabled_forbidden)
            )
        validate_governed_validation_inputs(
            operation["inputs"],
            operation["expected_mutations"],
            operation["publication"],
        )
        validation = _require_object(operation["validation"], "validation")
        if validation:
            raise SchemaError(
                "validation must be empty; profiles are executor-owned inputs"
            )

    result = _require_object(operation["result"], "result")
    _require_exact_fields(result, RESULT_FIELDS, RESULT_FIELDS, "result")
    if not isinstance(result["directory"], str) or not result["directory"]:
        raise SchemaError("result.directory must be a non-empty string")
    if not isinstance(result["filename"], str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{7,191}\.result\.json",
        result["filename"],
    ):
        raise SchemaError("result.filename has invalid form")

    return operation


def redact_text(text: str, environment: Mapping[str, str] | None = None) -> tuple[str, list[dict[str, str]]]:
    events: list[dict[str, str]] = []
    redacted = text

    def replace(category: str, secret: str) -> str:
        fingerprint = hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]
        events.append({"category": category, "fingerprint": fingerprint})
        return f"<redacted:{category}:{fingerprint}>"

    for pattern in TOKEN_PATTERNS:
        redacted = pattern.sub(lambda match: replace("credential", match.group(0)), redacted)

    split = urlsplit(redacted)
    if split.scheme and split.netloc and (split.username or split.password):
        credential = split.netloc.rsplit("@", 1)[0]
        safe_netloc = split.netloc.rsplit("@", 1)[-1]
        redacted = urlunsplit(
            (split.scheme, safe_netloc, split.path, split.query, split.fragment)
        )
        events.append(
            {
                "category": "credential-url",
                "fingerprint": hashlib.sha256(
                    credential.encode("utf-8")
                ).hexdigest()[:12],
            }
        )

    for name, value in (environment or {}).items():
        if value and SECRET_NAME.search(name) and value in redacted:
            redacted = redacted.replace(value, replace("environment-secret", value))

    unique_events = list({(e["category"], e["fingerprint"]): e for e in events}.values())
    return redacted, unique_events


@dataclass(frozen=True)
class CommandRecord:
    command: list[str]
    cwd: str
    started_at: str
    finished_at: str
    elapsed_seconds: float
    exit_code: int | None
    timed_out: bool
    stdout: str
    stderr: str
    redaction_events: list[dict[str, str]]


class CommandSupervisor:
    def __init__(
        self,
        heartbeat_seconds: float = 15.0,
        output: Callable[[str], None] = print,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        if heartbeat_seconds <= 0:
            raise ValueError("heartbeat_seconds must be positive")
        self.heartbeat_seconds = heartbeat_seconds
        self.output = output
        self.environment = dict(environment or os.environ)

    def run(
        self,
        command: Sequence[str],
        cwd: Path,
        *,
        timeout_seconds: float = 300.0,
        phase: str = "command",
    ) -> CommandRecord:
        if not command or any(not isinstance(part, str) or not part for part in command):
            raise ExecutorError("command must be a non-empty string sequence")
        if timeout_seconds <= 0:
            raise ExecutorError("timeout must be positive")

        started_at = utc_now()
        started = time.monotonic()
        proc = subprocess.Popen(
            list(command),
            cwd=cwd,
            env=self.environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
        timed_out = False
        stop = threading.Event()

        def heartbeat() -> None:
            while not stop.wait(self.heartbeat_seconds):
                elapsed = int(time.monotonic() - started)
                self.output(f"    heartbeat: {phase} still running ({elapsed}s)")

        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        try:
            stdout, stderr = proc.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            stdout, stderr = proc.communicate()
        finally:
            stop.set()
            thread.join(timeout=self.heartbeat_seconds + 0.1)

        finished_at = utc_now()
        redacted_stdout, stdout_events = redact_text(stdout, self.environment)
        redacted_stderr, stderr_events = redact_text(stderr, self.environment)
        record = CommandRecord(
            command=list(command),
            cwd=str(cwd),
            started_at=started_at,
            finished_at=finished_at,
            elapsed_seconds=round(time.monotonic() - started, 3),
            exit_code=proc.returncode,
            timed_out=timed_out,
            stdout=redacted_stdout,
            stderr=redacted_stderr,
            redaction_events=stdout_events + stderr_events,
        )
        if timed_out:
            raise CommandTimeoutError(
                f"command timed out after {timeout_seconds}s"
            )
        return record


def command_record_dict(record: CommandRecord) -> dict[str, Any]:
    return {
        "command": record.command,
        "cwd": record.cwd,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
        "elapsed_seconds": record.elapsed_seconds,
        "exit_code": record.exit_code,
        "timed_out": record.timed_out,
        "stdout": record.stdout,
        "stderr": record.stderr,
        "redaction_events": record.redaction_events,
    }


def evaluate_repository_guards(
    operation: Mapping[str, Any], supervisor: CommandSupervisor
) -> tuple[Path, list[dict[str, Any]], dict[str, Any]]:
    repository = operation["repository"]
    guards = operation["guards"]
    root = Path(repository["root"]).expanduser().resolve()
    if not root.is_dir():
        raise GuardError("repository root does not exist")

    records: list[dict[str, Any]] = []

    def git(*args: str) -> str:
        record = supervisor.run(
            ["git", *args], root, timeout_seconds=30, phase="repository guard"
        )
        records.append(command_record_dict(record))
        if record.exit_code != 0:
            raise GuardError(record.stderr.strip() or "git guard command failed")
        return record.stdout.strip()

    actual_root = Path(git("rev-parse", "--show-toplevel")).resolve()
    if actual_root != root:
        raise GuardError("repository root mismatch")
    actual_origin = git("remote", "get-url", "origin")
    if actual_origin != repository["origin"]:
        raise GuardError("repository origin mismatch")
    actual_branch = git("branch", "--show-current")
    if actual_branch != guards["branch"]:
        raise GuardError("repository branch mismatch")
    actual_head = git("rev-parse", "HEAD")
    if actual_head != guards["head"]:
        raise GuardError("repository HEAD mismatch")
    status = git("status", "--porcelain=v1")
    actual_clean = not bool(status)
    if actual_clean != guards["clean"]:
        raise GuardError("repository clean-state mismatch")

    state = {
        "root": str(root),
        "origin": actual_origin,
        "branch": actual_branch,
        "head": actual_head,
        "clean": actual_clean,
        "status": status.splitlines(),
    }
    return root, records, state


def result_destination(operation: Mapping[str, Any], repository_root: Path) -> Path:
    configured = operation["result"]
    directory = Path(configured["directory"]).expanduser().resolve()
    if not directory.is_dir():
        raise ResultConflictError("result directory does not exist")
    try:
        directory.relative_to(repository_root)
    except ValueError:
        pass
    else:
        raise ResultConflictError("result directory must be outside repository")
    return directory / configured["filename"]


def write_result_exclusive(path: Path, result: Mapping[str, Any]) -> None:
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise ResultConflictError(f"result already exists: {path}") from exc


def base_result(operation: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "executor_version": EXECUTOR_VERSION,
        "result_id": str(uuid.uuid4()),
        "operation_id": operation["operation_id"],
        "operation_digest": operation["operation_digest"],
        "operation_type": operation["operation_type"],
        "started_at": utc_now(),
        "finished_at": None,
        "terminal_status": "pre-mutation-failed",
        "mutation": {
            "authorized": False,
            "attempted": False,
            "observed": False,
            "completed": False,
        },
        "commands": [],
        "starting_state": None,
        "ending_state": None,
        "redaction_events": [],
        "diagnostics": [],
        "file_operations": [],
        "publication": {},
        "validation_evidence": {},
        "safest_next_interaction": "Review this result before any successor operation.",
    }


def execute_interrogation(operation: Mapping[str, Any]) -> tuple[dict[str, Any], Path]:
    result = base_result(operation)
    supervisor = CommandSupervisor()
    repository_root = Path(operation["repository"]["root"]).expanduser().resolve()
    destination = result_destination(operation, repository_root)
    if destination.exists():
        raise ResultConflictError(f"result already exists: {destination}")

    try:
        root, command_records, state = evaluate_repository_guards(
            operation, supervisor
        )
        result["commands"].extend(command_records)
        result["starting_state"] = state
        result["ending_state"] = state
        result["terminal_status"] = "local-mutation-completed"
        result["safest_next_interaction"] = (
            "Review the returned read-only repository evidence."
        )
    except GuardError as exc:
        result["terminal_status"] = "guard-failed"
        result["diagnostics"].append(str(exc))
    finally:
        result["finished_at"] = utc_now()

    if result["terminal_status"] not in TERMINAL_STATUSES:
        raise ExecutorError("invalid terminal result status")
    write_result_exclusive(destination, result)
    return result, destination



def capture_repository_state(
    root: Path, supervisor: CommandSupervisor
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def git(*args: str) -> str:
        record = supervisor.run(
            ["git", *args], root, timeout_seconds=30, phase="repository state"
        )
        records.append(command_record_dict(record))
        if record.exit_code != 0:
            raise ExecutorError(record.stderr.strip() or "git state command failed")
        return record.stdout.strip()

    state = {
        "root": str(root),
        "origin": git("remote", "get-url", "origin"),
        "branch": git("branch", "--show-current"),
        "head": git("rev-parse", "HEAD"),
    }
    status = git("status", "--porcelain=v1")
    state["clean"] = not bool(status)
    state["status"] = status.splitlines()
    return records, state


def execute_local_file_operation(
    operation: Mapping[str, Any],
) -> tuple[dict[str, Any], Path]:
    result = base_result(operation)
    result["mutation"]["authorized"] = True
    supervisor = CommandSupervisor()
    repository_root = Path(operation["repository"]["root"]).expanduser().resolve()
    destination = result_destination(operation, repository_root)
    if destination.exists():
        raise ResultConflictError(f"result already exists: {destination}")

    try:
        root, command_records, state = evaluate_repository_guards(
            operation, supervisor
        )
        result["commands"].extend(command_records)
        result["starting_state"] = state
        result["mutation"]["attempted"] = True
        records = apply_local_file_operations(
            root,
            operation["inputs"]["operations"],
        )
        result["file_operations"] = records
        result["mutation"]["observed"] = bool(records)
        result["mutation"]["completed"] = True
        ending_commands, ending_state = capture_repository_state(root, supervisor)
        result["commands"].extend(ending_commands)
        result["ending_state"] = ending_state
        result["terminal_status"] = "local-mutation-completed"
        result["safest_next_interaction"] = (
            "Review read-after-write evidence and repository state."
        )
    except GuardError as exc:
        result["terminal_status"] = "guard-failed"
        result["diagnostics"].append(str(exc))
    except LocalFileOperationError as exc:
        result["file_operations"] = exc.records
        result["mutation"]["observed"] = exc.mutation_observed
        result["terminal_status"] = (
            "partial-local-mutation"
            if exc.mutation_observed
            else "pre-mutation-failed"
        )
        result["diagnostics"].append(str(exc))
        try:
            ending_commands, ending_state = capture_repository_state(
                repository_root, supervisor
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
    write_result_exclusive(destination, result)
    return result, destination




def execute_git_publication(
    operation: Mapping[str, Any],
) -> tuple[dict[str, Any], Path]:
    result = base_result(operation)
    result["mutation"]["authorized"] = True
    supervisor = CommandSupervisor()
    repository_root = Path(operation["repository"]["root"]).expanduser().resolve()
    destination = result_destination(operation, repository_root)
    if destination.exists():
        raise ResultConflictError(f"result already exists: {destination}")

    try:
        root, command_records, state = evaluate_repository_guards(
            operation, supervisor
        )
        result["commands"].extend(command_records)
        result["starting_state"] = state
        result["mutation"]["attempted"] = True
        publication = publish_git_changes(
            root,
            supervisor,
            operation["inputs"],
            operation["expected_mutations"],
            operation["publication"],
            push_authorized=operation["authorization"]["push"],
        )
        result["commands"].extend(publication.pop("commands"))
        result["publication"] = publication
        result["mutation"]["observed"] = True
        result["mutation"]["completed"] = True
        ending_commands, ending_state = capture_repository_state(root, supervisor)
        result["commands"].extend(ending_commands)
        result["ending_state"] = ending_state
        result["terminal_status"] = "publication-completed"
        result["safest_next_interaction"] = (
            "Review commit and remote verification evidence."
        )
    except GuardError as exc:
        result["terminal_status"] = "guard-failed"
        result["diagnostics"].append(str(exc))
    except GitPublicationError as exc:
        result["publication"] = exc.evidence
        result["commands"].extend(exc.commands)
        result["mutation"]["observed"] = exc.mutation_observed
        result["terminal_status"] = (
            "partial-publication"
            if exc.mutation_observed
            else "pre-publication-failed"
        )
        result["diagnostics"].append(str(exc))
        try:
            ending_commands, ending_state = capture_repository_state(
                repository_root, supervisor
            )
            result["commands"].extend(ending_commands)
            result["ending_state"] = ending_state
        except ExecutorError as state_exc:
            result["diagnostics"].append(
                f"ending-state capture failed: {state_exc}"
            )
    finally:
        result["finished_at"] = utc_now()

    write_result_exclusive(destination, result)
    return result, destination



def execute_governed_validation(
    operation: Mapping[str, Any],
) -> tuple[dict[str, Any], Path]:
    result = base_result(operation)
    supervisor = CommandSupervisor()
    repository_root = Path(operation["repository"]["root"]).expanduser().resolve()
    destination = result_destination(operation, repository_root)
    if destination.exists():
        raise ResultConflictError(f"result already exists: {destination}")

    try:
        root, command_records, state = evaluate_repository_guards(
            operation, supervisor
        )
        result["commands"].extend(command_records)
        result["starting_state"] = state
        evidence = run_governed_validation(
            root,
            supervisor,
            operation["inputs"],
            operation["expected_mutations"],
            operation["publication"],
        )
        result["commands"].extend(evidence.pop("commands"))
        result["validation_evidence"] = evidence
        ending_commands, ending_state = capture_repository_state(root, supervisor)
        result["commands"].extend(ending_commands)
        result["ending_state"] = ending_state
        result["terminal_status"] = "validation-completed"
        result["safest_next_interaction"] = (
            "Review governed validation evidence before successor mutation."
        )
    except GuardError as exc:
        result["terminal_status"] = "guard-failed"
        result["diagnostics"].append(str(exc))
    except GovernedValidationError as exc:
        result["validation_evidence"] = exc.evidence
        result["commands"].extend(exc.commands)
        result["terminal_status"] = "pre-mutation-failed"
        result["diagnostics"].append(str(exc))
        try:
            ending_commands, ending_state = capture_repository_state(
                repository_root, supervisor
            )
            result["commands"].extend(ending_commands)
            result["ending_state"] = ending_state
        except ExecutorError as state_exc:
            result["diagnostics"].append(
                f"ending-state capture failed: {state_exc}"
            )
    finally:
        result["finished_at"] = utc_now()

    write_result_exclusive(destination, result)
    return result, destination


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    total = 5
    if len(args) != 1:
        print("usage: ./scripts/governed-execute /path/to/operation.json", file=sys.stderr)
        return 64

    operation_path = Path(args[0]).expanduser().resolve()
    operation: dict[str, Any] | None = None
    destination: Path | None = None
    try:
        print(f"[1/{total}] Loading and validating operation.", flush=True)
        operation = load_operation(operation_path)
        print(
            f"[2/{total}] Operation {operation['operation_id']} "
            f"({operation['operation_type']}).",
            flush=True,
        )
        print(f"[3/{total}] Verifying repository guards.", flush=True)
        if operation["operation_type"] == "repository-interrogation":
            result, destination = execute_interrogation(operation)
        elif operation["operation_type"] == "local-file-operations":
            result, destination = execute_local_file_operation(operation)
        elif operation["operation_type"] == "git-publication":
            result, destination = execute_git_publication(operation)
        else:
            result, destination = execute_governed_validation(operation)
        print(f"[4/{total}] Writing exclusive result evidence.", flush=True)
        if result["terminal_status"] not in {
            "local-mutation-completed",
            "commit-completed",
            "publication-completed",
            "validation-completed",
        }:
            print(
                f"FAILED: executor ended with {result['terminal_status']}. "
                f"Result: {destination}",
                flush=True,
            )
            return 1
        print(f"[5/{total}] SUCCESS: all executor steps completed.", flush=True)
        print(f"Result written to: {destination}", flush=True)
        print("Return that result for review before further action.", flush=True)
        return 0
    except ExecutorError as exc:
        print(f"FAILED: {exc}", file=sys.stderr, flush=True)
        if destination is not None:
            print(f"Result path: {destination}", file=sys.stderr, flush=True)
        return 1
