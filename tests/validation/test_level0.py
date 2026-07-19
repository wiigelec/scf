"""Focused tests for Level 0 authority validation."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = "authority/level-0/SCF-LEVEL-0.json"
MANIFEST = "authority/level-0/manifest.json"
CHECKSUM = "authority/level-0/SCF-LEVEL-0.sha256"
SCHEMA = "authority/level-0/SCF-LEVEL-0.schema.json"
SCHEMA_CHECKSUM = "authority/level-0/SCF-LEVEL-0.schema.sha256"


class Level0Tests(unittest.TestCase):
    def repository(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name) / "repo"
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        return temporary, root

    def run_check(self, root):
        return subprocess.run(["./scripts/validate", "--check", "SCF-LEVEL0-001"], cwd=root, text=True, capture_output=True)

    def write_json(self, root, relative, value):
        (root / relative).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def refresh(self, root):
        digest = hashlib.sha256((root / AUTHORITY).read_bytes()).hexdigest()
        (root / CHECKSUM).write_text(f"{digest}  {AUTHORITY}\n", encoding="utf-8")
        manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
        manifest["sha256"] = digest
        self.write_json(root, MANIFEST, manifest)

    def test_valid_level0(self):
        temporary, root = self.repository()
        self.addCleanup(temporary.cleanup)
        result = self.run_check(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_semantic_overlap_fails(self):
        temporary, root = self.repository()
        self.addCleanup(temporary.cleanup)
        value = json.loads((root / AUTHORITY).read_text(encoding="utf-8"))
        value["document"]["field_semantics"]["descriptive_metadata"].append("architecture_invariants")
        self.write_json(root, AUTHORITY, value)
        self.refresh(root)
        result = self.run_check(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("SCF-LEVEL0-SEMANTIC-OVERLAP", result.stdout)

    def test_normative_parent_fails(self):
        temporary, root = self.repository()
        self.addCleanup(temporary.cleanup)
        value = json.loads((root / AUTHORITY).read_text(encoding="utf-8"))
        value["specification_hierarchy"]["normative_parent"] = "SCF-CORE"
        self.write_json(root, AUTHORITY, value)
        self.refresh(root)
        result = self.run_check(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("SCF-LEVEL0-HIERARCHY", result.stdout)

    def test_manifest_digest_fails(self):
        temporary, root = self.repository()
        self.addCleanup(temporary.cleanup)
        value = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
        value["sha256"] = "0" * 64
        self.write_json(root, MANIFEST, value)
        result = self.run_check(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("SCF-LEVEL0-MANIFEST-DIGEST", result.stdout)

    def test_unsafe_provenance_fails(self):
        temporary, root = self.repository()
        self.addCleanup(temporary.cleanup)
        value = json.loads((root / AUTHORITY).read_text(encoding="utf-8"))
        value["provenance"]["source_document"] = "../SCF-CORE.json"
        self.write_json(root, AUTHORITY, value)
        self.refresh(root)
        result = self.run_check(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("SCF-PATH-001", result.stdout)

    def refresh_schema(self, root):
        digest = hashlib.sha256((root / SCHEMA).read_bytes()).hexdigest()
        (root / SCHEMA_CHECKSUM).write_text(f"{digest}  {SCHEMA}\n", encoding="utf-8")
        manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
        manifest["schema"]["sha256"] = digest
        self.write_json(root, MANIFEST, manifest)

    def test_missing_schema_fails(self):
        temporary, root = self.repository()
        self.addCleanup(temporary.cleanup)
        (root / SCHEMA).unlink()
        result = self.run_check(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("SCF-REPO-002", result.stdout)

    def test_schema_dialect_fails(self):
        temporary, root = self.repository()
        self.addCleanup(temporary.cleanup)
        value = json.loads((root / SCHEMA).read_text(encoding="utf-8"))
        value["$schema"] = "https://json-schema.org/draft/2019-09/schema"
        self.write_json(root, SCHEMA, value)
        self.refresh_schema(root)
        result = self.run_check(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("SCF-LEVEL0-SCHEMA-DIALECT", result.stdout)

    def test_schema_identity_fails(self):
        temporary, root = self.repository()
        self.addCleanup(temporary.cleanup)
        value = json.loads((root / SCHEMA).read_text(encoding="utf-8"))
        value["$id"] = "urn:wrong"
        self.write_json(root, SCHEMA, value)
        self.refresh_schema(root)
        result = self.run_check(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("SCF-LEVEL0-SCHEMA-ID", result.stdout)

    def test_authority_schema_reference_fails(self):
        temporary, root = self.repository()
        self.addCleanup(temporary.cleanup)
        value = json.loads((root / AUTHORITY).read_text(encoding="utf-8"))
        value["$schema"] = "urn:wrong"
        self.write_json(root, AUTHORITY, value)
        self.refresh(root)
        result = self.run_check(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("SCF-LEVEL0-SCHEMA-REFERENCE", result.stdout)

    def test_schema_digest_fails(self):
        temporary, root = self.repository()
        self.addCleanup(temporary.cleanup)
        value = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
        value["schema"]["sha256"] = "0" * 64
        self.write_json(root, MANIFEST, value)
        result = self.run_check(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("SCF-LEVEL0-SCHEMA-MANIFEST-DIGEST", result.stdout)

    def test_additional_property_fails_schema_conformance(self):
        temporary, root = self.repository()
        self.addCleanup(temporary.cleanup)
        value = json.loads((root / AUTHORITY).read_text(encoding="utf-8"))
        value["unexpected"] = True
        self.write_json(root, AUTHORITY, value)
        self.refresh(root)
        result = self.run_check(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("SCF-LEVEL0-SCHEMA-CONFORMANCE", result.stdout)

    def test_missing_required_property_fails_schema_conformance(self):
        temporary, root = self.repository()
        self.addCleanup(temporary.cleanup)
        value = json.loads((root / AUTHORITY).read_text(encoding="utf-8"))
        del value["document"]["authority_scope"]
        self.write_json(root, AUTHORITY, value)
        self.refresh(root)
        result = self.run_check(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("SCF-LEVEL0-SCHEMA-CONFORMANCE", result.stdout)

    def test_unsupported_schema_keyword_fails(self):
        temporary, root = self.repository()
        self.addCleanup(temporary.cleanup)
        value = json.loads((root / SCHEMA).read_text(encoding="utf-8"))
        value["allOf"] = []
        self.write_json(root, SCHEMA, value)
        self.refresh_schema(root)
        result = self.run_check(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("SCF-LEVEL0-SCHEMA-KEYWORD", result.stdout)
