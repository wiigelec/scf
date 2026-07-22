from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from scf_governed_executor.core import (  # noqa: E402
    EXECUTOR_VERSION,
    SchemaError,
    load_operation,
    operation_digest,
)
from scf_governed_executor.local_files import (  # noqa: E402
    LocalFileOperationError,
    apply_local_file_operations,
    validate_local_file_inputs,
)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def operation_item(
    action: str,
    path: str,
    content: str,
    *,
    before: str | None = None,
    mode: str = "0644",
) -> dict:
    item = {
        "action": action,
        "path": path,
        "content": content,
        "content_sha256": digest(content),
        "mode": mode,
    }
    if action == "replace":
        item["expected_sha256"] = before
    return item


def expected(item: dict) -> dict:
    return {
        "action": item["action"],
        "path": item["path"],
        "before_sha256": item.get("expected_sha256"),
        "after_sha256": item["content_sha256"],
        "mode": item["mode"],
    }


class ValidationTests(unittest.TestCase):
    def test_duplicate_paths_are_rejected(self) -> None:
        item = operation_item("create", "one.txt", "one")
        with self.assertRaisesRegex(LocalFileOperationError, "duplicate"):
            validate_local_file_inputs(
                {"operations": [item, dict(item)]},
                {"files": [expected(item), expected(item)]},
            )

    def test_path_escape_is_rejected(self) -> None:
        item = operation_item("create", "../escape.txt", "bad")
        with self.assertRaisesRegex(LocalFileOperationError, "normalized"):
            validate_local_file_inputs(
                {"operations": [item]}, {"files": [expected(item)]}
            )

    def test_expected_mutations_must_match(self) -> None:
        item = operation_item("create", "one.txt", "one")
        with self.assertRaisesRegex(LocalFileOperationError, "exactly match"):
            validate_local_file_inputs(
                {"operations": [item]}, {"files": []}
            )


class ApplicationTests(unittest.TestCase):
    def test_create_and_read_after_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = operation_item("create", "nested/one.txt", "one")
            records = apply_local_file_operations(root, [item])
            self.assertEqual((root / "nested/one.txt").read_text(), "one")
            self.assertTrue(records[0]["verified"])

    def test_create_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "one.txt").write_text("existing")
            item = operation_item("create", "one.txt", "replacement")
            with self.assertRaisesRegex(
                LocalFileOperationError, "refuses existing"
            ):
                apply_local_file_operations(root, [item])
            self.assertEqual((root / "one.txt").read_text(), "existing")

    def test_replace_requires_expected_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "one.txt"
            target.write_text("before")
            item = operation_item(
                "replace", "one.txt", "after", before="0" * 64
            )
            with self.assertRaisesRegex(
                LocalFileOperationError, "precondition failed"
            ):
                apply_local_file_operations(root, [item])
            self.assertEqual(target.read_text(), "before")

    def test_replace_succeeds_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "one.txt"
            target.write_text("before")
            item = operation_item(
                "replace", "one.txt", "after", before=digest("before")
            )
            records = apply_local_file_operations(root, [item])
            self.assertEqual(target.read_text(), "after")
            self.assertEqual(records[0]["before_sha256"], digest("before"))
            self.assertTrue(records[0]["verified"])

    def test_partial_mutation_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = operation_item("create", "one.txt", "one")
            second = operation_item("create", "one.txt", "two")
            with self.assertRaises(LocalFileOperationError) as context:
                apply_local_file_operations(root, [first, second])
            self.assertTrue(context.exception.mutation_observed)
            self.assertEqual(len(context.exception.records), 1)
            self.assertEqual((root / "one.txt").read_text(), "one")


class OperationSchemaTests(unittest.TestCase):
    def test_local_file_payload_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            item = operation_item("create", "one.txt", "one")
            payload = {
                "schema_version": 1,
                "operation_id": "issue-31-local-files-test",
                "operation_type": "local-file-operations",
                "executor_version": EXECUTOR_VERSION,
                "operation_digest": "0" * 64,
                "repository": {
                    "root": "/tmp/repository",
                    "origin": "https://github.com/wiigelec/scf.git",
                },
                "guards": {
                    "branch": "issue-31-governed-executor",
                    "head": "e778d45d89d26927dfd85990a11e15daf13130f1",
                    "clean": False,
                },
                "authorization": {
                    "interrogate": True,
                    "edit": True,
                    "validate": False,
                    "stage": False,
                    "commit": False,
                    "push": False,
                    "issue": False,
                    "pull_request": False,
                    "review": False,
                    "merge": False,
                    "close_issue": False,
                },
                "inputs": {"operations": [item]},
                "expected_mutations": {"files": [expected(item)]},
                "validation": {},
                "publication": {},
                "result": {
                    "directory": tmp,
                    "filename": "issue-31-local-files-test.result.json",
                },
            }
            payload["operation_digest"] = operation_digest(payload)
            path = Path(tmp) / "operation.json"
            path.write_text(json.dumps(payload))
            loaded = load_operation(path)
            self.assertEqual(loaded["operation_type"], "local-file-operations")

    def test_local_file_payload_rejects_commit_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            item = operation_item("create", "one.txt", "one")
            payload = {
                "schema_version": 1,
                "operation_id": "issue-31-local-files-test",
                "operation_type": "local-file-operations",
                "executor_version": EXECUTOR_VERSION,
                "operation_digest": "0" * 64,
                "repository": {"root": "/tmp/repository", "origin": "origin"},
                "guards": {
                    "branch": "branch",
                    "head": "0" * 40,
                    "clean": True,
                },
                "authorization": {
                    "interrogate": True,
                    "edit": True,
                    "validate": False,
                    "stage": False,
                    "commit": True,
                    "push": False,
                    "issue": False,
                    "pull_request": False,
                    "review": False,
                    "merge": False,
                    "close_issue": False,
                },
                "inputs": {"operations": [item]},
                "expected_mutations": {"files": [expected(item)]},
                "validation": {},
                "publication": {},
                "result": {
                    "directory": tmp,
                    "filename": "issue-31-local-files-test.result.json",
                },
            }
            payload["operation_digest"] = operation_digest(payload)
            path = Path(tmp) / "operation.json"
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(SchemaError, "broadens authorization"):
                load_operation(path)


if __name__ == "__main__":
    unittest.main()
