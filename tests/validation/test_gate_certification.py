from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from scf_validation.cli import main
from scf_validation.registry import Check, RegistryError, validate_registry
from tests.validation.test_validation import RepositoryFixture


class ValidationGateCertificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = RepositoryFixture()
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.repo.root,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=self.repo.root,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-qm", "fixture"],
            cwd=self.repo.root,
            check=True,
        )

    def tearDown(self) -> None:
        self.repo.close()

    def invoke_json(self, *args: str) -> tuple[int, dict[str, object]]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(self.repo.root, [*args, "--format", "json"])
        return status, json.loads(output.getvalue())

    def test_clean_revision_certifies_exact_head(self) -> None:
        expected = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo.root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()

        status, payload = self.invoke_json("--mode", "certify")

        self.assertEqual(0, status)
        self.assertEqual("pass", payload["outcome"])
        self.assertEqual("certify", payload["mode"])
        self.assertEqual(expected, payload["repository"]["revision"])
        self.assertTrue(payload["repository"]["clean"])
        self.assertEqual("revision", payload["repository"]["content_source"])
        self.assertEqual(expected, payload["repository"]["content_revision"])
        self.assertEqual(6, len(payload["checks"]))

    def test_dirty_repository_refuses_certification(self) -> None:
        self.repo.write("README.md", "# changed\n")

        status, payload = self.invoke_json("--mode", "certify")

        self.assertEqual(1, status)
        self.assertEqual("fail", payload["outcome"])
        self.assertEqual([], payload["checks"])
        self.assertEqual(
            ["SCF-GATE-CERT-002"],
            [item["id"] for item in payload["diagnostics"]],
        )

    def test_complete_mode_validates_dirty_working_tree(self) -> None:
        self.repo.write("README.md", "# changed\n")

        status, payload = self.invoke_json("--mode", "complete")

        self.assertEqual(0, status)
        self.assertEqual("working-tree", payload["repository"]["classification"])
        self.assertEqual("working-tree", payload["repository"]["content_source"])
        self.assertIsNone(payload["repository"]["content_revision"])
        self.assertEqual("pass", payload["outcome"])
        self.assertEqual(6, len(payload["checks"]))

    def test_revision_context_ignores_unrelated_worktree_content(self) -> None:
        from scf_validation.context import RepositoryContentSource, ValidationContext

        expected = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo.root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()
        committed = (self.repo.root / "README.md").read_bytes()
        self.repo.write("README.md", "# unrelated local change\n")
        self.repo.write("untracked.json", "{not valid json")

        context = ValidationContext.create(
            self.repo.root,
            RepositoryContentSource.REVISION,
            expected,
        )

        self.assertEqual(committed, context.read_bytes("README.md"))
        self.assertNotIn("untracked.json", context.json_paths())

    def test_machine_output_has_deterministic_shape(self) -> None:
        status, payload = self.invoke_json("--check", "SCF-JSON-001")

        self.assertEqual(0, status)
        self.assertEqual(
            {
                "checks",
                "diagnostics",
                "mode",
                "outcome",
                "repository",
                "schema_version",
                "summary",
            },
            set(payload),
        )
        self.assertEqual("focused", payload["mode"])
        self.assertEqual(0, payload["summary"]["errors"])
        self.assertEqual("SCF-JSON-001", payload["checks"][0]["id"])

    def test_registry_rejects_missing_required_check(self) -> None:
        from scf_validation.checks import REGISTERED_CHECKS, REQUIRED_CHECK_IDS

        with self.assertRaisesRegex(RegistryError, "missing"):
            validate_registry(REGISTERED_CHECKS[:-1], REQUIRED_CHECK_IDS)

    def test_registry_rejects_duplicate_identifier(self) -> None:
        from scf_validation.checks import REGISTERED_CHECKS, REQUIRED_CHECK_IDS

        duplicate = (*REGISTERED_CHECKS[:-1], REGISTERED_CHECKS[0])
        with self.assertRaisesRegex(RegistryError, "duplicate"):
            validate_registry(duplicate, REQUIRED_CHECK_IDS)

    def test_registry_rejects_non_callable_entry(self) -> None:
        bad = Check("SCF-BAD-001", "bad", None)  # type: ignore[arg-type]
        with self.assertRaisesRegex(RegistryError, "non-callable"):
            validate_registry((bad,), ("SCF-BAD-001",))

    def test_json_check_listing_matches_required_inventory(self) -> None:
        from scf_validation.checks import REQUIRED_CHECK_IDS

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(
                self.repo.root,
                ["--list-checks", "--format", "json"],
            )
        payload = json.loads(output.getvalue())
        self.assertEqual(0, status)
        self.assertEqual(
            list(REQUIRED_CHECK_IDS),
            [item["id"] for item in payload["checks"]],
        )


if __name__ == "__main__":
    unittest.main()
