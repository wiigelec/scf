"""Validation for the canonical durable Level 0 authority."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from ..context import InputProblem, ValidationContext
from ..diagnostics import Diagnostic, Severity
from .common import from_problem

AUTHORITY_PATH = "authority/level-0/SCF-LEVEL-0.json"
CHECKSUM_PATH = "authority/level-0/SCF-LEVEL-0.sha256"
MANIFEST_PATH = "authority/level-0/manifest.json"
SOURCE_PATH = "authority/core/SCF-CORE.json"
_RECORD = re.compile(r"([0-9a-fA-F]{64})  ([^\r\n]+)\n?\Z")
_HEX64 = re.compile(r"[0-9a-fA-F]{64}\Z")


def diagnostic(identifier: str, message: str, path: str = AUTHORITY_PATH, field: str | None = None) -> Diagnostic:
    return Diagnostic(identifier, Severity.ERROR, message, path, field)


def lookup(value: Any, semantic_path: str) -> Any:
    current = value
    for segment in semantic_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            raise KeyError(semantic_path)
        current = current[segment]
    return current


def check_level0(context: ValidationContext) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    try:
        authority = context.parse_json(AUTHORITY_PATH)
        manifest = context.parse_json(MANIFEST_PATH)
        checksum_raw = context.read_bytes(CHECKSUM_PATH)
    except InputProblem as problem:
        return [from_problem(problem)]

    if not isinstance(authority, dict):
        return [diagnostic("SCF-LEVEL0-STRUCTURE", "Level 0 authority must be an object")]
    if not isinstance(manifest, dict):
        return [diagnostic("SCF-LEVEL0-MANIFEST-STRUCTURE", "Level 0 manifest must be an object", MANIFEST_PATH)]

    document = authority.get("document")
    scf = authority.get("scf")
    provenance = authority.get("provenance")
    hierarchy = authority.get("specification_hierarchy")
    invariants = authority.get("architecture_invariants")
    for field, value in (("document", document), ("scf", scf), ("provenance", provenance), ("specification_hierarchy", hierarchy)):
        if not isinstance(value, dict):
            diagnostics.append(diagnostic("SCF-LEVEL0-STRUCTURE", f"{field!r} must be an object", field=field))
    if not isinstance(invariants, list) or not invariants:
        diagnostics.append(diagnostic("SCF-LEVEL0-INVARIANTS", "architecture_invariants must be a nonempty array", field="architecture_invariants"))
    if diagnostics:
        return diagnostics

    assert isinstance(document, dict)
    assert isinstance(scf, dict)
    assert isinstance(provenance, dict)
    assert isinstance(hierarchy, dict)
    assert isinstance(invariants, list)

    expected = (
        ("document.id", document.get("id"), "SCF-LEVEL-0"),
        ("document.title", document.get("title"), "SCF Level 0 Authority"),
        ("document.authority_role", document.get("authority_role"), "durable Level 0 root authority"),
        ("scf.name", scf.get("name"), "Session Continuity Framework"),
        ("scf.abbreviation", scf.get("abbreviation"), "SCF"),
        ("scf.contract_foundation", scf.get("contract_foundation"), "SCF Contract Foundation"),
        ("scf.version", scf.get("version"), "1.0.0"),
        ("scf.status", scf.get("status"), "proposed"),
        ("provenance.source_document", provenance.get("source_document"), SOURCE_PATH),
        ("provenance.source_document_id", provenance.get("source_document_id"), "SCF-CORE"),
        ("provenance.relationship", provenance.get("relationship"), "derived-from-bootstrap-foundational-authority"),
    )
    for field, actual, required in expected:
        if actual != required:
            diagnostics.append(diagnostic("SCF-LEVEL0-METADATA", f"value {actual!r} does not match required value {required!r}", field=field))

    if hierarchy.get("level") != 0:
        diagnostics.append(diagnostic("SCF-LEVEL0-HIERARCHY", "specification_hierarchy.level must be 0", field="specification_hierarchy.level"))
    if hierarchy.get("normative_parent") is not None:
        diagnostics.append(diagnostic("SCF-LEVEL0-HIERARCHY", "Level 0 must not declare a normative parent", field="specification_hierarchy.normative_parent"))

    ids: set[str] = set()
    for index, invariant in enumerate(invariants):
        field = f"architecture_invariants[{index}]"
        if not isinstance(invariant, dict):
            diagnostics.append(diagnostic("SCF-LEVEL0-INVARIANTS", "each invariant must be an object", field=field))
            continue
        identifier = invariant.get("id")
        statement = invariant.get("statement")
        if not isinstance(identifier, str) or not identifier:
            diagnostics.append(diagnostic("SCF-LEVEL0-INVARIANTS", "invariant id must be nonempty", field=f"{field}.id"))
        elif identifier in ids:
            diagnostics.append(diagnostic("SCF-LEVEL0-INVARIANTS", f"duplicate invariant id {identifier!r}", field=f"{field}.id"))
        else:
            ids.add(identifier)
        if not isinstance(statement, str) or not statement.strip():
            diagnostics.append(diagnostic("SCF-LEVEL0-INVARIANTS", "invariant statement must be nonempty", field=f"{field}.statement"))

    semantics = document.get("field_semantics")
    sets: dict[str, set[str]] = {}
    if not isinstance(semantics, dict):
        diagnostics.append(diagnostic("SCF-LEVEL0-SEMANTIC", "document.field_semantics must be an object", field="document.field_semantics"))
    else:
        for name in ("descriptive_metadata", "normative_authority"):
            values = semantics.get(name)
            if not isinstance(values, list):
                diagnostics.append(diagnostic("SCF-LEVEL0-SEMANTIC", f"{name} must be an array", field=f"document.field_semantics.{name}"))
                continue
            seen: set[str] = set()
            sets[name] = seen
            for index, semantic_path in enumerate(values):
                field = f"document.field_semantics.{name}[{index}]"
                if not isinstance(semantic_path, str) or not semantic_path or any(not part for part in semantic_path.split(".")):
                    diagnostics.append(diagnostic("SCF-LEVEL0-SEMANTIC", "semantic path must be a nonempty dot-separated string", field=field))
                    continue
                if semantic_path in seen:
                    diagnostics.append(diagnostic("SCF-LEVEL0-SEMANTIC", f"duplicate semantic path {semantic_path!r}", field=field))
                    continue
                seen.add(semantic_path)
                try:
                    lookup(authority, semantic_path)
                except KeyError:
                    diagnostics.append(diagnostic("SCF-LEVEL0-SEMANTIC", f"semantic path {semantic_path!r} does not resolve", field=field))
        for semantic_path in sorted(sets.get("descriptive_metadata", set()) & sets.get("normative_authority", set())):
            diagnostics.append(diagnostic("SCF-LEVEL0-SEMANTIC-OVERLAP", f"semantic path {semantic_path!r} is both descriptive and normative", field="document.field_semantics"))

    try:
        source_file = context.safe_path(str(provenance.get("source_document")))
        if not source_file.is_file():
            diagnostics.append(diagnostic("SCF-LEVEL0-PROVENANCE", "provenance source is missing", field="provenance.source_document"))
        else:
            source = context.parse_json(SOURCE_PATH)
            source_id = source.get("document", {}).get("id") if isinstance(source, dict) else None
            if source_id != provenance.get("source_document_id"):
                diagnostics.append(diagnostic("SCF-LEVEL0-PROVENANCE", "source identity does not match provenance", field="provenance.source_document_id"))
    except InputProblem as problem:
        diagnostics.append(from_problem(problem))

    required_manifest = ("document_id", "title", "framework", "foundation", "level", "version", "status", "authority_role", "canonical_path", "provenance_source", "sha256")
    missing = [field for field in required_manifest if field not in manifest]
    for field in missing:
        diagnostics.append(diagnostic("SCF-LEVEL0-MANIFEST-MISSING", f"missing manifest field {field!r}", MANIFEST_PATH, field))
    if missing:
        return diagnostics

    framework = manifest.get("framework")
    comparisons = (
        ("document_id", manifest.get("document_id"), document.get("id")),
        ("title", manifest.get("title"), document.get("title")),
        ("framework.name", framework.get("name") if isinstance(framework, dict) else None, scf.get("name")),
        ("framework.abbreviation", framework.get("abbreviation") if isinstance(framework, dict) else None, scf.get("abbreviation")),
        ("foundation", manifest.get("foundation"), scf.get("contract_foundation")),
        ("level", manifest.get("level"), hierarchy.get("level")),
        ("version", manifest.get("version"), scf.get("version")),
        ("status", manifest.get("status"), scf.get("status")),
        ("authority_role", manifest.get("authority_role"), document.get("authority_role")),
        ("canonical_path", manifest.get("canonical_path"), AUTHORITY_PATH),
        ("provenance_source", manifest.get("provenance_source"), SOURCE_PATH),
    )
    for field, actual, required in comparisons:
        if actual != required:
            diagnostics.append(diagnostic("SCF-LEVEL0-MANIFEST-MISMATCH", f"manifest value {actual!r} does not match {required!r}", MANIFEST_PATH, field))

    try:
        checksum_text = checksum_raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return diagnostics + [diagnostic("SCF-LEVEL0-CHECKSUM", f"invalid UTF-8 at byte {exc.start}", CHECKSUM_PATH)]
    match = _RECORD.fullmatch(checksum_text)
    if not match:
        return diagnostics + [diagnostic("SCF-LEVEL0-CHECKSUM", "malformed checksum record", CHECKSUM_PATH)]

    checksum_digest = match.group(1).lower()
    checksum_target = match.group(2)
    actual_digest = hashlib.sha256(context.read_bytes(AUTHORITY_PATH)).hexdigest()
    manifest_digest = manifest.get("sha256")
    if checksum_target != AUTHORITY_PATH:
        diagnostics.append(diagnostic("SCF-LEVEL0-CHECKSUM-TARGET", f"checksum target must be {AUTHORITY_PATH!r}", CHECKSUM_PATH))
    if not isinstance(manifest_digest, str) or not _HEX64.fullmatch(manifest_digest):
        diagnostics.append(diagnostic("SCF-LEVEL0-MANIFEST-DIGEST", "manifest sha256 must be 64 hexadecimal characters", MANIFEST_PATH, "sha256"))
    else:
        manifest_digest = manifest_digest.lower()
        if manifest_digest != actual_digest:
            diagnostics.append(diagnostic("SCF-LEVEL0-MANIFEST-DIGEST", "manifest digest does not match canonical bytes", MANIFEST_PATH, "sha256"))
        if manifest_digest != checksum_digest:
            diagnostics.append(diagnostic("SCF-LEVEL0-DIGEST-CONSISTENCY", "manifest and checksum digests do not match", MANIFEST_PATH, "sha256"))
    if checksum_digest != actual_digest:
        diagnostics.append(diagnostic("SCF-LEVEL0-CHECKSUM-MISMATCH", "checksum digest does not match canonical bytes", CHECKSUM_PATH))
    return diagnostics
