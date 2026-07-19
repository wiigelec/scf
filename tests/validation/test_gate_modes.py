from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from scf_validation.cli import main
from scf_validation.gate import (
    CheckResult,
    RepositoryState,
    ValidationMode,
    ValidationRun,
    inspect_repository_state,
    resolve_mode,
)


class ValidationGateModeTests(unittest.TestCase):
    def test_default_without_checks_is_complete(self) -> None:
        self.assertEqual(ValidationMode.COMPLETE, resolve_mode(None, None))

    def test_default_with_checks_is_focused(self) -> None:
        self.assertEqual(
            ValidationMode.FOCUSED,
            resolve_mode(None, ["SCF-JSON-001"]),
        )

    def test_explicit_focused_requires_check(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires at least one"):
            resolve_mode("focused", None)

    def test_complete_rejects_check_selection(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not accept --check"):
            resolve_mode("complete", ["SCF-JSON-001"])

    def test_explicit_certify_resolves_certification_mode(self) -> None:
        self.assertEqual(
            ValidationMode.CERTIFY,
            resolve_mode("certify", None),
        )

    def test_run_result_aggregates_ordered_check_results(self) -> None:
        run = ValidationRun(
            mode=ValidationMode.COMPLETE,
            repository=RepositoryState("a" * 40, True),
            checks=(
                CheckResult("A", "first", ()),
                CheckResult("B", "second", ()),
            ),
        )
        self.assertTrue(run.passed)
        self.assertEqual(0, run.errors)
        self.assertEqual(0, run.warnings)
        self.assertEqual("clean-revision", run.repository.classification)

    def test_repository_state_supports_unborn_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / "tracked.txt").write_text("one\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True)

            state = inspect_repository_state(root)
            self.assertIsNone(state.revision)
            self.assertFalse(state.clean)
            self.assertEqual("unborn-working-tree", state.classification)

    def test_repository_state_distinguishes_clean_and_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=root,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=root,
                check=True,
            )
            (root / "tracked.txt").write_text("one\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True)
            subprocess.run(
                ["git", "commit", "-qm", "initial"],
                cwd=root,
                check=True,
            )

            clean = inspect_repository_state(root)
            self.assertTrue(clean.clean)
            self.assertEqual("clean-revision", clean.classification)

            (root / "tracked.txt").write_text("two\n", encoding="utf-8")
            dirty = inspect_repository_state(root)
            self.assertFalse(dirty.clean)
            self.assertEqual(clean.revision, dirty.revision)
            self.assertEqual("working-tree", dirty.classification)

    def test_list_checks_rejects_mode_combination(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(
                REPOSITORY_ROOT,
                ["--list-checks", "--mode", "complete"],
            )
        self.assertEqual(2, status)
        self.assertIn("cannot be combined", output.getvalue())

    def test_explicit_complete_preserves_success_contract(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(REPOSITORY_ROOT, ["--mode", "complete"])
        self.assertEqual(0, status)
        self.assertIn("Validation passed:", output.getvalue())


if __name__ == "__main__":
    unittest.main()
