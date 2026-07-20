from __future__ import annotations

import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = REPOSITORY_ROOT / "docs" / "GOVERNED-DEVELOPMENT-SESSION-RESTORATION.md"


class GovernedDevelopmentSessionInitializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prose = " ".join(PROTOCOL.read_text(encoding="utf-8").split())

    def assert_required(self, *phrases: str) -> None:
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.prose)

    def test_initialization_and_transport_contract(self) -> None:
        self.assert_required(
            "# Governed Development Session Initialization and Interaction",
            "## Remote session orientation",
            "## Local-tree initialization",
            "## Definitive transport protocol",
            "exclusive execution boundary",
            "governed local repository mutations and remote GitHub mutations",
            "python ~/Downloads/<unique-script-name>.py",
            "safe to copy directly into `zsh`",
        )

    def test_guard_result_and_recovery_contract(self) -> None:
        self.assert_required(
            "## Script guard contract",
            "## Mutation boundary",
            "## Terminal progress and heartbeat",
            "periodic heartbeat messages",
            "## Single result artifact",
            "exactly one uniquely named result file",
            "must refuse to overwrite an existing result file",
            "## Execution-state distinctions",
            "`guard-failed`",
            "`partial-local-mutation`",
            "`partial-remote-mutation`",
            "`mutation-completed-validation-failed`",
            "`completed-and-committed`",
            "`completed-and-published`",
        )

    def test_publication_and_authority_boundaries(self) -> None:
        self.assert_required(
            "## Commit, push, and remote GitHub operations",
            "standard `git` commands to push",
            "standard `gh` commands",
            "Remote success is verified by reading the resulting remote object",
            "## Evidence and authority boundary",
            "not accepted repository authority",
            "direct chatbot connector write",
        )


if __name__ == "__main__":
    unittest.main()
