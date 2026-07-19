from __future__ import annotations

import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_DOC = REPOSITORY_ROOT / "docs/VALIDATION.md"
README = REPOSITORY_ROOT / "README.md"


class ValidationGateDocumentationTests(unittest.TestCase):
    def test_validation_guide_documents_all_modes_and_defaults(self) -> None:
        text = VALIDATION_DOC.read_text(encoding="utf-8")
        for required in (
            "### Focused validation",
            "### Complete-work validation",
            "### Certification validation",
            "Using `--check` without `--mode` selects focused mode",
            "Running without `--mode` or `--check` selects complete mode",
        ):
            self.assertIn(required, text)

    def test_validation_guide_documents_exact_certification_boundary(self) -> None:
        text = VALIDATION_DOC.read_text(encoding="utf-8")
        for required in (
            "CERTIFIED <exact-commit-sha>",
            "Certification means only that the exact clean revision passed",
            "It does not approve, accept, merge, close, authorize",
            "Certification requires",
            "`clean-revision`",
        ):
            self.assertIn(required, text)

    def test_validation_guide_documents_machine_result_contract(self) -> None:
        text = VALIDATION_DOC.read_text(encoding="utf-8")
        for required in (
            "Machine-readable output is deterministic compact JSON",
            "`schema_version` 1",
            "`repository`",
            "`checks`",
            "`diagnostics`",
            "`summary`",
            "same immutable validation result",
        ):
            self.assertIn(required, text)

    def test_validation_guide_documents_registry_failure_behavior(self) -> None:
        text = VALIDATION_DOC.read_text(encoding="utf-8")
        for required in (
            "REQUIRED_CHECK_IDS",
            "REGISTERED_CHECKS",
            "fails rather than silently passing",
            "does not use",
            "dynamic validator",
        ):
            self.assertIn(required, text)

    def test_validation_guide_distinguishes_validation_and_diff_review(self) -> None:
        text = VALIDATION_DOC.read_text(encoding="utf-8")
        for required in (
            "## Validation is not diff review",
            "full-state validation",
            "A passing gate does not prove",
            "A clean diff does not prove",
        ):
            self.assertIn(required, text)

    def test_readme_discovers_gate_modes(self) -> None:
        text = README.read_text(encoding="utf-8")
        for required in (
            "development validation gate",
            "default complete-work mode",
            "./scripts/validate --check SCF-JSON-001",
            "./scripts/validate --mode certify",
            "docs/VALIDATION.md",
        ):
            self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
