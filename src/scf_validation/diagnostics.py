"""Structured diagnostics for SCF repository validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    diagnostic_id: str
    severity: Severity
    message: str
    path: str | None = None
    context: str | None = None

    def render(self) -> str:
        location = f" {self.path}" if self.path else ""
        suffix = f" ({self.context})" if self.context else ""
        return f"     {self.severity.value.upper()} {self.diagnostic_id}{location}: {self.message}{suffix}"
