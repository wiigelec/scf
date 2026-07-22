from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import branch_create
from . import core as core_module
from . import strict_validation
from . import lifecycle
from . import local_files
from . import issue_comments


core_module.EXECUTOR_VERSION = "0.7.0"

PROTECTED_EXECUTOR_PATHS = frozenset(
    {
        "scripts/governed-execute",
        "src/scf_governed_executor/__init__.py",
        "src/scf_governed_executor/__main__.py",
        "src/scf_governed_executor/core.py",
        "src/scf_governed_executor/errors.py",
        "src/scf_governed_executor/git_publication.py",
        "src/scf_governed_executor/local_files.py",
        "src/scf_governed_executor/lifecycle.py",
        "src/scf_governed_executor/runtime.py",
        "src/scf_governed_executor/issue_comments.py",
        "src/scf_governed_executor/self_update.py",
        "src/scf_governed_executor/validation.py",
    }
)
SHA1 = re.compile(r"^[0-9a-f]{40}$")


_original_validate_local_file_inputs = local_files.validate_local_file_inputs


def _validate_unprotected_local_file_inputs(inputs, expected_mutations):
    normalized = _original_validate_local_file_inputs(inputs, expected_mutations)
    protected = sorted(
        operation["path"]
        for operation in normalized
        if operation["path"] in PROTECTED_EXECUTOR_PATHS
    )
    if protected:
        raise local_files.LocalFileOperationError(
            "local-file-operations cannot modify protected executor paths: "
            + ", ".join(protected)
        )
    return normalized


local_files.validate_local_file_inputs = _validate_unprotected_local_file_inputs
core_module.validate_local_file_inputs = _validate_unprotected_local_file_inputs


def _operation_type(argv: Sequence[str]) -> str | None:
    if len(argv) != 1:
        return None
    try:
        value = json.loads(Path(argv[0]).expanduser().read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    operation_type = value.get("operation_type")
    return operation_type if isinstance(operation_type, str) else None


_STRICT = strict_validation.StrictValidator(core_module.SchemaError)


def _object(value: Any, location: str) -> dict[str, Any]:
    return _STRICT.object(value, location)


def _exact(
    value: Mapping[str, Any],
    allowed: set[str] | frozenset[str],
    required: set[str] | frozenset[str],
    location: str,
) -> None:
    _STRICT.exact_fields(value, allowed, required, location)


def _string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise core_module.SchemaError(f"{location} must be a non-empty string")
    return value


def _load_branch_operation(path: Path) -> dict[str, Any]:
    try:
        operation = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-standard JSON constant: {value}")
            ),
        )
    except OSError as exc:
        raise core_module.SchemaError(f"cannot read operation: {exc}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise core_module.SchemaError(f"invalid operation JSON: {exc}") from exc

    operation = _object(operation, "operation")
    _exact(
        operation,
        core_module.TOP_LEVEL_FIELDS,
        core_module.TOP_LEVEL_FIELDS,
        "operation",
    )
    if operation["schema_version"] != core_module.OPERATION_SCHEMA_VERSION:
        raise core_module.SchemaError("unsupported operation schema version")
    if operation["operation_type"] != branch_create.BRANCH_CREATE_OPERATION_TYPE:
        raise core_module.SchemaError("unsupported branch operation type")
    if operation["executor_version"] != core_module.EXECUTOR_VERSION:
        raise core_module.SchemaError("incompatible executor version")
    if not isinstance(operation["operation_id"], str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}", operation["operation_id"]
    ):
        raise core_module.SchemaError("operation_id has invalid form")
    if not isinstance(operation["operation_digest"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", operation["operation_digest"]
    ):
        raise core_module.SchemaError(
            "operation_digest must be lowercase SHA-256"
        )
    if operation["operation_digest"] != core_module.operation_digest(operation):
        raise core_module.SchemaError("operation digest mismatch")

    repository = _object(operation["repository"], "repository")
    _exact(
        repository,
        core_module.REPOSITORY_FIELDS,
        core_module.REPOSITORY_FIELDS,
        "repository",
    )
    for field in core_module.REPOSITORY_FIELDS:
        _string(repository[field], f"repository.{field}")

    guards = _object(operation["guards"], "guards")
    _exact(
        guards,
        core_module.GUARD_FIELDS,
        core_module.GUARD_FIELDS,
        "guards",
    )
    _string(guards["branch"], "guards.branch")
    if not isinstance(guards["head"], str) or not SHA1.fullmatch(guards["head"]):
        raise core_module.SchemaError(
            "guards.head must be a lowercase full commit id"
        )
    if not isinstance(guards["clean"], bool):
        raise core_module.SchemaError("guards.clean must be boolean")

    authorization = _object(operation["authorization"], "authorization")
    _exact(
        authorization,
        core_module.AUTHORIZATION_FIELDS,
        core_module.AUTHORIZATION_FIELDS,
        "authorization",
    )
    if any(not isinstance(value, bool) for value in authorization.values()):
        raise core_module.SchemaError("authorization values must be boolean")

    result = _object(operation["result"], "result")
    _exact(
        result,
        core_module.RESULT_FIELDS,
        core_module.RESULT_FIELDS,
        "result",
    )
    _string(result["directory"], "result.directory")
    if not isinstance(result["filename"], str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{7,191}\.result\.json",
        result["filename"],
    ):
        raise core_module.SchemaError("result.filename has invalid form")
    return branch_create.validate_branch_create_contract(operation)


def branch_main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print(
            "usage: ./scripts/governed-execute /path/to/operation.json",
            file=sys.stderr,
        )
        return 64
    operation_path = Path(args[0]).expanduser().resolve()
    destination: Path | None = None
    progress = core_module.TerminalProgress()
    try:
        print(f"Governed Executor {core_module.EXECUTOR_VERSION}", flush=True)
        progress.phase(1, "validating branch-creation operation description")
        operation = _load_branch_operation(operation_path)
        destination = core_module.result_destination(
            operation,
            Path(operation["repository"]["root"]).expanduser().resolve(),
        )
        progress.check("closed branch-creation contract verified")
        progress.check("authorization separation verified")
        progress.check("operation digest verified")
        print("", flush=True)
        print(f"Repository : {operation['repository']['root']}", flush=True)
        print(f"Revision   : {operation['guards']['head']}", flush=True)
        print(f"Operation  : {operation['operation_id']}", flush=True)
        print(f"Type       : {operation['operation_type']}", flush=True)
        print(f"Result     : {destination}", flush=True)
        print("", flush=True)
        result, destination = branch_create.execute_branch_create(
            operation, progress
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
    except core_module.ExecutorError as exc:
        print("", file=sys.stderr, flush=True)
        print("-" * 60, file=sys.stderr, flush=True)
        print("STATUS: executor-failed", file=sys.stderr, flush=True)
        print(f"Reason: {exc}", file=sys.stderr, flush=True)
        if destination is not None:
            print(f"Result: {destination}", file=sys.stderr, flush=True)
        return 1


INITIALIZE_OPERATION_TYPE = "repository-initialize"


def _canonical_origin(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    if normalized.startswith("git@github.com:"):
        normalized = "https://github.com/" + normalized[len("git@github.com:"):]
    elif normalized.startswith("ssh://git@github.com/"):
        normalized = "https://github.com/" + normalized[len("ssh://git@github.com/"):]
    return normalized.rstrip("/")


def _load_initialize_operation(path: Path) -> dict[str, Any]:
    try:
        operation = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-standard JSON constant: {value}")
            ),
        )
    except OSError as exc:
        raise core_module.SchemaError(f"cannot read operation: {exc}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise core_module.SchemaError(f"invalid operation JSON: {exc}") from exc

    operation = _object(operation, "operation")
    _exact(operation, core_module.TOP_LEVEL_FIELDS, core_module.TOP_LEVEL_FIELDS, "operation")
    if operation["schema_version"] != core_module.OPERATION_SCHEMA_VERSION:
        raise core_module.SchemaError("unsupported operation schema version")
    if operation["operation_type"] != INITIALIZE_OPERATION_TYPE:
        raise core_module.SchemaError("unsupported initialization operation type")
    if operation["executor_version"] != core_module.EXECUTOR_VERSION:
        raise core_module.SchemaError("incompatible executor version")
    if not isinstance(operation["operation_id"], str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}", operation["operation_id"]
    ):
        raise core_module.SchemaError("operation_id has invalid form")
    if not isinstance(operation["operation_digest"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", operation["operation_digest"]
    ):
        raise core_module.SchemaError("operation_digest must be lowercase SHA-256")
    if operation["operation_digest"] != core_module.operation_digest(operation):
        raise core_module.SchemaError("operation digest mismatch")

    repository = _object(operation["repository"], "repository")
    _exact(repository, core_module.REPOSITORY_FIELDS, core_module.REPOSITORY_FIELDS, "repository")
    _string(repository["root"], "repository.root")
    _string(repository["origin"], "repository.origin")

    guards = _object(operation["guards"], "guards")
    _exact(guards, {"clean"}, {"clean"}, "guards")
    if guards["clean"] is not True:
        raise core_module.SchemaError("repository initialization requires a clean checkout")

    authorization = _object(operation["authorization"], "authorization")
    _exact(
        authorization,
        core_module.AUTHORIZATION_FIELDS,
        core_module.AUTHORIZATION_FIELDS,
        "authorization",
    )
    if any(not isinstance(value, bool) for value in authorization.values()):
        raise core_module.SchemaError("authorization values must be boolean")
    required = {"interrogate", "edit"}
    if not all(authorization[field] for field in required):
        raise core_module.SchemaError(
            "repository initialization requires interrogate and edit authorization"
        )
    broadened = sorted(
        field
        for field in core_module.AUTHORIZATION_FIELDS - required
        if authorization[field]
    )
    if broadened:
        raise core_module.SchemaError(
            "operation broadens authorization: " + ", ".join(broadened)
        )

    inputs = _object(operation["inputs"], "inputs")
    _exact(inputs, {"remote", "branch"}, {"remote", "branch"}, "inputs")
    if inputs != {"remote": "origin", "branch": "main"}:
        raise core_module.SchemaError(
            "repository initialization currently supports only origin/main"
        )

    expected = _object(operation["expected_mutations"], "expected_mutations")
    required_expected = {
        "remote": "origin",
        "branch": "main",
        "strategy": "fetch-switch-fast-forward-only",
    }
    _exact(
        expected,
        set(required_expected),
        set(required_expected),
        "expected_mutations",
    )
    if expected != required_expected:
        raise core_module.SchemaError(
            "expected_mutations does not match repository initialization"
        )

    for name in ("validation", "publication"):
        if _object(operation[name], name):
            raise core_module.SchemaError(
                f"{name} must be empty for repository-initialize"
            )

    result = _object(operation["result"], "result")
    _exact(result, core_module.RESULT_FIELDS, core_module.RESULT_FIELDS, "result")
    _string(result["directory"], "result.directory")
    if not isinstance(result["filename"], str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{7,191}\.result\.json",
        result["filename"],
    ):
        raise core_module.SchemaError("result.filename has invalid form")
    return operation


def _initialize_record(record: Any) -> dict[str, Any]:
    return core_module.command_record_dict(record)


def _initialize_run(
    supervisor: core_module.CommandSupervisor,
    root: Path,
    commands: list[dict[str, Any]],
    command: Sequence[str],
    *,
    phase: str,
    timeout: float = 60.0,
    allowed_exit_codes: set[int] | None = None,
) -> core_module.CommandRecord:
    record = supervisor.run(
        list(command),
        root,
        timeout_seconds=timeout,
        phase=phase,
    )
    commands.append(_initialize_record(record))
    allowed = {0} if allowed_exit_codes is None else allowed_exit_codes
    if record.exit_code not in allowed:
        raise core_module.ExecutorError(
            record.stderr.strip() or f"{phase} failed"
        )
    return record


def _initialize_git(
    supervisor: core_module.CommandSupervisor,
    root: Path,
    commands: list[dict[str, Any]],
    *arguments: str,
    phase: str,
    timeout: float = 60.0,
    allowed_exit_codes: set[int] | None = None,
) -> core_module.CommandRecord:
    return _initialize_run(
        supervisor,
        root,
        commands,
        ["git", *arguments],
        phase=phase,
        timeout=timeout,
        allowed_exit_codes=allowed_exit_codes,
    )


def _initialize_snapshot(
    supervisor: core_module.CommandSupervisor,
    root: Path,
    commands: list[dict[str, Any]],
) -> dict[str, Any]:
    branch = _initialize_git(
        supervisor, root, commands, "branch", "--show-current",
        phase="inspect current branch",
    ).stdout.strip()
    head = _initialize_git(
        supervisor, root, commands, "rev-parse", "HEAD",
        phase="inspect current head",
    ).stdout.strip()
    status = _initialize_git(
        supervisor, root, commands, "status", "--porcelain=v1", "--untracked-files=all",
        phase="inspect checkout cleanliness",
    ).stdout.splitlines()
    return {
        "root": str(root),
        "origin": _initialize_git(
            supervisor, root, commands, "remote", "get-url", "origin",
            phase="inspect canonical origin",
        ).stdout.strip(),
        "branch": branch or None,
        "detached_head": not bool(branch),
        "head": head,
        "clean": not status,
        "status": status,
    }


def execute_repository_initialize(
    operation: Mapping[str, Any],
    progress: core_module.TerminalProgress,
) -> tuple[dict[str, Any], Path]:
    root = Path(operation["repository"]["root"]).expanduser().resolve()
    destination = core_module.result_destination(operation, root)
    if destination.exists():
        raise core_module.ResultConflictError(
            f"result already exists: {destination}"
        )

    result = {
        "schema_version": core_module.RESULT_SCHEMA_VERSION,
        "result_id": None,
        "operation_id": operation["operation_id"],
        "operation_type": operation["operation_type"],
        "operation_digest": operation["operation_digest"],
        "executor_version": core_module.EXECUTOR_VERSION,
        "started_at": core_module.utc_now(),
        "finished_at": None,
        "terminal_status": "pre-mutation-failed",
        "mutation": {
            "authorized": True,
            "attempted": False,
            "observed": False,
            "completed": False,
        },
        "starting_state": {},
        "ending_state": {},
        "commands": [],
        "file_operations": [],
        "validation_evidence": {},
        "publication": {},
        "diagnostics": [],
        "redaction_events": [],
        "safest_next_interaction": (
            "Review repository initialization evidence before successor work."
        ),
    }
    supervisor = core_module.CommandSupervisor()
    commands: list[dict[str, Any]] = []
    mutation_started = False

    try:
        progress.phase(2, "interrogating repository and remote state")
        root_record = _initialize_git(
            supervisor, root, commands, "rev-parse", "--show-toplevel",
            phase="verify repository root",
        )
        if Path(root_record.stdout.strip()).resolve() != root:
            raise core_module.GuardError("repository root mismatch")

        starting = _initialize_snapshot(supervisor, root, commands)
        result["starting_state"] = starting
        if _canonical_origin(starting["origin"]) != _canonical_origin(
            operation["repository"]["origin"]
        ):
            raise core_module.GuardError("canonical origin mismatch")
        if not starting["clean"]:
            raise core_module.GuardError("checkout is not clean")

        prior_branch = starting["branch"]
        prior_head = starting["head"]

        local_main = _initialize_git(
            supervisor,
            root,
            commands,
            "rev-parse",
            "--verify",
            "refs/heads/main",
            phase="verify local main exists",
        ).stdout.strip()

        remote_before = _initialize_git(
            supervisor,
            root,
            commands,
            "ls-remote",
            "--heads",
            "origin",
            "refs/heads/main",
            phase="inspect remote main",
            timeout=120.0,
        ).stdout.strip()
        if not remote_before:
            raise core_module.GuardError("remote main is absent")
        remote_before_sha = remote_before.split()[0]
        if not SHA1.fullmatch(remote_before_sha):
            raise core_module.GuardError("remote main returned an invalid commit id")

        progress.phase(3, "refreshing remote state and selecting safe transition")
        result["mutation"]["attempted"] = True
        mutation_started = True
        _initialize_git(
            supervisor,
            root,
            commands,
            "fetch",
            "--prune",
            "origin",
            phase="fetch canonical remote",
            timeout=300.0,
        )
        result["mutation"]["observed"] = True

        fetched_main = _initialize_git(
            supervisor,
            root,
            commands,
            "rev-parse",
            "--verify",
            "refs/remotes/origin/main",
            phase="resolve fetched origin main",
        ).stdout.strip()
        if fetched_main != remote_before_sha:
            raise core_module.GuardError(
                "fetched origin/main does not match observed remote main"
            )

        ancestry = _initialize_git(
            supervisor,
            root,
            commands,
            "merge-base",
            "--is-ancestor",
            local_main,
            fetched_main,
            phase="verify fast-forward relationship",
            allowed_exit_codes={0, 1},
        )
        if ancestry.exit_code != 0:
            reverse = _initialize_git(
                supervisor,
                root,
                commands,
                "merge-base",
                "--is-ancestor",
                fetched_main,
                local_main,
                phase="classify local main relationship",
                allowed_exit_codes={0, 1},
            )
            if reverse.exit_code == 0:
                raise core_module.GuardError(
                    "local main contains commits not present on remote main"
                )
            raise core_module.GuardError("local and remote main have diverged")

        progress.phase(4, "switching to main and applying fast-forward only")
        current_branch = _initialize_git(
            supervisor, root, commands, "branch", "--show-current",
            phase="recheck current branch",
        ).stdout.strip()
        current_head = _initialize_git(
            supervisor, root, commands, "rev-parse", "HEAD",
            phase="recheck current head",
        ).stdout.strip()
        current_status = _initialize_git(
            supervisor, root, commands, "status", "--porcelain=v1", "--untracked-files=all",
            phase="recheck checkout cleanliness",
        ).stdout.strip()
        if current_status:
            raise core_module.GuardError("checkout changed before branch switch")
        if current_branch != (prior_branch or "") or current_head != prior_head:
            raise core_module.GuardError("checkout identity changed before branch switch")

        if current_branch != "main":
            _initialize_git(
                supervisor, root, commands, "switch", "main",
                phase="switch to existing main",
            )

        if local_main != fetched_main:
            _initialize_git(
                supervisor,
                root,
                commands,
                "merge",
                "--ff-only",
                "refs/remotes/origin/main",
                phase="fast-forward main",
            )

        remote_after = _initialize_git(
            supervisor,
            root,
            commands,
            "ls-remote",
            "--heads",
            "origin",
            "refs/heads/main",
            phase="verify remote main remained stable",
            timeout=120.0,
        ).stdout.strip()
        remote_after_sha = remote_after.split()[0] if remote_after else ""
        if remote_after_sha != fetched_main:
            raise core_module.ExecutorError(
                "remote main changed during initialization"
            )

        ending = _initialize_snapshot(supervisor, root, commands)
        result["ending_state"] = ending
        ending_main = _initialize_git(
            supervisor, root, commands, "rev-parse", "refs/heads/main",
            phase="verify terminal local main",
        ).stdout.strip()
        ending_origin_main = _initialize_git(
            supervisor, root, commands, "rev-parse", "refs/remotes/origin/main",
            phase="verify terminal origin main",
        ).stdout.strip()
        if (
            ending["branch"] != "main"
            or ending["head"] != fetched_main
            or ending_main != fetched_main
            or ending_origin_main != fetched_main
            or not ending["clean"]
        ):
            raise core_module.ExecutorError(
                "repository initialization terminal state verification failed"
            )

        if prior_branch and prior_branch != "main":
            preserved = _initialize_git(
                supervisor,
                root,
                commands,
                "rev-parse",
                "--verify",
                f"refs/heads/{prior_branch}",
                phase="verify prior branch preservation",
            ).stdout.strip()
            if preserved != prior_head:
                raise core_module.ExecutorError(
                    "prior branch was not preserved at its original commit"
                )

        result["mutation"]["completed"] = True
        result["terminal_status"] = "local-mutation-completed"
        result["publication"] = {
            "remote": "origin",
            "branch": "main",
            "remote_head": fetched_main,
            "prior_branch": prior_branch,
            "prior_head": prior_head,
            "verified": True,
        }
    except core_module.GuardError as exc:
        result["terminal_status"] = (
            "partial-local-mutation" if mutation_started else "guard-failed"
        )
        result["diagnostics"].append(str(exc))
    except (core_module.ExecutorError, OSError) as exc:
        result["terminal_status"] = (
            "partial-local-mutation" if mutation_started else "pre-mutation-failed"
        )
        result["diagnostics"].append(str(exc))
    finally:
        result["commands"] = commands
        result["redaction_events"] = [
            event
            for command in commands
            for event in command.get("redaction_events", [])
        ]
        if not result["ending_state"]:
            try:
                result["ending_state"] = _initialize_snapshot(
                    supervisor, root, commands
                )
                result["commands"] = commands
            except (core_module.ExecutorError, OSError) as exc:
                result["diagnostics"].append(
                    f"ending-state capture failed: {exc}"
                )
        result["finished_at"] = core_module.utc_now()

    progress.phase(5, "writing initialization evidence")
    core_module.write_result_exclusive(destination, result)
    progress.check("result artifact created without overwrite")
    return result, destination


def initialize_main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print(
            "usage: ./scripts/governed-execute /path/to/operation.json",
            file=sys.stderr,
        )
        return 64
    operation_path = Path(args[0]).expanduser().resolve()
    destination: Path | None = None
    progress = core_module.TerminalProgress()
    try:
        print(f"Governed Executor {core_module.EXECUTOR_VERSION}", flush=True)
        progress.phase(1, "validating repository initialization description")
        operation = _load_initialize_operation(operation_path)
        destination = core_module.result_destination(
            operation,
            Path(operation["repository"]["root"]).expanduser().resolve(),
        )
        progress.check("closed initialization contract verified")
        progress.check("minimal input boundary verified")
        progress.check("operation digest verified")
        print("", flush=True)
        print(f"Repository : {operation['repository']['root']}", flush=True)
        print(f"Operation  : {operation['operation_id']}", flush=True)
        print(f"Type       : {operation['operation_type']}", flush=True)
        print(f"Result     : {destination}", flush=True)
        print("", flush=True)
        result, destination = execute_repository_initialize(operation, progress)
        print("", flush=True)
        print("-" * 60, flush=True)
        print(f"STATUS: {result['terminal_status']}", flush=True)
        print("")
        print("Result:", flush=True)
        print(f"  {destination}", flush=True)
        print("")
        print("Next step:", flush=True)
        print(f"  {result['safest_next_interaction']}", flush=True)
        return 0 if result["terminal_status"] == "local-mutation-completed" else 1
    except core_module.ExecutorError as exc:
        print("", file=sys.stderr, flush=True)
        print("-" * 60, file=sys.stderr, flush=True)
        print("STATUS: executor-failed", file=sys.stderr, flush=True)
        print(f"Reason: {exc}", file=sys.stderr, flush=True)
        if destination is not None:
            print(f"Result: {destination}", file=sys.stderr, flush=True)
        return 1


operation_type = _operation_type(sys.argv[1:])
if operation_type == "executor-self-update":
    from .self_update import main
elif operation_type == INITIALIZE_OPERATION_TYPE:
    main = initialize_main
elif operation_type == branch_create.BRANCH_CREATE_OPERATION_TYPE:
    main = branch_main
elif operation_type == issue_comments.ISSUE_COMMENT_OPERATION_TYPE:
    main = issue_comments.issue_comment_main
elif operation_type in lifecycle.LIFECYCLE_OPERATION_TYPES:
    main = lifecycle.lifecycle_main
else:
    main = core_module.main


raise SystemExit(main())
