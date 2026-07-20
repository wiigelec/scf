from __future__ import annotations

import re
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "repository-validation.yml"


class ContinuousIntegrationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_has_authorized_triggers(self) -> None:
        for required in (
            "pull_request:",
            "- opened",
            "- reopened",
            "- synchronize",
            "- ready_for_review",
            "push:",
            "- main",
            "workflow_dispatch:",
        ):
            self.assertIn(required, self.text)

    def test_workflow_uses_least_privilege_checkout(self) -> None:
        self.assertIn("permissions:\n  contents: read", self.text)
        self.assertIn("uses: actions/checkout@v4", self.text)
        self.assertIn("persist-credentials: false", self.text)
        self.assertNotRegex(
            self.text,
            re.compile(r"^\s+(?:contents|actions|checks|pull-requests): write\s*$", re.MULTILINE),
        )

    def test_pull_requests_resolve_exact_head_sha(self) -> None:
        self.assertIn("github.event.pull_request.head.sha", self.text)
        self.assertIn("ref: ${{ env.TESTED_SHA }}", self.text)
        self.assertIn('actual_sha="$(git rev-parse HEAD)"', self.text)
        self.assertIn('"${actual_sha}" != "${TESTED_SHA}"', self.text)
        self.assertIn("tested_sha=${TESTED_SHA}", self.text)
        self.assertIn("Tested commit:", self.text)

    def test_workflow_runs_tests_and_accepted_complete_gate(self) -> None:
        self.assertIn(
            "python -m unittest discover -s tests/validation -v",
            self.text,
        )
        self.assertIn(
            "./scripts/validate --mode complete --format json",
            self.text,
        )
        self.assertNotIn("--mode certify", self.text)

    def test_validation_failure_cannot_be_masked_by_tee(self) -> None:
        complete_step = self.text.split(
            "- name: Run complete repository validation", 1
        )[1].split("- name: Record validation result", 1)[0]
        self.assertIn("set -euo pipefail", complete_step)
        self.assertIn(
            'result_file="${RUNNER_TEMP}/validation-result.json"',
            complete_step,
        )
        self.assertIn('| tee "$result_file"', complete_step)
        self.assertIn('cp "$result_file" validation-result.json', complete_step)
        self.assertNotIn("continue-on-error", complete_step)

    def test_evidence_is_bound_to_tested_sha(self) -> None:
        self.assertIn(
            "name: repository-validation-${{ steps.revision.outputs.tested_sha }}",
            self.text,
        )
        self.assertIn("validation-result.json", self.text)
        self.assertIn("GITHUB_STEP_SUMMARY", self.text)

    def test_workflow_does_not_duplicate_validator_registry(self) -> None:
        self.assertNotIn("REQUIRED_CHECK_IDS", self.text)
        self.assertNotRegex(self.text, re.compile(r"SCF-[A-Z0-9-]+-\d+"))


if __name__ == "__main__":
    unittest.main()
