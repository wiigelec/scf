"""Shared helpers for validation checks."""

from __future__ import annotations

from ..context import InputProblem
from ..diagnostics import Diagnostic, Severity


def from_problem(problem: InputProblem) -> Diagnostic:
    return Diagnostic(
        problem.diagnostic_id,
        Severity.ERROR,
        problem.message,
        problem.path,
    )
