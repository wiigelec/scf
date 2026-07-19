from __future__ import annotations

import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROCESS = REPOSITORY_ROOT / "docs" / "OFFICIAL-GOVERNED-DEVELOPMENT-PROCESS.md"


class OfficialGovernedDevelopmentProcessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = PROCESS.read_text(encoding="utf-8")
        cls.prose = " ".join(cls.text.split())

    def test_process_identifies_status_role_and_parent(self) -> None:
        for required in (
            "# Official Governed Development Process",
            "## Status, role, and governing parent",
            "official repository-wide development process",
            "governed by the accepted SCF authority hierarchy",
            "durable Level 0 authority",
            "does not itself define SCF product runtime architecture",
        ):
            self.assertIn(required, self.prose)

    def test_process_distinguishes_records_and_evidence(self) -> None:
        for required in (
            "## Core record and evidence boundaries",
            "### Accepted repository authority",
            "### Governing issue",
            "### Designated planning records",
            "### Working branch",
            "### Commits",
            "### Local validation and certification",
            "### Continuous-integration evidence",
            "### Diff and semantic review",
            "### Acceptance, merge, and closure",
        ):
            self.assertIn(required, self.prose)

    def test_process_defines_complete_governed_lifecycle(self) -> None:
        for heading in (
            "### 1. Discover authority and current process",
            "### 2. Establish bounded authorization",
            "### 3. Record governed planning",
            "### 4. Create the isolated branch",
            "### 5. Implement bounded patches",
            "### 6. Validate before commit",
            "### 7. Commit intentionally",
            "### 8. Validate and certify the proposed branch head",
            "### 9. Push and open the pull request",
            "### 10. Obtain CI and review evidence",
            "### 11. Correct open work",
            "### 12. Determine readiness and acceptance",
            "### 13. Merge accepted work",
            "### 14. Close out the issue",
            "### 15. Authorize successor work separately",
        ):
            self.assertIn(heading, self.prose)

    def test_process_keeps_lifecycle_states_non_equivalent(self) -> None:
        for required in (
            "Issue existence alone is not authorization",
            "A commit is an immutable implementation record",
            "it is not acceptance",
            "A passing CI result does not approve, accept, merge, or close work",
            "Passing validation is not semantic review",
            "Technical readiness, audit readiness, or certification does not automatically establish acceptance",
            "Completion, merge, or closure does not automatically authorize the next issue",
        ):
            self.assertIn(required, self.prose)

    def test_process_defines_exact_revision_and_stale_evidence(self) -> None:
        for required in (
            "A later commit creates a different proposed revision",
            "invalidates earlier exact-revision certification or CI evidence",
            "CI evidence is exact-revision evidence",
            "A passing run for one SHA is not evidence for a later SHA",
            "Any later commit requires fresh certification",
            "A later push requires a new run",
            "previously passing SHA",
        ):
            self.assertIn(required, self.prose)

    def test_process_defines_validation_review_commit_and_push_requirements(self) -> None:
        for required in (
            "### 6. Validate before commit",
            "run applicable focused tests",
            "run complete-work validation",
            "inspect the full patch diff",
            "Commit only the files belonging to the bounded patch",
            "Push only after the branch is in a known, validated state",
            "Review the entire diff",
        ):
            self.assertIn(required, self.prose)

    def test_process_defines_failure_and_incomplete_evidence(self) -> None:
        for required in (
            "## Failure and incomplete-evidence behavior",
            "deterministic validation, test, certification, or CI failure",
            "must not be silently retried",
            "produces incomplete evidence",
            "it is also not a pass",
            "state exactly what is missing",
            "defer acceptance when the missing evidence is required",
        ):
            self.assertIn(required, self.prose)

    def test_process_defines_correction_and_closeout(self) -> None:
        for required in (
            "### 11. Correct open work",
            "fresh local validation",
            "fresh certification when required",
            "fresh CI for the new SHA",
            "renewed full-diff review",
            "### 14. Close out the issue",
            "Issue state alone is never sufficient completion evidence",
        ):
            self.assertIn(required, self.prose)

    def test_process_defines_repository_wide_change_boundary(self) -> None:
        for required in (
            "## Repository-wide process changes",
            "must itself follow this process",
            "explicit supersession or amendment semantics",
            "acceptance and merge to `main`",
            "A branch-local instruction may not silently amend this process",
        ):
            self.assertIn(required, self.prose)

    def test_process_supersedes_provisional_process_without_erasure(self) -> None:
        for required in (
            "## Supersession",
            "`bootstrap/INITIAL-DEVELOPMENT-PROCESS.md`",
            "prospectively upon acceptance and merge to `main`",
            "remains historical evidence",
            "does not erase its history",
            "Work already in progress continues under the process authoritative when that work began",
        ):
            self.assertIn(required, self.prose)


if __name__ == "__main__":
    unittest.main()
