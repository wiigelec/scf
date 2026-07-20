from __future__ import annotations

import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
README = REPOSITORY_ROOT / "README.md"
BOOTSTRAP = REPOSITORY_ROOT / "bootstrap" / "INITIAL-DEVELOPMENT-PROCESS.md"
PLANNING = REPOSITORY_ROOT / "docs" / "GOVERNED-ISSUE-PLANNING.md"
OFFICIAL = REPOSITORY_ROOT / "docs" / "OFFICIAL-GOVERNED-DEVELOPMENT-PROCESS.md"
RESTORATION = (
    REPOSITORY_ROOT / "docs" / "GOVERNED-DEVELOPMENT-SESSION-RESTORATION.md"
)
RESTORE_SCRIPT = REPOSITORY_ROOT / "scripts" / "restore-session"


class OfficialProcessDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.readme = " ".join(README.read_text(encoding="utf-8").split())
        cls.bootstrap = " ".join(BOOTSTRAP.read_text(encoding="utf-8").split())
        cls.planning = " ".join(PLANNING.read_text(encoding="utf-8").split())
        cls.official = " ".join(OFFICIAL.read_text(encoding="utf-8").split())
        cls.restoration = " ".join(
            RESTORATION.read_text(encoding="utf-8").split()
        )
        cls.restore_script = " ".join(
            RESTORE_SCRIPT.read_text(encoding="utf-8").split()
        )

    def test_readme_discovers_one_official_process(self) -> None:
        for required in (
            "official governed development process",
            "docs/OFFICIAL-GOVERNED-DEVELOPMENT-PROCESS.md",
            "authority discovery",
            "bounded authorization",
            "successor-work boundaries",
        ):
            self.assertIn(required, self.readme)

    def test_readme_identifies_planning_relationship(self) -> None:
        for required in (
            "three-record bounded-work planning convention",
            "docs/GOVERNED-ISSUE-PLANNING.md",
        ):
            self.assertIn(required, self.readme)

    def test_readme_discovers_session_restoration(self) -> None:
        for required in (
            "governed development session-restoration protocol",
            "docs/GOVERNED-DEVELOPMENT-SESSION-RESTORATION.md",
            "./scripts/restore-session --evidence PATH --format json",
            "user-run-python-script",
            "does not depend on prior chat history",
        ):
            self.assertIn(required, self.readme)

    def test_restoration_is_subordinate_and_read_only(self) -> None:
        for required in (
            "official read-only restoration protocol",
            "docs/OFFICIAL-GOVERNED-DEVELOPMENT-PROCESS.md",
            "does not create product authority",
            "without relying on prior chat history",
            "without mutating state",
        ):
            self.assertIn(required, self.restoration)

    def test_official_process_identifies_restoration_relationship(self) -> None:
        for required in (
            "## Session restoration across independent sessions",
            "docs/GOVERNED-DEVELOPMENT-SESSION-RESTORATION.md",
            "./scripts/restore-session",
            "user-run-python-script",
            "may not execute that command",
        ):
            self.assertIn(required, self.official)

    def test_planning_guide_identifies_restoration_inputs(self) -> None:
        for required in (
            "## Relationship to session restoration",
            "## Governed detailed scope",
            "## Governed work breakdown and patch plan",
            "expected changed-file boundary",
            "user-run-python-script",
            "repository-local registry",
        ):
            self.assertIn(required, self.planning)

    def test_restore_script_is_repository_root_entrypoint(self) -> None:
        for required in (
            "Run governed development session restoration from the repository root",
            "docs/GOVERNED-DEVELOPMENT-SESSION-RESTORATION.md",
            "from scf_restoration.cli import main",
        ):
            self.assertIn(required, self.restore_script)

    def test_required_artifacts_protect_restoration(self) -> None:
        from src.scf_validation.checks.repository import REQUIRED_ARTIFACTS

        self.assertIn(
            "docs/GOVERNED-DEVELOPMENT-SESSION-RESTORATION.md",
            REQUIRED_ARTIFACTS,
        )
        self.assertIn("scripts/restore-session", REQUIRED_ARTIFACTS)

    def test_readme_marks_bootstrap_process_historical(self) -> None:
        for required in (
            "bootstrap/INITIAL-DEVELOPMENT-PROCESS.md",
            "historical bootstrap evidence",
            "prospectively superseded",
        ):
            self.assertIn(required, self.readme)

    def test_bootstrap_process_preserves_history_and_supersession(self) -> None:
        for required in (
            "## Historical status and supersession",
            "provisional bootstrap-era development process",
            "retained as historical evidence",
            "docs/OFFICIAL-GOVERNED-DEVELOPMENT-PROCESS.md",
            "prospectively superseded",
            "does not erase this document's historical role",
            "New governed work uses the official process",
        ):
            self.assertIn(required, self.bootstrap)

    def test_planning_guide_is_subordinate_to_official_process(self) -> None:
        for required in (
            "three-record convention",
            "used within the official governed development process",
            "does not replace, supersede, or reinterpret",
            "official governed development process",
        ):
            self.assertIn(required, self.planning)

    def test_planning_guide_uses_transition_rule_for_open_work(self) -> None:
        for required in (
            "official governed development process",
            "earlier process that remains authoritative for already-open work",
            "explicit transition rules",
        ):
            self.assertIn(required, self.planning)

    def test_planning_guide_no_longer_defers_to_issue_10(self) -> None:
        self.assertNotIn("Issue #10 may later establish", self.planning)
        self.assertNotIn("Issue #10 may establish", self.planning)
        self.assertIn(
            "The official governed development process defines the lifecycle vocabulary",
            self.planning,
        )

    def test_planning_guide_does_not_duplicate_live_state(self) -> None:
        for required in (
            "must not duplicate live issue",
            "pull-request, commit, validation, or CI state",
            "does not define",
            "a custom lifecycle engine",
        ):
            self.assertIn(required, self.planning)

    def test_official_process_and_bootstrap_notice_agree(self) -> None:
        self.assertIn("bootstrap/INITIAL-DEVELOPMENT-PROCESS.md", self.official)
        self.assertIn("prospectively", self.official)
        self.assertIn("historical evidence", self.official)
        self.assertIn("docs/OFFICIAL-GOVERNED-DEVELOPMENT-PROCESS.md", self.bootstrap)
        self.assertIn("prospectively", self.bootstrap)
        self.assertIn("historical evidence", self.bootstrap)


if __name__ == "__main__":
    unittest.main()
