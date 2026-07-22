from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scf_governed_executor import core
from scf_governed_executor import issue_create


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def make_operation(directory: str, issues: list[dict[str, str]]) -> dict:
    operation = {
        "schema_version": 1,
        "operation_id": "issue-create-test-operation",
        "operation_type": "issue-create",
        "executor_version": core.EXECUTOR_VERSION,
        "operation_digest": "",
        "repository": {
            "root": ".",
            "origin": "https://github.com/wiigelec/scf.git",
        },
        "guards": {
            "branch": "issue-57-create-issue-operation",
            "head": "81a1270b93d9d5bc1142631225ddeffb4f49ed1c",
            "clean": True,
        },
        "authorization": {
            "interrogate": True,
            "edit": False,
            "validate": False,
            "stage": False,
            "commit": False,
            "push": False,
            "issue": True,
            "pull_request": False,
            "review": False,
            "merge": False,
            "close_issue": False,
        },
        "inputs": {"issues": issues},
        "expected_mutations": {
            "issues": [
                {
                    "title_sha256": digest_text(item["title"]),
                    "body_sha256": digest_text(item["body"]),
                }
                for item in issues
            ]
        },
        "validation": {},
        "publication": {},
        "result": {
            "directory": directory,
            "filename": "issue-create-test.result.json",
        },
    }
    operation["operation_digest"] = core.operation_digest(operation)
    return operation


class IssueCreateSchemaTests(unittest.TestCase):
    def load(self, operation: dict) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "operation.json"
            path.write_text(json.dumps(operation), encoding="utf-8")
            return issue_create.load_operation(path)

    def test_accepts_single_and_multiple_issues(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            one = make_operation(directory, [{"title": "One", "body": "Body one."}])
            two = make_operation(
                directory,
                [
                    {"title": "One", "body": "Body one."},
                    {"title": "Two", "body": "Body two."},
                ],
            )
            self.assertEqual(len(self.load(one)["inputs"]["issues"]), 1)
            self.assertEqual(len(self.load(two)["inputs"]["issues"]), 2)

    def test_rejects_empty_issue_list(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            operation = make_operation(directory, [])
            with self.assertRaisesRegex(core.SchemaError, "non-empty array"):
                self.load(operation)

    def test_rejects_broadened_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            operation = make_operation(
                directory, [{"title": "One", "body": "Body."}]
            )
            operation["authorization"]["push"] = True
            operation["operation_digest"] = core.operation_digest(operation)
            with self.assertRaisesRegex(core.SchemaError, "broadens authorization"):
                self.load(operation)

    def test_rejects_extra_issue_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            operation = make_operation(
                directory,
                [{"title": "One", "body": "Body.", "labels": ["bug"]}],
            )
            operation["expected_mutations"]["issues"] = [
                {
                    "title_sha256": digest_text("One"),
                    "body_sha256": digest_text("Body."),
                }
            ]
            operation["operation_digest"] = core.operation_digest(operation)
            with self.assertRaisesRegex(core.SchemaError, "unknown fields"):
                self.load(operation)


class FakeSupervisor:
    def __init__(self, responses: list[core.CommandRecord]) -> None:
        self.responses = list(responses)
        self.commands: list[list[str]] = []

    def run(self, command, cwd, **kwargs):
        self.commands.append(list(command))
        return self.responses.pop(0)


def record(stdout: str, exit_code: int = 0) -> core.CommandRecord:
    return core.CommandRecord(
        command=["gh"],
        cwd=".",
        started_at="start",
        finished_at="finish",
        elapsed_seconds=0.0,
        exit_code=exit_code,
        timed_out=False,
        stdout=stdout,
        stderr="",
        redaction_events=[],
        stdin={"supplied": False, "byte_count": 0, "sha256": None, "label": None},
    )


class IssueCreateRemoteTests(unittest.TestCase):
    def test_create_issue_posts_and_verifies(self) -> None:
        created = {
            "number": 58,
            "node_id": "I_node",
            "title": "Title",
            "body": "Body",
            "state": "open",
            "html_url": "https://github.com/wiigelec/scf/issues/58",
        }
        supervisor = FakeSupervisor(
            [record(json.dumps(created)), record(json.dumps(created))]
        )
        commands: list[dict] = []
        result = issue_create._create_issue(
            supervisor,
            Path("."),
            commands,
            "wiigelec/scf",
            "Title",
            "Body",
        )
        self.assertEqual(result["number"], 58)
        self.assertTrue(result["verified"])
        self.assertEqual(
            supervisor.commands[0],
            [
                "gh",
                "api",
                "--method",
                "POST",
                "--input",
                "-",
                "repos/wiigelec/scf/issues",
            ],
        )
        self.assertEqual(
            supervisor.commands[1],
            ["gh", "api", "repos/wiigelec/scf/issues/58"],
        )

    def test_verification_failure_marks_remote_possible(self) -> None:
        created = {"number": 58, "node_id": "I_node"}
        verified = {
            "number": 58,
            "node_id": "I_node",
            "title": "Changed",
            "body": "Body",
            "state": "open",
        }
        supervisor = FakeSupervisor(
            [record(json.dumps(created)), record(json.dumps(verified))]
        )
        with self.assertRaises(issue_create.IssueCreateError) as caught:
            issue_create._create_issue(
                supervisor, Path("."), [], "wiigelec/scf", "Title", "Body"
            )
        self.assertTrue(caught.exception.remote_may_have_mutated)


if __name__ == "__main__":
    unittest.main()
