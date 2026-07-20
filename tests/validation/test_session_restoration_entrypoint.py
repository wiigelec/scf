from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from scf_restoration.restore import restore_session  # noqa: E402


class SessionRestorationEntrypointTests(unittest.TestCase):
    def git(self, root: Path, *args: str) -> str:
        result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True)
        return result.stdout.strip()

    def make_repository(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        subprocess.run(["git", "init", "-b", "issue-11-governed-development-session-restoration"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
        subprocess.run(["git", "remote", "add", "origin", "https://github.com/wiigelec/scf.git"], cwd=root, check=True)
        for path in (
            "authority/core/SCF-CORE.json",
            "docs/OFFICIAL-GOVERNED-DEVELOPMENT-PROCESS.md",
            "docs/GOVERNED-ISSUE-PLANNING.md",
            "docs/GOVERNED-DEVELOPMENT-SESSION-RESTORATION.md",
        ):
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("{}\n" if path.endswith(".json") else path + "\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "fixture"], cwd=root, check=True, capture_output=True)
        return temporary, root, self.git(root, "rev-parse", "HEAD")

    def base_evidence(self, head: str):
        expected = [
            "scripts/restore-session",
            "src/scf_restoration/__init__.py",
            "src/scf_restoration/cli.py",
            "src/scf_restoration/model.py",
            "src/scf_restoration/restore.py",
            "tests/validation/test_session_restoration_entrypoint.py",
        ]
        return {
            "repository_full_name": "wiigelec/scf",
            "supplied_branch": "issue-11-governed-development-session-restoration",
            "accepted_base": head,
            "authority": {"paths": ["authority/core/SCF-CORE.json"]},
            "planning": {
                "issue_number": 11,
                "detailed_scope_comment": "issuecomment-5017814402",
                "work_breakdown_comment": "issuecomment-5017814450",
                "strict_dependencies": ["#7", "#10"],
                "active_patch": "Patch 2",
                "expected_files": expected,
                "planned_commit_subject": "Implement read-only session restoration",
            },
            "execution": {
                "filename": "scf_issue_11_patch_2.py",
                "sha256": "a" * 64,
                "invocation": "python ~/Downloads/scf_issue_11_patch_2.py",
                "state": "pending",
                "expected_repository": "wiigelec/scf",
                "expected_branch": "issue-11-governed-development-session-restoration",
                "expected_starting_head": head,
                "expected_files": expected,
                "planned_commit_subject": "Implement read-only session restoration",
            },
            "remote_evidence": {"visible_commits": [], "references": ["issue-11"]},
            "local_only_evidence": {"references": ["patch-2-script"]},
        }

    def test_complete_pending_script_identifies_exact_next_command(self):
        temporary, root, head = self.make_repository()
        self.addCleanup(temporary.cleanup)
        result = restore_session(root, self.base_evidence(head)).as_dict()
        self.assertEqual("complete", result["status"])
        self.assertEqual("patch execution pending", result["lifecycle"]["frontier"])
        self.assertEqual("python ~/Downloads/scf_issue_11_patch_2.py", result["lifecycle"]["next_authorized_action"])

    def test_missing_authority_is_underspecified(self):
        temporary, root, head = self.make_repository()
        self.addCleanup(temporary.cleanup)
        (root / "authority/core/SCF-CORE.json").unlink()
        result = restore_session(root, self.base_evidence(head)).as_dict()
        self.assertEqual("underspecified", result["status"])
        self.assertIn("RESTORE-AUTHORITY-MISSING", {item["code"] for item in result["diagnostics"]})

    def test_missing_planning_record_is_underspecified(self):
        temporary, root, head = self.make_repository()
        self.addCleanup(temporary.cleanup)
        evidence = self.base_evidence(head)
        del evidence["planning"]["detailed_scope_comment"]
        result = restore_session(root, evidence).as_dict()
        self.assertEqual("underspecified", result["status"])
        self.assertIn("RESTORE-DETAILED-COMMENT", {item["code"] for item in result["diagnostics"]})

    def test_branch_mismatch_is_underspecified(self):
        temporary, root, head = self.make_repository()
        self.addCleanup(temporary.cleanup)
        evidence = self.base_evidence(head)
        evidence["supplied_branch"] = "wrong-branch"
        result = restore_session(root, evidence).as_dict()
        self.assertEqual("underspecified", result["status"])
        self.assertIn("RESTORE-BRANCH-MISMATCH", {item["code"] for item in result["diagnostics"]})

    def test_failed_script_requires_transcript(self):
        temporary, root, head = self.make_repository()
        self.addCleanup(temporary.cleanup)
        evidence = self.base_evidence(head)
        evidence["execution"]["state"] = "failed"
        result = restore_session(root, evidence).as_dict()
        self.assertEqual("underspecified", result["status"])
        self.assertIn("RESTORE-SCRIPT-TRANSCRIPT", {item["code"] for item in result["diagnostics"]})

    def test_recovery_script_remains_distinguishable(self):
        temporary, root, head = self.make_repository()
        self.addCleanup(temporary.cleanup)
        evidence = self.base_evidence(head)
        evidence["execution"].update({
            "state": "recovered",
            "transcript_reference": "transcript-2",
            "resulting_commit": head,
            "recovery_of": "scf_issue_11_patch_2_initial.py",
        })
        result = restore_session(root, evidence).as_dict()
        self.assertEqual("complete", result["status"])
        self.assertEqual("scf_issue_11_patch_2_initial.py", result["execution"]["recovery_of"])
        self.assertEqual("patch recovered locally", result["lifecycle"]["frontier"])

    def test_local_commit_becomes_remote_visible(self):
        temporary, root, head = self.make_repository()
        self.addCleanup(temporary.cleanup)
        evidence = self.base_evidence(head)
        evidence["execution"].update({
            "state": "completed",
            "transcript_reference": "transcript-3",
            "resulting_commit": head,
        })
        local = restore_session(root, evidence).as_dict()
        self.assertEqual("local patch committed", local["lifecycle"]["frontier"])
        evidence["remote_evidence"]["visible_commits"] = [head]
        remote = restore_session(root, evidence).as_dict()
        self.assertEqual("local patch committed and remotely visible", remote["lifecycle"]["frontier"])
        self.assertIsNone(remote["lifecycle"]["next_authorized_action"])

    def test_output_is_deterministic(self):
        temporary, root, head = self.make_repository()
        self.addCleanup(temporary.cleanup)
        evidence = self.base_evidence(head)
        first = json.dumps(restore_session(root, evidence).as_dict(), sort_keys=True, separators=(",", ":"))
        second = json.dumps(restore_session(root, evidence).as_dict(), sort_keys=True, separators=(",", ":"))
        self.assertEqual(first, second)

    def test_restoration_performs_no_mutation(self):
        temporary, root, head = self.make_repository()
        self.addCleanup(temporary.cleanup)
        evidence = self.base_evidence(head)
        before = (self.git(root, "rev-parse", "HEAD"), self.git(root, "status", "--porcelain=v1", "--untracked-files=all"), self.git(root, "show-ref"))
        restore_session(root, evidence)
        after = (self.git(root, "rev-parse", "HEAD"), self.git(root, "status", "--porcelain=v1", "--untracked-files=all"), self.git(root, "show-ref"))
        self.assertEqual(before, after)

    def test_cli_json_contract(self):
        head = self.git(REPOSITORY_ROOT, "rev-parse", "HEAD")
        evidence = self.base_evidence(head)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json", delete=False) as handle:
            json.dump(evidence, handle)
            evidence_path = Path(handle.name)
        self.addCleanup(evidence_path.unlink, missing_ok=True)
        result = subprocess.run(
            [str(REPOSITORY_ROOT / "scripts/restore-session"), "--evidence", str(evidence_path), "--format", "json"],
            cwd=REPOSITORY_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(1, payload["schema_version"])
        self.assertEqual("complete", payload["status"])


if __name__ == "__main__":
    unittest.main()
