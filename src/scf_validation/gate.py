"""Governed validation-gate modes, results, and repository state."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Sequence

from .context import ContextError
from .diagnostics import Diagnostic, Severity
from .registry import Check


class ValidationMode(str, Enum):
    """User-visible validation modes."""

    FOCUSED = "focused"
    COMPLETE = "complete"
    CERTIFY = "certify"


@dataclass(frozen=True, slots=True)
class RepositoryState:
    """Read-only identity and cleanliness of the validated repository."""

    revision: str | None
    clean: bool

    @property
    def classification(self) -> str:
        if self.revision is None:
            return "unborn-working-tree"
        return "clean-revision" if self.clean else "working-tree"


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Result of one explicitly registered check."""

    check_id: str
    name: str
    diagnostics: tuple[Diagnostic, ...]

    @property
    def errors(self) -> int:
        return sum(item.severity == Severity.ERROR for item in self.diagnostics)

    @property
    def warnings(self) -> int:
        return sum(item.severity == Severity.WARNING for item in self.diagnostics)

    @property
    def passed(self) -> bool:
        return self.errors == 0


@dataclass(frozen=True, slots=True)
class ValidationRun:
    """One governed validation execution before rendering."""

    mode: ValidationMode
    repository: RepositoryState
    checks: tuple[CheckResult, ...]

    @property
    def errors(self) -> int:
        return sum(item.errors for item in self.checks)

    @property
    def warnings(self) -> int:
        return sum(item.warnings for item in self.checks)

    @property
    def passed(self) -> bool:
        return self.errors == 0


def resolve_mode(
    explicit_mode: str | None,
    check_ids: Sequence[str] | None,
) -> ValidationMode:
    """Resolve compatible mode/check arguments without running validation."""

    requested = bool(check_ids)
    if explicit_mode is None:
        return ValidationMode.FOCUSED if requested else ValidationMode.COMPLETE

    mode = ValidationMode(explicit_mode)
    if mode == ValidationMode.FOCUSED and not requested:
        raise ValueError("focused mode requires at least one --check")
    if mode != ValidationMode.FOCUSED and requested:
        raise ValueError(f"{mode.value} mode does not accept --check")
    if mode == ValidationMode.CERTIFY:
        raise ValueError(
            "certify mode is reserved until certification semantics are implemented"
        )
    return mode


def inspect_repository_state(root: Path) -> RepositoryState:
    """Read HEAD and worktree/index cleanliness without modifying the repository."""

    try:
        revision_result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=root,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if revision_result.returncode not in (0, 128):
            detail = revision_result.stderr.strip()
            raise ContextError(f"unable to identify repository HEAD: {detail}")
        revision = (
            revision_result.stdout.strip()
            if revision_result.returncode == 0
            else None
        )
        status = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
    except FileNotFoundError as exc:
        raise ContextError("git is required but was not found") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip()
        raise ContextError(f"unable to inspect repository state: {detail}") from exc

    return RepositoryState(revision=revision, clean=not bool(status))


def build_run(
    mode: ValidationMode,
    repository: RepositoryState,
    checks: Sequence[Check],
    diagnostics_by_check: Sequence[Sequence[Diagnostic]],
) -> ValidationRun:
    """Build one immutable run result from ordered check diagnostics."""

    if len(checks) != len(diagnostics_by_check):
        raise ValueError("check and diagnostic result counts do not match")
    results = tuple(
        CheckResult(check.check_id, check.name, tuple(diagnostics))
        for check, diagnostics in zip(checks, diagnostics_by_check, strict=True)
    )
    return ValidationRun(mode=mode, repository=repository, checks=results)
