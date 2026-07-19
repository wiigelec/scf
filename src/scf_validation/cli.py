"""Command-line orchestration and rendering."""

from __future__ import annotations

import argparse
import traceback
from pathlib import Path
from typing import Sequence

from .checks import REGISTERED_CHECKS
from .context import ContextError, ValidationContext
from .gate import (
    ValidationMode,
    ValidationRun,
    build_run,
    inspect_repository_state,
    resolve_mode,
)
from .registry import Check


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
            "registry; certify is reserved until certification semantics are implemented"
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
        "--debug",
        action="store_true",
        help="show a traceback for unexpected internal failures",
    )
    return parser


def select_checks(
    mode: ValidationMode,
    check_ids: Sequence[str] | None,
) -> tuple[Check, ...]:
    if mode == ValidationMode.COMPLETE:
        return REGISTERED_CHECKS

    by_id = {check.check_id: check for check in REGISTERED_CHECKS}
    unknown = sorted(set(check_ids or ()) - set(by_id))
    if unknown:
        raise ValueError("unknown check identifier(s): " + ", ".join(unknown))
    requested = set(check_ids or ())
    return tuple(check for check in REGISTERED_CHECKS if check.check_id in requested)


def execute_checks(
    context: ValidationContext,
    mode: ValidationMode,
    checks: Sequence[Check],
) -> ValidationRun:
    repository = inspect_repository_state(context.root)
    diagnostics = tuple(check.function(context) for check in checks)
    return build_run(mode, repository, checks, diagnostics)


def render_human(run: ValidationRun) -> None:
    for result in run.checks:
        status = "PASS" if result.passed else "FAIL"
        print(f"{status} {result.check_id} {result.name}")
        for diagnostic in result.diagnostics:
            print(diagnostic.render())


def main(root: Path, argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.list_checks:
            if args.mode or args.check_ids:
                raise ValueError(
                    "--list-checks cannot be combined with --mode or --check"
                )
            for check in REGISTERED_CHECKS:
                print(f"{check.check_id} {check.name}")
            return 0

        mode = resolve_mode(args.mode, args.check_ids)
        checks = select_checks(mode, args.check_ids)
        context = ValidationContext.create(root)
        run = execute_checks(context, mode, checks)
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
        print(
            f"Validation failed: {run.errors} error(s), "
            f"{run.warnings} warning(s)"
        )
        return 1
    print(
        f"Validation passed: {run.errors} error(s), "
        f"{run.warnings} warning(s)"
    )
    return 0
