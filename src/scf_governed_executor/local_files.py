from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence


SHA256 = re.compile(r"^[0-9a-f]{64}$")
MODE = re.compile(r"^0[0-7]{3}$")
INPUT_FIELDS = {"operations"}
EXPECTED_FIELDS = {"files"}
COMMON_FIELDS = {"action", "path", "content", "content_sha256", "mode"}
REPLACE_FIELDS = COMMON_FIELDS | {"expected_sha256"}


class LocalFileOperationError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        records: list[dict[str, Any]] | None = None,
        mutation_observed: bool = False,
    ) -> None:
        super().__init__(message)
        self.records = list(records or [])
        self.mutation_observed = mutation_observed


def _exact_fields(
    value: Mapping[str, Any],
    allowed: set[str],
    required: set[str],
    location: str,
) -> None:
    unknown = set(value) - allowed
    missing = required - set(value)
    if unknown:
        raise LocalFileOperationError(
            f"{location} contains unknown fields: {', '.join(sorted(unknown))}"
        )
    if missing:
        raise LocalFileOperationError(
            f"{location} is missing required fields: {', '.join(sorted(missing))}"
        )


def _validated_path(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise LocalFileOperationError(f"{location} must be a non-empty string")
    candidate = Path(value)
    if candidate.is_absolute() or value.startswith(("/", "\\")):
        raise LocalFileOperationError(f"{location} must be repository-relative")
    if any(part in ("", ".", "..") for part in candidate.parts):
        raise LocalFileOperationError(f"{location} is not normalized")
    normalized = candidate.as_posix()
    if normalized != value:
        raise LocalFileOperationError(f"{location} must use normalized POSIX form")
    return normalized


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def validate_local_file_inputs(
    inputs: Any, expected_mutations: Any
) -> list[dict[str, Any]]:
    if not isinstance(inputs, dict):
        raise LocalFileOperationError("inputs must be an object")
    _exact_fields(inputs, INPUT_FIELDS, INPUT_FIELDS, "inputs")
    operations = inputs["operations"]
    if not isinstance(operations, list) or not operations:
        raise LocalFileOperationError("inputs.operations must be a non-empty array")
    if len(operations) > 100:
        raise LocalFileOperationError("inputs.operations exceeds maximum length")

    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    expected_files: list[dict[str, Any]] = []
    for index, item in enumerate(operations):
        location = f"inputs.operations[{index}]"
        if not isinstance(item, dict):
            raise LocalFileOperationError(f"{location} must be an object")
        action = item.get("action")
        fields = COMMON_FIELDS if action == "create" else REPLACE_FIELDS
        if action not in {"create", "replace"}:
            raise LocalFileOperationError(f"{location}.action is unsupported")
        _exact_fields(item, fields, fields, location)
        path = _validated_path(item["path"], f"{location}.path")
        if path in seen:
            raise LocalFileOperationError(f"duplicate operation path: {path}")
        seen.add(path)
        if not isinstance(item["content"], str):
            raise LocalFileOperationError(f"{location}.content must be a string")
        if not isinstance(item["content_sha256"], str) or not SHA256.fullmatch(
            item["content_sha256"]
        ):
            raise LocalFileOperationError(
                f"{location}.content_sha256 must be lowercase SHA-256"
            )
        actual = _sha256_bytes(item["content"].encode("utf-8"))
        if actual != item["content_sha256"]:
            raise LocalFileOperationError(
                f"{location}.content_sha256 does not match content"
            )
        if not isinstance(item["mode"], str) or not MODE.fullmatch(item["mode"]):
            raise LocalFileOperationError(f"{location}.mode has invalid form")
        if action == "replace":
            if not isinstance(item["expected_sha256"], str) or not SHA256.fullmatch(
                item["expected_sha256"]
            ):
                raise LocalFileOperationError(
                    f"{location}.expected_sha256 must be lowercase SHA-256"
                )
        normalized.append(dict(item))
        expected_files.append(
            {
                "action": action,
                "path": path,
                "before_sha256": (
                    None if action == "create" else item["expected_sha256"]
                ),
                "after_sha256": item["content_sha256"],
                "mode": item["mode"],
            }
        )

    if not isinstance(expected_mutations, dict):
        raise LocalFileOperationError("expected_mutations must be an object")
    _exact_fields(
        expected_mutations,
        EXPECTED_FIELDS,
        EXPECTED_FIELDS,
        "expected_mutations",
    )
    if expected_mutations["files"] != expected_files:
        raise LocalFileOperationError(
            "expected_mutations.files does not exactly match operations"
        )
    return normalized


def _target(root: Path, relative: str) -> Path:
    target = root.joinpath(*Path(relative).parts)
    try:
        target.resolve(strict=False).relative_to(root.resolve())
    except ValueError as exc:
        raise LocalFileOperationError(
            f"path escapes repository: {relative}"
        ) from exc
    current = root
    for part in Path(relative).parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise LocalFileOperationError(
                f"symlink ancestor is forbidden: {relative}"
            )
    if target.is_symlink():
        raise LocalFileOperationError(f"symlink target is forbidden: {relative}")
    return target


def _write_create(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def _write_replace(path: Path, data: bytes, mode: int) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.governed-", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def apply_local_file_operations(
    root: Path, operations: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    mutation_observed = False
    try:
        for index, operation in enumerate(operations):
            relative = operation["path"]
            target = _target(root, relative)
            action = operation["action"]
            data = operation["content"].encode("utf-8")
            desired_hash = operation["content_sha256"]
            mode = int(operation["mode"], 8)
            before_hash = None

            if action == "create":
                if target.exists():
                    raise LocalFileOperationError(
                        f"create refuses existing path: {relative}"
                    )
                _write_create(target, data, mode)
            else:
                if not target.is_file():
                    raise LocalFileOperationError(
                        f"replace requires an existing regular file: {relative}"
                    )
                before_hash = _sha256_bytes(target.read_bytes())
                if before_hash != operation["expected_sha256"]:
                    raise LocalFileOperationError(
                        f"replace precondition failed: {relative}"
                    )
                _write_replace(target, data, mode)

            mutation_observed = True
            after_hash = _sha256_bytes(target.read_bytes())
            actual_mode = f"0{target.stat().st_mode & 0o777:03o}"
            verified = after_hash == desired_hash and actual_mode == operation["mode"]
            record = {
                "index": index,
                "action": action,
                "path": relative,
                "before_sha256": before_hash,
                "after_sha256": after_hash,
                "expected_after_sha256": desired_hash,
                "mode": actual_mode,
                "verified": verified,
            }
            records.append(record)
            if not verified:
                raise LocalFileOperationError(
                    f"read-after-write verification failed: {relative}"
                )
        return records
    except LocalFileOperationError as exc:
        raise LocalFileOperationError(
            str(exc),
            records=records,
            mutation_observed=mutation_observed,
        ) from exc
    except OSError as exc:
        raise LocalFileOperationError(
            f"local file operation failed: {exc}",
            records=records,
            mutation_observed=mutation_observed,
        ) from exc
