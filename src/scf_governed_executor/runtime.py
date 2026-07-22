from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

from .errors import (
    CommandTimeoutError,
    ExecutorError,
    GuardError,
    ResultConflictError,
)


SECRET_NAME = re.compile(
    r"(?:token|password|passwd|secret|private[_-]?key|credential|authorization)",
    re.IGNORECASE,
)
TOKEN_PATTERNS = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}"),
)


class TerminalProgress:
    """Consistent human-facing phase and check rendering."""

    def __init__(self, total: int = 5) -> None:
        if total <= 0:
            raise ValueError("total must be positive")
        self.total = total
        self.current = 0
        self.description = "initializing"

    def phase(self, current: int, description: str) -> None:
        if current < 1 or current > self.total:
            raise ExecutorError("progress phase is outside the configured range")
        if current < self.current:
            raise ExecutorError("progress phase cannot move backward")
        self.current = current
        self.description = description
        print(f"Phase [{current}/{self.total}]: {description}...", flush=True)

    def check(self, description: str) -> None:
        print(f"  ✓ {description}", flush=True)

    def heartbeat_phase(self, detail: str | None = None) -> str:
        description = detail or self.description
        return f"phase=[{self.current}/{self.total}] {description}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_text(
    text: str, environment: Mapping[str, str] | None = None
) -> tuple[str, list[dict[str, str]]]:
    events: list[dict[str, str]] = []
    redacted = text

    def replace(category: str, secret: str) -> str:
        fingerprint = hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]
        events.append({"category": category, "fingerprint": fingerprint})
        return f"<redacted:{category}:{fingerprint}>"

    for pattern in TOKEN_PATTERNS:
        redacted = pattern.sub(
            lambda match: replace("credential", match.group(0)), redacted
        )

    split = urlsplit(redacted)
    if split.scheme and split.netloc and (split.username or split.password):
        credential = split.netloc.rsplit("@", 1)[0]
        safe_netloc = split.netloc.rsplit("@", 1)[-1]
        redacted = urlunsplit(
            (split.scheme, safe_netloc, split.path, split.query, split.fragment)
        )
        events.append(
            {
                "category": "credential-url",
                "fingerprint": hashlib.sha256(
                    credential.encode("utf-8")
                ).hexdigest()[:12],
            }
        )

    for name, value in (environment or {}).items():
        if value and SECRET_NAME.search(name) and value in redacted:
            redacted = redacted.replace(
                value, replace("environment-secret", value)
            )

    unique_events = list(
        {(event["category"], event["fingerprint"]): event for event in events}.values()
    )
    return redacted, unique_events


@dataclass(frozen=True)
class CommandRecord:
    command: list[str]
    cwd: str
    started_at: str
    finished_at: str
    elapsed_seconds: float
    exit_code: int | None
    timed_out: bool
    stdout: str
    stderr: str
    redaction_events: list[dict[str, str]]
    stdin: dict[str, Any]


class CommandSupervisor:
    def __init__(
        self,
        heartbeat_seconds: float = 15.0,
        output: Callable[[str], None] = print,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        if heartbeat_seconds <= 0:
            raise ValueError("heartbeat_seconds must be positive")
        self.heartbeat_seconds = heartbeat_seconds
        self.output = output
        self.environment = dict(environment or os.environ)

    def run(
        self,
        command: Sequence[str],
        cwd: Path,
        *,
        timeout_seconds: float = 300.0,
        phase: str = "command",
        stdin_text: str | None = None,
        stdin_bytes: bytes | None = None,
        stdin_label: str | None = None,
    ) -> CommandRecord:
        if not command or any(not isinstance(part, str) or not part for part in command):
            raise ExecutorError("command must be a non-empty string sequence")
        if timeout_seconds <= 0:
            raise ExecutorError("timeout must be positive")
        if stdin_text is not None and stdin_bytes is not None:
            raise ExecutorError("stdin_text and stdin_bytes are mutually exclusive")
        if stdin_text is not None and not isinstance(stdin_text, str):
            raise ExecutorError("stdin_text must be a string")
        if stdin_bytes is not None and not isinstance(stdin_bytes, bytes):
            raise ExecutorError("stdin_bytes must be bytes")
        if stdin_label is not None:
            if (
                not isinstance(stdin_label, str)
                or not stdin_label
                or len(stdin_label) > 128
                or any(
                    ord(character) < 32 or ord(character) == 127
                    for character in stdin_label
                )
            ):
                raise ExecutorError("stdin_label must be bounded printable text")
        payload = stdin_text.encode("utf-8") if stdin_text is not None else stdin_bytes
        stdin_evidence = {
            "supplied": payload is not None,
            "byte_count": len(payload) if payload is not None else 0,
            "sha256": hashlib.sha256(payload).hexdigest() if payload is not None else None,
            "label": stdin_label,
        }

        started_at = utc_now()
        started = time.monotonic()
        proc = subprocess.Popen(
            list(command),
            cwd=cwd,
            env=self.environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
        timed_out = False
        stop = threading.Event()

        def heartbeat() -> None:
            while not stop.wait(self.heartbeat_seconds):
                elapsed = int(time.monotonic() - started)
                self.output(f"    heartbeat: {phase} still running ({elapsed}s)")

        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        try:
            stdout_bytes, stderr_bytes = proc.communicate(
                input=payload, timeout=timeout_seconds
            )
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            stdout_bytes, stderr_bytes = proc.communicate()
        finally:
            stop.set()
            thread.join(timeout=self.heartbeat_seconds + 0.1)

        finished_at = utc_now()
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        redacted_stdout, stdout_events = redact_text(stdout, self.environment)
        redacted_stderr, stderr_events = redact_text(stderr, self.environment)
        record = CommandRecord(
            command=list(command),
            cwd=str(cwd),
            started_at=started_at,
            finished_at=finished_at,
            elapsed_seconds=round(time.monotonic() - started, 3),
            exit_code=proc.returncode,
            timed_out=timed_out,
            stdout=redacted_stdout,
            stderr=redacted_stderr,
            redaction_events=stdout_events + stderr_events,
            stdin=stdin_evidence,
        )
        if timed_out:
            raise CommandTimeoutError(
                f"command timed out after {timeout_seconds}s"
            )
        return record


def command_record_dict(record: CommandRecord) -> dict[str, Any]:
    return {
        "command": record.command,
        "cwd": record.cwd,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
        "elapsed_seconds": record.elapsed_seconds,
        "exit_code": record.exit_code,
        "timed_out": record.timed_out,
        "stdout": record.stdout,
        "stderr": record.stderr,
        "redaction_events": record.redaction_events,
        "stdin": dict(record.stdin),
    }


def evaluate_repository_guards(
    operation: Mapping[str, Any],
    supervisor: CommandSupervisor,
    progress: TerminalProgress | None = None,
) -> tuple[Path, list[dict[str, Any]], dict[str, Any]]:
    repository = operation["repository"]
    guards = operation["guards"]
    root = Path(repository["root"]).expanduser().resolve()
    if not root.is_dir():
        raise GuardError("repository root does not exist")

    records: list[dict[str, Any]] = []

    def git(*args: str) -> str:
        record = supervisor.run(
            ["git", *args],
            root,
            timeout_seconds=30,
            phase=(
                progress.heartbeat_phase("evaluating repository guards")
                if progress is not None
                else "repository guard"
            ),
        )
        records.append(command_record_dict(record))
        if record.exit_code != 0:
            raise GuardError(record.stderr.strip() or "git guard command failed")
        return record.stdout.strip()

    actual_root = Path(git("rev-parse", "--show-toplevel")).resolve()
    if actual_root != root:
        raise GuardError("repository root mismatch")
    actual_origin = git("remote", "get-url", "origin")
    if actual_origin != repository["origin"]:
        raise GuardError("repository origin mismatch")
    actual_branch = git("branch", "--show-current")
    if actual_branch != guards["branch"]:
        raise GuardError("repository branch mismatch")
    actual_head = git("rev-parse", "HEAD")
    if actual_head != guards["head"]:
        raise GuardError("repository HEAD mismatch")
    status = git("status", "--porcelain=v1")
    actual_clean = not bool(status)
    if actual_clean != guards["clean"]:
        raise GuardError("repository clean-state mismatch")

    state = {
        "root": str(root),
        "origin": actual_origin,
        "branch": actual_branch,
        "head": actual_head,
        "clean": actual_clean,
        "status": status.splitlines(),
    }
    return root, records, state


def result_destination(operation: Mapping[str, Any], repository_root: Path) -> Path:
    configured = operation["result"]
    directory = Path(configured["directory"]).expanduser().resolve()
    if not directory.is_dir():
        raise ResultConflictError("result directory does not exist")
    try:
        directory.relative_to(repository_root)
    except ValueError:
        pass
    else:
        raise ResultConflictError("result directory must be outside repository")
    return directory / configured["filename"]


def write_result_exclusive(path: Path, result: Mapping[str, Any]) -> None:
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise ResultConflictError(f"result already exists: {path}") from exc


def capture_repository_state(
    root: Path, supervisor: CommandSupervisor
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def git(*args: str) -> str:
        record = supervisor.run(
            ["git", *args], root, timeout_seconds=30, phase="repository state"
        )
        records.append(command_record_dict(record))
        if record.exit_code != 0:
            raise ExecutorError(record.stderr.strip() or "git state command failed")
        return record.stdout.strip()

    state = {
        "root": str(root),
        "origin": git("remote", "get-url", "origin"),
        "branch": git("branch", "--show-current"),
        "head": git("rev-parse", "HEAD"),
    }
    status = git("status", "--porcelain=v1")
    state["clean"] = not bool(status)
    state["status"] = status.splitlines()
    return records, state
