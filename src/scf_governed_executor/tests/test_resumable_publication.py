from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from scf_governed_executor.core import CommandSupervisor  # noqa: E402
from scf_governed_executor.resumable_publication import (  # noqa: E402
    _existing_commit,
)


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


class ExistingCommitTests(unittest.TestCase):
    def test_clean_exact_child_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init", "-q")
            git(root, "config", "user.name", "Governed Test")
            git(root, "config", "user.email", "governed@example.invalid")
            (root / "base.txt").write_text("base\n")
            git(root, "add", "base.txt")
            git(root, "commit", "-q", "-m", "base")
            parent = git(root, "rev-parse", "HEAD")
            (root / "change.txt").write_text("change\n")
            git(root, "add", "change.txt")
            git(root, "commit", "-q", "-m", "Publish change")
            head = git(root, "rev-parse", "HEAD")
            branch = git(root, "branch", "--show-current")
            operation = {
                "repository": {"root": str(root), "origin": "unused"},
                "guards": {"branch": branch, "head": parent, "clean": False},
                "inputs": {
                    "paths": ["change.txt"],
                    "message": "Publish change",
                },
                "expected_mutations": {
                    "paths": ["change.txt"],
                    "parent_head": parent,
                },
                "publication": {
                    "remote": "origin",
                    "branch": branch,
                },
            }
            evidence = _existing_commit(
                operation,
                root,
                CommandSupervisor(heartbeat_seconds=0.01),
                {
                    "head": head,
                    "clean": True,
                    "branch": branch,
                    "status": [],
                },
            )
            self.assertEqual(evidence["commit"], head)
            self.assertEqual(evidence["staging"], "already-completed")
            self.assertEqual(
                evidence["commit_creation"], "already-completed"
            )

    def test_wrong_child_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init", "-q")
            git(root, "config", "user.name", "Governed Test")
            git(root, "config", "user.email", "governed@example.invalid")
            (root / "base.txt").write_text("base\n")
            git(root, "add", "base.txt")
            git(root, "commit", "-q", "-m", "base")
            parent = git(root, "rev-parse", "HEAD")
            (root / "wrong.txt").write_text("wrong\n")
            git(root, "add", "wrong.txt")
            git(root, "commit", "-q", "-m", "Publish change")
            head = git(root, "rev-parse", "HEAD")
            branch = git(root, "branch", "--show-current")
            operation = {
                "repository": {"root": str(root), "origin": "unused"},
                "guards": {"branch": branch, "head": parent, "clean": False},
                "inputs": {
                    "paths": ["change.txt"],
                    "message": "Publish change",
                },
                "expected_mutations": {
                    "paths": ["change.txt"],
                    "parent_head": parent,
                },
                "publication": {
                    "remote": "origin",
                    "branch": branch,
                },
            }
            with self.assertRaisesRegex(
                Exception, "paths outside the exact authorization"
            ):
                _existing_commit(
                    operation,
                    root,
                    CommandSupervisor(heartbeat_seconds=0.01),
                    {
                        "head": head,
                        "clean": True,
                        "branch": branch,
                        "status": [],
                    },
                )


if __name__ == "__main__":
    unittest.main()
