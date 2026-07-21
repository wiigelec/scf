from __future__ import annotations

import json
import sys
from pathlib import Path

from . import core as core_module
from . import local_files


core_module.EXECUTOR_VERSION = "0.2.1"


PROTECTED_EXECUTOR_PATHS = frozenset(
    {
        "scripts/governed-execute",
        "src/scf_governed_executor/__init__.py",
        "src/scf_governed_executor/__main__.py",
        "src/scf_governed_executor/core.py",
        "src/scf_governed_executor/git_publication.py",
        "src/scf_governed_executor/local_files.py",
        "src/scf_governed_executor/self_update.py",
        "src/scf_governed_executor/validation.py",
    }
)


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


def _operation_type(argv: list[str]) -> str | None:
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


if _operation_type(sys.argv[1:]) == "executor-self-update":
    from .self_update import main
else:
    main = core_module.main


raise SystemExit(main())
