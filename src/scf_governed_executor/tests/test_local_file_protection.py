from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scf_governed_executor.core import AUTHORIZATION_FIELDS, operation_digest


ROOT = Path(__file__).resolve().parents[3]
BRANCH = "issue-40-governed-executor-self-update"
HEAD = "209b29c19164dfc59b4917a8f591ca80a42550a4"
ORIGIN = "https://github.com/wiigelec/scf.git"


class LocalFileProtectionTests(unittest.TestCase):
    def test_generic_file_operation_rejects_executor_path(self) -> None:
        protected = ROOT / "src/scf_governed_executor/core.py"
        before = hashlib.sha256(protected.read_bytes()).hexdigest()
        replacement = "forbidden replacement\n"
        replacement_digest = hashlib.sha256(
            replacement.encode("utf-8")
        ).hexdigest()

        with tempfile.TemporaryDirectory() as directory:
            result_name = "test.local-file-protected-path.result.json"
            operation = {
                "schema_version": 1,
                "operation_id": "test.local-file-protected-path",
                "operation_type": "local-file-operations",
                "executor_version": "0.7.0",
                "operation_digest": "",
                "repository": {"root": str(ROOT), "origin": ORIGIN},
                "guards": {
                    "branch": BRANCH,
                    "head": HEAD,
                    "clean": False,
                },
                "authorization": {
                    key: key in {"interrogate", "edit"}
                    for key in AUTHORIZATION_FIELDS
                },
                "inputs": {
                    "operations": [
                        {
                            "action": "replace",
                            "path": "src/scf_governed_executor/core.py",
                            "content": replacement,
                            "content_sha256": replacement_digest,
                            "mode": "0644",
                            "expected_sha256": before,
                        }
                    ]
                },
                "expected_mutations": {
                    "files": [
                        {
                            "action": "replace",
                            "path": "src/scf_governed_executor/core.py",
                            "before_sha256": before,
                            "after_sha256": replacement_digest,
                            "mode": "0644",
                        }
                    ]
                },
                "validation": {},
                "publication": {},
                "result": {
                    "directory": directory,
                    "filename": result_name,
                },
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

        self.assertEqual(completed.returncode, 1)
        self.assertIn(
            "local-file-operations cannot modify protected executor paths",
            completed.stderr,
        )
        self.assertEqual(
            hashlib.sha256(protected.read_bytes()).hexdigest(),
            before,
        )


if __name__ == "__main__":
    unittest.main()
