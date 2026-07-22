from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from scf_governed_executor.core import CommandSupervisor  # noqa: E402
from scf_governed_executor.git_publication import (  # noqa: E402
    GitPublicationError,
    publish_git_changes,
    validate_git_publication_inputs,
)


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def init_repo(root: Path) -> str:
    git(root, "init", "-q")
    git(root, "config", "user.name", "Governed Test")
    git(root, "config", "user.email", "governed@example.invalid")
    (root / "base.txt").write_text("base\n")
    git(root, "add", "base.txt")
    git(root, "commit", "-q", "-m", "base")
    return git(root, "rev-parse", "HEAD")


class ValidationTests(unittest.TestCase):
    def test_paths_must_be_sorted_and_unique(self) -> None:
        with self.assertRaisesRegex(GitPublicationError, "sorted"):
            validate_git_publication_inputs(
                {"paths": ["b", "a"], "message": "commit"},
                {"paths": ["b", "a"], "parent_head": "0" * 40},
                {"push": False, "remote": "origin", "branch": "main"},
                push_authorized=False,
            )

    def test_push_requires_exact_authority(self) -> None:
        with self.assertRaisesRegex(GitPublicationError, "without push"):
            validate_git_publication_inputs(
                {"paths": ["a"], "message": "commit"},
                {"paths": ["a"], "parent_head": "0" * 40},
                {"push": True, "remote": "origin", "branch": "main"},
                push_authorized=False,
            )

    def test_unused_push_authority_is_rejected(self) -> None:
        with self.assertRaisesRegex(GitPublicationError, "must not exceed"):
            validate_git_publication_inputs(
                {"paths": ["a"], "message": "commit"},
                {"paths": ["a"], "parent_head": "0" * 40},
                {"push": False, "remote": "origin", "branch": "main"},
                push_authorized=True,
            )


class PublicationTests(unittest.TestCase):
    def test_exact_paths_are_committed_and_verified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = init_repo(root)
            branch = git(root, "branch", "--show-current")
            (root / "a.txt").write_text("a\n")
            (root / "b.txt").write_text("b\n")
            evidence = publish_git_changes(
                root,
                CommandSupervisor(heartbeat_seconds=0.01),
                {"paths": ["a.txt"], "message": "Add a"},
                {"paths": ["a.txt"], "parent_head": parent},
                {"push": False, "remote": "origin", "branch": branch},
                push_authorized=False,
            )
            self.assertTrue(evidence["verified"])
            self.assertEqual(evidence["committed_paths"], ["a.txt"])
            self.assertEqual(git(root, "show", "HEAD:a.txt"), "a")
            self.assertTrue((root / "b.txt").exists())
            self.assertEqual(git(root, "status", "--porcelain"), "?? b.txt")

    def test_dirty_index_is_rejected_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = init_repo(root)
            branch = git(root, "branch", "--show-current")
            (root / "already.txt").write_text("already\n")
            git(root, "add", "already.txt")
            (root / "a.txt").write_text("a\n")
            with self.assertRaisesRegex(GitPublicationError, "index must be empty") as ctx:
                publish_git_changes(
                    root,
                    CommandSupervisor(),
                    {"paths": ["a.txt"], "message": "Add a"},
                    {"paths": ["a.txt"], "parent_head": parent},
                    {"push": False, "remote": "origin", "branch": branch},
                    push_authorized=False,
                )
            self.assertFalse(ctx.exception.mutation_observed)
            self.assertEqual(git(root, "rev-parse", "HEAD"), parent)

    def test_parent_guard_is_rechecked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = init_repo(root)
            branch = git(root, "branch", "--show-current")
            (root / "a.txt").write_text("a\n")
            with self.assertRaisesRegex(GitPublicationError, "parent HEAD") as ctx:
                publish_git_changes(
                    root,
                    CommandSupervisor(),
                    {"paths": ["a.txt"], "message": "Add a"},
                    {"paths": ["a.txt"], "parent_head": "0" * 40},
                    {"push": False, "remote": "origin", "branch": branch},
                    push_authorized=False,
                )
            self.assertFalse(ctx.exception.mutation_observed)
            self.assertEqual(git(root, "rev-parse", "HEAD"), parent)


if __name__ == "__main__":
    unittest.main()
