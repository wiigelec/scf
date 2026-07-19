"""Canonical checksum record validation."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from ..context import InputProblem, ValidationContext
from ..diagnostics import Diagnostic, Severity
from .common import from_problem

CHECKSUM_PATH = "authority/core/SCF-CORE.sha256"
_RECORD = re.compile(r"([0-9a-fA-F]{64})  ([^\r\n]+)\n?\Z")


@dataclass(frozen=True, slots=True)
class ChecksumRecord:
    digest: str
    target: str


def parse_checksum_record(context: ValidationContext) -> ChecksumRecord:
    raw = context.read_bytes(CHECKSUM_PATH)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputProblem(
            "SCF-CHECKSUM-UTF8",
            f"invalid UTF-8 at byte {exc.start}",
            CHECKSUM_PATH,
        ) from exc
    match = _RECORD.fullmatch(text)
    if not match:
        raise InputProblem(
            "SCF-CHECKSUM-FORMAT",
            "expected one SHA-256 record using '<64 hex><two spaces><path>'",
            CHECKSUM_PATH,
        )
    return ChecksumRecord(match.group(1).lower(), match.group(2))


def check_checksum(context: ValidationContext) -> list[Diagnostic]:
    try:
        record = parse_checksum_record(context)
        target = context.safe_path(record.target)
        if not target.is_file():
            return [
                Diagnostic(
                    "SCF-CHECKSUM-TARGET",
                    Severity.ERROR,
                    "checksum target does not exist or is not a regular file",
                    record.target,
                )
            ]
        actual = hashlib.sha256(context.read_bytes(record.target)).hexdigest()
    except InputProblem as problem:
        return [from_problem(problem)]

    if actual != record.digest:
        return [
            Diagnostic(
                "SCF-CHECKSUM-MISMATCH",
                Severity.ERROR,
                f"recorded {record.digest}, calculated {actual}",
                record.target,
            )
        ]
    return []
