from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from scf_governed_executor.core import (  # noqa: E402
    EXECUTOR_VERSION,
    CommandSupervisor,
    CommandTimeoutError,
    ResultConflictError,
    SchemaError,
    TerminalProgress,
    load_operation,
    operation_digest,
    redact_text,
    result_destination,
    write_result_exclusive,
)


AUTHORIZATION = {
    "interrogate": True,
    "edit": False,
    "validate": False,
    "stage": False,
    "commit": False,
    "push": False,
    "issue": False,
    "pull_request": False,
    "review": False,
    "merge": False,
    "close_issue": False,
}


def valid_operation(result_directory: str) -> dict:
    operation = {
        "schema_version": 1,
        "operation_id": "issue-31-test-operation",
        "operation_type": "repository-interrogation",
        "executor_version": EXECUTOR_VERSION,
        "operation_digest": "0" * 64,
        "repository": {
            "root": "/tmp/example-repository",
            "origin": "https://github.com/wiigelec/scf.git",
        },
        "guards": {
            "branch": "issue-31-governed-executor",
            "head": "e778d45d89d26927dfd85990a11e15daf13130f1",
            "clean": True,
        },
        "authorization": dict(AUTHORIZATION),
        "inputs": {},
        "expected_mutations": {},
        "validation": {},
        "publication": {},
        "result": {
            "directory": result_directory,
            "filename": "issue-31-test-operation.result.json",
        },
    }
    operation["operation_digest"] = operation_digest(operation)
    return operation


class OperationSchemaTests(unittest.TestCase):
    def write_operation(self, directory: Path, operation: dict) -> Path:
        path = directory / "operation.json"
        path.write_text(json.dumps(operation), encoding="utf-8")
        return path

    def test_valid_operation_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            loaded = load_operation(
                self.write_operation(directory, valid_operation(tmp))
            )
            self.assertEqual(loaded["operation_type"], "repository-interrogation")

    def test_unknown_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            operation = valid_operation(tmp)
            operation["surprise"] = True
            operation["operation_digest"] = operation_digest(operation)
            with self.assertRaisesRegex(SchemaError, "unknown fields"):
                load_operation(self.write_operation(directory, operation))

    def test_digest_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            operation = valid_operation(tmp)
            operation["guards"]["clean"] = False
            with self.assertRaisesRegex(SchemaError, "digest mismatch"):
                load_operation(self.write_operation(directory, operation))

    def test_authorization_expansion_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            operation = valid_operation(tmp)
            operation["authorization"]["edit"] = True
            operation["operation_digest"] = operation_digest(operation)
            with self.assertRaisesRegex(SchemaError, "broadens authorization"):
                load_operation(self.write_operation(directory, operation))

    def test_non_standard_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "operation.json"
            path.write_text('{"schema_version": NaN}', encoding="utf-8")
            with self.assertRaisesRegex(SchemaError, "non-standard JSON"):
                load_operation(path)


class RedactionTests(unittest.TestCase):
    def test_known_token_is_redacted(self) -> None:
        token = "ghp_" + "A" * 40
        redacted, events = redact_text(f"value={token}")
        self.assertNotIn(token, redacted)
        self.assertTrue(events)

    def test_environment_secret_is_redacted(self) -> None:
        secret = "top-secret-value"
        redacted, events = redact_text(
            f"message {secret}", {"SERVICE_TOKEN": secret}
        )
        self.assertNotIn(secret, redacted)
        self.assertEqual(events[0]["category"], "environment-secret")

    def test_credential_url_is_redacted(self) -> None:
        value = "https://person:password@example.test/path"
        redacted, events = redact_text(value)
        self.assertEqual(redacted, "https://example.test/path")
        self.assertEqual(events[0]["category"], "credential-url")


class ResultBoundaryTests(unittest.TestCase):
    def test_result_must_be_outside_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            operation = valid_operation(str(root))
            with self.assertRaisesRegex(ResultConflictError, "outside repository"):
                result_destination(operation, root)

    def test_result_write_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            write_result_exclusive(path, {"status": "first"})
            with self.assertRaises(ResultConflictError):
                write_result_exclusive(path, {"status": "second"})
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8"))["status"], "first"
            )


class SupervisionTests(unittest.TestCase):
    def test_command_is_not_run_through_shell(self) -> None:
        supervisor = CommandSupervisor(heartbeat_seconds=0.01, environment={})
        with tempfile.TemporaryDirectory() as tmp:
            record = supervisor.run(
                [sys.executable, "-c", "print('ok')"],
                Path(tmp),
                timeout_seconds=2,
            )
        self.assertEqual(record.exit_code, 0)
        self.assertEqual(record.stdout.strip(), "ok")

    def test_timeout_is_reported(self) -> None:
        supervisor = CommandSupervisor(heartbeat_seconds=0.01, environment={})
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(CommandTimeoutError):
                supervisor.run(
                    [sys.executable, "-c", "import time; time.sleep(1)"],
                    Path(tmp),
                    timeout_seconds=0.05,
                )

    def test_heartbeat_is_emitted(self) -> None:
        messages: list[str] = []
        supervisor = CommandSupervisor(
            heartbeat_seconds=0.01, output=messages.append, environment={}
        )
        with tempfile.TemporaryDirectory() as tmp:
            supervisor.run(
                [sys.executable, "-c", "import time; time.sleep(.06)"],
                Path(tmp),
                timeout_seconds=2,
                phase="test",
            )
        self.assertTrue(any("heartbeat: test" in message for message in messages))


class TerminalProgressTests(unittest.TestCase):
    def test_numbered_phase_and_heartbeat_rendering(self) -> None:
        progress = TerminalProgress(total=5)
        with patch("builtins.print") as output:
            progress.phase(4, "verifying remote state")
            progress.check("remote revision matches")
        rendered = [" ".join(str(part) for part in call.args) for call in output.call_args_list]
        self.assertIn("Phase [4/5]: verifying remote state...", rendered)
        self.assertIn("  ✓ remote revision matches", rendered)
        self.assertEqual(
            progress.heartbeat_phase("verifying remote state"),
            "phase=[4/5] verifying remote state",
        )


class SchemaArtifactTests(unittest.TestCase):
    def test_schema_files_are_strict_and_versioned(self) -> None:
        for name in (
            "governed-operation-v1.schema.json",
            "governed-result-v1.schema.json",
        ):
            data = json.loads((ROOT / "src" / "scf_governed_executor" / "schemas" / name).read_text(encoding="utf-8"))
            self.assertFalse(data["additionalProperties"])
            self.assertEqual(data["properties"]["schema_version"]["const"], 1)


if __name__ == "__main__":
    unittest.main()
