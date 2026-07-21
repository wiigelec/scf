from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scf_governed_executor import core
from scf_governed_executor import combined_publication
from scf_governed_executor import session_initialize


EXECUTOR_VERSION = "0.8.2"
HEAD = "1" * 40
AUTHORIZATION_FIELDS = sorted(core.AUTHORIZATION_FIELDS)


def digest(operation: dict[str, object]) -> str:
    candidate = copy.deepcopy(operation)
    candidate["operation_digest"] = ""
    return core.operation_digest(candidate)


def authorization(*enabled: str) -> dict[str, bool]:
    return {name: name in enabled for name in AUTHORIZATION_FIELDS}


def write_operation(operation: dict[str, object]) -> Path:
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".json", delete=False
    )
    with handle:
        json.dump(operation, handle)
    return Path(handle.name)


class SessionInitializationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_version = core.EXECUTOR_VERSION
        core.EXECUTOR_VERSION = EXECUTOR_VERSION

    def tearDown(self) -> None:
        core.EXECUTOR_VERSION = self.original_version

    def operation(self) -> dict[str, object]:
        detailed = "## Governed detailed scope\n\nBounded implementation."
        patch = (
            "## Governed work breakdown and patch plan\n\n"
            "1. Implement.\n2. Validate."
        )
        value: dict[str, object] = {
            "schema_version": core.OPERATION_SCHEMA_VERSION,
            "operation_id": "test.session-initialize",
            "operation_type": "development-session-initialize",
            "executor_version": EXECUTOR_VERSION,
            "operation_digest": "",
            "repository": {
                "root": ".",
                "origin": "https://github.com/wiigelec/scf",
            },
            "guards": {"clean": True},
            "authorization": authorization("interrogate", "edit", "issue"),
            "inputs": {
                "issue": 47,
                "branch": "issue-47-combined-initialization",
                "detailed_scope_body": detailed,
                "patch_plan_body": patch,
            },
            "expected_mutations": {
                "issue": 47,
                "branch": "issue-47-combined-initialization",
                "detailed_scope_body_sha256": hashlib.sha256(
                    detailed.encode("utf-8")
                ).hexdigest(),
                "patch_plan_body_sha256": hashlib.sha256(
                    patch.encode("utf-8")
                ).hexdigest(),
            },
            "validation": {},
            "publication": {},
            "result": {
                "directory": "~/Downloads",
                "filename": "test.session-initialize.result.json",
            },
        }
        value["operation_digest"] = digest(value)
        return value

    def load(self, operation: dict[str, object]) -> dict[str, object]:
        path = write_operation(operation)
        self.addCleanup(path.unlink)
        return session_initialize.load_operation(path)

    def test_accepts_exact_combined_initialization_contract(self) -> None:
        loaded = self.load(self.operation())
        self.assertEqual(
            loaded["operation_type"], "development-session-initialize"
        )

    def test_rejects_wrong_designated_scope_heading(self) -> None:
        operation = self.operation()
        operation["inputs"]["detailed_scope_body"] = "## Scope\n\nWrong heading."
        operation["expected_mutations"]["detailed_scope_body_sha256"] = (
            hashlib.sha256(
                operation["inputs"]["detailed_scope_body"].encode("utf-8")
            ).hexdigest()
        )
        operation["operation_digest"] = digest(operation)
        with self.assertRaisesRegex(core.SchemaError, "designated heading"):
            self.load(operation)

    def test_rejects_authorization_broader_than_combined_initialization(self) -> None:
        operation = self.operation()
        operation["authorization"]["push"] = True
        operation["operation_digest"] = digest(operation)
        with self.assertRaisesRegex(core.SchemaError, "broadens authorization"):
            self.load(operation)


class SessionInitializationCommandTests(unittest.TestCase):
    class Supervisor:
        def __init__(self, exit_code: int) -> None:
            self.exit_code = exit_code
            self.calls: list[dict[str, object]] = []

        def run(
            self,
            command,
            cwd,
            *,
            timeout_seconds=300.0,
            phase="command",
            stdin_text=None,
            stdin_bytes=None,
            stdin_label=None,
        ):
            self.calls.append(
                {
                    "command": list(command),
                    "cwd": cwd,
                    "timeout_seconds": timeout_seconds,
                    "phase": phase,
                    "stdin_text": stdin_text,
                    "stdin_bytes": stdin_bytes,
                    "stdin_label": stdin_label,
                }
            )
            return SimpleNamespace(
                command=list(command),
                cwd=str(cwd),
                started_at="2026-07-21T00:00:00+00:00",
                finished_at="2026-07-21T00:00:01+00:00",
                elapsed_seconds=1.0,
                exit_code=self.exit_code,
                timed_out=False,
                stdout="",
                stderr="rejected" if self.exit_code else "",
                redaction_events=[],
                stdin={
                    "supplied": False,
                    "byte_count": 0,
                    "sha256": None,
                    "label": None,
                },
            )

    def test_run_accepts_explicit_nonzero_exit_code(self) -> None:
        supervisor = self.Supervisor(1)
        commands: list[dict[str, object]] = []
        record = session_initialize._run(
            supervisor,
            Path("."),
            commands,
            ["git", "show-ref", "--verify", "--quiet", "refs/heads/missing"],
            phase="check absent branch",
            allowed_exit_codes={0, 1},
        )
        self.assertEqual(record.exit_code, 1)
        self.assertEqual(commands[0]["exit_code"], 1)
        self.assertNotIn("allowed_exit_codes", supervisor.calls[0])

    def test_run_rejects_exit_code_outside_explicit_set(self) -> None:
        supervisor = self.Supervisor(2)
        commands: list[dict[str, object]] = []
        with self.assertRaisesRegex(
            session_initialize.SessionInitializationError, "rejected"
        ):
            session_initialize._run(
                supervisor,
                Path("."),
                commands,
                ["git", "show-ref", "--verify", "--quiet", "refs/heads/missing"],
                phase="check absent branch",
                allowed_exit_codes={0, 1},
            )
        self.assertEqual(commands[0]["exit_code"], 2)


class CombinedPublicationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_version = core.EXECUTOR_VERSION
        core.EXECUTOR_VERSION = EXECUTOR_VERSION

    def tearDown(self) -> None:
        core.EXECUTOR_VERSION = self.original_version

    def operation(self) -> dict[str, object]:
        paths = ["docs/example.md"]
        value: dict[str, object] = {
            "schema_version": core.OPERATION_SCHEMA_VERSION,
            "operation_id": "test.combined-publication",
            "operation_type": "git-publication",
            "executor_version": EXECUTOR_VERSION,
            "operation_digest": "",
            "repository": {
                "root": ".",
                "origin": "https://github.com/wiigelec/scf",
            },
            "guards": {
                "branch": "issue-47-combined-initialization",
                "head": HEAD,
                "clean": False,
            },
            "authorization": authorization(
                "interrogate", "stage", "commit", "push", "pull_request"
            ),
            "inputs": {
                "paths": paths,
                "message": "Test combined publication",
            },
            "expected_mutations": {
                "paths": paths,
                "parent_head": HEAD,
            },
            "validation": {
                "result_path": "/tmp/validation.result.json",
                "result_sha256": "2" * 64,
                "required_terminal_status": "validation-completed",
                "required_branch": "issue-47-combined-initialization",
                "required_head": HEAD,
            },
            "publication": {
                "push": True,
                "remote": "origin",
                "branch": "issue-47-combined-initialization",
                "pull_request": {
                    "base": "main",
                    "head": "issue-47-combined-initialization",
                    "title": "Test combined publication",
                    "body": "Test body.",
                    "draft": True,
                },
            },
            "result": {
                "directory": "~/Downloads",
                "filename": "test.combined-publication.result.json",
            },
        }
        value["operation_digest"] = digest(value)
        return value

    def load(self, operation: dict[str, object]) -> dict[str, object]:
        path = write_operation(operation)
        self.addCleanup(path.unlink)
        return combined_publication.load_operation(path)

    def test_accepts_exact_combined_publication_contract(self) -> None:
        loaded = self.load(self.operation())
        self.assertEqual(loaded["operation_type"], "git-publication")

    def test_rejects_clean_guard_for_reviewed_changes(self) -> None:
        operation = self.operation()
        operation["guards"]["clean"] = True
        operation["operation_digest"] = digest(operation)
        with self.assertRaisesRegex(core.SchemaError, "guards.clean=false"):
            self.load(operation)

    def test_rejects_validation_for_different_head(self) -> None:
        operation = self.operation()
        operation["validation"]["required_head"] = "3" * 40
        operation["operation_digest"] = digest(operation)
        with self.assertRaisesRegex(core.SchemaError, "required_head"):
            self.load(operation)


if __name__ == "__main__":
    unittest.main()
