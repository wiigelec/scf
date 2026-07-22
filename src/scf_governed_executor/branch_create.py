from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import core as core_module
from . import strict_validation


BRANCH_CREATE_OPERATION_TYPE = "git-branch-create"
SHA1 = re.compile(r"^[0-9a-f]{40}$")
BRANCH = re.compile(
    r"^(?!/)(?!.*(?:\.\.|//|@\{|\\))(?!.*[/.]$)[A-Za-z0-9._/-]+$"
)


_STRICT = strict_validation.StrictValidator(core_module.SchemaError)

def _object(value: Any, location: str) -> dict[str, Any]:
    return _STRICT.object(value, location)


def _exact(
    value: Mapping[str, Any],
    allowed: set[str],
    required: set[str],
    location: str,
) -> None:
    _STRICT.exact_fields(value, allowed, required, location)


def _record(record: Any) -> dict[str, Any]:
    return core_module.command_record_dict(record)


def _git(
    supervisor: core_module.CommandSupervisor,
    root: Path,
    commands: list[dict[str, Any]],
    *arguments: str,
    phase: str,
) -> str:
    record = supervisor.run(
        ["git", *arguments],
        root,
        timeout_seconds=30,
        phase=phase,
    )
    commands.append(_record(record))
    if record.exit_code != 0:
        raise core_module.ExecutorError(
            record.stderr.strip() or f"{phase} failed"
        )
    return record.stdout.strip()


def validate_branch_create_contract(
    operation: Mapping[str, Any],
) -> dict[str, Any]:
    authorization = _object(operation["authorization"], "authorization")
    required = {"interrogate", "edit"}
    if not all(authorization[field] for field in required):
        raise core_module.SchemaError(
            "git-branch-create requires interrogate and edit authorization"
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

    inputs = _object(operation["inputs"], "inputs")
    _exact(
        inputs,
        {"base", "branch"},
        {"base", "branch"},
        "inputs",
    )
    base = inputs["base"]
    branch = inputs["branch"]
    if not isinstance(base, str) or not SHA1.fullmatch(base):
        raise core_module.SchemaError(
            "inputs.base must be a lowercase full commit id"
        )
    if not isinstance(branch, str) or not BRANCH.fullmatch(branch):
        raise core_module.SchemaError("inputs.branch has invalid form")
    if branch == operation["guards"]["branch"]:
        raise core_module.SchemaError(
            "inputs.branch must differ from the guarded branch"
        )

    expected = _object(
        operation["expected_mutations"], "expected_mutations"
    )
    _exact(
        expected,
        {"base", "branch"},
        {"base", "branch"},
        "expected_mutations",
    )
    if expected != {"base": base, "branch": branch}:
        raise core_module.SchemaError(
            "expected_mutations must exactly match branch inputs"
        )
    if base != operation["guards"]["head"]:
        raise core_module.SchemaError(
            "inputs.base must match guards.head"
        )
    if operation["guards"]["clean"] is not True:
        raise core_module.SchemaError(
            "git-branch-create requires a clean repository"
        )

    for name in ("validation", "publication"):
        if _object(operation[name], name):
            raise core_module.SchemaError(
                f"{name} must be empty for git-branch-create"
            )
    return dict(operation)


def execute_branch_create(
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
    root: Path | None = None
    try:
        progress.phase(2, "evaluating branch-creation guards")
        root, guard_commands, state = (
            core_module.evaluate_repository_guards(
                operation, supervisor, progress
            )
        )
        commands.extend(guard_commands)
        result["starting_state"] = state
        progress.check("repository identity and exact state verified")

        base = operation["inputs"]["base"]
        branch = operation["inputs"]["branch"]
        resolved = _git(
            supervisor,
            root,
            commands,
            "rev-parse",
            "--verify",
            f"{base}^{{commit}}",
            phase="verify exact branch base",
        )
        if resolved != base:
            raise core_module.GuardError(
                "branch base does not resolve to the guarded commit"
            )

        check = supervisor.run(
            ["git", "show-ref", "--verify", "--quiet",
             f"refs/heads/{branch}"],
            root,
            timeout_seconds=30,
            phase="verify target branch absence",
        )
        commands.append(_record(check))
        if check.exit_code == 0:
            raise core_module.GuardError(
                "target local branch already exists"
            )
        if check.exit_code != 1:
            raise core_module.ExecutorError(
                check.stderr.strip()
                or "target branch absence check failed"
            )

        progress.phase(3, "creating and entering issue branch")
        result["mutation"]["attempted"] = True
        _git(
            supervisor,
            root,
            commands,
            "switch",
            "-c",
            branch,
            base,
            phase="create exact local issue branch",
        )
        result["mutation"]["observed"] = True

        progress.phase(4, "verifying resulting branch state")
        ending_commands, ending_state = (
            core_module.capture_repository_state(root, supervisor)
        )
        commands.extend(ending_commands)
        result["ending_state"] = ending_state
        if ending_state["branch"] != branch:
            raise core_module.ExecutorError(
                "ending branch does not match requested branch"
            )
        if ending_state["head"] != base:
            raise core_module.ExecutorError(
                "branch creation changed the exact base commit"
            )
        if not ending_state["clean"]:
            raise core_module.ExecutorError(
                "branch creation left a dirty repository"
            )

        result["mutation"]["completed"] = True
        result["terminal_status"] = "local-mutation-completed"
        result["publication"] = {
            "branch": branch,
            "base": base,
            "local_only": True,
            "verified": True,
        }
        result["safest_next_interaction"] = (
            "Review the created local branch before any successor operation."
        )
    except core_module.GuardError as exc:
        result["terminal_status"] = "guard-failed"
        result["diagnostics"].append(str(exc))
    except (core_module.ExecutorError, OSError) as exc:
        result["mutation"]["observed"] = result["mutation"]["attempted"]
        result["terminal_status"] = (
            "partial-local-mutation"
            if result["mutation"]["attempted"]
            else "pre-mutation-failed"
        )
        result["diagnostics"].append(str(exc))
        try:
            ending_commands, ending_state = (
                core_module.capture_repository_state(
                    root or repository_root, supervisor
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
