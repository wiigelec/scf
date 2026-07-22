from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OPERATION_SCHEMA = ROOT / "src/scf_governed_executor/schemas/governed-operation-v1.schema.json"
RESULT_SCHEMA = ROOT / "src/scf_governed_executor/schemas/governed-result-v1.schema.json"


class LifecycleSchemaArtifactTests(unittest.TestCase):
    def test_operation_schema_declares_independent_lifecycle_types(self) -> None:
        schema = json.loads(OPERATION_SCHEMA.read_text(encoding="utf-8"))
        operation_types = schema["properties"]["operation_type"]["enum"]
        for operation_type in (
            "git-stage",
            "git-commit",
            "git-push",
            "pull-request-create",
            "git-publication",
        ):
            self.assertIn(operation_type, operation_types)
        self.assertEqual(
            schema["properties"]["executor_version"]["const"],
            "0.3.1",
        )

    def test_independent_authorization_is_closed_in_schema(self) -> None:
        schema = json.loads(OPERATION_SCHEMA.read_text(encoding="utf-8"))
        definitions = schema["$defs"]
        self.assertIs(
            definitions["authStage"]["properties"]["stage"]["const"], True
        )
        self.assertIs(
            definitions["authStage"]["properties"]["commit"]["const"], False
        )
        self.assertIs(
            definitions["authCommit"]["properties"]["stage"]["const"], False
        )
        self.assertIs(
            definitions["authCommit"]["properties"]["commit"]["const"], True
        )
        self.assertIs(
            definitions["authPush"]["properties"]["push"]["const"], True
        )
        self.assertIs(
            definitions["authPr"]["properties"]["pull_request"]["const"], True
        )

    def test_result_schema_accepts_lifecycle_result_types(self) -> None:
        schema = json.loads(RESULT_SCHEMA.read_text(encoding="utf-8"))
        operation_types = schema["properties"]["operation_type"]["enum"]
        for operation_type in (
            "git-stage",
            "git-commit",
            "git-push",
            "pull-request-create",
        ):
            self.assertIn(operation_type, operation_types)
        self.assertEqual(
            schema["properties"]["executor_version"]["const"],
            "0.3.1",
        )


if __name__ == "__main__":
    unittest.main()
