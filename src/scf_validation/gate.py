"""Governed validation-gate modes, results, and repository state."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

from .context import ContextError, RepositoryContentSource
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
    content_source: RepositoryContentSource = RepositoryContentSource.WORKING_TREE
    content_revision: str | None = None

    @property
    def classification(self) -> str:
        if self.revision is None:
            return "unborn-working-tree"
        return "clean-revision" if self.clean else "working-tree"

    def as_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "revision": self.revision,
            "clean": self.clean,
            "content_source": self.content_source.value,
            "content_revision": self.content_revision,
        }


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

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.check_id,
            "name": self.name,
            "outcome": "pass" if self.passed else "fail",
            "diagnostics": [diagnostic_as_dict(item) for item in self.diagnostics],
        }


@dataclass(frozen=True, slots=True)
class ValidationRun:
    """One governed validation execution before rendering."""

    mode: ValidationMode
    repository: RepositoryState
    checks: tuple[CheckResult, ...]
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def errors(self) -> int:
        return sum(item.errors for item in self.checks) + sum(
            item.severity == Severity.ERROR for item in self.diagnostics
        )

    @property
    def warnings(self) -> int:
        return sum(item.warnings for item in self.checks) + sum(
            item.severity == Severity.WARNING for item in self.diagnostics
        )

    @property
    def passed(self) -> bool:
        return self.errors == 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "mode": self.mode.value,
            "outcome": "pass" if self.passed else "fail",
            "repository": self.repository.as_dict(),
            "checks": [item.as_dict() for item in self.checks],
            "diagnostics": [diagnostic_as_dict(item) for item in self.diagnostics],
            "summary": {
                "errors": self.errors,
                "warnings": self.warnings,
            },
        }


def diagnostic_as_dict(diagnostic: Diagnostic) -> dict[str, Any]:
    return {
        "id": diagnostic.diagnostic_id,
        "severity": diagnostic.severity.value,
        "message": diagnostic.message,
        "path": diagnostic.path,
        "context": diagnostic.context,
    }


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


def working_tree_state_diagnostics(root: Path) -> tuple[Diagnostic, ...]:
    """Reject local states that cannot be represented by one filesystem view."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "-u", "-z"],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise ContextError("git is required but was not found") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", "replace").strip()
        raise ContextError(f"unable to inspect unresolved index entries: {detail}") from exc
    if not result.stdout:
        return ()
    return (
        Diagnostic(
            "SCF-GATE-STATE-001",
            Severity.ERROR,
            "working-tree validation cannot proceed with unresolved merge conflicts",
            context="content_source=working-tree",
        ),
    )


def certification_diagnostics(
    repository: RepositoryState,
) -> tuple[Diagnostic, ...]:
    """Return controlled certification-precondition failures."""

    diagnostics: list[Diagnostic] = []
    if repository.revision is None:
        diagnostics.append(
            Diagnostic(
                "SCF-GATE-CERT-001",
                Severity.ERROR,
                "certification requires an existing HEAD revision",
            )
        )
    if not repository.clean:
        diagnostics.append(
            Diagnostic(
                "SCF-GATE-CERT-002",
                Severity.ERROR,
                "certification requires a clean working tree and index",
            )
        )
    return tuple(diagnostics)


def build_run(
    mode: ValidationMode,
    repository: RepositoryState,
    checks: Sequence[Check],
    diagnostics_by_check: Sequence[Sequence[Diagnostic]],
    diagnostics: Sequence[Diagnostic] = (),
) -> ValidationRun:
    """Build one immutable run result from ordered check diagnostics."""

    if len(checks) != len(diagnostics_by_check):
        raise ValueError("check and diagnostic result counts do not match")
    results = tuple(
        CheckResult(check.check_id, check.name, tuple(check_diagnostics))
        for check, check_diagnostics in zip(
            checks,
            diagnostics_by_check,
            strict=True,
        )
    )
    return ValidationRun(
        mode=mode,
        repository=repository,
        checks=results,
        diagnostics=tuple(diagnostics),
    )
