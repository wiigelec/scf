from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "src" / "scf_governed_executor" / "docs" / "GOVERNED-EXECUTOR.md"


class GovernedExecutorContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SPEC.read_text(encoding="utf-8")

    def test_normative_specification_exists(self) -> None:
        self.assertTrue(SPEC.is_file())
        self.assertTrue(self.text.startswith("# Governed Executor\n"))

    def test_operation_descriptions_are_declarative_and_closed(self) -> None:
        required = (
            "An operation description is data, not executable source.",
            "Unknown fields are rejected",
            "arbitrary shell commands",
            "description-provided command allowlist",
            "An operation description cannot expand its own authorization.",
        )
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_authorization_classes_remain_separate(self) -> None:
        for phrase in (
            "file edit",
            "validation",
            "commit",
            "push",
            "issue creation or modification",
            "pull-request creation or modification",
            "review submission",
            "merge",
            "issue closure",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_failure_states_are_explicit(self) -> None:
        statuses = (
            "`guard-failed`",
            "`pre-mutation-failed`",
            "`partial-local-mutation`",
            "`partial-remote-mutation`",
            "`post-mutation-validation-failed`",
            "`local-mutation-completed`",
            "`commit-completed`",
            "`publication-completed`",
        )
        for status in statuses:
            with self.subTest(status=status):
                self.assertIn(status, self.text)

    def test_security_and_evidence_requirements_are_present(self) -> None:
        required = (
            "read-after-write verification",
            "Redaction occurs before ordinary output is persisted.",
            "exclusive-create semantics",
            "periodic heartbeat output",
            "Symlinks are not followed",
            "does not contain the original secret",
        )
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_effective_executor_policy_is_present(self) -> None:
        self.assertIn(
            "Repository-supported governed operations use the versioned executor",
            self.text,
        )
        self.assertIn(
            "Unsupported operation classes fail closed",
            self.text,
        )


if __name__ == "__main__":
    unittest.main()

class GovernedExecutorTransitionContractTests(unittest.TestCase):
    def test_session_standard_names_repository_entrypoint(self) -> None:
        text = (ROOT / "docs/GOVERNED-DEVELOPMENT-SESSION-INITIALIZATION.md").read_text()
        self.assertIn("./scripts/governed-execute ~/Downloads/<unique-operation-name>.operation.json", text)
        self.assertIn("There is no silent fallback", text)

    def test_official_process_states_current_executor_policy(self) -> None:
        text = (ROOT / "docs/OFFICIAL-GOVERNED-DEVELOPMENT-PROCESS.md").read_text()
        self.assertIn("Governed operations use the repository-native governed executor", text)
        self.assertIn("Unsupported operation classes remain blocked", text)

    def test_planning_requires_executor_owned_boundary(self) -> None:
        text = (ROOT / "docs/GOVERNED-ISSUE-PLANNING.md").read_text()
        self.assertIn("executor operation type", text)
        self.assertIn("Unsupported classes remain blocked", text)

    def test_executor_spec_states_effective_boundary(self) -> None:
        text = (ROOT / "src/scf_governed_executor/docs/GOVERNED-EXECUTOR.md").read_text()
        self.assertIn("This specification is effective repository policy", text)
        self.assertIn("Unsupported operations fail closed", text)
