"""Working-tree JSON encoding, syntax, and duplicate-key validation."""

from __future__ import annotations

from ..context import InputProblem, ValidationContext
from ..diagnostics import Diagnostic
from .common import from_problem


def check_json_files(context: ValidationContext) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for repository_path in context.json_paths():
        try:
            context.parse_json(repository_path)
        except InputProblem as problem:
            diagnostics.append(from_problem(problem))
    return diagnostics
