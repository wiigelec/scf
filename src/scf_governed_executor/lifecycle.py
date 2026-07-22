from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import core as core_module
from . import strict_validation


LIFECYCLE_OPERATION_TYPES = frozenset(
    {"git-stage", "git-commit", "git-push", "pull-request-create"}
)
SHA1 = re.compile(r"^[0-9a-f]{40}$")
REMOTE = re.compile(r"^[A-Za-z0-9._-]+$")
BRANCH = re.compile(
    r"^(?!/)(?!.*(?:\.\.|//|@\{|\\))(?!.*[/.]$)[A-Za-z0-9._/-]+$"
)


_STRICT = strict_validation.StrictValidator(core_module.SchemaError)


def _object(value: Any, location: str) -> dict[str, Any]:
    return _STRICT.object(value, location)


def _exact(
    value: Mapping[str, Any],
    allowed: set[str] | frozenset[str],
    required: set[str] | frozenset[str],
    location: str,
) -> None:
    _STRICT.exact_fields(value, allowed, required, location)


def _string(value: Any, location: str, *, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise core_module.SchemaError(f"{location} must be a non-empty string")
    if "\x00" in value or len(value.encode("utf-8")) > maximum:
        raise core_module.SchemaError(f"{location} is invalid")
    return value


def _path(value: Any, location: str) -> str:
    text = _string(value, location)
    candidate = Path(text)
    if candidate.is_absolute() or any(
        part in ("", ".", "..") for part in candidate.parts
    ):
        raise core_module.SchemaError(
            f"{location} must be normalized and repository-relative"
        )
    if candidate.as_posix() != text:
        raise core_module.SchemaError(
            f"{location} must use normalized POSIX form"
        )
    return text


def _empty_sections(operation: Mapping[str, Any], *names: str) -> None:
    for name in names:
        if _object(operation[name], name):
            raise core_module.SchemaError(
                f"{name} must be empty for {operation['operation_type']}"
            )


def _require_authorization(
    authorization: Mapping[str, bool], required: set[str]
) -> None:
    if not all(authorization[field] for field in required):
        raise core_module.SchemaError(
            f"{', '.join(sorted(required))} authorization is required"
        )
    enabled = sorted(
        field
        for field in core_module.AUTHORIZATION_FIELDS - required
        if authorization[field]
    )
    if enabled:
        raise core_module.SchemaError(
            "operation broadens authorization: " + ", ".join(enabled)
        )


def _validate_paths(value: Any, location: str) -> list[str]:
    if not isinstance(value, list) or not value or len(value) > 500:
        raise core_module.SchemaError(
            f"{location} must be a non-empty array of at most 500 paths"
        )
    paths = [_path(item, f"{location}[{index}]") for index, item in enumerate(value)]
    if paths != sorted(set(paths)):
        raise core_module.SchemaError(
            f"{location} must be unique and lexicographically sorted"
        )
    return paths


def validate_lifecycle_contract(operation: dict[str, Any]) -> dict[str, Any]:
    operation_type = operation["operation_type"]
    authorization = operation["authorization"]
    inputs = _object(operation["inputs"], "inputs")
    expected = _object(operation["expected_mutations"], "expected_mutations")
    publication = _object(operation["publication"], "publication")
    _empty_sections(operation, "validation")

    if operation_type == "git-stage":
        _require_authorization(authorization, {"interrogate", "stage"})
        _exact(inputs, {"paths"}, {"paths"}, "inputs")
        paths = _validate_paths(inputs["paths"], "inputs.paths")
        _exact(expected, {"paths", "head"}, {"paths", "head"}, "expected_mutations")
        if expected != {"paths": paths, "head": operation["guards"]["head"]}:
            raise core_module.SchemaError(
                "expected_mutations must exactly match staged paths and guarded HEAD"
            )
        _empty_sections(operation, "publication")
    elif operation_type == "git-commit":
        _require_authorization(authorization, {"interrogate", "commit"})
        _exact(inputs, {"message"}, {"message"}, "inputs")
        _string(inputs["message"], "inputs.message")
        _exact(
            expected,
            {"paths", "parent_head"},
            {"paths", "parent_head"},
            "expected_mutations",
        )
        _validate_paths(expected["paths"], "expected_mutations.paths")
        if expected["parent_head"] != operation["guards"]["head"]:
            raise core_module.SchemaError(
                "expected_mutations.parent_head must match guards.head"
            )
        _empty_sections(operation, "publication")
    elif operation_type == "git-push":
        _require_authorization(authorization, {"interrogate", "push"})
        _exact(inputs, set(), set(), "inputs")
        _exact(
            expected,
            {"head", "remote", "branch"},
            {"head", "remote", "branch"},
            "expected_mutations",
        )
        if expected["head"] != operation["guards"]["head"]:
            raise core_module.SchemaError(
                "expected_mutations.head must match guards.head"
            )
        if not isinstance(expected["remote"], str) or not REMOTE.fullmatch(
            expected["remote"]
        ):
            raise core_module.SchemaError(
                "expected_mutations.remote has invalid form"
            )
        if not isinstance(expected["branch"], str) or not BRANCH.fullmatch(
            expected["branch"]
        ):
            raise core_module.SchemaError(
                "expected_mutations.branch has invalid form"
            )
        _exact(
            publication,
            {"remote", "branch"},
            {"remote", "branch"},
            "publication",
        )
        if publication != {
            "remote": expected["remote"],
            "branch": expected["branch"],
        }:
            raise core_module.SchemaError(
                "publication must exactly match expected remote and branch"
            )
        if operation["guards"]["clean"] is not True:
            raise core_module.SchemaError(
                "git-push requires a clean repository"
            )
    else:
        _require_authorization(authorization, {"interrogate", "pull_request"})
        _exact(
            inputs,
            {"base", "head", "title", "body", "draft"},
            {"base", "head", "title", "body", "draft"},
            "inputs",
        )
        for field in ("base", "head"):
            if not isinstance(inputs[field], str) or not BRANCH.fullmatch(
                inputs[field]
            ):
                raise core_module.SchemaError(
                    f"inputs.{field} has invalid form"
                )
        _string(inputs["title"], "inputs.title", maximum=256)
        _string(inputs["body"], "inputs.body", maximum=65536)
        if not isinstance(inputs["draft"], bool):
            raise core_module.SchemaError("inputs.draft must be boolean")
        _exact(
            expected,
            {"head_sha"},
            {"head_sha"},
            "expected_mutations",
        )
        if not isinstance(expected["head_sha"], str) or not SHA1.fullmatch(
            expected["head_sha"]
        ):
            raise core_module.SchemaError(
                "expected_mutations.head_sha must be a lowercase full commit id"
            )
        _empty_sections(operation, "publication")
    return operation


def load_lifecycle_operation(path: Path) -> dict[str, Any]:
    try:
        operation = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-standard JSON constant: {value}")
            ),
        )
    except OSError as exc:
        raise core_module.SchemaError(f"cannot read operation: {exc}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise core_module.SchemaError(f"invalid operation JSON: {exc}") from exc

    operation = _object(operation, "operation")
    _exact(
        operation,
        core_module.TOP_LEVEL_FIELDS,
        core_module.TOP_LEVEL_FIELDS,
        "operation",
    )
    if operation["schema_version"] != core_module.OPERATION_SCHEMA_VERSION:
        raise core_module.SchemaError("unsupported operation schema version")
    if operation["executor_version"] != core_module.EXECUTOR_VERSION:
        raise core_module.SchemaError("incompatible executor version")
    if operation["operation_type"] not in LIFECYCLE_OPERATION_TYPES:
        raise core_module.SchemaError("unsupported lifecycle operation type")
    if not isinstance(operation["operation_id"], str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}", operation["operation_id"]
    ):
        raise core_module.SchemaError("operation_id has invalid form")
    if not isinstance(operation["operation_digest"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", operation["operation_digest"]
    ):
        raise core_module.SchemaError(
            "operation_digest must be lowercase SHA-256"
        )
    if operation["operation_digest"] != core_module.operation_digest(operation):
        raise core_module.SchemaError("operation digest mismatch")

    repository = _object(operation["repository"], "repository")
    _exact(
        repository,
        core_module.REPOSITORY_FIELDS,
        core_module.REPOSITORY_FIELDS,
        "repository",
    )
    for field in core_module.REPOSITORY_FIELDS:
        _string(repository[field], f"repository.{field}")

    guards = _object(operation["guards"], "guards")
    _exact(
        guards,
        core_module.GUARD_FIELDS,
        core_module.GUARD_FIELDS,
        "guards",
    )
    _string(guards["branch"], "guards.branch")
    if not isinstance(guards["head"], str) or not SHA1.fullmatch(guards["head"]):
        raise core_module.SchemaError(
            "guards.head must be a lowercase full commit id"
        )
    if not isinstance(guards["clean"], bool):
        raise core_module.SchemaError("guards.clean must be boolean")

    authorization = _object(operation["authorization"], "authorization")
    _exact(
        authorization,
        core_module.AUTHORIZATION_FIELDS,
        core_module.AUTHORIZATION_FIELDS,
        "authorization",
    )
    for field, value in authorization.items():
        if not isinstance(value, bool):
            raise core_module.SchemaError(
                f"authorization.{field} must be boolean"
            )

    result = _object(operation["result"], "result")
    _exact(
        result,
        core_module.RESULT_FIELDS,
        core_module.RESULT_FIELDS,
        "result",
    )
    _string(result["directory"], "result.directory")
    if not isinstance(result["filename"], str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{7,191}\.result\.json",
        result["filename"],
    ):
        raise core_module.SchemaError("result.filename has invalid form")
    return validate_lifecycle_contract(operation)


def _record(record: Any) -> dict[str, Any]:
    return core_module.command_record_dict(record)


def _run(
    supervisor: core_module.CommandSupervisor,
    root: Path,
    command: Sequence[str],
    commands: list[dict[str, Any]],
    *,
    phase: str,
    timeout: float = 60.0,
) -> str:
    record = supervisor.run(
        list(command), root, timeout_seconds=timeout, phase=phase
    )
    commands.append(_record(record))
    if record.exit_code != 0:
        raise core_module.ExecutorError(
            record.stderr.strip() or f"{phase} failed"
        )
    return record.stdout.strip()


def _git(
    supervisor: core_module.CommandSupervisor,
    root: Path,
    commands: list[dict[str, Any]],
    *arguments: str,
    phase: str,
    timeout: float = 60.0,
) -> str:
    return _run(
        supervisor,
        root,
        ["git", *arguments],
        commands,
        phase=phase,
        timeout=timeout,
    )


def _ensure_exact_state(
    root: Path,
    supervisor: core_module.CommandSupervisor,
    operation: Mapping[str, Any],
    commands: list[dict[str, Any]],
) -> None:
    branch = _git(
        supervisor, root, commands, "branch", "--show-current",
        phase="verify lifecycle branch",
    )
    head = _git(
        supervisor, root, commands, "rev-parse", "HEAD",
        phase="verify lifecycle head",
    )
    if branch != operation["guards"]["branch"]:
        raise core_module.GuardError(
            "lifecycle branch changed before mutation"
        )
    if head != operation["guards"]["head"]:
        raise core_module.GuardError(
            "lifecycle HEAD changed before mutation"
        )


def _execute_stage(root, supervisor, operation, commands):
    _ensure_exact_state(root, supervisor, operation, commands)
    paths = operation["inputs"]["paths"]
    conflicts = _git(
        supervisor, root, commands, "diff", "--name-only", "--diff-filter=U",
        phase="verify no conflicts",
    )
    if conflicts:
        raise core_module.GuardError(
            "unmerged paths prevent governed staging"
        )
    staged_before = _git(
        supervisor, root, commands, "diff", "--cached", "--name-only",
        phase="verify empty starting index",
    )
    if staged_before:
        raise core_module.GuardError(
            "index must be empty before git-stage"
        )
    _git(
        supervisor, root, commands, "add", "--", *paths,
        phase="stage exact paths",
    )
    staged = _git(
        supervisor, root, commands, "diff", "--cached", "--name-only",
        phase="verify staged paths",
    )
    actual = staged.splitlines() if staged else []
    if actual != paths:
        raise core_module.ExecutorError(
            "staged path set does not exactly match authorization"
        )
    _git(
        supervisor, root, commands, "diff", "--cached", "--check",
        phase="verify staged content",
    )
    return {"paths": actual, "verified": True}


def _execute_commit(root, supervisor, operation, commands):
    _ensure_exact_state(root, supervisor, operation, commands)
    expected = operation["expected_mutations"]
    staged = _git(
        supervisor, root, commands, "diff", "--cached", "--name-only",
        phase="verify staged paths",
    )
    staged_paths = staged.splitlines() if staged else []
    if staged_paths != expected["paths"]:
        raise core_module.GuardError(
            "staged path set does not exactly match commit authorization"
        )
    _git(
        supervisor, root, commands, "diff", "--cached", "--check",
        phase="verify staged content",
    )
    _git(
        supervisor, root, commands, "commit", "--no-gpg-sign", "-m",
        operation["inputs"]["message"],
        phase="create governed commit",
    )
    commit = _git(
        supervisor, root, commands, "rev-parse", "HEAD",
        phase="verify created commit",
    )
    parent = _git(
        supervisor, root, commands, "rev-parse", "HEAD^",
        phase="verify commit parent",
    )
    if parent != expected["parent_head"]:
        raise core_module.ExecutorError(
            "created commit has unexpected parent"
        )
    committed = _git(
        supervisor, root, commands, "diff-tree", "--no-commit-id",
        "--name-only", "-r", "HEAD",
        phase="verify committed paths",
    )
    committed_paths = committed.splitlines() if committed else []
    if committed_paths != expected["paths"]:
        raise core_module.ExecutorError(
            "created commit contains unauthorized paths"
        )
    tree = _git(
        supervisor, root, commands, "rev-parse", "HEAD^{tree}",
        phase="verify commit tree",
    )
    return {
        "commit": commit,
        "parent": parent,
        "tree": tree,
        "paths": committed_paths,
        "verified": True,
    }


def _execute_push(root, supervisor, operation, commands):
    _ensure_exact_state(root, supervisor, operation, commands)
    expected = operation["expected_mutations"]
    status = _git(
        supervisor, root, commands, "status", "--porcelain=v1",
        phase="verify clean push state",
    )
    if status:
        raise core_module.GuardError(
            "git-push requires a clean index and worktree"
        )
    branch = _git(
        supervisor, root, commands, "branch", "--show-current",
        phase="verify attached push branch",
    )
    if not branch:
        raise core_module.GuardError(
            "git-push refuses detached HEAD"
        )
    remote = expected["remote"]
    destination = expected["branch"]
    remote_line = _git(
        supervisor, root, commands, "ls-remote", "--heads", remote,
        f"refs/heads/{destination}",
        phase="inspect destination branch",
    )
    remote_before = remote_line.split()[0] if remote_line else None
    if remote_before:
        ancestor = supervisor.run(
            ["git", "merge-base", "--is-ancestor",
             remote_before, expected["head"]],
            root,
            timeout_seconds=30,
            phase="verify fast-forward publication",
        )
        commands.append(_record(ancestor))
        if ancestor.exit_code != 0:
            raise core_module.GuardError(
                "destination branch is not a fast-forward ancestor"
            )
    _git(
        supervisor, root, commands, "push", "--porcelain", remote,
        f"HEAD:refs/heads/{destination}",
        phase="push exact clean HEAD",
        timeout=120,
    )
    remote_line = _git(
        supervisor, root, commands, "ls-remote", "--heads", remote,
        f"refs/heads/{destination}",
        phase="verify remote branch",
    )
    remote_after = remote_line.split()[0] if remote_line else ""
    if remote_after != expected["head"]:
        raise core_module.ExecutorError(
            "remote read-after-write verification failed"
        )
    return {
        "remote": remote,
        "branch": destination,
        "remote_before": remote_before,
        "remote_commit": remote_after,
        "verified": True,
    }


def _execute_pull_request(root, supervisor, operation, commands):
    inputs = operation["inputs"]
    expected_sha = operation["expected_mutations"]["head_sha"]
    remote_line = _git(
        supervisor, root, commands, "ls-remote", "--heads", "origin",
        f"refs/heads/{inputs['head']}",
        phase="verify pull-request head",
    )
    remote_sha = remote_line.split()[0] if remote_line else ""
    if remote_sha != expected_sha:
        raise core_module.GuardError(
            "pull-request head branch does not resolve to expected commit"
        )
    existing = _run(
        supervisor,
        root,
        [
            "gh", "pr", "list", "--state", "open",
            "--head", inputs["head"], "--base", inputs["base"],
            "--json", "number,url,headRefOid",
        ],
        commands,
        phase="check existing pull request",
    )
    if json.loads(existing or "[]"):
        raise core_module.GuardError(
            "an open pull request already exists for this base and head"
        )
    command = [
        "gh", "pr", "create", "--base", inputs["base"],
        "--head", inputs["head"], "--title", inputs["title"],
        "--body", inputs["body"],
    ]
    if inputs["draft"]:
        command.append("--draft")
    created = _run(
        supervisor, root, command, commands,
        phase="create pull request", timeout=120,
    )
    view = _run(
        supervisor,
        root,
        [
            "gh", "pr", "view", inputs["head"], "--json",
            "number,url,state,isDraft,baseRefName,headRefName,"
            "headRefOid,title,body",
        ],
        commands,
        phase="verify pull request",
    )
    evidence = json.loads(view)
    required = {
        "baseRefName": inputs["base"],
        "headRefName": inputs["head"],
        "headRefOid": expected_sha,
        "title": inputs["title"],
        "body": inputs["body"],
        "isDraft": inputs["draft"],
        "state": "OPEN",
    }
    for field, value in required.items():
        if evidence.get(field) != value:
            raise core_module.ExecutorError(
                f"pull-request read-after-write verification failed: {field}"
            )
    evidence["created_output"] = created
    evidence["verified"] = True
    return evidence


def execute_lifecycle(
    operation: Mapping[str, Any],
    progress: core_module.TerminalProgress,
) -> tuple[dict[str, Any], Path]:
    result = core_module.base_result(operation)
    result["mutation"]["authorized"] = True
    supervisor = core_module.CommandSupervisor()
    repository_root = (
        Path(operation["repository"]["root"]).expanduser().resolve()
    )
    destination = core_module.result_destination(
        operation, repository_root
    )
    if destination.exists():
        raise core_module.ResultConflictError(
            f"result already exists: {destination}"
        )
    commands: list[dict[str, Any]] = []
    remote_type = operation["operation_type"] in {
        "git-push", "pull-request-create"
    }
    try:
        progress.phase(2, "evaluating lifecycle guards")
        root, guard_commands, state = (
            core_module.evaluate_repository_guards(
                operation, supervisor, progress
            )
        )
        commands.extend(guard_commands)
        result["starting_state"] = state
        progress.check("repository identity and exact state verified")
        progress.phase(
            3, f"performing {operation['operation_type']}"
        )
        result["mutation"]["attempted"] = True
        if operation["operation_type"] == "git-stage":
            evidence = _execute_stage(
                root, supervisor, operation, commands
            )
            terminal = "local-mutation-completed"
        elif operation["operation_type"] == "git-commit":
            evidence = _execute_commit(
                root, supervisor, operation, commands
            )
            terminal = "commit-completed"
        elif operation["operation_type"] == "git-push":
            evidence = _execute_push(
                root, supervisor, operation, commands
            )
            terminal = "publication-completed"
        else:
            evidence = _execute_pull_request(
                root, supervisor, operation, commands
            )
            terminal = "publication-completed"
        result["mutation"]["observed"] = True
        result["mutation"]["completed"] = True
        result["publication"] = evidence
        progress.phase(4, "verifying resulting state")
        ending_commands, ending_state = (
            core_module.capture_repository_state(root, supervisor)
        )
        commands.extend(ending_commands)
        result["ending_state"] = ending_state
        result["terminal_status"] = terminal
        result["safest_next_interaction"] = (
            "Review exact lifecycle mutation and verification evidence."
        )
    except core_module.GuardError as exc:
        result["terminal_status"] = "guard-failed"
        result["diagnostics"].append(str(exc))
    except (
        core_module.ExecutorError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        result["mutation"]["observed"] = result["mutation"]["attempted"]
        result["terminal_status"] = (
            "partial-remote-mutation"
            if remote_type and result["mutation"]["attempted"]
            else "partial-local-mutation"
            if result["mutation"]["attempted"]
            else "pre-mutation-failed"
        )
        result["diagnostics"].append(str(exc))
        try:
            ending_commands, ending_state = (
                core_module.capture_repository_state(
                    repository_root, supervisor
                )
            )
            commands.extend(ending_commands)
            result["ending_state"] = ending_state
        except core_module.ExecutorError as state_exc:
            result["diagnostics"].append(
                f"ending-state capture failed: {state_exc}"
            )
    finally:
        result["commands"].extend(commands)
        result["finished_at"] = core_module.utc_now()

    progress.phase(5, "writing execution evidence")
    core_module.write_result_exclusive(destination, result)
    progress.check("result artifact created without overwrite")
    return result, destination


def lifecycle_main(argv: Sequence[str] | None = None) -> int:
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
        print(
            f"Governed Executor {core_module.EXECUTOR_VERSION}",
            flush=True,
        )
        progress.phase(
            1, "validating lifecycle operation description"
        )
        operation = load_lifecycle_operation(operation_path)
        destination = core_module.result_destination(
            operation,
            Path(operation["repository"]["root"]).expanduser().resolve(),
        )
        progress.check("closed lifecycle contract verified")
        progress.check("authorization separation verified")
        progress.check("operation digest verified")
        print("", flush=True)
        print(
            f"Repository : {operation['repository']['root']}",
            flush=True,
        )
        print(f"Revision   : {operation['guards']['head']}", flush=True)
        print(f"Operation  : {operation['operation_id']}", flush=True)
        print(f"Type       : {operation['operation_type']}", flush=True)
        print(f"Result     : {destination}", flush=True)
        print("", flush=True)
        result, destination = execute_lifecycle(operation, progress)
        print("", flush=True)
        print("-" * 60, flush=True)
        print(f"STATUS: {result['terminal_status']}", flush=True)
        print("", flush=True)
        print("Result:", flush=True)
        print(f"  {destination}", flush=True)
        print("", flush=True)
        print("Next step:", flush=True)
        print(f"  {result['safest_next_interaction']}", flush=True)
        return 0 if result["terminal_status"] in {
            "local-mutation-completed",
            "commit-completed",
            "publication-completed",
        } else 1
    except core_module.ExecutorError as exc:
        print("", file=sys.stderr, flush=True)
        print("-" * 60, file=sys.stderr, flush=True)
        print(
            "STATUS: executor-failed", file=sys.stderr, flush=True
        )
        print(f"Reason: {exc}", file=sys.stderr, flush=True)
        if destination is not None:
            print(
                f"Result: {destination}",
                file=sys.stderr,
                flush=True,
            )
        return 1
