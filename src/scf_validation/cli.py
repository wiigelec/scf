"""Command-line orchestration and rendering."""

from __future__ import annotations

import argparse
import traceback
from pathlib import Path
from typing import Sequence

from .checks import REGISTERED_CHECKS
from .context import ContextError, ValidationContext
from .diagnostics import Diagnostic, Severity
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


def select_checks(check_ids: Sequence[str] | None) -> tuple[Check, ...]:
    if not check_ids:
        return REGISTERED_CHECKS
    by_id = {check.check_id: check for check in REGISTERED_CHECKS}
    unknown = sorted(set(check_ids) - set(by_id))
    if unknown:
        raise ValueError("unknown check identifier(s): " + ", ".join(unknown))
    requested = set(check_ids)
    return tuple(check for check in REGISTERED_CHECKS if check.check_id in requested)


def run_checks(context: ValidationContext, checks: Sequence[Check]) -> tuple[int, int]:
    errors = 0
    warnings = 0
    for check in checks:
        diagnostics = check.function(context)
        check_errors = [d for d in diagnostics if d.severity == Severity.ERROR]
        status = "FAIL" if check_errors else "PASS"
        print(f"{status} {check.check_id} {check.name}")
        for diagnostic in diagnostics:
            print(diagnostic.render())
            if diagnostic.severity == Severity.ERROR:
                errors += 1
            else:
                warnings += 1
    return errors, warnings


def main(root: Path, argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.list_checks:
            for check in REGISTERED_CHECKS:
                print(f"{check.check_id} {check.name}")
            return 0
        checks = select_checks(args.check_ids)
        context = ValidationContext.create(root)
        errors, warnings = run_checks(context, checks)
    except (ContextError, ValueError) as exc:
        print(f"Validation invocation failed: {exc}")
        return 2
    except Exception as exc:  # unexpected validator failure
        print(f"Internal validator failure: {type(exc).__name__}: {exc}")
        if "args" in locals() and args.debug:
            traceback.print_exc()
        return 2

    if errors:
        print(f"Validation failed: {errors} error(s), {warnings} warning(s)")
        return 1
    print(f"Validation passed: {errors} error(s), {warnings} warning(s)")
    return 0
