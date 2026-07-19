"""Declared descriptive and normative semantic path validation."""

from __future__ import annotations

from collections import Counter
from typing import Any

from ..context import InputProblem, ValidationContext
from ..diagnostics import Diagnostic, Severity
from .common import from_problem

AUTHORITY_PATH = "authority/core/SCF-CORE.json"


def _resolve(document: Any, declared: str) -> tuple[bool, str | None]:
    current = document
    for segment in declared.split("."):
        if not isinstance(current, dict):
            return False, segment
        if segment not in current:
            return False, segment
        current = current[segment]
    return True, None


def check_semantic_paths(context: ValidationContext) -> list[Diagnostic]:
    try:
        authority = context.parse_json(AUTHORITY_PATH)
    except InputProblem as problem:
        return [from_problem(problem)]

    diagnostics: list[Diagnostic] = []
    try:
        semantics = authority["document"]["field_semantics"]
    except (KeyError, TypeError):
        return [
            Diagnostic(
                "SCF-SEMANTIC-CONTAINER",
                Severity.ERROR,
                "missing document.field_semantics object",
                AUTHORITY_PATH,
                "document.field_semantics",
            )
        ]
    if not isinstance(semantics, dict):
        return [
            Diagnostic(
                "SCF-SEMANTIC-CONTAINER",
                Severity.ERROR,
                "document.field_semantics must be an object",
                AUTHORITY_PATH,
                "document.field_semantics",
            )
        ]

    parsed: dict[str, list[str]] = {}
    for field in ("descriptive_metadata", "normative_authority"):
        value = semantics.get(field)
        if not isinstance(value, list):
            diagnostics.append(
                Diagnostic(
                    "SCF-SEMANTIC-LIST",
                    Severity.ERROR,
                    f"{field} must be an array",
                    AUTHORITY_PATH,
                    f"document.field_semantics.{field}",
                )
            )
            continue
        valid_paths: list[str] = []
        for index, declared in enumerate(value):
            location = f"document.field_semantics.{field}[{index}]"
            if not isinstance(declared, str):
                diagnostics.append(
                    Diagnostic(
                        "SCF-SEMANTIC-TYPE",
                        Severity.ERROR,
                        "semantic path must be a string",
                        AUTHORITY_PATH,
                        location,
                    )
                )
                continue
            if not declared or any(segment == "" for segment in declared.split(".")):
                diagnostics.append(
                    Diagnostic(
                        "SCF-SEMANTIC-SYNTAX",
                        Severity.ERROR,
                        f"malformed semantic path {declared!r}",
                        AUTHORITY_PATH,
                        location,
                    )
                )
                continue
            valid_paths.append(declared)
            resolved, segment = _resolve(authority, declared)
            if not resolved:
                diagnostics.append(
                    Diagnostic(
                        "SCF-SEMANTIC-MISSING",
                        Severity.ERROR,
                        f"semantic path {declared!r} does not resolve at segment {segment!r}",
                        AUTHORITY_PATH,
                        location,
                    )
                )
        for declared, count in Counter(valid_paths).items():
            if count > 1:
                diagnostics.append(
                    Diagnostic(
                        "SCF-SEMANTIC-DUPLICATE",
                        Severity.ERROR,
                        f"semantic path {declared!r} is declared {count} times",
                        AUTHORITY_PATH,
                        field,
                    )
                )
        parsed[field] = valid_paths

    overlap = sorted(
        set(parsed.get("descriptive_metadata", ()))
        & set(parsed.get("normative_authority", ()))
    )
    for declared in overlap:
        diagnostics.append(
            Diagnostic(
                "SCF-SEMANTIC-OVERLAP",
                Severity.ERROR,
                f"semantic path {declared!r} appears in both semantic sets",
                AUTHORITY_PATH,
                "document.field_semantics",
            )
        )
    return diagnostics
