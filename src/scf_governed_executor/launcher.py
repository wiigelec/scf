#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = str(ROOT / "src")
sys.path.insert(0, SOURCE_PATH)
existing_pythonpath = os.environ.get("PYTHONPATH")
os.environ["PYTHONPATH"] = (
    SOURCE_PATH
    if not existing_pythonpath
    else SOURCE_PATH + os.pathsep + existing_pythonpath
)

from scf_governed_executor import EXECUTOR_VERSION
from scf_governed_executor import core as core_module


LEGACY_EXECUTOR_VERSION = "0.7.0"


def _operation_metadata(path: Path) -> tuple[str | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None, None
    if not isinstance(value, dict):
        return None, None
    operation_type = value.get("operation_type")
    executor_version = value.get("executor_version")
    return (
        operation_type if isinstance(operation_type, str) else None,
        executor_version if isinstance(executor_version, str) else None,
    )


def _legacy(operation_path: Path) -> int:
    completed = subprocess.run(
        [sys.executable, "-m", "scf_governed_executor", str(operation_path)],
        cwd=ROOT,
        env=dict(os.environ),
        check=False,
    )
    return completed.returncode


def _git_publication(operation_path: Path) -> int:
    from scf_governed_executor import resumable_publication

    return resumable_publication.main([str(operation_path)])


def _session_initialize(operation_path: Path) -> int:
    from scf_governed_executor import session_initialize

    return session_initialize.main([str(operation_path)])


def _self_update(operation_path: Path) -> int:
    from scf_governed_executor import self_update

    return self_update.main([str(operation_path)])


def _issue_create(operation_path: Path) -> int:
    from scf_governed_executor import issue_create

    return issue_create.main([str(operation_path)])


def _repository_interrogation(operation_path: Path) -> int:
    return core_module.main([str(operation_path)])


CURRENT_DISPATCH: dict[str, Callable[[Path], int]] = {
    "development-session-initialize": _session_initialize,
    "executor-self-update": _self_update,
    "git-publication": _git_publication,
    "issue-create": _issue_create,
    "repository-interrogation": _repository_interrogation,
}


def _unsupported(operation_type: str | None) -> int:
    print(
        f"unsupported executor version for operation type {operation_type!r}",
        file=sys.stderr,
    )
    return 1


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "usage: ./scripts/governed-execute /path/to/operation.json",
            file=sys.stderr,
        )
        return 64

    operation_path = Path(sys.argv[1]).expanduser().resolve()
    operation_type, version = _operation_metadata(operation_path)

    if version == EXECUTOR_VERSION:
        handler = CURRENT_DISPATCH.get(operation_type or "")
        return handler(operation_path) if handler is not None else _unsupported(operation_type)

    if version == LEGACY_EXECUTOR_VERSION:
        return _legacy(operation_path)

    return _unsupported(operation_type)


if __name__ == "__main__":
    raise SystemExit(main())
