from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scf_governed_executor import EXECUTOR_VERSION
from scf_governed_executor.core import AUTHORIZATION_FIELDS, SchemaError
from scf_governed_executor.issue_comments import (
    ISSUE_COMMENT_OPERATION_TYPE,
    load_issue_comment_operation,
    validate_issue_comment_contract,
)


def operation(action: str = "create") -> dict:
    inputs = {
        "action": action,
        "issue": 37,
        "body": "## Governed detailed scope\n\nBody\n",
        "required_heading": "## Governed detailed scope",
        "expected_issue_state": "open",
    }
    expected = {
        "action": action,
        "issue": 37,
        "body_sha256": (
            "f8571be93f4541c19a3b7e83fca14c3ab6cbb09b0aeb109505f5db1d1df8fe7d"
        ),
    }
    if action == "update":
        inputs["comment_id"] = 123
        inputs["expected_body_sha256"] = "0" * 64
        expected["comment_id"] = 123
    return {
        "operation_type": ISSUE_COMMENT_OPERATION_TYPE,
        "repository": {
            "root": ".",
            "origin": "https://github.com/wiigelec/scf.git",
        },
        "guards": {
            "branch": "issue-37-governed-issue-comments",
            "head": "0" * 40,
            "clean": True,
        },
        "authorization": {
            field: field in {"interrogate", "issue"}
            for field in AUTHORIZATION_FIELDS
        },
        "inputs": inputs,
        "expected_mutations": expected,
        "validation": {},
        "publication": {},
    }


class IssueCommentContractTests(unittest.TestCase):
    def test_accepts_closed_create_contract(self) -> None:
        value = operation()
        value["expected_mutations"]["body_sha256"] = hashlib.sha256(
            value["inputs"]["body"].encode()
        ).hexdigest()
        validated = validate_issue_comment_contract(value)
        self.assertEqual(validated["inputs"]["issue"], 37)

    def test_accepts_explicit_update_identifier(self) -> None:
        value = operation("update")
        value["expected_mutations"]["body_sha256"] = hashlib.sha256(
            value["inputs"]["body"].encode()
        ).hexdigest()
        validated = validate_issue_comment_contract(value)
        self.assertEqual(validated["inputs"]["comment_id"], 123)

    def test_rejects_broadened_authorization(self) -> None:
        value = operation()
        value["authorization"]["edit"] = True
        with self.assertRaisesRegex(SchemaError, "broadens authorization"):
            validate_issue_comment_contract(value)

    def test_rejects_unknown_input_field(self) -> None:
        value = operation()
        value["inputs"]["command"] = "gh issue comment"
        with self.assertRaisesRegex(SchemaError, "unknown fields"):
            validate_issue_comment_contract(value)

    def test_requires_heading_to_match_body_prefix(self) -> None:
        value = operation()
        value["inputs"]["required_heading"] = "## Other heading"
        with self.assertRaisesRegex(SchemaError, "must begin"):
            validate_issue_comment_contract(value)

    def test_update_requires_positive_comment_identifier(self) -> None:
        value = operation("update")
        value["inputs"]["comment_id"] = 0
        value["expected_mutations"]["comment_id"] = 0
        with self.assertRaisesRegex(SchemaError, "positive integer"):
            validate_issue_comment_contract(value)


    def test_complete_operation_loader_accepts_exact_contract(self) -> None:
        value = operation()
        value.update(
            {
                "schema_version": 1,
                "operation_id": "test.issue-37.issue-comment",
                "executor_version": EXECUTOR_VERSION,
                "operation_digest": "",
                "result": {
                    "directory": tempfile.gettempdir(),
                    "filename": "test.issue-37.issue-comment.result.json",
                },
            }
        )
        value["expected_mutations"]["body_sha256"] = hashlib.sha256(
            value["inputs"]["body"].encode()
        ).hexdigest()
        body = dict(value)
        body.pop("operation_digest")
        value["operation_digest"] = hashlib.sha256(
            json.dumps(
                body,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "operation.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            loaded = load_issue_comment_operation(path)
        self.assertEqual(loaded["operation_type"], ISSUE_COMMENT_OPERATION_TYPE)

    def test_issue_comment_transport_uses_supervised_stdin(self) -> None:
        source = (
            Path(__file__).resolve().parents[3]
            / "src/scf_governed_executor/issue_comments.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"--input",\n                "-",', source)
        self.assertIn("stdin_bytes=payload", source)
        self.assertIn('stdin_label="github-issue-comment-json"', source)
        self.assertNotIn("NamedTemporaryFile", source)
        self.assertNotIn("payload_path", source)


if __name__ == "__main__":
    unittest.main()
