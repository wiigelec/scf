from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import scf_governed_executor.self_update as self_update_module
from scf_governed_executor.core import AUTHORIZATION_FIELDS, SchemaError
from scf_governed_executor.core import operation_digest


class ExecutorSelfUpdateSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_version = self_update_module.EXECUTOR_VERSION
        self_update_module.EXECUTOR_VERSION = "0.2.1"

    def tearDown(self) -> None:
        self_update_module.EXECUTOR_VERSION = self.original_version

    def operation(self) -> dict:
        content = "replacement"
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        operation = {
            "schema_version": 1,
            "operation_id": "test.executor-self-update.schema",
            "operation_type": "executor-self-update",
            "executor_version": "0.2.1",
            "operation_digest": "",
            "repository": {
                "root": ".",
                "origin": "https://github.com/wiigelec/scf.git",
            },
            "guards": {
                "branch": "issue-40-governed-executor-self-update",
                "head": "209b29c19164dfc59b4917a8f591ca80a42550a4",
                "clean": True,
            },
            "authorization": {
                key: key in {"interrogate", "edit", "validate"}
                for key in AUTHORIZATION_FIELDS
            },
            "inputs": {
                "current_executor_version": "0.2.1",
                "replacement_executor_version": "0.2.2",
                "operations": [
                    {
                        "action": "create",
                        "path": (
                            "tests/governed_executor/"
                            "test_executor_self_update.py"
                        ),
                        "content": content,
                        "content_sha256": digest,
                        "mode": "0644",
                    }
                ],
                "validation_profile": "focused",
            },
            "expected_mutations": {
                "files": [
                    {
                        "action": "create",
                        "path": (
                            "tests/governed_executor/"
                            "test_executor_self_update.py"
                        ),
                        "before_sha256": None,
                        "after_sha256": digest,
                        "mode": "0644",
                    }
                ]
            },
            "validation": {},
            "publication": {},
            "result": {
                "directory": tempfile.gettempdir(),
                "filename": "test.executor-self-update.schema.result.json",
            },
        }
        operation["operation_digest"] = operation_digest(operation)
        return operation

    def load(self, operation: dict) -> dict:
        operation["operation_digest"] = operation_digest(operation)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "operation.json"
            path.write_text(
                json.dumps(operation, sort_keys=True),
                encoding="utf-8",
            )
            return self_update_module.load_self_update_operation(path)

    def test_accepts_closed_inventory_operation(self) -> None:
        loaded = self.load(self.operation())
        self.assertEqual(
            loaded["inputs"]["replacement_executor_version"],
            "0.2.2",
        )

    def test_rejects_path_outside_inventory(self) -> None:
        operation = self.operation()
        operation["inputs"]["operations"][0]["path"] = "README.md"
        operation["expected_mutations"]["files"][0]["path"] = "README.md"
        with self.assertRaisesRegex(
            SchemaError,
            "outside the self-update path inventory",
        ):
            self.load(operation)

    def test_rejects_dirty_starting_tree(self) -> None:
        operation = self.operation()
        operation["guards"]["clean"] = False
        with self.assertRaisesRegex(
            SchemaError,
            "requires a clean starting tree",
        ):
            self.load(operation)

    def test_rejects_equal_replacement_version(self) -> None:
        operation = self.operation()
        operation["inputs"]["replacement_executor_version"] = "0.2.1"
        with self.assertRaisesRegex(
            SchemaError,
            "replacement executor version must differ",
        ):
            self.load(operation)


if __name__ == "__main__":
    unittest.main()
