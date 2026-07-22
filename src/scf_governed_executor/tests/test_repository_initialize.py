from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scf_governed_executor.core import AUTHORIZATION_FIELDS, operation_digest


EXECUTOR = Path(__file__).resolve().parents[3] / "scripts/governed-execute"
EXECUTOR_VERSION = "0.7.0"


def run(command: list[str], cwd: Path) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


class RepositoryInitializeTests(unittest.TestCase):
    def fixture(self) -> tuple[tempfile.TemporaryDirectory, Path, Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        remote = root / "remote.git"
        seed = root / "seed"
        work = root / "work"

        run(["git", "init", "--bare", str(remote)], root)
        run(["git", "init", "-b", "main", str(seed)], root)
        run(["git", "config", "user.name", "SCF Test"], seed)
        run(["git", "config", "user.email", "scf-test@example.invalid"], seed)
        (seed / "tracked.txt").write_text("base\n", encoding="utf-8")
        run(["git", "add", "tracked.txt"], seed)
        run(["git", "commit", "-m", "base"], seed)
        run(["git", "remote", "add", "origin", str(remote)], seed)
        run(["git", "push", "-u", "origin", "main"], seed)

        run(["git", "clone", str(remote), str(work)], root)
        run(["git", "config", "user.name", "SCF Test"], work)
        run(["git", "config", "user.email", "scf-test@example.invalid"], work)
        return temporary, remote, seed, work

    def operation(self, work: Path, remote: Path, result_dir: Path) -> dict:
        operation = {
            "schema_version": 1,
            "operation_id": "test.issue-48.repository-initialize",
            "operation_type": "repository-initialize",
            "executor_version": EXECUTOR_VERSION,
            "operation_digest": "",
            "repository": {
                "root": str(work),
                "origin": str(remote),
            },
            "guards": {"clean": True},
            "authorization": {
                field: field in {"interrogate", "edit"}
                for field in AUTHORIZATION_FIELDS
            },
            "inputs": {"remote": "origin", "branch": "main"},
            "expected_mutations": {
                "remote": "origin",
                "branch": "main",
                "strategy": "fetch-switch-fast-forward-only",
            },
            "validation": {},
            "publication": {},
            "result": {
                "directory": str(result_dir),
                "filename": "repository-initialize.result.json",
            },
        }
        operation["operation_digest"] = operation_digest(operation)
        return operation

    def execute(self, operation: dict, directory: Path) -> tuple[subprocess.CompletedProcess[str], dict]:
        operation_path = directory / "operation.json"
        operation_path.write_text(
            json.dumps(operation, sort_keys=True),
            encoding="utf-8",
        )
        completed = subprocess.run(
            [str(EXECUTOR), str(operation_path)],
            cwd=EXECUTOR.parents[1],
            text=True,
            capture_output=True,
            check=False,
        )
        result_path = Path(operation["result"]["directory"]) / operation["result"]["filename"]
        result = json.loads(result_path.read_text(encoding="utf-8"))
        return completed, result

    def test_switches_clean_topic_branch_and_fast_forwards_main(self) -> None:
        temporary, remote, seed, work = self.fixture()
        self.addCleanup(temporary.cleanup)
        original_main = run(["git", "rev-parse", "main"], work)
        run(["git", "switch", "-c", "topic"], work)
        topic_head = run(["git", "rev-parse", "HEAD"], work)

        (seed / "tracked.txt").write_text("remote update\n", encoding="utf-8")
        run(["git", "commit", "-am", "remote update"], seed)
        run(["git", "push", "origin", "main"], seed)
        remote_main = run(["git", "rev-parse", "main"], seed)
        self.assertNotEqual(original_main, remote_main)

        operation = self.operation(work, remote, Path(temporary.name))
        completed, result = self.execute(operation, Path(temporary.name))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(result["terminal_status"], "local-mutation-completed")
        self.assertEqual(run(["git", "branch", "--show-current"], work), "main")
        self.assertEqual(run(["git", "rev-parse", "HEAD"], work), remote_main)
        self.assertEqual(run(["git", "rev-parse", "topic"], work), topic_head)
        self.assertEqual(run(["git", "status", "--porcelain"], work), "")

    def test_current_main_is_a_verified_no_op(self) -> None:
        temporary, remote, _seed, work = self.fixture()
        self.addCleanup(temporary.cleanup)
        before = run(["git", "rev-parse", "HEAD"], work)

        operation = self.operation(work, remote, Path(temporary.name))
        completed, result = self.execute(operation, Path(temporary.name))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(result["terminal_status"], "local-mutation-completed")
        self.assertEqual(run(["git", "rev-parse", "HEAD"], work), before)
        self.assertEqual(run(["git", "branch", "--show-current"], work), "main")
        self.assertEqual(run(["git", "status", "--porcelain"], work), "")

    def test_dirty_checkout_is_refused_without_switching(self) -> None:
        temporary, remote, _seed, work = self.fixture()
        self.addCleanup(temporary.cleanup)
        run(["git", "switch", "-c", "topic"], work)
        before = run(["git", "rev-parse", "HEAD"], work)
        (work / "untracked.txt").write_text("local work\n", encoding="utf-8")

        operation = self.operation(work, remote, Path(temporary.name))
        completed, result = self.execute(operation, Path(temporary.name))

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(result["terminal_status"], "guard-failed")
        self.assertIn("not clean", "\n".join(result["diagnostics"]))
        self.assertEqual(run(["git", "branch", "--show-current"], work), "topic")
        self.assertEqual(run(["git", "rev-parse", "HEAD"], work), before)
        self.assertTrue((work / "untracked.txt").exists())


if __name__ == "__main__":
    unittest.main()
