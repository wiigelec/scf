from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import branch_create
from . import core as core_module
from . import lifecycle
from . import local_files
from . import issue_comments


core_module.EXECUTOR_VERSION = "0.5.0"

PROTECTED_EXECUTOR_PATHS = frozenset(
    {
        "scripts/governed-execute",
        "src/scf_governed_executor/__init__.py",
        "src/scf_governed_executor/__main__.py",
        "src/scf_governed_executor/core.py",
        "src/scf_governed_executor/git_publication.py",
        "src/scf_governed_executor/local_files.py",
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


def _object(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise core_module.SchemaError(f"{location} must be an object")
    return value


def _exact(
    value: Mapping[str, Any],
    allowed: set[str] | frozenset[str],
    required: set[str] | frozenset[str],
    location: str,
) -> None:
    unknown = set(value) - set(allowed)
    missing = set(required) - set(value)
    if unknown:
        raise core_module.SchemaError(
            f"{location} contains unknown fields: {', '.join(sorted(unknown))}"
        )
    if missing:
        raise core_module.SchemaError(
            f"{location} is missing required fields: {', '.join(sorted(missing))}"
        )


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


operation_type = _operation_type(sys.argv[1:])
if operation_type == "executor-self-update":
    from .self_update import main
elif operation_type == branch_create.BRANCH_CREATE_OPERATION_TYPE:
    main = branch_main
elif operation_type == issue_comments.ISSUE_COMMENT_OPERATION_TYPE:
    main = issue_comments.issue_comment_main
elif operation_type in lifecycle.LIFECYCLE_OPERATION_TYPES:
    main = lifecycle.lifecycle_main
else:
    main = core_module.main


raise SystemExit(main())
