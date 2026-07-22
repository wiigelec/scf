from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from scf_governed_executor.validation import (  # noqa: E402
    GovernedValidationError,
    run_governed_validation,
    validate_governed_validation_inputs,
)


class FakeRecord:
    def __init__(self, command: list[str], exit_code: int = 0) -> None:
        self.command = command
        self.cwd = "/tmp/repo"
        self.started_at = "2026-01-01T00:00:00+00:00"
        self.finished_at = "2026-01-01T00:00:01+00:00"
        self.elapsed_seconds = 1.0
        self.exit_code = exit_code
        self.timed_out = False
        self.stdout = ""
        self.stderr = ""
        self.redaction_events = []


class FakeSupervisor:
    def __init__(self, exit_codes: list[int] | None = None) -> None:
        self.exit_codes = list(exit_codes or [])
        self.commands: list[list[str]] = []

    def run(self, command, root, *, timeout_seconds, phase):
        command = list(command)
        self.commands.append(command)
        exit_code = self.exit_codes.pop(0) if self.exit_codes else 0
        return FakeRecord(command, exit_code)


class ValidationContractTests(unittest.TestCase):
    def test_unknown_profile_is_rejected(self) -> None:
        with self.assertRaisesRegex(GovernedValidationError, "unsupported"):
            validate_governed_validation_inputs(
                {"profiles": ["arbitrary-shell"]},
                {"profiles": ["arbitrary-shell"]},
                {},
            )

    def test_profiles_must_be_sorted_and_unique(self) -> None:
        with self.assertRaisesRegex(GovernedValidationError, "sorted"):
            validate_governed_validation_inputs(
                {"profiles": ["whitespace", "repository-complete"]},
                {"profiles": ["whitespace", "repository-complete"]},
                {},
            )

    def test_expected_profiles_must_match(self) -> None:
        with self.assertRaisesRegex(GovernedValidationError, "exactly match"):
            validate_governed_validation_inputs(
                {"profiles": ["whitespace"]},
                {"profiles": ["repository-complete"]},
                {},
            )

    def test_publication_must_be_empty(self) -> None:
        with self.assertRaisesRegex(GovernedValidationError, "empty"):
            validate_governed_validation_inputs(
                {"profiles": ["whitespace"]},
                {"profiles": ["whitespace"]},
                {"push": False},
            )


class ExecutionTests(unittest.TestCase):
    def test_executor_constructs_allowlisted_commands(self) -> None:
        supervisor = FakeSupervisor()
        with tempfile.TemporaryDirectory() as tmp:
            evidence = run_governed_validation(
                Path(tmp),
                supervisor,
                {"profiles": ["repository-complete", "whitespace"]},
                {"profiles": ["repository-complete", "whitespace"]},
                {},
            )
        self.assertTrue(evidence["verified"])
        self.assertEqual(
            supervisor.commands,
            [
                ["./scripts/validate", "--mode", "complete", "--format", "json"],
                ["git", "diff", "--check"],
            ],
        )

    def test_failure_stops_later_profiles_and_preserves_evidence(self) -> None:
        supervisor = FakeSupervisor([1])
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(
                GovernedValidationError, "profile failed"
            ) as ctx:
                run_governed_validation(
                    Path(tmp),
                    supervisor,
                    {"profiles": ["repository-complete", "whitespace"]},
                    {"profiles": ["repository-complete", "whitespace"]},
                    {},
                )
        self.assertEqual(len(supervisor.commands), 1)
        self.assertFalse(ctx.exception.evidence["verified"])
        self.assertFalse(ctx.exception.evidence["profiles"][0]["passed"])


if __name__ == "__main__":
    unittest.main()
