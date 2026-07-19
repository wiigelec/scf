"""Validation for the canonical durable Level 0 authority and schema."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from ..context import InputProblem, ValidationContext
from ..diagnostics import Diagnostic, Severity
from .common import from_problem

AUTHORITY_PATH = "authority/level-0/SCF-LEVEL-0.json"
CHECKSUM_PATH = "authority/level-0/SCF-LEVEL-0.sha256"
SCHEMA_PATH = "authority/level-0/SCF-LEVEL-0.schema.json"
SCHEMA_CHECKSUM_PATH = "authority/level-0/SCF-LEVEL-0.schema.sha256"
MANIFEST_PATH = "authority/level-0/manifest.json"
SOURCE_PATH = "authority/core/SCF-CORE.json"
SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_ID = "https://wiigelec.github.io/scf/schemas/SCF-LEVEL-0.schema.json"
_RECORD = re.compile(r"([0-9a-fA-F]{64})  ([^\r\n]+)\n?\Z")
_HEX64 = re.compile(r"[0-9a-fA-F]{64}\Z")
_SUPPORTED_SCHEMA_KEYWORDS = {
    "$schema", "$id", "title", "description", "type", "required", "properties",
    "additionalProperties", "const", "enum", "pattern", "minLength", "minItems",
    "items", "uniqueItems",
}


def diagnostic(identifier: str, message: str, path: str = AUTHORITY_PATH, field: str | None = None) -> Diagnostic:
    return Diagnostic(identifier, Severity.ERROR, message, path, field)


def lookup(value: Any, semantic_path: str) -> Any:
    current = value
    for segment in semantic_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            raise KeyError(semantic_path)
        current = current[segment]
    return current


def _schema_location(parts: list[str]) -> str:
    return "$" + "".join(f".{part}" if part.isidentifier() else f"[{part}]" for part in parts)


def _instance_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return type(value).__name__


def _validate_schema_definition(schema: Any, parts: list[str], diagnostics: list[Diagnostic]) -> None:
    location = _schema_location(parts)
    if not isinstance(schema, dict):
        diagnostics.append(diagnostic("SCF-LEVEL0-SCHEMA-DEFINITION", "schema node must be an object", SCHEMA_PATH, location))
        return
    for keyword in schema:
        if keyword not in _SUPPORTED_SCHEMA_KEYWORDS:
            diagnostics.append(diagnostic("SCF-LEVEL0-SCHEMA-KEYWORD", f"unsupported schema keyword {keyword!r}", SCHEMA_PATH, location))
    properties = schema.get("properties")
    if properties is not None:
        if not isinstance(properties, dict):
            diagnostics.append(diagnostic("SCF-LEVEL0-SCHEMA-DEFINITION", "properties must be an object", SCHEMA_PATH, f"{location}.properties"))
        else:
            for name, subschema in properties.items():
                _validate_schema_definition(subschema, parts + ["properties", str(name)], diagnostics)
    items = schema.get("items")
    if items is not None:
        _validate_schema_definition(items, parts + ["items"], diagnostics)


def _matches_type(value: Any, expected: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(expected, False)


def _validate_instance(instance: Any, schema: dict[str, Any], path: str, diagnostics: list[Diagnostic]) -> None:
    expected_type = schema.get("type")
    if expected_type is not None:
        if not isinstance(expected_type, str) or not _matches_type(instance, expected_type):
            diagnostics.append(diagnostic(
                "SCF-LEVEL0-SCHEMA-CONFORMANCE",
                f"{path} has type {_instance_type(instance)!r}; expected {expected_type!r}",
                AUTHORITY_PATH,
                path,
            ))
            return

    if "const" in schema and instance != schema["const"]:
        diagnostics.append(diagnostic("SCF-LEVEL0-SCHEMA-CONFORMANCE", f"{path} must equal {schema['const']!r}", AUTHORITY_PATH, path))
    enum = schema.get("enum")
    if isinstance(enum, list) and instance not in enum:
        diagnostics.append(diagnostic("SCF-LEVEL0-SCHEMA-CONFORMANCE", f"{path} must be one of {enum!r}", AUTHORITY_PATH, path))

    if isinstance(instance, str):
        minimum = schema.get("minLength")
        if isinstance(minimum, int) and len(instance) < minimum:
            diagnostics.append(diagnostic("SCF-LEVEL0-SCHEMA-CONFORMANCE", f"{path} is shorter than minLength {minimum}", AUTHORITY_PATH, path))
        pattern = schema.get("pattern")
        if isinstance(pattern, str):
            try:
                matched = re.search(pattern, instance)
            except re.error as exc:
                diagnostics.append(diagnostic("SCF-LEVEL0-SCHEMA-DEFINITION", f"invalid regular expression: {exc}", SCHEMA_PATH, path))
            else:
                if matched is None:
                    diagnostics.append(diagnostic("SCF-LEVEL0-SCHEMA-CONFORMANCE", f"{path} does not match required pattern", AUTHORITY_PATH, path))

    if isinstance(instance, list):
        minimum = schema.get("minItems")
        if isinstance(minimum, int) and len(instance) < minimum:
            diagnostics.append(diagnostic("SCF-LEVEL0-SCHEMA-CONFORMANCE", f"{path} has fewer than {minimum} items", AUTHORITY_PATH, path))
        if schema.get("uniqueItems") is True:
            serialized = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in instance]
            if len(serialized) != len(set(serialized)):
                diagnostics.append(diagnostic("SCF-LEVEL0-SCHEMA-CONFORMANCE", f"{path} items must be unique", AUTHORITY_PATH, path))
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(instance):
                _validate_instance(item, item_schema, f"{path}[{index}]", diagnostics)

    if isinstance(instance, dict):
        required = schema.get("required")
        if isinstance(required, list):
            for name in required:
                if isinstance(name, str) and name not in instance:
                    diagnostics.append(diagnostic("SCF-LEVEL0-SCHEMA-CONFORMANCE", f"{path} is missing required property {name!r}", AUTHORITY_PATH, f"{path}.{name}"))
        properties = schema.get("properties")
        if isinstance(properties, dict):
            for name, value in instance.items():
                subschema = properties.get(name)
                if isinstance(subschema, dict):
                    _validate_instance(value, subschema, f"{path}.{name}", diagnostics)
                elif schema.get("additionalProperties") is False:
                    diagnostics.append(diagnostic("SCF-LEVEL0-SCHEMA-CONFORMANCE", f"{path} contains unexpected property {name!r}", AUTHORITY_PATH, f"{path}.{name}"))


def _validate_checksum(
    context: ValidationContext,
    raw: bytes,
    checksum_path: str,
    target_path: str,
    manifest_digest: Any,
    prefix: str,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [diagnostic(f"{prefix}-CHECKSUM", f"invalid UTF-8 at byte {exc.start}", checksum_path)]
    match = _RECORD.fullmatch(text)
    if not match:
        return [diagnostic(f"{prefix}-CHECKSUM", "malformed checksum record", checksum_path)]
    checksum_digest = match.group(1).lower()
    checksum_target = match.group(2)
    actual_digest = hashlib.sha256(context.read_bytes(target_path)).hexdigest()
    if checksum_target != target_path:
        diagnostics.append(diagnostic(f"{prefix}-CHECKSUM-TARGET", f"checksum target must be {target_path!r}", checksum_path))
    if not isinstance(manifest_digest, str) or not _HEX64.fullmatch(manifest_digest):
        diagnostics.append(diagnostic(f"{prefix}-MANIFEST-DIGEST", "manifest sha256 must be 64 hexadecimal characters", MANIFEST_PATH))
    else:
        normalized = manifest_digest.lower()
        if normalized != actual_digest:
            diagnostics.append(diagnostic(f"{prefix}-MANIFEST-DIGEST", "manifest digest does not match canonical bytes", MANIFEST_PATH))
        if normalized != checksum_digest:
            diagnostics.append(diagnostic(f"{prefix}-DIGEST-CONSISTENCY", "manifest and checksum digests do not match", MANIFEST_PATH))
    if checksum_digest != actual_digest:
        diagnostics.append(diagnostic(f"{prefix}-CHECKSUM-MISMATCH", "checksum digest does not match canonical bytes", checksum_path))
    return diagnostics


def check_level0(context: ValidationContext) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    try:
        authority = context.parse_json(AUTHORITY_PATH)
        schema = context.parse_json(SCHEMA_PATH)
        manifest = context.parse_json(MANIFEST_PATH)
        checksum_raw = context.read_bytes(CHECKSUM_PATH)
        schema_checksum_raw = context.read_bytes(SCHEMA_CHECKSUM_PATH)
    except InputProblem as problem:
        return [from_problem(problem)]

    if not isinstance(authority, dict):
        return [diagnostic("SCF-LEVEL0-STRUCTURE", "Level 0 authority must be an object")]
    if not isinstance(schema, dict):
        return [diagnostic("SCF-LEVEL0-SCHEMA-STRUCTURE", "Level 0 schema must be an object", SCHEMA_PATH)]
    if not isinstance(manifest, dict):
        return [diagnostic("SCF-LEVEL0-MANIFEST-STRUCTURE", "Level 0 manifest must be an object", MANIFEST_PATH)]

    if schema.get("$schema") != SCHEMA_DIALECT:
        diagnostics.append(diagnostic("SCF-LEVEL0-SCHEMA-DIALECT", f"schema dialect must be {SCHEMA_DIALECT!r}", SCHEMA_PATH, "$schema"))
    if schema.get("$id") != SCHEMA_ID:
        diagnostics.append(diagnostic("SCF-LEVEL0-SCHEMA-ID", f"schema id must be {SCHEMA_ID!r}", SCHEMA_PATH, "$id"))
    if authority.get("$schema") != SCHEMA_ID:
        diagnostics.append(diagnostic("SCF-LEVEL0-SCHEMA-REFERENCE", f"authority $schema must be {SCHEMA_ID!r}", AUTHORITY_PATH, "$schema"))

    _validate_schema_definition(schema, [], diagnostics)
    if not any(item.diagnostic_id in {"SCF-LEVEL0-SCHEMA-STRUCTURE", "SCF-LEVEL0-SCHEMA-KEYWORD", "SCF-LEVEL0-SCHEMA-DEFINITION"} for item in diagnostics):
        _validate_instance(authority, schema, "$", diagnostics)

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
    if not all(isinstance(value, dict) for value in (document, scf, provenance, hierarchy)) or not isinstance(invariants, list):
        return diagnostics

    assert isinstance(document, dict)
    assert isinstance(scf, dict)
    assert isinstance(provenance, dict)
    assert isinstance(hierarchy, dict)

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

    required_manifest = (
        "document_id", "title", "framework", "foundation", "level", "version",
        "status", "authority_role", "canonical_path", "provenance_source",
        "sha256", "schema",
    )
    missing = [field for field in required_manifest if field not in manifest]
    for field in missing:
        diagnostics.append(diagnostic("SCF-LEVEL0-MANIFEST-MISSING", f"missing manifest field {field!r}", MANIFEST_PATH, field))
    if missing:
        return diagnostics

    framework = manifest.get("framework")
    schema_manifest = manifest.get("schema")
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
        ("schema.id", schema_manifest.get("id") if isinstance(schema_manifest, dict) else None, SCHEMA_ID),
        ("schema.dialect", schema_manifest.get("dialect") if isinstance(schema_manifest, dict) else None, SCHEMA_DIALECT),
        ("schema.canonical_path", schema_manifest.get("canonical_path") if isinstance(schema_manifest, dict) else None, SCHEMA_PATH),
    )
    for field, actual, required in comparisons:
        if actual != required:
            diagnostics.append(diagnostic("SCF-LEVEL0-MANIFEST-MISMATCH", f"manifest value {actual!r} does not match {required!r}", MANIFEST_PATH, field))

    diagnostics.extend(_validate_checksum(context, checksum_raw, CHECKSUM_PATH, AUTHORITY_PATH, manifest.get("sha256"), "SCF-LEVEL0"))
    schema_digest = schema_manifest.get("sha256") if isinstance(schema_manifest, dict) else None
    diagnostics.extend(_validate_checksum(context, schema_checksum_raw, SCHEMA_CHECKSUM_PATH, SCHEMA_PATH, schema_digest, "SCF-LEVEL0-SCHEMA"))
    return diagnostics
