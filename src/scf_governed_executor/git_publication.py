from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import strict_validation


SHA1 = re.compile(r"^[0-9a-f]{40}$")
PATH = re.compile(r"^[A-Za-z0-9._/@+-][A-Za-z0-9._/@+ -]*$")
INPUT_FIELDS = {"paths", "message"}
EXPECTED_FIELDS = {"paths", "parent_head"}
PUBLICATION_FIELDS = {"push", "remote", "branch"}


class GitPublicationError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        commands: list[dict[str, Any]] | None = None,
        evidence: dict[str, Any] | None = None,
        mutation_observed: bool = False,
    ) -> None:
        super().__init__(message)
        self.commands = list(commands or [])
        self.evidence = dict(evidence or {})
        self.mutation_observed = mutation_observed


_STRICT = strict_validation.StrictValidator(GitPublicationError)


def _exact(
    value: Mapping[str, Any],
    allowed: set[str],
    required: set[str],
    location: str,
) -> None:
    _STRICT.exact_fields(value, allowed, required, location)


def _path(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise GitPublicationError(f"{location} must be a non-empty string")
    candidate = Path(value)
    if candidate.is_absolute() or any(part in ("", ".", "..") for part in candidate.parts):
        raise GitPublicationError(f"{location} must be normalized and repository-relative")
    normalized = candidate.as_posix()
    if normalized != value:
        raise GitPublicationError(f"{location} must use normalized POSIX form")
    return normalized


def validate_git_publication_inputs(
    inputs: Any,
    expected_mutations: Any,
    publication: Any,
    *,
    push_authorized: bool,
) -> None:
    if not isinstance(inputs, dict):
        raise GitPublicationError("inputs must be an object")
    _exact(inputs, INPUT_FIELDS, INPUT_FIELDS, "inputs")
    paths = inputs["paths"]
    if not isinstance(paths, list) or not paths:
        raise GitPublicationError("inputs.paths must be a non-empty array")
    if len(paths) > 500:
        raise GitPublicationError("inputs.paths exceeds maximum length")
    normalized = [_path(value, f"inputs.paths[{index}]") for index, value in enumerate(paths)]
    if normalized != sorted(set(normalized)):
        raise GitPublicationError("inputs.paths must be unique and lexicographically sorted")
    message = inputs["message"]
    if not isinstance(message, str) or not message.strip():
        raise GitPublicationError("inputs.message must be non-empty")
    if "\x00" in message or len(message.encode("utf-8")) > 4096:
        raise GitPublicationError("inputs.message is invalid")

    if not isinstance(expected_mutations, dict):
        raise GitPublicationError("expected_mutations must be an object")
    _exact(expected_mutations, EXPECTED_FIELDS, EXPECTED_FIELDS, "expected_mutations")
    if expected_mutations["paths"] != normalized:
        raise GitPublicationError("expected_mutations.paths must exactly match inputs.paths")
    parent = expected_mutations["parent_head"]
    if not isinstance(parent, str) or not SHA1.fullmatch(parent):
        raise GitPublicationError("expected_mutations.parent_head must be a lowercase SHA-1")

    if not isinstance(publication, dict):
        raise GitPublicationError("publication must be an object")
    _exact(publication, PUBLICATION_FIELDS, PUBLICATION_FIELDS, "publication")
    if not isinstance(publication["push"], bool):
        raise GitPublicationError("publication.push must be boolean")
    if publication["push"] and not push_authorized:
        raise GitPublicationError("push requested without push authorization")
    if push_authorized and not publication["push"]:
        raise GitPublicationError("push authorization must not exceed requested publication")
    for field in ("remote", "branch"):
        value = publication[field]
        if not isinstance(value, str) or not value or not PATH.fullmatch(value):
            raise GitPublicationError(f"publication.{field} has invalid form")


def _record_dict(record: Any) -> dict[str, Any]:
    return {
        "command": list(record.command),
        "cwd": record.cwd,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
        "elapsed_seconds": record.elapsed_seconds,
        "exit_code": record.exit_code,
        "timed_out": record.timed_out,
        "stdout": record.stdout,
        "stderr": record.stderr,
        "redaction_events": list(record.redaction_events),
    }


def publish_git_changes(
    root: Path,
    supervisor: Any,
    inputs: Mapping[str, Any],
    expected_mutations: Mapping[str, Any],
    publication: Mapping[str, Any],
    *,
    push_authorized: bool,
    progress: Any | None = None,
) -> dict[str, Any]:
    validate_git_publication_inputs(
        inputs, expected_mutations, publication, push_authorized=push_authorized
    )
    commands: list[dict[str, Any]] = []
    evidence: dict[str, Any] = {
        "requested_paths": list(inputs["paths"]),
        "message": inputs["message"],
        "push_requested": publication["push"],
        "remote": publication["remote"],
        "branch": publication["branch"],
        "parent_head": expected_mutations["parent_head"],
        "commit": None,
        "tree": None,
        "remote_commit": None,
        "verified": False,
    }
    mutation_observed = False

    def git(*args: str, phase: str, timeout: int = 60) -> str:
        nonlocal mutation_observed
        record = supervisor.run(
            ["git", *args], root, timeout_seconds=timeout, phase=phase
        )
        commands.append(_record_dict(record))
        if record.exit_code != 0:
            raise GitPublicationError(
                record.stderr.strip() or f"git command failed during {phase}",
                commands=commands,
                evidence=evidence,
                mutation_observed=mutation_observed,
            )
        return record.stdout.strip()

    actual_parent = git("rev-parse", "HEAD", phase="verify parent")
    if actual_parent != expected_mutations["parent_head"]:
        raise GitPublicationError(
            "parent HEAD precondition failed",
            commands=commands,
            evidence=evidence,
            mutation_observed=False,
        )

    branch = git("branch", "--show-current", phase="verify branch")
    if branch != publication["branch"]:
        raise GitPublicationError(
            "publication branch precondition failed",
            commands=commands,
            evidence=evidence,
            mutation_observed=False,
        )

    unmerged = git("diff", "--name-only", "--diff-filter=U", phase="verify index")
    if unmerged:
        raise GitPublicationError(
            "unmerged paths prevent publication",
            commands=commands,
            evidence=evidence,
            mutation_observed=False,
        )

    staged_before = git("diff", "--cached", "--name-only", phase="verify index")
    if staged_before:
        raise GitPublicationError(
            "index must be empty before governed staging",
            commands=commands,
            evidence=evidence,
            mutation_observed=False,
        )

    for path in inputs["paths"]:
        if not (root / path).exists():
            raise GitPublicationError(
                f"publication path does not exist: {path}",
                commands=commands,
                evidence=evidence,
                mutation_observed=False,
            )

    git("add", "--", *inputs["paths"], phase="stage exact paths")
    mutation_observed = True

    staged = git("diff", "--cached", "--name-only", phase="verify staged paths")
    staged_paths = staged.splitlines() if staged else []
    evidence["staged_paths"] = staged_paths
    if staged_paths != inputs["paths"]:
        raise GitPublicationError(
            "staged path set does not exactly match authorization",
            commands=commands,
            evidence=evidence,
            mutation_observed=True,
        )

    git("diff", "--cached", "--check", phase="verify staged content")
    git("commit", "--no-gpg-sign", "-m", inputs["message"], phase="create commit")
    commit = git("rev-parse", "HEAD", phase="verify commit")
    parent = git("rev-parse", "HEAD^", phase="verify commit parent")
    committed_paths = git(
        "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD",
        phase="verify committed paths"
    )
    committed_path_list = committed_paths.splitlines() if committed_paths else []
    tree = git("rev-parse", "HEAD^{tree}", phase="verify commit tree")
    subject = git("show", "-s", "--format=%s", "HEAD", phase="verify commit message")

    evidence.update({
        "commit": commit,
        "tree": tree,
        "committed_paths": committed_path_list,
        "subject": subject,
    })
    if parent != expected_mutations["parent_head"]:
        raise GitPublicationError(
            "created commit has unexpected parent",
            commands=commands,
            evidence=evidence,
            mutation_observed=True,
        )
    if committed_path_list != inputs["paths"]:
        raise GitPublicationError(
            "created commit contains unauthorized paths",
            commands=commands,
            evidence=evidence,
            mutation_observed=True,
        )
    if subject != inputs["message"].splitlines()[0]:
        raise GitPublicationError(
            "created commit message verification failed",
            commands=commands,
            evidence=evidence,
            mutation_observed=True,
        )

    if publication["push"]:
        git(
            "push",
            "--porcelain",
            publication["remote"],
            f"HEAD:refs/heads/{publication['branch']}",
            phase="push commit",
            timeout=120,
        )
        if progress is not None:
            progress.phase(4, "verifying remote state")
        remote_commit = git(
            "ls-remote",
            "--heads",
            publication["remote"],
            f"refs/heads/{publication['branch']}",
            phase="verify remote commit",
            timeout=60,
        )
        remote_hash = remote_commit.split()[0] if remote_commit else ""
        evidence["remote_commit"] = remote_hash
        if remote_hash != commit:
            raise GitPublicationError(
                "remote read-after-write verification failed",
                commands=commands,
                evidence=evidence,
                mutation_observed=True,
            )
        if progress is not None:
            progress.check("remote revision matches created commit")
    elif progress is not None:
        progress.phase(4, "verifying resulting state")
        progress.check("created commit matches the authorized mutation")

    evidence["verified"] = True
    evidence["commands"] = commands
    return evidence
