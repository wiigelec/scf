# Command-line interface for session restoration.

from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path
from typing import Sequence

from .restore import RestorationError, restore_session


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="./scripts/restore-session",
        description="Restore governed SCF development context without mutation.",
    )
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--format", choices=("human", "json"), default="json")
    parser.add_argument("--debug", action="store_true")
    return parser


def render_human(payload: dict[str, object]) -> None:
    print(f"Restoration status: {payload['status']}")
    lifecycle = payload["lifecycle"]
    assert isinstance(lifecycle, dict)
    print(f"Lifecycle frontier: {lifecycle['frontier']}")
    print(f"Next authorized action: {lifecycle['next_authorized_action']}")
    diagnostics = payload["diagnostics"]
    assert isinstance(diagnostics, list)
    for item in diagnostics:
        assert isinstance(item, dict)
        print(f"{item['code']}: {item['message']}")


def main(root: Path, argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        supplied = json.loads(args.evidence.read_text(encoding="utf-8"))
        if not isinstance(supplied, dict):
            raise RestorationError("evidence bundle must be a JSON object")
        result = restore_session(root, supplied)
        payload = result.as_dict()
        if args.format == "json":
            print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        else:
            render_human(payload)
        return 0 if result.status == "complete" else 1
    except (OSError, json.JSONDecodeError, RestorationError, ValueError) as exc:
        print(f"Restoration invocation failed: {exc}")
        return 2
    except Exception as exc:
        print(f"Internal restoration failure: {type(exc).__name__}: {exc}")
        if "args" in locals() and args.debug:
            traceback.print_exc()
        return 2
