"""Read-only repository context and shared parsing utilities."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any


class ContextError(RuntimeError):
    """Invalid invocation or unavailable repository tooling."""


class InputProblem(RuntimeError):
    """Expected repository-content problem."""

    def __init__(self, diagnostic_id: str, message: str, path: str | None = None):
        super().__init__(message)
        self.diagnostic_id = diagnostic_id
        self.message = message
        self.path = path


class DuplicateKeyError(ValueError):
    def __init__(self, key: str):
        super().__init__(f"duplicate object key {key!r}")
        self.key = key


class ValidationContext:
    REQUIRED_SENTINELS = (
        ".git",
        "authority/core/SCF-CORE.json",
        "bootstrap/INITIAL-DEVELOPMENT-PROCESS.md",
        "planning/BOOTSTRAP-TO-DEVELOPMENT-ROADMAP.md",
    )

    def __init__(self, root: Path):
        self.root = root.resolve()
        self._bytes_cache: dict[str, bytes] = {}
        self._json_cache: dict[str, Any] = {}
        self._tracked_json_cache: tuple[str, ...] | None = None

    @classmethod
    def create(cls, root: Path) -> "ValidationContext":
        resolved = root.resolve()
        missing = [item for item in cls.REQUIRED_SENTINELS if not (resolved / item).exists()]
        if missing:
            raise ContextError(
                "current directory is not the SCF repository root; missing: "
                + ", ".join(missing)
            )
        return cls(resolved)

    def tracked_json_paths(self) -> tuple[str, ...]:
        if self._tracked_json_cache is not None:
            return self._tracked_json_cache
        try:
            result = subprocess.run(
                ["git", "ls-files", "-z", "--", "*.json"],
                cwd=self.root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise ContextError("git is required but was not found") from exc
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode("utf-8", "replace").strip()
            raise ContextError(f"unable to enumerate tracked JSON files: {detail}") from exc
        paths = tuple(
            part.decode("utf-8", "surrogateescape")
            for part in result.stdout.split(b"\0")
            if part
        )
        self._tracked_json_cache = tuple(sorted(paths))
        return self._tracked_json_cache

    def safe_path(self, repository_path: str) -> Path:
        if not isinstance(repository_path, str) or not repository_path:
            raise InputProblem("SCF-PATH-001", "repository path must be a nonempty string")
        if "\\" in repository_path:
            raise InputProblem(
                "SCF-PATH-001",
                "repository path must use forward slashes",
                repository_path,
            )
        pure = PurePosixPath(repository_path)
        if pure.is_absolute() or ".." in pure.parts:
            raise InputProblem(
                "SCF-PATH-001",
                "repository path must be relative and must not contain parent traversal",
                repository_path,
            )
        candidate = (self.root / Path(*pure.parts)).resolve(strict=False)
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise InputProblem(
                "SCF-PATH-002",
                "repository path escapes the repository root",
                repository_path,
            ) from exc
        return candidate

    def read_bytes(self, repository_path: str) -> bytes:
        if repository_path in self._bytes_cache:
            return self._bytes_cache[repository_path]
        target = self.safe_path(repository_path)
        try:
            data = target.read_bytes()
        except FileNotFoundError as exc:
            raise InputProblem("SCF-REPO-002", "required file is missing", repository_path) from exc
        except OSError as exc:
            raise InputProblem(
                "SCF-REPO-003",
                f"unable to read file: {exc}",
                repository_path,
            ) from exc
        self._bytes_cache[repository_path] = data
        return data

    def parse_json(self, repository_path: str) -> Any:
        if repository_path in self._json_cache:
            return self._json_cache[repository_path]
        raw = self.read_bytes(repository_path)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InputProblem(
                "SCF-JSON-UTF8",
                f"invalid UTF-8 at byte {exc.start}",
                repository_path,
            ) from exc

        def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise DuplicateKeyError(key)
                result[key] = value
            return result

        try:
            value = json.loads(text, object_pairs_hook=reject_duplicates)
        except DuplicateKeyError as exc:
            raise InputProblem(
                "SCF-JSON-DUPLICATE",
                f"duplicate object key {exc.key!r}",
                repository_path,
            ) from exc
        except json.JSONDecodeError as exc:
            raise InputProblem(
                "SCF-JSON-SYNTAX",
                f"{exc.msg} at line {exc.lineno}, column {exc.colno}",
                repository_path,
            ) from exc
        self._json_cache[repository_path] = value
        return value
