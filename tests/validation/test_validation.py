from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from scf_validation.checks import REGISTERED_CHECKS
from scf_validation.checks.checksums import check_checksum
from scf_validation.checks.json_files import check_json_files
from scf_validation.checks.manifests import check_manifest
from scf_validation.checks.repository import check_repository
from scf_validation.checks.semantic_paths import check_semantic_paths
from scf_validation.cli import main
from scf_validation.context import ValidationContext
from scf_validation.registry import Check


class RepositoryFixture:
    def __init__(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        self.write(".gitignore", "__pycache__/\n")
        self.write("README.md", "# Test SCF\n")
        self.write("VERSION", "0.0.0-test\n")
        self.write("bootstrap/INITIAL-DEVELOPMENT-PROCESS.md", "# Process\n")
        self.write("bootstrap/README.md", "# Bootstrap\n")
        for relative in (
            ".github/ISSUE_TEMPLATE/governed-work.md",
            "docs/GOVERNED-ISSUE-PLANNING.md",
            "docs/templates/GOVERNED-DETAILED-SCOPE.md",
            "docs/templates/GOVERNED-WORK-BREAKDOWN.md",
        ):
            source = REPOSITORY_ROOT / relative
            self.write(relative, source.read_bytes())
        self.write("planning/README.md", "# Planning\n")
        self.write("planning/BOOTSTRAP-TO-DEVELOPMENT-ROADMAP.md", "# Roadmap\n")
        self.authority = {
            "document": {
                "id": "SCF-CORE",
                "title": "SCF Bootstrap Foundational Authority",
                "authority_role": "bootstrap foundational authority",
                "authority_scope": "scope",
                "field_semantics": {
                    "descriptive_metadata": [
                        "document.id",
                        "document.title",
                        "scf.name",
                        "scf.abbreviation",
                        "scf.version",
                        "scf.status",
                        "scf.purpose",
                        "scf.contract_foundation.name",
                        "scf.contract_foundation.role",
                    ],
                    "normative_authority": [
                        "document.authority_role",
                        "document.authority_scope",
                        "document.field_semantics",
                        "architecture",
                        "authority_model",
                        "mutation_model",
                        "context_model",
                        "specification_model",
                        "construction_model",
                        "foundation_model",
                        "controlled_vocabulary",
                        "conformance_minimum",
                    ],
                    "interpretation": "meaning",
                },
            },
            "scf": {
                "name": "Session Continuity Framework",
                "abbreviation": "SCF",
                "version": "1.0.1-proposed-core",
                "status": "proposed",
                "purpose": "purpose",
                "contract_foundation": {
                    "name": "SCF Contract Foundation",
                    "role": "role",
                },
            },
            "architecture": {},
            "authority_model": {},
            "mutation_model": {},
            "context_model": {},
            "specification_model": {},
            "construction_model": {},
            "foundation_model": {},
            "controlled_vocabulary": {},
            "conformance_minimum": [],
        }
        self.bootstrap = {
            "id": "SCF-BOOTSTRAP-001",
            "status": "consumed-by-bootstrap-commit",
            "allowed_outputs": [
                ".gitignore",
                "README.md",
                "VERSION",
                "authority/core/SCF-CORE.json",
                "authority/core/SCF-CORE.sha256",
                "authority/core/manifest.json",
                "bootstrap/BOOTSTRAP-SCOPE.json",
                "bootstrap/INITIAL-DEVELOPMENT-PROCESS.md",
                "bootstrap/README.md",
                "planning/README.md",
            ],
            "expires_after": "creation of the SCF bootstrap commit",
        }
        self.refresh_authority()
        level0_source = REPOSITORY_ROOT / "authority/level-0"
        for name in ("SCF-LEVEL-0.json", "SCF-LEVEL-0.schema.json", "SCF-LEVEL-0.sha256", "SCF-LEVEL-0.schema.sha256", "manifest.json", "README.md"):
            source = level0_source / name
            if source.is_file():
                self.write(f"authority/level-0/{name}", source.read_bytes())
        authority_readme = REPOSITORY_ROOT / "authority/README.md"
        if authority_readme.is_file():
            self.write("authority/README.md", authority_readme.read_bytes())
        self.write_json("bootstrap/BOOTSTRAP-SCOPE.json", self.bootstrap)
        self.track_all()

    def close(self) -> None:
        self.temp.cleanup()

    def write(self, relative: str, content: str | bytes) -> None:
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")

    def write_json(self, relative: str, value: object) -> None:
        self.write(relative, json.dumps(value, indent=2) + "\n")

    def refresh_authority(self) -> None:
        self.write_json("authority/core/SCF-CORE.json", self.authority)
        raw = (self.root / "authority/core/SCF-CORE.json").read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        self.write(
            "authority/core/SCF-CORE.sha256",
            f"{digest}  authority/core/SCF-CORE.json\n",
        )
        manifest = {
            "document_id": self.authority["document"]["id"],
            "title": self.authority["document"]["title"],
            "framework": {
                "name": self.authority["scf"]["name"],
                "abbreviation": self.authority["scf"]["abbreviation"],
            },
            "foundation": self.authority["scf"]["contract_foundation"]["name"],
            "version": self.authority["scf"]["version"],
            "status": self.authority["scf"]["status"],
            "canonical_path": "authority/core/SCF-CORE.json",
            "sha256": digest,
        }
        self.write_json("authority/core/manifest.json", manifest)

    def track_all(self) -> None:
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)

    def context(self) -> ValidationContext:
        return ValidationContext.create(self.root)


class ValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = RepositoryFixture()

    def tearDown(self) -> None:
        self.repo.close()

    def ids(self, diagnostics) -> set[str]:
        return {item.diagnostic_id for item in diagnostics}

    def test_valid_repository_passes_all_checks(self) -> None:
        context = self.repo.context()
        for check in REGISTERED_CHECKS:
            self.assertEqual([], check.function(context), check.check_id)

    def test_untracked_json_is_outside_default_scope(self) -> None:
        self.repo.write("untracked.json", "{bad")
        self.assertEqual([], check_json_files(self.repo.context()))

    def test_working_tree_edit_is_validated(self) -> None:
        self.repo.write("authority/core/manifest.json", "{bad")
        self.assertIn("SCF-JSON-SYNTAX", self.ids(check_json_files(self.repo.context())))

    def test_invalid_utf8_fails(self) -> None:
        self.repo.write("authority/core/manifest.json", b"\xff")
        self.assertIn("SCF-JSON-UTF8", self.ids(check_json_files(self.repo.context())))

    def test_duplicate_key_at_nested_level_fails(self) -> None:
        self.repo.write("authority/core/manifest.json", '{"a":{"x":1,"x":2}}\n')
        self.assertIn("SCF-JSON-DUPLICATE", self.ids(check_json_files(self.repo.context())))

    def test_malformed_checksum_record_fails(self) -> None:
        self.repo.write("authority/core/SCF-CORE.sha256", "bad\n")
        self.assertIn("SCF-CHECKSUM-FORMAT", self.ids(check_checksum(self.repo.context())))

    def test_missing_checksum_target_fails(self) -> None:
        digest = "0" * 64
        self.repo.write("authority/core/SCF-CORE.sha256", f"{digest}  missing.json\n")
        self.assertIn("SCF-CHECKSUM-TARGET", self.ids(check_checksum(self.repo.context())))

    def test_checksum_mismatch_fails(self) -> None:
        self.repo.write(
            "authority/core/SCF-CORE.sha256",
            f"{'0' * 64}  authority/core/SCF-CORE.json\n",
        )
        self.assertIn("SCF-CHECKSUM-MISMATCH", self.ids(check_checksum(self.repo.context())))

    def test_unsafe_checksum_path_fails(self) -> None:
        self.repo.write(
            "authority/core/SCF-CORE.sha256",
            f"{'0' * 64}  ../outside.json\n",
        )
        self.assertIn("SCF-PATH-001", self.ids(check_checksum(self.repo.context())))

    def test_missing_manifest_field_fails(self) -> None:
        manifest = json.loads((self.repo.root / "authority/core/manifest.json").read_text())
        del manifest["version"]
        self.repo.write_json("authority/core/manifest.json", manifest)
        self.assertIn("SCF-MANIFEST-MISSING", self.ids(check_manifest(self.repo.context())))

    def test_manifest_metadata_mismatch_fails(self) -> None:
        manifest = json.loads((self.repo.root / "authority/core/manifest.json").read_text())
        manifest["title"] = "wrong"
        self.repo.write_json("authority/core/manifest.json", manifest)
        self.assertIn("SCF-MANIFEST-MISMATCH", self.ids(check_manifest(self.repo.context())))

    def test_manifest_digest_against_bytes_fails(self) -> None:
        manifest = json.loads((self.repo.root / "authority/core/manifest.json").read_text())
        manifest["sha256"] = "0" * 64
        self.repo.write_json("authority/core/manifest.json", manifest)
        self.assertIn("SCF-MANIFEST-DIGEST-MISMATCH", self.ids(check_manifest(self.repo.context())))

    def test_manifest_digest_against_checksum_fails(self) -> None:
        self.repo.write(
            "authority/core/SCF-CORE.sha256",
            f"{'0' * 64}  authority/core/SCF-CORE.json\n",
        )
        self.assertIn(
            "SCF-MANIFEST-CHECKSUM-MISMATCH",
            self.ids(check_manifest(self.repo.context())),
        )

    def test_checksum_target_against_canonical_path_fails(self) -> None:
        raw = (self.repo.root / "authority/core/SCF-CORE.json").read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        self.repo.write("other.json", raw)
        self.repo.write("authority/core/SCF-CORE.sha256", f"{digest}  other.json\n")
        self.assertIn(
            "SCF-MANIFEST-CHECKSUM-PATH",
            self.ids(check_manifest(self.repo.context())),
        )

    def test_invalid_canonical_path_fails(self) -> None:
        manifest = json.loads((self.repo.root / "authority/core/manifest.json").read_text())
        manifest["canonical_path"] = "../SCF-CORE.json"
        self.repo.write_json("authority/core/manifest.json", manifest)
        diagnostics = check_manifest(self.repo.context())
        self.assertTrue({"SCF-PATH-001", "SCF-MANIFEST-CANONICAL"} & self.ids(diagnostics))

    def test_valid_semantic_paths_pass(self) -> None:
        self.assertEqual([], check_semantic_paths(self.repo.context()))

    def test_malformed_semantic_path_fails(self) -> None:
        self.repo.authority["document"]["field_semantics"]["descriptive_metadata"].append("scf..name")
        self.repo.refresh_authority()
        self.assertIn("SCF-SEMANTIC-SYNTAX", self.ids(check_semantic_paths(self.repo.context())))

    def test_missing_semantic_segment_fails(self) -> None:
        self.repo.authority["document"]["field_semantics"]["descriptive_metadata"].append("scf.missing")
        self.repo.refresh_authority()
        self.assertIn("SCF-SEMANTIC-MISSING", self.ids(check_semantic_paths(self.repo.context())))

    def test_duplicate_semantic_declaration_fails(self) -> None:
        self.repo.authority["document"]["field_semantics"]["descriptive_metadata"].append("scf.name")
        self.repo.refresh_authority()
        self.assertIn("SCF-SEMANTIC-DUPLICATE", self.ids(check_semantic_paths(self.repo.context())))

    def test_semantic_overlap_fails(self) -> None:
        self.repo.authority["document"]["field_semantics"]["normative_authority"].append("scf.name")
        self.repo.refresh_authority()
        self.assertIn("SCF-SEMANTIC-OVERLAP", self.ids(check_semantic_paths(self.repo.context())))

    def test_missing_required_artifact_fails(self) -> None:
        (self.repo.root / "VERSION").unlink()
        self.assertIn("SCF-REPO-MISSING", self.ids(check_repository(self.repo.context())))

    def test_missing_governed_planning_artifacts_fail(self) -> None:
        required = (
            ".github/ISSUE_TEMPLATE/governed-work.md",
            "docs/GOVERNED-ISSUE-PLANNING.md",
            "docs/templates/GOVERNED-DETAILED-SCOPE.md",
            "docs/templates/GOVERNED-WORK-BREAKDOWN.md",
        )
        for relative in required:
            with self.subTest(relative=relative):
                target = self.repo.root / relative
                original = target.read_bytes()
                target.unlink()
                diagnostics = check_repository(self.repo.context())
                self.assertTrue(
                    any(
                        item.diagnostic_id == "SCF-REPO-MISSING"
                        and item.path == relative
                        for item in diagnostics
                    )
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(original)

    def test_bootstrap_status_fails(self) -> None:
        self.repo.bootstrap["status"] = "active"
        self.repo.write_json("bootstrap/BOOTSTRAP-SCOPE.json", self.repo.bootstrap)
        self.assertIn("SCF-BOOTSTRAP-STATUS", self.ids(check_repository(self.repo.context())))

    def test_invalid_invocation_root_returns_two(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(2, main(Path(directory), []))

    def test_unknown_check_returns_two(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(2, main(self.repo.root, ["--check", "NOPE"]))

    def test_wrapper_outside_repository_returns_two_without_traceback(self) -> None:
        wrapper = REPOSITORY_ROOT / "scripts/validate"
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(wrapper)],
                cwd=directory,
                text=True,
                capture_output=True,
            )
        self.assertEqual(2, result.returncode)
        self.assertIn("Validation invocation failed", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_list_checks_returns_zero_and_lists_registry(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(self.repo.root, ["--list-checks"])
        self.assertEqual(0, status)
        for check in REGISTERED_CHECKS:
            self.assertIn(check.check_id, output.getvalue())

    def test_selected_valid_check_returns_zero(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(self.repo.root, ["--check", "SCF-JSON-001"])
        self.assertEqual(0, status)
        self.assertIn("PASS SCF-JSON-001", output.getvalue())
        self.assertNotIn("SCF-CHECKSUM-001", output.getvalue())

    def test_repository_error_returns_one(self) -> None:
        self.repo.write("authority/core/manifest.json", "{bad")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(1, main(self.repo.root, ["--check", "SCF-JSON-001"]))

    def test_internal_failure_returns_two_without_traceback(self) -> None:
        broken = Check("SCF-TEST-001", "broken", lambda context: (_ for _ in ()).throw(RuntimeError("boom")))
        with mock.patch("scf_validation.cli.REGISTERED_CHECKS", (broken,)):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = main(self.repo.root, [])
        self.assertEqual(2, status)
        self.assertIn("Internal validator failure", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())


if __name__ == "__main__":
    unittest.main()
