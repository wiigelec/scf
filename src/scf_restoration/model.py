# Deterministic restoration result models.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    required: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "required": self.required}


@dataclass(frozen=True)
class RestorationResult:
    status: str
    repository: dict[str, Any]
    authority: dict[str, Any]
    planning: dict[str, Any]
    execution: dict[str, Any]
    evidence: dict[str, Any]
    lifecycle: dict[str, Any]
    diagnostics: tuple[Diagnostic, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "status": self.status,
            "repository": self.repository,
            "authority": self.authority,
            "planning": self.planning,
            "execution": self.execution,
            "evidence": self.evidence,
            "lifecycle": self.lifecycle,
            "diagnostics": [item.as_dict() for item in self.diagnostics],
        }
