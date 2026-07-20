"""Read-only repository context and shared parsing utilities."""

from __future__ import annotations

import json
import subprocess
from enum import Enum
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


class RepositoryContentSource(str, Enum):
    """Authoritative repository content presented to validation checks."""

    WORKING_TREE = "working-tree"
    REVISION = "revision"


class ValidationContext:
    REQUIRED_SENTINELS = (
        ".git",
        "authority/core/SCF-CORE.json",
        "bootstrap/INITIAL-DEVELOPMENT-PROCESS.md",
        "planning/BOOTSTRAP-TO-DEVELOPMENT-ROADMAP.md",
    )

    def __init__(
        self,
        root: Path,
        source: RepositoryContentSource = RepositoryContentSource.WORKING_TREE,
        revision: str | None = None,
    ):
        self.root = root.resolve()
        self.source = source
        self.revision = revision
        if source == RepositoryContentSource.REVISION and not revision:
            raise ContextError("revision content source requires an exact revision")
        self._bytes_cache: dict[str, bytes] = {}
        self._json_cache: dict[str, Any] = {}
        self._json_paths_cache: tuple[str, ...] | None = None

    @classmethod
    def create(
        cls,
        root: Path,
        source: RepositoryContentSource = RepositoryContentSource.WORKING_TREE,
        revision: str | None = None,
    ) -> "ValidationContext":
        resolved = root.resolve()
        if not (resolved / ".git").exists():
            raise ContextError(
                "current directory is not the SCF repository root; missing: .git"
            )

        context = cls(resolved, source, revision)
        content_sentinels = tuple(
            item for item in cls.REQUIRED_SENTINELS if item != ".git"
        )
        missing = [
            item for item in content_sentinels
            if not context.path_exists(item)
        ]
        if missing:
            raise ContextError(
                f"{source.value} repository content is missing required SCF files: "
                + ", ".join(missing)
            )
        return context

    def _git_bytes(self, arguments: list[str], failure: str) -> bytes:
        try:
            result = subprocess.run(
                ["git", *arguments],
                cwd=self.root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise ContextError("git is required but was not found") from exc
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode("utf-8", "replace").strip()
            raise ContextError(f"{failure}: {detail}") from exc
        return result.stdout

    def path_exists(self, repository_path: str) -> bool:
        if self.source == RepositoryContentSource.WORKING_TREE:
            return self.safe_path(repository_path).exists()
        assert self.revision is not None
        result = subprocess.run(
            ["git", "cat-file", "-e", f"{self.revision}:{repository_path}"],
            cwd=self.root,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        if result.returncode == 0:
            return True
        if result.returncode in (1, 128):
            return False
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise ContextError(f"unable to inspect revision path {repository_path}: {detail}")

    def is_regular_file(self, repository_path: str) -> bool:
        """Return whether the selected source contains a regular file at the path."""
        if self.source == RepositoryContentSource.WORKING_TREE:
            target = self.root / repository_path
            try:
                target.relative_to(self.root)
            except ValueError as exc:
                raise InputProblem(
                    "SCF-INPUT-PATH-001",
                    "repository path escapes the repository root",
                    repository_path,
                ) from exc
            return target.exists() and target.is_file() and not target.is_symlink()

        assert self.revision is not None
        output = self._git_bytes(
            ["ls-tree", "-z", self.revision, "--", repository_path],
            f"unable to inspect revision file type {repository_path}",
        )
        if not output:
            return False
        record = output.split(b"\0", 1)[0]
        metadata, _, returned_path = record.partition(b"\t")
        parts = metadata.split()
        return (
            len(parts) >= 3
            and parts[0] in (b"100644", b"100755")
            and returned_path.decode("utf-8", "surrogateescape") == repository_path
        )

    def json_paths(self) -> tuple[str, ...]:
        """Return tracked and untracked, non-ignored JSON paths."""
        if self._json_paths_cache is not None:
            return self._json_paths_cache
        if self.source == RepositoryContentSource.WORKING_TREE:
            output = self._git_bytes(
                [
                    "ls-files", "-z", "--cached", "--others",
                    "--exclude-standard", "--", "*.json",
                ],
                "unable to enumerate working-tree JSON files",
            )
        else:
            assert self.revision is not None
            output = self._git_bytes(
                ["ls-tree", "-rz", "--name-only", self.revision, "--", "*.json"],
                "unable to enumerate revision JSON files",
            )
        paths = {
            part.decode("utf-8", "surrogateescape")
            for part in output.split(b"\0")
            if part
        }
        if self.source == RepositoryContentSource.WORKING_TREE:
            paths = {
                repository_path
                for repository_path in paths
                if (
                    (self.root / repository_path).exists()
                    or (self.root / repository_path).is_symlink()
                )
            }
        self._json_paths_cache = tuple(sorted(paths))
        return self._json_paths_cache

    def tracked_json_paths(self) -> tuple[str, ...]:
        """Compatibility alias for callers predating working-tree coverage."""
        return self.json_paths()

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
        if self.source == RepositoryContentSource.REVISION:
            assert self.revision is not None
            try:
                data = self._git_bytes(
                    ["show", f"{self.revision}:{repository_path}"],
                    f"unable to read revision file {repository_path}",
                )
            except ContextError as exc:
                raise InputProblem(
                    "SCF-REPO-002",
                    "required file is missing or unreadable in validated revision",
                    repository_path,
                ) from exc
        else:
            target = self.safe_path(repository_path)
            try:
                if target.is_symlink():
                    data = target.readlink().as_posix().encode("utf-8")
                else:
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
            def reject_constant(constant: str) -> None:
                raise ValueError(f"non-standard JSON constant {constant!r}")

            value = json.loads(
                text,
                object_pairs_hook=reject_duplicates,
                parse_constant=reject_constant,
            )
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
        except ValueError as exc:
            raise InputProblem(
                "SCF-JSON-SYNTAX",
                str(exc),
                repository_path,
            ) from exc
        self._json_cache[repository_path] = value
        return value
