from __future__ import annotations

import hashlib
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import EXECUTOR_VERSION

from .errors import (
    CommandTimeoutError,
    ExecutorError,
    GuardError,
    ResultConflictError,
    SchemaError,
)
from . import strict_validation
from .runtime import (
    CommandRecord,
    CommandSupervisor,
    TerminalProgress,
    capture_repository_state,
    command_record_dict,
    evaluate_repository_guards,
    redact_text,
    result_destination,
    utc_now,
    write_result_exclusive,
)

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


OPERATION_SCHEMA_VERSION = 1
RESULT_SCHEMA_VERSION = 1
TERMINAL_STATUSES = {
    "guard-failed",
    "pre-mutation-failed",
    "partial-local-mutation",
    "partial-remote-mutation",
    "partial-publication",
    "pre-publication-failed",
    "post-mutation-validation-failed",
    "local-mutation-completed",
    "commit-completed",
    "publication-completed",
    "validation-completed",
}
SUCCESS_TERMINAL_STATUSES = {
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
def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def operation_digest(operation: Mapping[str, Any]) -> str:
    body = dict(operation)
    body.pop("operation_digest", None)
    return hashlib.sha256(canonical_json(body)).hexdigest()


_STRICT = strict_validation.StrictValidator(SchemaError)


def _require_exact_fields(
    value: Mapping[str, Any],
    allowed: set[str],
    required: set[str],
    location: str,
) -> None:
    _STRICT.exact_fields(value, allowed, required, location)


def _require_object(value: Any, location: str) -> dict[str, Any]:
    return _STRICT.object(value, location)


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



def _prepare_execution(
    operation: Mapping[str, Any],
    progress: TerminalProgress | None,
    *,
    mutation_authorized: bool = False,
) -> tuple[
    TerminalProgress,
    dict[str, Any],
    CommandSupervisor,
    Path,
    Path,
]:
    progress = progress or TerminalProgress()
    progress.phase(2, "evaluating repository guards")
    result = base_result(operation)
    result["mutation"]["authorized"] = mutation_authorized
    supervisor = CommandSupervisor()
    repository_root = Path(operation["repository"]["root"]).expanduser().resolve()
    destination = result_destination(operation, repository_root)
    if destination.exists():
        raise ResultConflictError(f"result already exists: {destination}")
    return progress, result, supervisor, repository_root, destination


def _capture_ending_state(
    result: dict[str, Any],
    root: Path,
    supervisor: CommandSupervisor,
) -> None:
    commands, state = capture_repository_state(root, supervisor)
    result["commands"].extend(commands)
    result["ending_state"] = state


def _capture_ending_state_after_failure(
    result: dict[str, Any],
    root: Path,
    supervisor: CommandSupervisor,
) -> None:
    try:
        _capture_ending_state(result, root, supervisor)
    except ExecutorError as exc:
        result["diagnostics"].append(f"ending-state capture failed: {exc}")


def _evaluate_guarded_repository(
    operation: Mapping[str, Any],
    result: dict[str, Any],
    supervisor: CommandSupervisor,
    progress: TerminalProgress,
) -> Path:
    root, command_records, state = evaluate_repository_guards(
        operation,
        supervisor,
        progress,
    )
    result["commands"].extend(command_records)
    result["starting_state"] = state
    progress.check("repository identity and exact state verified")
    return root


def _record_guard_failure(result: dict[str, Any], exc: GuardError) -> None:
    result["terminal_status"] = "guard-failed"
    result["diagnostics"].append(str(exc))


def _record_operation_failure(
    result: dict[str, Any],
    exc: ExecutorError,
    repository_root: Path,
    supervisor: CommandSupervisor,
    *,
    terminal_status: str,
) -> None:
    result["terminal_status"] = terminal_status
    result["diagnostics"].append(str(exc))
    _capture_ending_state_after_failure(result, repository_root, supervisor)


def _finalize_execution(
    result: dict[str, Any],
    destination: Path,
    progress: TerminalProgress,
    *,
    validate_terminal_status: bool = False,
) -> tuple[dict[str, Any], Path]:
    result["finished_at"] = utc_now()
    if validate_terminal_status and result["terminal_status"] not in TERMINAL_STATUSES:
        raise ExecutorError("invalid terminal result status")
    progress.phase(5, "writing execution evidence")
    write_result_exclusive(destination, result)
    progress.check("result artifact created without overwrite")
    return result, destination


def execute_interrogation(
    operation: Mapping[str, Any],
    progress: TerminalProgress | None = None,
) -> tuple[dict[str, Any], Path]:
    (
        progress,
        result,
        supervisor,
        repository_root,
        destination,
    ) = _prepare_execution(operation, progress)

    try:
        root = _evaluate_guarded_repository(
            operation,
            result,
            supervisor,
            progress,
        )
        progress.phase(3, "collecting repository evidence")
        result["ending_state"] = result["starting_state"]
        progress.phase(4, "verifying resulting state")
        progress.check("read-only repository state preserved")
        result["terminal_status"] = "local-mutation-completed"
        result["safest_next_interaction"] = (
            "Review the returned read-only repository evidence."
        )
    except GuardError as exc:
        _record_guard_failure(result, exc)
    return _finalize_execution(
        result,
        destination,
        progress,
        validate_terminal_status=True,
    )



def execute_local_file_operation(
    operation: Mapping[str, Any],
    progress: TerminalProgress | None = None,
) -> tuple[dict[str, Any], Path]:
    (
        progress,
        result,
        supervisor,
        repository_root,
        destination,
    ) = _prepare_execution(operation, progress, mutation_authorized=True)

    try:
        root = _evaluate_guarded_repository(
            operation,
            result,
            supervisor,
            progress,
        )
        progress.phase(3, "performing bounded file mutation")
        result["mutation"]["attempted"] = True
        records = apply_local_file_operations(
            root,
            operation["inputs"]["operations"],
        )
        result["file_operations"] = records
        result["mutation"]["observed"] = bool(records)
        result["mutation"]["completed"] = True
        progress.check("authorized file operations completed")
        progress.phase(4, "verifying resulting state")
        _capture_ending_state(result, root, supervisor)
        result["terminal_status"] = "local-mutation-completed"
        result["safest_next_interaction"] = (
            "Review read-after-write evidence and repository state."
        )
    except GuardError as exc:
        _record_guard_failure(result, exc)
    except LocalFileOperationError as exc:
        result["file_operations"] = exc.records
        result["mutation"]["observed"] = exc.mutation_observed
        _record_operation_failure(
            result,
            exc,
            repository_root,
            supervisor,
            terminal_status=(
                "partial-local-mutation"
                if exc.mutation_observed
                else "pre-mutation-failed"
            ),
        )
    return _finalize_execution(
        result,
        destination,
        progress,
        validate_terminal_status=True,
    )




def execute_git_publication(
    operation: Mapping[str, Any],
    progress: TerminalProgress | None = None,
) -> tuple[dict[str, Any], Path]:
    (
        progress,
        result,
        supervisor,
        repository_root,
        destination,
    ) = _prepare_execution(operation, progress, mutation_authorized=True)

    try:
        root = _evaluate_guarded_repository(
            operation,
            result,
            supervisor,
            progress,
        )
        progress.phase(3, "performing publication")
        result["mutation"]["attempted"] = True
        publication = publish_git_changes(
            root,
            supervisor,
            operation["inputs"],
            operation["expected_mutations"],
            operation["publication"],
            push_authorized=operation["authorization"]["push"],
            progress=progress,
        )
        result["commands"].extend(publication.pop("commands"))
        result["publication"] = publication
        progress.check("commit and requested publication completed")
        result["mutation"]["observed"] = True
        result["mutation"]["completed"] = True
        _capture_ending_state(result, root, supervisor)
        result["terminal_status"] = "publication-completed"
        result["safest_next_interaction"] = (
            "Review commit and remote verification evidence."
        )
    except GuardError as exc:
        _record_guard_failure(result, exc)
    except GitPublicationError as exc:
        result["publication"] = exc.evidence
        result["commands"].extend(exc.commands)
        result["mutation"]["observed"] = exc.mutation_observed
        _record_operation_failure(
            result,
            exc,
            repository_root,
            supervisor,
            terminal_status=(
                "partial-publication"
                if exc.mutation_observed
                else "pre-publication-failed"
            ),
        )
    return _finalize_execution(
        result,
        destination,
        progress,
        validate_terminal_status=True,
    )



def execute_governed_validation(
    operation: Mapping[str, Any],
    progress: TerminalProgress | None = None,
) -> tuple[dict[str, Any], Path]:
    (
        progress,
        result,
        supervisor,
        repository_root,
        destination,
    ) = _prepare_execution(operation, progress)

    try:
        root = _evaluate_guarded_repository(
            operation,
            result,
            supervisor,
            progress,
        )
        progress.phase(3, "running governed validation")
        evidence = run_governed_validation(
            root,
            supervisor,
            operation["inputs"],
            operation["expected_mutations"],
            operation["publication"],
        )
        result["commands"].extend(evidence.pop("commands"))
        result["validation_evidence"] = evidence
        progress.check("all requested validation profiles passed")
        progress.phase(4, "verifying resulting state")
        _capture_ending_state(result, root, supervisor)
        result["terminal_status"] = "validation-completed"
        result["safest_next_interaction"] = (
            "Review governed validation evidence before successor mutation."
        )
    except GuardError as exc:
        _record_guard_failure(result, exc)
    except GovernedValidationError as exc:
        result["validation_evidence"] = exc.evidence
        result["commands"].extend(exc.commands)
        _record_operation_failure(
            result,
            exc,
            repository_root,
            supervisor,
            terminal_status="pre-mutation-failed",
        )
    return _finalize_execution(
        result,
        destination,
        progress,
        validate_terminal_status=True,
    )


OPERATION_HANDLERS = {
    "repository-interrogation": execute_interrogation,
    "local-file-operations": execute_local_file_operation,
    "git-publication": execute_git_publication,
    "governed-validation": execute_governed_validation,
}


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: ./scripts/governed-execute /path/to/operation.json", file=sys.stderr)
        return 64

    operation_path = Path(args[0]).expanduser().resolve()
    operation: dict[str, Any] | None = None
    destination: Path | None = None
    progress = TerminalProgress()
    try:
        print(f"Governed Executor {EXECUTOR_VERSION}", flush=True)
        progress.phase(1, "validating operation description")
        operation = load_operation(operation_path)
        destination = result_destination(
            operation,
            Path(operation["repository"]["root"]).expanduser().resolve(),
        )
        progress.check("schema version supported")
        progress.check("executor compatibility satisfied")
        progress.check("operation digest verified")
        print("", flush=True)
        print(f"Repository : {operation['repository']['root']}", flush=True)
        print(f"Revision   : {operation['guards']['head']}", flush=True)
        print(f"Operation  : {operation['operation_id']}", flush=True)
        print(f"Type       : {operation['operation_type']}", flush=True)
        print(f"Result     : {destination}", flush=True)
        print("", flush=True)

        handler = OPERATION_HANDLERS[operation["operation_type"]]
        result, destination = handler(operation, progress)

        print("", flush=True)
        print("-" * 60, flush=True)
        print(f"STATUS: {result['terminal_status']}", flush=True)
        print("", flush=True)
        print("Result:", flush=True)
        print(f"  {destination}", flush=True)
        print("", flush=True)
        print("Next step:", flush=True)
        print(f"  {result['safest_next_interaction']}", flush=True)

        if result["terminal_status"] not in SUCCESS_TERMINAL_STATUSES:
            return 1
        return 0
    except ExecutorError as exc:
        print("", file=sys.stderr, flush=True)
        print("-" * 60, file=sys.stderr, flush=True)
        print("STATUS: executor-failed", file=sys.stderr, flush=True)
        print(f"Reason: {exc}", file=sys.stderr, flush=True)
        if destination is not None:
            print(f"Result: {destination}", file=sys.stderr, flush=True)
        return 1
