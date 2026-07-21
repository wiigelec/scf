from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scf_governed_executor.branch_create import (
    execute_branch_create,
    validate_branch_create_contract,
)
from scf_governed_executor.core import (
    AUTHORIZATION_FIELDS,
    TerminalProgress,
    operation_digest,
)


ORIGIN = "https://example.invalid/scf.git"


def git(root: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=check,
    )
    return completed.stdout.strip()


class GovernedBranchCreateTests(unittest.TestCase):
    def repository(self, parent: Path) -> tuple[Path, str]:
        root = parent / "repo"
        root.mkdir()
        git(root, "init", "-b", "main")
        git(root, "config", "user.name", "SCF Test")
        git(root, "config", "user.email", "scf-test@example.invalid")
        git(root, "remote", "add", "origin", ORIGIN)
        (root / "README.md").write_text("test\n", encoding="utf-8")
        git(root, "add", "README.md")
        git(root, "commit", "-m", "Initial")
        return root, git(root, "rev-parse", "HEAD")

    def operation(
        self,
        root: Path,
        head: str,
        results: Path,
        *,
        target: str = "issue-39-test-branch",
    ) -> dict:
        operation = {
            "schema_version": 1,
            "operation_id": "test.issue-39.git-branch-create",
            "operation_type": "git-branch-create",
            "executor_version": "0.4.0",
            "operation_digest": "",
            "repository": {"root": str(root), "origin": ORIGIN},
            "guards": {"branch": "main", "head": head, "clean": True},
            "authorization": {
                field: field in {"interrogate", "edit"}
                for field in AUTHORIZATION_FIELDS
            },
            "inputs": {"base": head, "branch": target},
            "expected_mutations": {"base": head, "branch": target},
            "validation": {},
            "publication": {},
            "result": {
                "directory": str(results),
                "filename": "issue-39-branch-create.result.json",
            },
        }
        operation["operation_digest"] = operation_digest(operation)
        return operation

    def test_contract_accepts_exact_branch_creation_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root, head = self.repository(parent)
            results = parent / "results"
            results.mkdir()
            operation = self.operation(root, head, results)

            validated = validate_branch_create_contract(operation)

            self.assertEqual(validated["inputs"]["base"], head)
            self.assertEqual(
                validated["inputs"]["branch"],
                "issue-39-test-branch",
            )

    def test_creates_and_enters_exact_local_branch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root, head = self.repository(parent)
            results = parent / "results"
            results.mkdir()
            operation = self.operation(root, head, results)

            result, result_path = execute_branch_create(
                validate_branch_create_contract(operation),
                TerminalProgress(),
            )

            self.assertEqual(
                result["terminal_status"], "local-mutation-completed"
            )
            self.assertTrue(result["mutation"]["completed"])
            self.assertEqual(
                git(root, "branch", "--show-current"),
                "issue-39-test-branch",
            )
            self.assertEqual(git(root, "rev-parse", "HEAD"), head)
            self.assertEqual(git(root, "status", "--porcelain=v1"), "")
            self.assertTrue(result_path.is_file())
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(
                payload["publication"]["branch"],
                "issue-39-test-branch",
            )
            self.assertTrue(payload["publication"]["local_only"])

    def test_refuses_existing_target_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root, head = self.repository(parent)
            git(root, "branch", "issue-39-test-branch", head)
            results = parent / "results"
            results.mkdir()
            operation = self.operation(root, head, results)

            result, _ = execute_branch_create(
                validate_branch_create_contract(operation),
                TerminalProgress(),
            )

            self.assertEqual(result["terminal_status"], "guard-failed")
            self.assertFalse(result["mutation"]["attempted"])
            self.assertEqual(git(root, "branch", "--show-current"), "main")
            self.assertEqual(git(root, "rev-parse", "HEAD"), head)

    def test_rejects_broader_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root, head = self.repository(parent)
            results = parent / "results"
            results.mkdir()
            operation = self.operation(root, head, results)
            operation["authorization"]["commit"] = True
            operation["operation_digest"] = operation_digest(operation)

            with self.assertRaisesRegex(
                Exception, "broadens authorization"
            ):
                validate_branch_create_contract(operation)


if __name__ == "__main__":
    unittest.main()
