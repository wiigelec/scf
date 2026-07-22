from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scf_governed_executor.core import AUTHORIZATION_FIELDS, operation_digest


ROOT = Path(__file__).resolve().parents[3]
ORIGIN = "https://github.com/wiigelec/scf.git"
EXECUTOR_VERSION = "0.7.0"
HEAD = subprocess.run(
    ["git", "rev-parse", "HEAD"],
    cwd=ROOT,
    text=True,
    capture_output=True,
    check=True,
).stdout.strip()
BRANCH = subprocess.run(
    ["git", "branch", "--show-current"],
    cwd=ROOT,
    text=True,
    capture_output=True,
    check=True,
).stdout.strip()


class IndependentLifecycleContractTests(unittest.TestCase):
    def operation(
        self,
        operation_type: str,
        *,
        authorization: set[str],
        inputs: dict,
        expected_mutations: dict,
        publication: dict,
        clean: bool = True,
    ) -> dict:
        operation = {
            "schema_version": 1,
            "operation_id": f"test.issue-41.{operation_type}",
            "operation_type": operation_type,
            "executor_version": EXECUTOR_VERSION,
            "operation_digest": "",
            "repository": {"root": str(ROOT), "origin": ORIGIN},
            "guards": {
                "branch": "deliberately-wrong-branch",
                "head": HEAD,
                "clean": clean,
            },
            "authorization": {
                field: field in authorization for field in AUTHORIZATION_FIELDS
            },
            "inputs": inputs,
            "expected_mutations": expected_mutations,
            "validation": {},
            "publication": publication,
            "result": {
                "directory": "",
                "filename": "",
            },
        }
        return operation

    def execute(self, operation: dict) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            result_name = (
                operation["operation_id"].replace(".", "-") + ".result.json"
            )
            operation["result"] = {
                "directory": directory,
                "filename": result_name,
            }
            operation["operation_digest"] = operation_digest(operation)
            path = Path(directory) / "operation.json"
            path.write_text(
                json.dumps(operation, sort_keys=True),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [str(ROOT / "scripts/governed-execute"), str(path)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            result_path = Path(directory) / result_name
            completed.result_payload = (
                json.loads(result_path.read_text(encoding="utf-8"))
                if result_path.exists()
                else None
            )
            return completed

    def assert_contract_reaches_guards(self, operation: dict) -> None:
        completed = self.execute(operation)
        self.assertEqual(completed.returncode, 1)
        self.assertIsNotNone(completed.result_payload)
        self.assertEqual(
            completed.result_payload["terminal_status"],
            "guard-failed",
        )
        self.assertFalse(completed.result_payload["mutation"]["attempted"])
        self.assertNotIn("unsupported", completed.stderr.lower())

    def test_git_stage_contract_is_independently_accepted(self) -> None:
        self.assert_contract_reaches_guards(
            self.operation(
                "git-stage",
                authorization={"interrogate", "stage"},
                inputs={"paths": ["README.md"]},
                expected_mutations={"paths": ["README.md"], "head": HEAD},
                publication={},
            )
        )

    def test_git_commit_contract_is_independently_accepted(self) -> None:
        self.assert_contract_reaches_guards(
            self.operation(
                "git-commit",
                authorization={"interrogate", "commit"},
                inputs={"message": "Test governed commit"},
                expected_mutations={
                    "paths": ["README.md"],
                    "parent_head": HEAD,
                },
                publication={},
            )
        )

    def test_git_push_contract_is_independently_accepted(self) -> None:
        self.assert_contract_reaches_guards(
            self.operation(
                "git-push",
                authorization={"interrogate", "push"},
                inputs={},
                expected_mutations={
                    "head": HEAD,
                    "remote": "origin",
                    "branch": BRANCH,
                },
                publication={"remote": "origin", "branch": BRANCH},
            )
        )

    def test_pull_request_contract_is_independently_accepted(self) -> None:
        self.assert_contract_reaches_guards(
            self.operation(
                "pull-request-create",
                authorization={"interrogate", "pull_request"},
                inputs={
                    "base": "main",
                    "head": BRANCH,
                    "title": "Test pull request",
                    "body": "Test body",
                    "draft": True,
                },
                expected_mutations={"head_sha": HEAD},
                publication={},
            )
        )

    def test_stage_rejects_commit_authority(self) -> None:
        operation = self.operation(
            "git-stage",
            authorization={"interrogate", "stage", "commit"},
            inputs={"paths": ["README.md"]},
            expected_mutations={"paths": ["README.md"], "head": HEAD},
            publication={},
        )
        completed = self.execute(operation)
        self.assertEqual(completed.returncode, 1)
        self.assertIsNone(completed.result_payload)
        self.assertIn("broadens authorization", completed.stderr)

    def test_commit_rejects_stage_authority(self) -> None:
        operation = self.operation(
            "git-commit",
            authorization={"interrogate", "stage", "commit"},
            inputs={"message": "Test governed commit"},
            expected_mutations={
                "paths": ["README.md"],
                "parent_head": HEAD,
            },
            publication={},
        )
        completed = self.execute(operation)
        self.assertEqual(completed.returncode, 1)
        self.assertIsNone(completed.result_payload)
        self.assertIn("broadens authorization", completed.stderr)

    def test_push_requires_clean_guard(self) -> None:
        operation = self.operation(
            "git-push",
            authorization={"interrogate", "push"},
            inputs={},
            expected_mutations={
                "head": HEAD,
                "remote": "origin",
                "branch": BRANCH,
            },
            publication={"remote": "origin", "branch": BRANCH},
            clean=False,
        )
        completed = self.execute(operation)
        self.assertEqual(completed.returncode, 1)
        self.assertIsNone(completed.result_payload)
        self.assertIn("requires a clean repository", completed.stderr)


if __name__ == "__main__":
    unittest.main()
