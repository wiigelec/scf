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

    def test_readme_discovers_session_initialization(self) -> None:
        for required in (
            "governed development-session initialization and interaction standard",
            "docs/GOVERNED-DEVELOPMENT-SESSION-RESTORATION.md",
            "guarded read-only Python interrogation script",
            "python ~/Downloads/<unique-script-name>.py",
            "exactly one unique non-overwriting result file",
            "Direct chatbot connector writes are not a governed mutation path",
            "does not depend on prior chat history or model memory",
        ):
            self.assertIn(required, self.readme)

    def test_initialization_standard_is_subordinate(self) -> None:
        for required in (
            "official initialization and interaction standard",
            "docs/OFFICIAL-GOVERNED-DEVELOPMENT-PROCESS.md",
            "does not create product authority",
            "without relying on prior chat history or model memory",
        ):
            self.assertIn(required, self.restoration)

    def test_official_process_identifies_initialization_relationship(self) -> None:
        for required in (
            "## Development-session initialization and interaction",
            "docs/GOVERNED-DEVELOPMENT-SESSION-RESTORATION.md",
            "python ~/Downloads/<unique-script-name>.py",
            "direct connector writes are not a governed mutation path",
        ):
            self.assertIn(required, self.official)

    def test_planning_guide_identifies_initialization_inputs(self) -> None:
        for required in (
            "## Relationship to session initialization and interaction",
            "## Governed detailed scope",
            "## Governed work breakdown and patch plan",
            "expected changed-file boundary",
            "single result artifact",
            "guarded script transport protocol",
        ):
            self.assertIn(required, self.planning)

    def test_required_artifacts_protect_initialization_standard(self) -> None:
        from src.scf_validation.checks.repository import REQUIRED_ARTIFACTS

        self.assertIn(
            "docs/GOVERNED-DEVELOPMENT-SESSION-RESTORATION.md",
            REQUIRED_ARTIFACTS,
        )
        self.assertNotIn("scripts/restore-session", REQUIRED_ARTIFACTS)

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
