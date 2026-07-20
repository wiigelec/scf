from __future__ import annotations

import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = REPOSITORY_ROOT / "docs" / "GOVERNED-DEVELOPMENT-SESSION-RESTORATION.md"


class GovernedDevelopmentSessionRestorationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = PROTOCOL.read_text(encoding="utf-8")
        cls.prose = " ".join(cls.text.split())

    def assert_required(self, *phrases: str) -> None:
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.prose)

    def test_protocol_identifies_role_and_governing_parent(self) -> None:
        self.assert_required(
            "# Governed Development Session Restoration",
            "## Status, role, and governing parent",
            "official read-only restoration protocol",
            "governed by the accepted SCF authority hierarchy",
            "`docs/OFFICIAL-GOVERNED-DEVELOPMENT-PROCESS.md`",
            "`docs/GOVERNED-ISSUE-PLANNING.md`",
            "without relying on prior chat history or model memory",
        )

    def test_protocol_defines_authority_first_bounded_discovery(self) -> None:
        self.assert_required(
            "## Restoration properties",
            "**read-only**",
            "**authority-first**",
            "**bounded**",
            "**non-inventive**",
            "## Authority and discovery order",
            "smallest authoritative context sufficient for the active task",
            "must not silently select whichever source is most convenient",
        )

    def test_protocol_separates_evidence_classes(self) -> None:
        self.assert_required(
            "## Evidence classes",
            "### Remote evidence",
            "### Repository-local evidence",
            "### User-supplied local-only evidence",
            "### Transient conversation context",
            "must not be relabeled as remote evidence",
            "are not durable authority or completion evidence",
        )

    def test_protocol_records_exact_identities(self) -> None:
        self.assert_required(
            "## Required identity fields",
            "accepted base revision, observed `HEAD`, and merge base",
            "designated detailed-scope comment identity",
            "designated work-breakdown comment identity",
            "planned patch, expected files, and planned commit subject",
            "An unknown field remains unknown",
            "It is not populated from a guess",
        )

    def test_protocol_defines_lifecycle_frontier_and_next_action(self) -> None:
        self.assert_required(
            "## Lifecycle frontier",
            "patch execution pending",
            "local patch committed",
            "branch clean-revision certified",
            "exact PR-head CI passed",
            "exact revision accepted",
            "completed states, remaining states, and the next authorized action",
            "must not infer acceptance from validation, CI, merge, or issue state alone",
        )

    def test_protocol_defines_guarded_python_script_execution(self) -> None:
        self.assert_required(
            "## Chat-developed local execution artifacts",
            "### Guarded user-run Python scripts",
            "`user-run-python-script`",
            "transient execution vehicle",
            "SHA-256 digest",
            "exact invocation command",
            "intended changed-file boundary",
            "planned commit subject",
            "its existence is not proof that it ran",
        )

    def test_protocol_distinguishes_script_states_and_recovery(self) -> None:
        self.assert_required(
            "### Script execution states",
            "`pending`",
            "`failed`",
            "`partially-applied`",
            "`recovered`",
            "`completed`",
            "a recovery script",
            "remain separately identifiable",
            "must not collapse them into a single successful event",
        )

    def test_protocol_defines_transcript_and_visibility_boundaries(self) -> None:
        self.assert_required(
            "### Transcript evidence",
            "A user-supplied terminal transcript is local-only evidence",
            "A script body alone cannot establish execution",
            "### Local and remote visibility",
            "remains local-only evidence until the exact SHA is remotely resolvable",
            "Push, pull-request creation, CI execution, semantic review, acceptance, merge, and issue closure are separate facts",
        )

    def test_protocol_defines_complete_and_underspecified_results(self) -> None:
        self.assert_required(
            "## Complete restoration result",
            "A result is `complete`",
            "Completeness is task-relative",
            "## Underspecified restoration result",
            "A result is `underspecified`",
            "missing or duplicate designated planning comments",
            "script reported as run without a transcript",
            "Underspecified is not failure, completion, or permission to invent missing architecture",
        )

    def test_protocol_defines_no_mutation_and_deterministic_output(self) -> None:
        self.assert_required(
            "## No-mutation boundary",
            "must not create, edit, or delete repository files",
            "stage or commit changes",
            "create or edit issues",
            "must inspect before-and-after repository state",
            "## Deterministic machine-readable result",
            "explicit schema version",
            "stable field names and deterministic ordering",
            "retrieval record, not a durable copy of live lifecycle state",
        )

    def test_protocol_requires_representative_recovery_cases(self) -> None:
        self.assert_required(
            "## Representative recovery cases",
            "a pending guarded Python script",
            "a failed script followed by a separately identified recovery script",
            "a completed script producing a local-only commit",
            "the same commit after it becomes remotely visible",
            "proof that restoration performs no mutation",
            "deterministic repeated output",
        )

    def test_protocol_defines_failure_and_success_boundaries(self) -> None:
        self.assert_required(
            "## Failure and incomplete-evidence behavior",
            "produce explicit diagnostics",
            "must not be silently retried until a convenient result appears",
            "returns `underspecified`",
            "false pass",
            "## Success boundary",
            "without relying on prior chat history",
            "without mutating state",
        )


if __name__ == "__main__":
    unittest.main()
