"""Command-line orchestration and rendering."""

from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path
from typing import Sequence

from .checks import REGISTERED_CHECKS, REQUIRED_CHECK_IDS
from .context import ContextError, RepositoryContentSource, ValidationContext
from .gate import (
    ValidationMode,
    ValidationRun,
    build_run,
    certification_diagnostics,
    inspect_repository_state,
    resolve_mode,
    working_tree_state_diagnostics,
)
from .registry import Check, validate_registry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="./scripts/validate",
        description="Validate current SCF repository content.",
    )
    parser.add_argument(
        "--list-checks",
        action="store_true",
        help="list registered checks and exit",
    )
    parser.add_argument(
        "--mode",
        choices=tuple(item.value for item in ValidationMode),
        help=(
            "validation mode: focused requires --check; complete runs the full "
            "registry; certify runs the full registry against a clean revision"
        ),
    )
    parser.add_argument(
        "--check",
        action="append",
        dest="check_ids",
        metavar="CHECK_ID",
        help="run only the named registered check; may be repeated",
    )
    parser.add_argument(
        "--format",
        choices=("human", "json"),
        default="human",
        help="result format; default: human",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="show a traceback for unexpected internal failures",
    )
    return parser


def select_checks(
    mode: ValidationMode,
    check_ids: Sequence[str] | None,
    registry: Sequence[Check],
) -> tuple[Check, ...]:
    if mode in (ValidationMode.COMPLETE, ValidationMode.CERTIFY):
        return tuple(registry)

    by_id = {check.check_id: check for check in registry}
    unknown = sorted(set(check_ids or ()) - set(by_id))
    if unknown:
        raise ValueError("unknown check identifier(s): " + ", ".join(unknown))
    requested = set(check_ids or ())
    return tuple(check for check in registry if check.check_id in requested)


def execute_checks(
    root: Path,
    mode: ValidationMode,
    checks: Sequence[Check],
) -> ValidationRun:
    repository = inspect_repository_state(root)
    preconditions = (
        certification_diagnostics(repository)
        if mode == ValidationMode.CERTIFY
        else ()
    )
    if preconditions:
        return build_run(mode, repository, (), (), preconditions)

    if mode != ValidationMode.CERTIFY:
        local_state_diagnostics = working_tree_state_diagnostics(root)
        if local_state_diagnostics:
            return build_run(mode, repository, (), (), local_state_diagnostics)

    if mode == ValidationMode.CERTIFY:
        assert repository.revision is not None
        source = RepositoryContentSource.REVISION
        content_revision = repository.revision
    else:
        source = RepositoryContentSource.WORKING_TREE
        content_revision = None

    context = ValidationContext.create(root, source, content_revision)
    repository = type(repository)(
        revision=repository.revision,
        clean=repository.clean,
        content_source=source,
        content_revision=content_revision,
    )
    diagnostics = tuple(check.function(context) for check in checks)
    return build_run(mode, repository, checks, diagnostics)


def render_human(run: ValidationRun) -> None:
    for diagnostic in run.diagnostics:
        print(diagnostic.render())
    for result in run.checks:
        status = "PASS" if result.passed else "FAIL"
        print(f"{status} {result.check_id} {result.name}")
        for diagnostic in result.diagnostics:
            print(diagnostic.render())
    if run.mode == ValidationMode.CERTIFY and run.passed:
        print(f"CERTIFIED {run.repository.revision}")


def render_json(run: ValidationRun) -> None:
    print(json.dumps(run.as_dict(), sort_keys=True, separators=(",", ":")))


def render_check_list(registry: Sequence[Check], output_format: str) -> None:
    if output_format == "json":
        payload = {
            "schema_version": 1,
            "checks": [
                {"id": check.check_id, "name": check.name}
                for check in registry
            ],
        }
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return
    for check in registry:
        print(f"{check.check_id} {check.name}")


def main(root: Path, argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        registry = validate_registry(REGISTERED_CHECKS, REQUIRED_CHECK_IDS)
        if args.list_checks:
            if args.mode or args.check_ids:
                raise ValueError(
                    "--list-checks cannot be combined with --mode or --check"
                )
            render_check_list(registry, args.format)
            return 0

        mode = resolve_mode(args.mode, args.check_ids)
        checks = select_checks(mode, args.check_ids, registry)
        run = execute_checks(root, mode, checks)
        if args.format == "json":
            render_json(run)
        else:
            render_human(run)
    except (ContextError, ValueError) as exc:
        print(f"Validation invocation failed: {exc}")
        return 2
    except Exception as exc:  # unexpected validator failure
        print(f"Internal validator failure: {type(exc).__name__}: {exc}")
        if "args" in locals() and args.debug:
            traceback.print_exc()
        return 2

    if run.errors:
        if args.format == "human":
            print(
                f"Validation failed: {run.errors} error(s), "
                f"{run.warnings} warning(s)"
            )
        return 1
    if args.format == "human":
        print(
            f"Validation passed: {run.errors} error(s), "
            f"{run.warnings} warning(s)"
        )
    return 0
