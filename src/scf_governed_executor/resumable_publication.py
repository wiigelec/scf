from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import combined_publication
from . import core as core_module
from . import git_publication


def _command(
    supervisor: core_module.CommandSupervisor,
    root: Path,
    commands: list[dict[str, Any]],
    *args: str,
    phase: str,
    timeout: float = 120.0,
    allowed_exit_codes: set[int] | None = None,
) -> str:
    record = supervisor.run(
        ["git", *args],
        root,
        timeout_seconds=timeout,
        phase=phase,
    )
    commands.append(core_module.command_record_dict(record))
    accepted = allowed_exit_codes or {0}
    if record.exit_code not in accepted:
        raise core_module.ExecutorError(
            record.stderr.strip() or f"{phase} failed"
        )
    return record.stdout.strip()


def _evaluate_identity(
    operation: Mapping[str, Any],
    supervisor: core_module.CommandSupervisor,
) -> tuple[Path, list[dict[str, Any]], dict[str, Any]]:
    root = Path(operation["repository"]["root"]).expanduser().resolve()
    if not root.is_dir():
        raise core_module.GuardError("repository root does not exist")
    commands: list[dict[str, Any]] = []
    actual_root = Path(
        _command(
            supervisor, root, commands,
            "rev-parse", "--show-toplevel",
            phase="resolve repository root",
        )
    ).resolve()
    if actual_root != root:
        raise core_module.GuardError("repository root mismatch")
    origin = _command(
        supervisor, root, commands,
        "remote", "get-url", "origin",
        phase="verify repository origin",
    )
    if origin != operation["repository"]["origin"]:
        raise core_module.GuardError("repository origin mismatch")
    branch = _command(
        supervisor, root, commands,
        "branch", "--show-current",
        phase="verify publication branch",
    )
    if branch != operation["guards"]["branch"]:
        raise core_module.GuardError("repository branch mismatch")
    head = _command(
        supervisor, root, commands,
        "rev-parse", "HEAD",
        phase="read publication head",
    )
    status = _command(
        supervisor, root, commands,
        "status", "--porcelain=v1",
        phase="read publication status",
    )
    state = {
        "root": str(root),
        "origin": origin,
        "branch": branch,
        "head": head,
        "clean": not bool(status),
        "status": status.splitlines(),
    }
    return root, commands, state


def _existing_commit(
    operation: Mapping[str, Any],
    root: Path,
    supervisor: core_module.CommandSupervisor,
    starting: Mapping[str, Any],
) -> dict[str, Any]:
    commands: list[dict[str, Any]] = []
    if not starting["clean"]:
        raise core_module.GuardError(
            "repository must be clean when the planned commit already exists"
        )
    parent = _command(
        supervisor, root, commands,
        "rev-parse", "HEAD^",
        phase="verify existing commit parent",
    )
    paths_text = _command(
        supervisor, root, commands,
        "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD",
        phase="verify existing committed paths",
    )
    paths = paths_text.splitlines() if paths_text else []
    subject = _command(
        supervisor, root, commands,
        "show", "-s", "--format=%s", "HEAD",
        phase="verify existing commit subject",
    )
    tree = _command(
        supervisor, root, commands,
        "rev-parse", "HEAD^{tree}",
        phase="verify existing commit tree",
    )
    expected_parent = operation["expected_mutations"]["parent_head"]
    expected_paths = operation["inputs"]["paths"]
    expected_subject = operation["inputs"]["message"].splitlines()[0]
    if parent != expected_parent:
        raise core_module.GuardError("existing commit has unexpected parent")
    if paths != expected_paths:
        raise core_module.GuardError(
            "existing commit contains paths outside the exact authorization"
        )
    if subject != expected_subject:
        raise core_module.GuardError("existing commit subject does not match the plan")
    return {
        "requested_paths": list(expected_paths),
        "message": operation["inputs"]["message"],
        "push_requested": True,
        "remote": operation["publication"]["remote"],
        "branch": operation["publication"]["branch"],
        "parent_head": expected_parent,
        "commit": starting["head"],
        "tree": tree,
        "committed_paths": paths,
        "subject": subject,
        "staging": "already-completed",
        "commit_creation": "already-completed",
        "commands": commands,
        "verified": False,
    }


def _push_or_verify(
    operation: Mapping[str, Any],
    root: Path,
    supervisor: core_module.CommandSupervisor,
    evidence: dict[str, Any],
) -> None:
    commands = evidence["commands"]
    remote = operation["publication"]["remote"]
    branch = operation["publication"]["branch"]
    commit = evidence["commit"]
    remote_line = _command(
        supervisor, root, commands,
        "ls-remote", "--heads", remote, f"refs/heads/{branch}",
        phase="inspect publication remote",
    )
    remote_commit = remote_line.split()[0] if remote_line else ""
    if remote_commit and remote_commit != commit:
        raise core_module.GuardError(
            "remote publication branch points to a conflicting commit"
        )
    if remote_commit == commit:
        evidence["push"] = "already-completed"
    else:
        _command(
            supervisor, root, commands,
            "push", "--porcelain", remote, f"HEAD:refs/heads/{branch}",
            phase="push planned commit",
            timeout=120.0,
        )
        evidence["push"] = "performed"
        remote_line = _command(
            supervisor, root, commands,
            "ls-remote", "--heads", remote, f"refs/heads/{branch}",
            phase="verify pushed commit",
        )
        remote_commit = remote_line.split()[0] if remote_line else ""
    evidence["remote_commit"] = remote_commit
    if remote_commit != commit:
        raise core_module.ExecutorError(
            "remote read-after-write verification failed"
        )
    evidence["verified"] = True


def execute(
    operation: Mapping[str, Any],
    progress: core_module.TerminalProgress,
) -> tuple[dict[str, Any], Path]:
    root = Path(operation["repository"]["root"]).expanduser().resolve()
    destination = core_module.result_destination(operation, root)
    result = core_module.base_result(operation)
    result["mutation"]["authorized"] = True
    supervisor = core_module.CommandSupervisor()

    try:
        progress.phase(2, "evaluating resumable publication guards")
        root, commands, starting = _evaluate_identity(operation, supervisor)
        result["commands"].extend(commands)
        result["starting_state"] = starting
        result["validation_evidence"] = combined_publication._verify_validation(
            operation
        )
        progress.check("reviewed validation evidence verified")

        parent = operation["expected_mutations"]["parent_head"]
        progress.phase(3, "classifying and completing Git publication")
        result["mutation"]["attempted"] = True
        if starting["head"] == parent:
            if starting["clean"]:
                raise core_module.GuardError(
                    "planned parent is clean and contains no publishable change"
                )
            git_evidence = git_publication.publish_git_changes(
                root,
                supervisor,
                operation["inputs"],
                operation["expected_mutations"],
                {
                    "push": True,
                    "remote": operation["publication"]["remote"],
                    "branch": operation["publication"]["branch"],
                },
                push_authorized=True,
                progress=progress,
            )
            git_evidence["staging"] = "performed"
            git_evidence["commit_creation"] = "performed"
            git_evidence["push"] = "performed"
        else:
            git_evidence = _existing_commit(
                operation, root, supervisor, starting
            )
            _push_or_verify(
                operation, root, supervisor, git_evidence
            )
        result["mutation"]["observed"] = any(
            git_evidence.get(field) == "performed"
            for field in ("staging", "commit_creation", "push")
        )
        result["commands"].extend(git_evidence.pop("commands", []))
        commit = git_evidence["commit"]

        progress.phase(4, "creating or verifying pull request")
        pull_request, pr_commands = combined_publication._pull_request(
            operation, commit, supervisor, root
        )
        pull_request["disposition"] = (
            "performed" if pull_request["created"] else "already-completed"
        )
        result["commands"].extend(pr_commands)
        result["publication"] = {
            "git": git_evidence,
            "pull_request": pull_request,
            "verified": True,
        }

        ending_commands, ending = core_module.capture_repository_state(
            root, supervisor
        )
        result["commands"].extend(ending_commands)
        result["ending_state"] = ending
        if (
            ending["branch"] != operation["guards"]["branch"]
            or ending["head"] != commit
            or not ending["clean"]
        ):
            raise core_module.ExecutorError(
                "combined publication terminal repository state is invalid"
            )
        result["mutation"]["completed"] = True
        result["terminal_status"] = "publication-completed"
        result["safest_next_interaction"] = (
            "Review the exact commit, remote branch, and pull request evidence."
        )
    except core_module.GuardError as exc:
        result["terminal_status"] = (
            "partial-remote-mutation"
            if result["mutation"]["observed"]
            else "guard-failed"
        )
        result["diagnostics"].append(str(exc))
    except (
        core_module.ExecutorError,
        git_publication.GitPublicationError,
        OSError,
    ) as exc:
        observed = result["mutation"]["observed"] or getattr(
            exc, "mutation_observed", False
        )
        result["mutation"]["observed"] = observed
        result["terminal_status"] = (
            "partial-remote-mutation"
            if observed
            else (
                "partial-local-mutation"
                if result["mutation"]["attempted"]
                else "pre-mutation-failed"
            )
        )
        result["diagnostics"].append(str(exc))
        extra_commands = getattr(exc, "commands", None)
        if extra_commands:
            result["commands"].extend(extra_commands)
        extra_evidence = getattr(exc, "evidence", None)
        if extra_evidence:
            result.setdefault("publication", {})[
                "failure_evidence"
            ] = extra_evidence
    finally:
        result["finished_at"] = core_module.utc_now()

    progress.phase(5, "writing combined publication evidence")
    core_module.write_result_exclusive(destination, result)
    progress.check("result artifact created without overwrite")
    return result, destination


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print(
            "usage: ./scripts/governed-execute /path/to/operation.json",
            file=sys.stderr,
        )
        return 64
    operation_path = Path(args[0]).expanduser().resolve()
    destination: Path | None = None
    progress = core_module.TerminalProgress()
    try:
        print(f"Governed Executor {core_module.EXECUTOR_VERSION}", flush=True)
        progress.phase(1, "validating resumable Git publication description")
        operation = combined_publication.load_operation(operation_path)
        destination = core_module.result_destination(
            operation,
            Path(operation["repository"]["root"]).expanduser().resolve(),
        )
        progress.check("closed combined publication contract verified")
        progress.check("validation-evidence boundary verified")
        progress.check("operation digest verified")
        result, destination = execute(operation, progress)
        print("")
        print("-" * 60)
        print(f"STATUS: {result['terminal_status']}")
        print("")
        print("Result:")
        print(f"  {destination}")
        print("")
        print("Next step:")
        print(f"  {result['safest_next_interaction']}")
        return 0 if result["terminal_status"] == "publication-completed" else 1
    except core_module.ExecutorError as exc:
        print("", file=sys.stderr)
        print("-" * 60, file=sys.stderr)
        print("STATUS: executor-failed", file=sys.stderr)
        print(f"Reason: {exc}", file=sys.stderr)
        if destination is not None:
            print(f"Result: {destination}", file=sys.stderr)
        return 1
