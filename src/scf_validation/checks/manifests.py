"""Current authority manifest structure and consistency validation."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from ..context import InputProblem, ValidationContext
from ..diagnostics import Diagnostic, Severity
from .checksums import parse_checksum_record
from .common import from_problem

MANIFEST_PATH = "authority/core/manifest.json"
AUTHORITY_PATH = "authority/core/SCF-CORE.json"
_REQUIRED = (
    "document_id",
    "title",
    "framework",
    "foundation",
    "version",
    "status",
    "canonical_path",
    "sha256",
)
_HEX64 = re.compile(r"[0-9a-fA-F]{64}\Z")


def _lookup(value: Any, *parts: str) -> Any:
    current = value
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            raise KeyError(".".join(parts))
        current = current[part]
    return current


def check_manifest(context: ValidationContext) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    try:
        manifest = context.parse_json(MANIFEST_PATH)
        authority = context.parse_json(AUTHORITY_PATH)
    except InputProblem as problem:
        return [from_problem(problem)]

    if not isinstance(manifest, dict):
        return [
            Diagnostic(
                "SCF-MANIFEST-TOPLEVEL",
                Severity.ERROR,
                "manifest must be a JSON object",
                MANIFEST_PATH,
            )
        ]
    if not isinstance(authority, dict):
        return [
            Diagnostic(
                "SCF-MANIFEST-AUTHORITY",
                Severity.ERROR,
                "canonical authority must be a JSON object",
                AUTHORITY_PATH,
            )
        ]

    for field in _REQUIRED:
        if field not in manifest:
            diagnostics.append(
                Diagnostic(
                    "SCF-MANIFEST-MISSING",
                    Severity.ERROR,
                    f"missing required field {field!r}",
                    MANIFEST_PATH,
                    field,
                )
            )

    framework = manifest.get("framework")
    if not isinstance(framework, dict):
        diagnostics.append(
            Diagnostic(
                "SCF-MANIFEST-FRAMEWORK",
                Severity.ERROR,
                "'framework' must be an object",
                MANIFEST_PATH,
                "framework",
            )
        )
    else:
        for field in ("name", "abbreviation"):
            if field not in framework:
                diagnostics.append(
                    Diagnostic(
                        "SCF-MANIFEST-MISSING",
                        Severity.ERROR,
                        f"missing required field 'framework.{field}'",
                        MANIFEST_PATH,
                        f"framework.{field}",
                    )
                )

    if diagnostics:
        return diagnostics

    comparisons = (
        ("document_id", manifest["document_id"], ("document", "id")),
        ("title", manifest["title"], ("document", "title")),
        ("framework.name", framework["name"], ("scf", "name")),
        ("framework.abbreviation", framework["abbreviation"], ("scf", "abbreviation")),
        ("foundation", manifest["foundation"], ("scf", "contract_foundation", "name")),
        ("version", manifest["version"], ("scf", "version")),
        ("status", manifest["status"], ("scf", "status")),
    )
    for field, manifest_value, authority_parts in comparisons:
        try:
            authority_value = _lookup(authority, *authority_parts)
        except KeyError:
            diagnostics.append(
                Diagnostic(
                    "SCF-MANIFEST-AUTHORITY-FIELD",
                    Severity.ERROR,
                    f"canonical authority lacks {'.'.join(authority_parts)!r}",
                    AUTHORITY_PATH,
                    field,
                )
            )
            continue
        if manifest_value != authority_value:
            diagnostics.append(
                Diagnostic(
                    "SCF-MANIFEST-MISMATCH",
                    Severity.ERROR,
                    f"manifest value {manifest_value!r} does not match authority value {authority_value!r}",
                    MANIFEST_PATH,
                    field,
                )
            )

    canonical = manifest["canonical_path"]
    try:
        canonical_file = context.safe_path(canonical)
    except InputProblem as problem:
        diagnostics.append(from_problem(problem))
        canonical_file = None
    if not isinstance(canonical, str) or not canonical.startswith("authority/"):
        diagnostics.append(
            Diagnostic(
                "SCF-MANIFEST-CANONICAL",
                Severity.ERROR,
                "canonical_path must identify a file beneath authority/",
                MANIFEST_PATH,
                "canonical_path",
            )
        )
    elif canonical != AUTHORITY_PATH:
        diagnostics.append(
            Diagnostic(
                "SCF-MANIFEST-CANONICAL",
                Severity.ERROR,
                f"canonical_path must be {AUTHORITY_PATH!r}",
                MANIFEST_PATH,
                "canonical_path",
            )
        )
    elif canonical_file is not None and not canonical_file.is_file():
        diagnostics.append(
            Diagnostic(
                "SCF-MANIFEST-CANONICAL",
                Severity.ERROR,
                "canonical authority file is missing",
                canonical,
            )
        )

    manifest_digest = manifest["sha256"]
    if not isinstance(manifest_digest, str) or not _HEX64.fullmatch(manifest_digest):
        diagnostics.append(
            Diagnostic(
                "SCF-MANIFEST-DIGEST",
                Severity.ERROR,
                "sha256 must be a 64-character hexadecimal string",
                MANIFEST_PATH,
                "sha256",
            )
        )
        return diagnostics
    manifest_digest = manifest_digest.lower()

    try:
        record = parse_checksum_record(context)
        actual = hashlib.sha256(context.read_bytes(AUTHORITY_PATH)).hexdigest()
    except InputProblem as problem:
        diagnostics.append(from_problem(problem))
        return diagnostics

    if record.target != canonical:
        diagnostics.append(
            Diagnostic(
                "SCF-MANIFEST-CHECKSUM-PATH",
                Severity.ERROR,
                f"checksum target {record.target!r} does not match canonical_path {canonical!r}",
                MANIFEST_PATH,
                "canonical_path",
            )
        )
    if manifest_digest != actual:
        diagnostics.append(
            Diagnostic(
                "SCF-MANIFEST-DIGEST-MISMATCH",
                Severity.ERROR,
                f"manifest digest {manifest_digest} does not match canonical bytes {actual}",
                MANIFEST_PATH,
                "sha256",
            )
        )
    if manifest_digest != record.digest:
        diagnostics.append(
            Diagnostic(
                "SCF-MANIFEST-CHECKSUM-MISMATCH",
                Severity.ERROR,
                f"manifest digest {manifest_digest} does not match checksum record {record.digest}",
                MANIFEST_PATH,
                "sha256",
            )
        )
    return diagnostics
