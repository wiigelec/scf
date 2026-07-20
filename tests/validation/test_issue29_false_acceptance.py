"""Regression tests for Issue #29 false-acceptance corrections."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.scf_validation.checks.json_files import check_json_files
from src.scf_validation.checks.level0 import _validate_schema_definition
from src.scf_validation.checks.repository import check_repository
from src.scf_validation.context import InputProblem, ValidationContext


class JsonCoverageTests(unittest.TestCase):
    def repository(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        (root / "tracked.json").write_text("{}\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.json"], cwd=root, check=True)
        (root / ".gitignore").write_text("ignored.json\n", encoding="utf-8")
        subprocess.run(["git", "add", ".gitignore"], cwd=root, check=True)
        return temporary, root

    def test_untracked_nonignored_json_is_checked(self):
        temporary, root = self.repository()
        self.addCleanup(temporary.cleanup)
        (root / "new.json").write_text("{ broken\n", encoding="utf-8")
        (root / "ignored.json").write_text("{ broken\n", encoding="utf-8")
        self.assertEqual(("new.json", "tracked.json"), ValidationContext(root).json_paths())
        diagnostics = check_json_files(ValidationContext(root))
        self.assertIn("SCF-JSON-SYNTAX", {item.diagnostic_id for item in diagnostics})

    def test_nonfinite_constants_fail(self):
        temporary, root = self.repository()
        self.addCleanup(temporary.cleanup)
        for index, token in enumerate(("NaN", "Infinity", "-Infinity")):
            relative = f"constant-{index}.json"
            (root / relative).write_text(token + "\n", encoding="utf-8")
            with self.subTest(token=token):
                with self.assertRaises(InputProblem) as raised:
                    ValidationContext(root).parse_json(relative)
                self.assertEqual("SCF-JSON-SYNTAX", raised.exception.diagnostic_id)
                self.assertIn("non-standard JSON constant", raised.exception.message)


class Level0SchemaDefinitionTests(unittest.TestCase):
    def test_malformed_supported_keywords_fail_closed(self):
        cases = (
            {"type": ["string"]},
            {"required": "field"},
            {"required": ["field", "field"]},
            {"properties": []},
            {"additionalProperties": "no"},
            {"enum": "value"},
            {"enum": []},
            {"pattern": 1},
            {"pattern": "["},
            {"minLength": True},
            {"minItems": -1},
            {"uniqueItems": 1},
            {"items": []},
            {"properties": {"child": {"required": "name"}}},
        )
        for schema in cases:
            diagnostics = []
            _validate_schema_definition(schema, [], diagnostics)
            with self.subTest(schema=schema):
                self.assertIn(
                    "SCF-LEVEL0-SCHEMA-DEFINITION",
                    {item.diagnostic_id for item in diagnostics},
                )


class BootstrapOutputTests(unittest.TestCase):
    class Context:
        def __init__(self, root, value):
            self.root = root
            self.value = value

        def parse_json(self, repository_path):
            return self.value

        def safe_path(self, repository_path):
            return self.root / repository_path

        def is_regular_file(self, repository_path):
            return self.safe_path(repository_path).is_file()

    def base(self):
        return {
            "status": "consumed-by-bootstrap-commit",
            "expires_after": "bootstrap complete",
            "allowed_outputs": ["output.txt"],
        }

    def run_check(self, root, value):
        with mock.patch("src.scf_validation.checks.repository.REQUIRED_ARTIFACTS", ()):
            return check_repository(self.Context(root, value))

    def test_malformed_outputs_and_directory_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for value in (None, "output.txt", [], [1]):
                bootstrap = self.base()
                if value is None:
                    del bootstrap["allowed_outputs"]
                else:
                    bootstrap["allowed_outputs"] = value
                with self.subTest(value=value):
                    diagnostics = self.run_check(root, bootstrap)
                    self.assertIn(
                        "SCF-BOOTSTRAP-OUTPUT",
                        {item.diagnostic_id for item in diagnostics},
                    )

            (root / "output.txt").mkdir()
            diagnostics = self.run_check(root, self.base())
            self.assertIn(
                "historical bootstrap output must be a regular file",
                [item.message for item in diagnostics],
            )


if __name__ == "__main__":
    unittest.main()
