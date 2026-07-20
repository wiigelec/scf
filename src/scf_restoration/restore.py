# Read-only restoration engine.

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from .model import Diagnostic, RestorationResult

REQUIRED_REPOSITORY_ARTIFACTS = (
    "authority/core/SCF-CORE.json",
    "docs/OFFICIAL-GOVERNED-DEVELOPMENT-PROCESS.md",
    "docs/GOVERNED-ISSUE-PLANNING.md",
    "docs/GOVERNED-DEVELOPMENT-SESSION-RESTORATION.md",
)
SCRIPT_STATES = {"pending", "failed", "partially-applied", "recovered", "completed"}


class RestorationError(ValueError):
    pass


def _git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True)
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RestorationError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def _stable_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({item for item in value if isinstance(item, str)})


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _script_record(raw: Mapping[str, Any]) -> tuple[dict[str, Any], list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []
    state = raw.get("state")
    if state not in SCRIPT_STATES:
        diagnostics.append(Diagnostic(
            "RESTORE-SCRIPT-STATE",
            "script state must be one of: " + ", ".join(sorted(SCRIPT_STATES)),
        ))
        state = "pending"

    filename = raw.get("filename")
    invocation = raw.get("invocation")
    digest = raw.get("sha256")
    if not isinstance(filename, str) or not filename:
        diagnostics.append(Diagnostic("RESTORE-SCRIPT-FILENAME", "script filename is required"))
        filename = None
    if not isinstance(invocation, str) or not invocation:
        diagnostics.append(Diagnostic("RESTORE-SCRIPT-INVOKE", "script invocation is required"))
        invocation = None
    if digest is not None and (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(char not in "0123456789abcdef" for char in digest.lower())
    ):
        diagnostics.append(Diagnostic("RESTORE-SCRIPT-DIGEST", "script SHA-256 is malformed"))
        digest = None
    if state in {"failed", "partially-applied", "recovered", "completed"} and not raw.get("transcript_reference"):
        diagnostics.append(Diagnostic(
            "RESTORE-SCRIPT-TRANSCRIPT",
            f"script state {state} requires a transcript or supplied evidence reference",
        ))
    if state in {"recovered", "completed"} and not raw.get("resulting_commit"):
        diagnostics.append(Diagnostic(
            "RESTORE-SCRIPT-COMMIT",
            f"script state {state} requires a resulting commit identity",
        ))

    return ({
        "method": "user-run-python-script",
        "filename": filename,
        "sha256": digest,
        "invocation": invocation,
        "state": state,
        "expected_repository": raw.get("expected_repository"),
        "expected_branch": raw.get("expected_branch"),
        "expected_starting_head": raw.get("expected_starting_head"),
        "expected_files": _stable_strings(raw.get("expected_files")),
        "planned_commit_subject": raw.get("planned_commit_subject"),
        "transcript_reference": raw.get("transcript_reference"),
        "resulting_commit": raw.get("resulting_commit"),
        "remote_visible": bool(raw.get("remote_visible", False)),
        "recovery_of": raw.get("recovery_of"),
    }, diagnostics)


def _next_action(
    script: Mapping[str, Any],
    repository: Mapping[str, Any],
    diagnostics: Sequence[Diagnostic],
) -> tuple[str | None, str]:
    if any(item.required for item in diagnostics):
        return None, "underspecified"
    state = script.get("state")
    if state == "pending":
        return script.get("invocation"), "patch execution pending"
    if state in {"failed", "partially-applied"}:
        return None, f"patch execution {state}"
    if state == "recovered":
        if script.get("remote_visible"):
            return None, "patch recovered and remotely visible"
        return "git push -u origin " + str(repository.get("observed_branch")), "patch recovered locally"
    if state == "completed":
        if script.get("remote_visible"):
            return None, "local patch committed and remotely visible"
        return "git push -u origin " + str(repository.get("observed_branch")), "local patch committed"
    return None, "underspecified"


def restore_session(root: Path, supplied: Mapping[str, Any]) -> RestorationResult:
    root = root.resolve()
    diagnostics: list[Diagnostic] = []
    if not (root / ".git").exists():
        raise RestorationError("repository root must contain .git")

    before_head = _git(root, "rev-parse", "HEAD")
    before_status = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
    before_refs = _git(root, "show-ref", check=False)

    observed_branch = _git(root, "branch", "--show-current")
    observed_head = before_head
    repository_full_name = supplied.get("repository_full_name")
    supplied_branch = supplied.get("supplied_branch")
    accepted_base = supplied.get("accepted_base")
    remote_url = _git(root, "remote", "get-url", "origin", check=False) or None

    merge_base = None
    if isinstance(accepted_base, str) and accepted_base:
        merge_base = _git(root, "merge-base", accepted_base, observed_head, check=False) or None
        if merge_base != accepted_base:
            diagnostics.append(Diagnostic(
                "RESTORE-MERGE-BASE",
                "accepted base is not the merge base of the observed branch head",
            ))
    else:
        diagnostics.append(Diagnostic("RESTORE-BASE-MISSING", "accepted base revision is required"))

    if not isinstance(repository_full_name, str) or not repository_full_name:
        diagnostics.append(Diagnostic("RESTORE-REPOSITORY-IDENTITY", "repository full name is required"))
    if not isinstance(supplied_branch, str) or not supplied_branch:
        diagnostics.append(Diagnostic("RESTORE-BRANCH-MISSING", "supplied branch is required"))
    elif supplied_branch != observed_branch:
        diagnostics.append(Diagnostic(
            "RESTORE-BRANCH-MISMATCH",
            f"supplied branch {supplied_branch} differs from observed branch {observed_branch}",
        ))

    missing_artifacts = [path for path in REQUIRED_REPOSITORY_ARTIFACTS if not (root / path).is_file()]
    for path in missing_artifacts:
        diagnostics.append(Diagnostic(
            "RESTORE-AUTHORITY-MISSING",
            f"required repository artifact is missing: {path}",
        ))

    authority_input = _mapping(supplied.get("authority"))
    authority_paths = _stable_strings(authority_input.get("paths"))
    if not authority_paths:
        diagnostics.append(Diagnostic(
            "RESTORE-AUTHORITY-CHAIN",
            "applicable authority path identities are required",
        ))

    planning_input = _mapping(supplied.get("planning"))
    issue_number = planning_input.get("issue_number")
    detailed_comment = planning_input.get("detailed_scope_comment")
    work_comment = planning_input.get("work_breakdown_comment")
    active_patch = planning_input.get("active_patch")
    expected_files = _stable_strings(planning_input.get("expected_files"))
    planned_subject = planning_input.get("planned_commit_subject")

    if not isinstance(issue_number, int) or issue_number <= 0:
        diagnostics.append(Diagnostic("RESTORE-ISSUE", "governing issue number is required"))
    if not isinstance(detailed_comment, str) or not detailed_comment:
        diagnostics.append(Diagnostic("RESTORE-DETAILED-COMMENT", "designated detailed-scope comment identity is required"))
    if not isinstance(work_comment, str) or not work_comment:
        diagnostics.append(Diagnostic("RESTORE-WORK-COMMENT", "designated work-breakdown comment identity is required"))
    if not isinstance(active_patch, str) or not active_patch:
        diagnostics.append(Diagnostic("RESTORE-ACTIVE-PATCH", "active patch identity is required"))
    if not expected_files:
        diagnostics.append(Diagnostic("RESTORE-EXPECTED-FILES", "expected changed-file boundary is required"))
    if not isinstance(planned_subject, str) or not planned_subject:
        diagnostics.append(Diagnostic("RESTORE-COMMIT-SUBJECT", "planned commit subject is required"))

    script, script_diagnostics = _script_record(_mapping(supplied.get("execution")))
    diagnostics.extend(script_diagnostics)

    if script.get("expected_repository") not in (None, repository_full_name):
        diagnostics.append(Diagnostic("RESTORE-SCRIPT-REPOSITORY", "script expected repository differs from restored repository"))
    if script.get("expected_branch") not in (None, observed_branch):
        diagnostics.append(Diagnostic("RESTORE-SCRIPT-BRANCH", "script expected branch differs from observed branch"))
    if script.get("expected_starting_head") not in (None, observed_head):
        diagnostics.append(Diagnostic("RESTORE-SCRIPT-HEAD", "script expected starting HEAD differs from observed HEAD"))
    if script.get("expected_files") and script.get("expected_files") != expected_files:
        diagnostics.append(Diagnostic("RESTORE-SCRIPT-FILES", "script file boundary differs from planned file boundary"))
    if script.get("planned_commit_subject") not in (None, planned_subject):
        diagnostics.append(Diagnostic("RESTORE-SCRIPT-SUBJECT", "script commit subject differs from planned subject"))

    remote_input = _mapping(supplied.get("remote_evidence"))
    local_input = _mapping(supplied.get("local_only_evidence"))
    visible_commits = _stable_strings(remote_input.get("visible_commits"))
    if script.get("resulting_commit") in visible_commits:
        script["remote_visible"] = True

    next_action, frontier = _next_action(script, {"observed_branch": observed_branch}, diagnostics)

    after_head = _git(root, "rev-parse", "HEAD")
    after_status = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
    after_refs = _git(root, "show-ref", check=False)
    if (before_head, before_status, before_refs) != (after_head, after_status, after_refs):
        raise RuntimeError("restoration mutated repository state")

    status = "underspecified" if any(item.required for item in diagnostics) else "complete"
    return RestorationResult(
        status=status,
        repository={
            "repository_full_name": repository_full_name,
            "canonical_remote": remote_url,
            "root": root.as_posix(),
            "supplied_branch": supplied_branch,
            "observed_branch": observed_branch,
            "accepted_base": accepted_base,
            "observed_head": observed_head,
            "merge_base": merge_base,
            "working_tree": "clean" if not before_status else "dirty",
        },
        authority={
            "root": "authority/core/SCF-CORE.json",
            "paths": authority_paths,
            "official_process": "docs/OFFICIAL-GOVERNED-DEVELOPMENT-PROCESS.md",
            "restoration_protocol": "docs/GOVERNED-DEVELOPMENT-SESSION-RESTORATION.md",
            "missing_artifacts": sorted(missing_artifacts),
        },
        planning={
            "issue_number": issue_number,
            "detailed_scope_comment": detailed_comment,
            "work_breakdown_comment": work_comment,
            "strict_dependencies": _stable_strings(planning_input.get("strict_dependencies")),
            "active_patch": active_patch,
            "expected_files": expected_files,
            "planned_commit_subject": planned_subject,
        },
        execution=script,
        evidence={
            "remote": {
                "visible_commits": visible_commits,
                "references": _stable_strings(remote_input.get("references")),
            },
            "repository_local": {
                "head": observed_head,
                "working_tree": "clean" if not before_status else "dirty",
            },
            "local_only": {
                "references": _stable_strings(local_input.get("references")),
            },
        },
        lifecycle={
            "frontier": frontier,
            "next_authorized_action": next_action,
        },
        diagnostics=tuple(sorted(diagnostics, key=lambda item: (item.code, item.message))),
    )
