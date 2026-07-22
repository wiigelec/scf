from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from scf_governed_executor import core
from scf_governed_executor import issue_comments
from scf_governed_executor import local_files
from scf_governed_executor import session_initialize
from scf_governed_executor import strict_validation


AUTHORIZATION_FIELDS = {
    "interrogate",
    "edit",
    "validate",
    "stage",
    "commit",
    "push",
    "issue",
    "pull_request",
    "review",
    "merge",
    "close_issue",
}


def operation_digest(operation: dict[str, object]) -> str:
    body = dict(operation)
    body.pop("operation_digest", None)
    canonical = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class GovernedExecutorCharacterizationTests(unittest.TestCase):
    def test_bound_strict_validator_preserves_exception_type(self) -> None:
        validator = strict_validation.StrictValidator(core.SchemaError)
        with self.assertRaisesRegex(
            core.SchemaError,
            r"^inputs must be an object$",
        ):
            validator.object([], "inputs")
        with self.assertRaisesRegex(
            core.SchemaError,
            r"^inputs contains unknown fields: extra$",
        ):
            validator.exact_fields(
                {"required": True, "extra": True},
                {"required"},
                {"required"},
                "inputs",
            )

    def test_strict_object_validators_preserve_shared_diagnostics(self) -> None:
        validators = (
            core._require_object,
            session_initialize._object,
            issue_comments._object,
            lambda value, location: strict_validation.require_object(
                value,
                location,
                error_type=core.SchemaError,
            ),
        )
        for validator in validators:
            with self.subTest(validator=validator.__module__):
                with self.assertRaisesRegex(
                    core.SchemaError,
                    r"^inputs must be an object$",
                ):
                    validator([], "inputs")
                value = {"field": "value"}
                self.assertIs(validator(value, "inputs"), value)

    def test_strict_exact_field_validators_preserve_shared_diagnostics(self) -> None:
        validators = (
            core._require_exact_fields,
            session_initialize._exact,
            issue_comments._exact,
            lambda value, allowed, required, location: (
                strict_validation.require_exact_fields(
                    value,
                    allowed,
                    required,
                    location,
                    error_type=core.SchemaError,
                )
            ),
        )
        for validator in validators:
            with self.subTest(validator=validator.__module__, case="unknown"):
                with self.assertRaisesRegex(
                    core.SchemaError,
                    r"^inputs contains unknown fields: extra, other$",
                ):
                    validator(
                        {"required": True, "other": True, "extra": True},
                        {"required"},
                        {"required"},
                        "inputs",
                    )
            with self.subTest(validator=validator.__module__, case="missing"):
                with self.assertRaisesRegex(
                    core.SchemaError,
                    r"^inputs is missing required fields: first, second$",
                ):
                    validator(
                        {},
                        {"first", "second"},
                        {"first", "second"},
                        "inputs",
                    )

    def test_shared_contract_sets_are_closed(self) -> None:
        self.assertEqual(core.AUTHORIZATION_FIELDS, AUTHORIZATION_FIELDS)
        self.assertEqual(
            core.TOP_LEVEL_FIELDS,
            {
                "schema_version",
                "operation_id",
                "operation_type",
                "executor_version",
                "operation_digest",
                "repository",
                "guards",
                "authorization",
                "inputs",
                "expected_mutations",
                "validation",
                "publication",
                "result",
            },
        )
        self.assertEqual(
            core.TERMINAL_STATUSES,
            {
                "guard-failed",
                "pre-mutation-failed",
                "partial-local-mutation",
                "partial-remote-mutation",
                "partial-publication",
                "pre-publication-failed",
                "post-mutation-validation-failed",
                "local-mutation-completed",
                "commit-completed",
                "publication-completed",
                "validation-completed",
            },
        )
        self.assertEqual(
            core.SUCCESS_TERMINAL_STATUSES,
            {
                "local-mutation-completed",
                "commit-completed",
                "publication-completed",
                "validation-completed",
            },
        )
        self.assertEqual(
            set(core.OPERATION_HANDLERS),
            core.SUPPORTED_OPERATION_TYPES,
        )

    def test_operation_digest_is_canonical_and_excludes_digest_field(self) -> None:
        first = {
            "z": [3, 2, 1],
            "a": {"two": 2, "one": 1},
            "operation_digest": "0" * 64,
        }
        second = {
            "operation_digest": "f" * 64,
            "a": {"one": 1, "two": 2},
            "z": [3, 2, 1],
        }
        self.assertEqual(core.operation_digest(first), core.operation_digest(second))
        self.assertEqual(core.operation_digest(first), operation_digest(first))

    def test_redaction_covers_token_and_environment_secret(self) -> None:
        token = "ghp_" + "A" * 24
        secret = "executor-private-value"
        text = f"{token} {secret}"
        redacted, events = core.redact_text(
            text,
            environment={"SCF_PRIVATE_KEY": secret},
        )

        self.assertNotIn(token, redacted)
        self.assertNotIn(secret, redacted)
        self.assertEqual(
            {event["category"] for event in events},
            {"credential", "environment-secret"},
        )

    def test_redaction_removes_credentials_when_input_is_a_url(self) -> None:
        redacted, events = core.redact_text(
            "https://user:password@example.com/path"
        )

        self.assertEqual(redacted, "https://example.com/path")
        self.assertEqual(
            {event["category"] for event in events},
            {"credential-url"},
        )

    def test_local_file_contract_requires_exact_expected_mutations(self) -> None:
        body = "characterization\n"
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        inputs = {
            "operations": [
                {
                    "action": "create",
                    "path": "tests/validation/example.py",
                    "content": body,
                    "content_sha256": digest,
                    "mode": "0644",
                }
            ]
        }
        expected = {
            "files": [
                {
                    "action": "create",
                    "path": "tests/validation/example.py",
                    "before_sha256": None,
                    "after_sha256": digest,
                    "mode": "0644",
                }
            ]
        }

        normalized = local_files.validate_local_file_inputs(inputs, expected)
        self.assertEqual(normalized, inputs["operations"])

        invalid = copy.deepcopy(expected)
        invalid["files"][0]["after_sha256"] = "0" * 64
        with self.assertRaisesRegex(
            local_files.LocalFileOperationError,
            "does not exactly match operations",
        ):
            local_files.validate_local_file_inputs(inputs, invalid)

    def test_local_file_contract_rejects_unknown_fields_and_parent_paths(self) -> None:
        body = "characterization\n"
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        base = {
            "action": "create",
            "path": "tests/validation/example.py",
            "content": body,
            "content_sha256": digest,
            "mode": "0644",
        }

        unknown = dict(base, command="forbidden")
        with self.assertRaisesRegex(
            local_files.LocalFileOperationError,
            "contains unknown fields",
        ):
            local_files.validate_local_file_inputs(
                {"operations": [unknown]},
                {"files": []},
            )

        traversal = dict(base, path="../example.py")
        with self.assertRaisesRegex(
            local_files.LocalFileOperationError,
            "is not normalized",
        ):
            local_files.validate_local_file_inputs(
                {"operations": [traversal]},
                {"files": []},
            )

    def test_session_initialization_rejects_broadened_authorization(self) -> None:
        detailed = "## Governed detailed scope\ncharacterization"
        patch_plan = (
            "## Governed work breakdown and patch plan\ncharacterization"
        )
        operation: dict[str, object] = {
            "schema_version": core.OPERATION_SCHEMA_VERSION,
            "operation_id": "characterization-session-init",
            "operation_type": "development-session-initialize",
            "executor_version": "0.8.4",
            "operation_digest": "",
            "repository": {
                "root": ".",
                "origin": "https://github.com/wiigelec/scf",
            },
            "guards": {"clean": True},
            "authorization": {
                field: field in {"interrogate", "edit", "issue", "push"}
                for field in AUTHORIZATION_FIELDS
            },
            "inputs": {
                "issue": 52,
                "branch": "issue-52-characterization",
                "detailed_scope_body": detailed,
                "patch_plan_body": patch_plan,
            },
            "expected_mutations": {
                "issue": 52,
                "branch": "issue-52-characterization",
                "detailed_scope_body_sha256": hashlib.sha256(
                    detailed.encode("utf-8")
                ).hexdigest(),
                "patch_plan_body_sha256": hashlib.sha256(
                    patch_plan.encode("utf-8")
                ).hexdigest(),
            },
            "validation": {},
            "publication": {},
            "result": {
                "directory": "~/Downloads",
                "filename": "characterization-session-init.result.json",
            },
        }
        operation["operation_digest"] = operation_digest(operation)

        original = core.EXECUTOR_VERSION
        core.EXECUTOR_VERSION = "0.8.4"
        try:
            path = ROOT / "tests" / "validation" / ".characterization.operation.json"
            path.write_text(json.dumps(operation), encoding="utf-8")
            self.addCleanup(lambda: path.unlink(missing_ok=True))
            with self.assertRaisesRegex(
                core.SchemaError,
                "operation broadens authorization: push",
            ):
                session_initialize.load_operation(path)
        finally:
            core.EXECUTOR_VERSION = original

    def test_launcher_preserves_closed_current_and_legacy_routing(self) -> None:
        launcher = (ROOT / "src" / "scf_governed_executor" / "launcher.py").read_text(
            encoding="utf-8"
        )
        package_init = (
            ROOT / "src" / "scf_governed_executor" / "__init__.py"
        ).read_text(encoding="utf-8")
        current_match = re.search(
            r'^EXECUTOR_VERSION = "([0-9]+\.[0-9]+\.[0-9]+)"$',
            package_init,
            flags=re.MULTILINE,
        )
        legacy_match = re.search(
            r'^LEGACY_EXECUTOR_VERSION = "([0-9]+\.[0-9]+\.[0-9]+)"$',
            launcher,
            flags=re.MULTILINE,
        )
        self.assertIsNotNone(current_match)
        self.assertIsNotNone(legacy_match)
        self.assertNotEqual(current_match.group(1), legacy_match.group(1))
        self.assertIn(
            "from scf_governed_executor import EXECUTOR_VERSION",
            launcher,
        )
        self.assertNotRegex(
            launcher,
            r'^EXECUTOR_VERSION = "',
        )
        self.assertNotIn(
            "core_module.EXECUTOR_VERSION = EXECUTOR_VERSION",
            launcher,
        )
        core_source = (
            ROOT / "src" / "scf_governed_executor" / "core.py"
        ).read_text(encoding="utf-8")
        self.assertIn("from . import EXECUTOR_VERSION", core_source)
        self.assertNotRegex(
            core_source,
            r'^EXECUTOR_VERSION = "',
        )
        dispatch_body = launcher.split("CURRENT_DISPATCH", 1)[1].split(
            "def _unsupported", 1
        )[0]
        dispatch_keys = set(
            re.findall(
                r'^\s+"([^"]+)":',
                dispatch_body,
                flags=re.MULTILINE,
            )
        )
        self.assertEqual(
            dispatch_keys,
            {
                "development-session-initialize",
                "executor-self-update",
                "git-publication",
                "issue-create",
                "repository-interrogation",
            },
        )
        self.assertIn("return _legacy(operation_path)", launcher)
        self.assertIn("unsupported executor version for operation type", launcher)


if __name__ == "__main__":
    unittest.main()
