from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from scf_validation.cli import main
from scf_validation.context import (
    InputProblem,
    RepositoryContentSource,
    ValidationContext,
)
from tests.validation.test_validation import RepositoryFixture


class RepositoryStateBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = RepositoryFixture()
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo.root, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=self.repo.root, check=True)
        self.head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo.root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()

    def tearDown(self) -> None:
        self.repo.close()

    def context(self) -> ValidationContext:
        return ValidationContext.create(self.repo.root)

    def invoke_json(self, *args: str) -> tuple[int, dict[str, object]]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(self.repo.root, [*args, "--format", "json"])
        return status, json.loads(output.getvalue())

    def test_working_tree_includes_staged_new_json(self) -> None:
        self.repo.write("staged.json", "{}\n")
        subprocess.run(["git", "add", "staged.json"], cwd=self.repo.root, check=True)
        self.assertIn("staged.json", self.context().json_paths())

    def test_working_tree_includes_unstaged_and_untracked_json(self) -> None:
        self.repo.write("authority/core/SCF-CORE.json", "{}\n")
        self.repo.write("untracked.json", "{}\n")
        paths = self.context().json_paths()
        self.assertIn("authority/core/SCF-CORE.json", paths)
        self.assertIn("untracked.json", paths)

    def test_working_tree_excludes_ignored_json(self) -> None:
        self.repo.write(".gitignore", "__pycache__/\nignored.json\n")
        self.repo.write("ignored.json", "{}\n")
        self.assertNotIn("ignored.json", self.context().json_paths())

    def test_working_tree_represents_deletion_as_absent(self) -> None:
        self.repo.write("delete-me.json", "{}\n")
        subprocess.run(["git", "add", "delete-me.json"], cwd=self.repo.root, check=True)
        subprocess.run(["git", "commit", "-qm", "add deletion target"], cwd=self.repo.root, check=True)
        (self.repo.root / "delete-me.json").unlink()
        self.assertNotIn("delete-me.json", self.context().json_paths())
        subprocess.run(["git", "add", "-u", "delete-me.json"], cwd=self.repo.root, check=True)
        self.assertNotIn("delete-me.json", ValidationContext.create(self.repo.root).json_paths())

    def test_working_tree_rename_exposes_only_destination(self) -> None:
        self.repo.write("old.json", "{}\n")
        subprocess.run(["git", "add", "old.json"], cwd=self.repo.root, check=True)
        subprocess.run(["git", "commit", "-qm", "add rename target"], cwd=self.repo.root, check=True)
        os.rename(self.repo.root / "old.json", self.repo.root / "new.json")
        paths = self.context().json_paths()
        self.assertNotIn("old.json", paths)
        self.assertIn("new.json", paths)

    def test_revision_source_ignores_all_local_path_states(self) -> None:
        self.repo.write("staged.json", "{}\n")
        subprocess.run(["git", "add", "staged.json"], cwd=self.repo.root, check=True)
        self.repo.write("untracked.json", "{}\n")
        self.repo.write(".gitignore", "__pycache__/\nignored.json\n")
        self.repo.write("ignored.json", "{}\n")
        self.repo.write("README.md", "# local modification\n")
        context = ValidationContext.create(
            self.repo.root,
            RepositoryContentSource.REVISION,
            self.head,
        )
        paths = context.json_paths()
        self.assertNotIn("staged.json", paths)
        self.assertNotIn("untracked.json", paths)
        self.assertNotIn("ignored.json", paths)
        self.assertNotEqual(b"# local modification\n", context.read_bytes("README.md"))

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_working_tree_symlink_read_does_not_follow_target(self) -> None:
        outside = self.repo.root.parent / "outside-state-target.json"
        outside.write_text('{"outside": true}\n', encoding="utf-8")
        link = self.repo.root / "link.json"
        link.symlink_to(outside)
        context = self.context()
        self.assertIn("link.json", context.json_paths())
        with self.assertRaises(InputProblem) as raised:
            context.read_bytes("link.json")
        self.assertEqual("SCF-PATH-002", raised.exception.diagnostic_id)
        self.assertFalse(context.is_regular_file("link.json"))
        outside.unlink()

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_type_change_to_symlink_is_not_regular_file(self) -> None:
        self.repo.write("README.md", "# original\n")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo.root, check=True)
        subprocess.run(["git", "commit", "-qm", "regular readme"], cwd=self.repo.root, check=True)
        (self.repo.root / "README.md").unlink()
        (self.repo.root / "README.md").symlink_to("VERSION")
        self.assertFalse(self.context().is_regular_file("README.md"))

    def test_unresolved_conflict_fails_with_state_source_diagnostic(self) -> None:
        self.repo.write("conflict.json", '{"side": "base"}\n')
        subprocess.run(["git", "add", "conflict.json"], cwd=self.repo.root, check=True)
        subprocess.run(["git", "commit", "-qm", "conflict base"], cwd=self.repo.root, check=True)
        default_branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=self.repo.root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()
        subprocess.run(["git", "checkout", "-qb", "other"], cwd=self.repo.root, check=True)
        self.repo.write("conflict.json", '{"side": "other"}\n')
        subprocess.run(["git", "commit", "-am", "other side", "-q"], cwd=self.repo.root, check=True)
        subprocess.run(["git", "checkout", "-q", default_branch], cwd=self.repo.root, check=True)
        self.repo.write("conflict.json", '{"side": "current"}\n')
        subprocess.run(["git", "commit", "-am", "current side", "-q"], cwd=self.repo.root, check=True)
        merge = subprocess.run(
            ["git", "merge", "other"],
            cwd=self.repo.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertNotEqual(0, merge.returncode)
        status, payload = self.invoke_json("--mode", "complete")
        self.assertEqual(1, status)
        self.assertEqual([], payload["checks"])
        self.assertEqual(["SCF-GATE-STATE-001"], [item["id"] for item in payload["diagnostics"]])
        self.assertEqual("content_source=working-tree", payload["diagnostics"][0]["context"])


if __name__ == "__main__":
    unittest.main()
