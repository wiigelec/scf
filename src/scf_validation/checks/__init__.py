"""Explicitly registered SCF repository checks."""

from __future__ import annotations

from ..registry import Check
from .checksums import check_checksum
from .json_files import check_json_files
from .level0 import check_level0
from .manifests import check_manifest
from .repository import check_repository
from .semantic_paths import check_semantic_paths

REGISTERED_CHECKS = (
    Check("SCF-JSON-001", "tracked JSON integrity", check_json_files),
    Check("SCF-CHECKSUM-001", "canonical checksum", check_checksum),
    Check("SCF-MANIFEST-001", "authority manifest", check_manifest),
    Check("SCF-SEMANTIC-001", "authority semantic paths", check_semantic_paths),
    Check("SCF-LEVEL0-001", "durable Level 0 authority", check_level0),
    Check("SCF-REPO-001", "required repository artifacts", check_repository),
)
