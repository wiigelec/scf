from __future__ import annotations

import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_DOC = REPOSITORY_ROOT / "docs" / "VALIDATION.md"
README = REPOSITORY_ROOT / "README.md"


class ContinuousIntegrationDocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validation_text = VALIDATION_DOC.read_text(encoding="utf-8")
        cls.validation_prose = " ".join(cls.validation_text.split())
        cls.readme_text = README.read_text(encoding="utf-8")
        cls.readme_prose = " ".join(cls.readme_text.split())

    def test_validation_guide_documents_ci_triggers_and_stable_check(self) -> None:
        for required in (
            "## Continuous integration evidence",
            "stable check name `repository-validation`",
            "opened, reopened, synchronized with a later commit",
            "pushes to `main`",
            "manual workflow dispatches",
        ):
            self.assertIn(required, self.validation_prose)

    def test_validation_guide_documents_exact_tested_revision(self) -> None:
        for required in (
            "`github.event.pull_request.head.sha`",
            "synthetic pull-request merge ref",
            "`github.sha`",
            "`git rev-parse HEAD`",
            "CI evidence is commit-specific",
            "not evidence for a later SHA",
        ):
            self.assertIn(required, self.validation_prose)

    def test_validation_guide_documents_command_equivalence_and_failure(self) -> None:
        for required in (
            "python -m unittest discover -s tests/validation -v",
            "./scripts/validate --mode complete --format json",
            "without reimplementing its registry or rules",
            "`pipefail`",
            "validation failure fails the workflow check",
        ):
            self.assertIn(required, self.validation_prose)

    def test_validation_guide_documents_read_only_boundary(self) -> None:
        for required in (
            "grants only read access",
            "disables persisted checkout credentials",
            "does not repair files, commit changes, push branches",
        ):
            self.assertIn(required, self.validation_prose)

    def test_validation_guide_separates_ci_from_other_evidence(self) -> None:
        for required in (
            "focused local validation",
            "complete local validation",
            "local certification",
            "CI independently reports",
            "diff review",
            "does not approve or accept",
        ):
            self.assertIn(required, self.validation_prose)

    def test_branch_protection_is_an_expectation_not_a_claim(self) -> None:
        for required in (
            "### Branch-protection expectation",
            "required status check",
            "does not claim that branch protection is configured",
            "must be verified independently",
        ):
            self.assertIn(required, self.validation_prose)

    def test_readme_links_ci_entrypoint(self) -> None:
        for required in (
            "Continuous integration",
            ".github/workflows/repository-validation.yml",
            "repository-validation",
            "docs/VALIDATION.md",
        ):
            self.assertIn(required, self.readme_prose)


if __name__ == "__main__":
    unittest.main()
