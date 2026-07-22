from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from . import core as core_module
from . import strict_validation


OPERATION_TYPE = "development-session-initialize"
DETAILED_HEADING = "## Governed detailed scope"
PATCH_PLAN_HEADING = "## Governed work breakdown and patch plan"
SHA1 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
BRANCH = re.compile(
    r"^(?!/)(?!.*(?:\.\.|//|@\{|\\))(?!.*[/.]$)[A-Za-z0-9._/-]+$"
)


_STRICT = strict_validation.StrictValidator(core_module.SchemaError)


class SessionInitializationError(core_module.ExecutorError):
    def __init__(
        self,
        message: str,
        *,
        evidence: Mapping[str, Any] | None = None,
        remote_may_have_mutated: bool = False,
    ) -> None:
        super().__init__(message)
        self.evidence = dict(evidence or {})
        self.remote_may_have_mutated = remote_may_have_mutated


def _object(value: Any, location: str) -> dict[str, Any]:
    return _STRICT.object(value, location)

def _exact(
    value: Mapping[str, Any],
    allowed: set[str] | frozenset[str],
    required: set[str] | frozenset[str],
    location: str,
) -> None:
    _STRICT.exact_fields(value, allowed, required, location)

def _string(value: Any, location: str, *, maximum: int = 65536) -> str:
    if not isinstance(value, str) or not value:
        raise core_module.SchemaError(f"{location} must be a non-empty string")
    if "\x00" in value or len(value.encode("utf-8")) > maximum:
        raise core_module.SchemaError(f"{location} is invalid")
    return value


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_origin(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    if normalized.startswith("git@github.com:"):
        normalized = "https://github.com/" + normalized[len("git@github.com:"):]
    elif normalized.startswith("ssh://git@github.com/"):
        normalized = "https://github.com/" + normalized[len("ssh://git@github.com/"):]
    return normalized.rstrip("/")


def _repository_slug(origin: str) -> str:
    parsed = urlsplit(_canonical_origin(origin))
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise core_module.SchemaError(
            "development-session-initialize requires a canonical GitHub HTTPS origin"
        )
    slug = parsed.path.strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", slug):
        raise core_module.SchemaError("repository origin is not a GitHub repository")
    return slug


def load_operation(path: Path) -> dict[str, Any]:
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
    if operation["operation_type"] != OPERATION_TYPE:
        raise core_module.SchemaError("unsupported development initialization type")
    if operation["executor_version"] != core_module.EXECUTOR_VERSION:
        raise core_module.SchemaError("incompatible executor version")
    if not isinstance(operation["operation_id"], str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}", operation["operation_id"]
    ):
        raise core_module.SchemaError("operation_id has invalid form")
    digest = operation["operation_digest"]
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise core_module.SchemaError("operation_digest must be lowercase SHA-256")
    if digest != core_module.operation_digest(operation):
        raise core_module.SchemaError("operation digest mismatch")

    repository = _object(operation["repository"], "repository")
    _exact(repository, {"root", "origin"}, {"root", "origin"}, "repository")
    _string(repository["root"], "repository.root")
    _string(repository["origin"], "repository.origin")
    _repository_slug(repository["origin"])

    guards = _object(operation["guards"], "guards")
    _exact(guards, {"clean"}, {"clean"}, "guards")
    if guards["clean"] is not True:
        raise core_module.SchemaError(
            "development-session-initialize requires guards.clean=true"
        )

    authorization = _object(operation["authorization"], "authorization")
    _exact(
        authorization,
        core_module.AUTHORIZATION_FIELDS,
        core_module.AUTHORIZATION_FIELDS,
        "authorization",
    )
    if any(not isinstance(value, bool) for value in authorization.values()):
        raise core_module.SchemaError("authorization values must be boolean")
    required = {"interrogate", "edit", "issue"}
    if not all(authorization[field] for field in required):
        raise core_module.SchemaError(
            "development-session-initialize requires interrogate, edit, and issue authorization"
        )
    broadened = sorted(
        field
        for field in core_module.AUTHORIZATION_FIELDS - required
        if authorization[field]
    )
    if broadened:
        raise core_module.SchemaError(
            "operation broadens authorization: " + ", ".join(broadened)
        )

    inputs = _object(operation["inputs"], "inputs")
    _exact(
        inputs,
        {"issue", "branch", "detailed_scope_body", "patch_plan_body"},
        {"issue", "branch", "detailed_scope_body", "patch_plan_body"},
        "inputs",
    )
    issue = inputs["issue"]
    if not isinstance(issue, int) or isinstance(issue, bool) or issue <= 0:
        raise core_module.SchemaError("inputs.issue must be a positive integer")
    branch = inputs["branch"]
    if not isinstance(branch, str) or not BRANCH.fullmatch(branch):
        raise core_module.SchemaError("inputs.branch has invalid form")
    if branch == "main":
        raise core_module.SchemaError("inputs.branch must differ from main")
    detailed = _string(inputs["detailed_scope_body"], "inputs.detailed_scope_body")
    patch_plan = _string(inputs["patch_plan_body"], "inputs.patch_plan_body")
    if not detailed.startswith(DETAILED_HEADING + "\n"):
        raise core_module.SchemaError(
            "inputs.detailed_scope_body must begin with the designated heading"
        )
    if not patch_plan.startswith(PATCH_PLAN_HEADING + "\n"):
        raise core_module.SchemaError(
            "inputs.patch_plan_body must begin with the designated heading"
        )

    expected = _object(operation["expected_mutations"], "expected_mutations")
    _exact(
        expected,
        {
            "issue",
            "branch",
            "detailed_scope_body_sha256",
            "patch_plan_body_sha256",
        },
        {
            "issue",
            "branch",
            "detailed_scope_body_sha256",
            "patch_plan_body_sha256",
        },
        "expected_mutations",
    )
    required_expected = {
        "issue": issue,
        "branch": branch,
        "detailed_scope_body_sha256": _digest(detailed),
        "patch_plan_body_sha256": _digest(patch_plan),
    }
    if expected != required_expected:
        raise core_module.SchemaError(
            "expected_mutations must exactly match initialization inputs"
        )

    if _object(operation["validation"], "validation"):
        raise core_module.SchemaError(
            "validation must be empty for development-session-initialize"
        )
    if _object(operation["publication"], "publication"):
        raise core_module.SchemaError(
            "publication must be empty for development-session-initialize"
        )

    result = _object(operation["result"], "result")
    _exact(result, core_module.RESULT_FIELDS, core_module.RESULT_FIELDS, "result")
    _string(result["directory"], "result.directory")
    filename = _string(result["filename"], "result.filename")
    if not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{7,191}\.result\.json", filename
    ):
        raise core_module.SchemaError("result.filename has invalid form")
    return operation


def _record(record: Any) -> dict[str, Any]:
    return core_module.command_record_dict(record)


def _run(
    supervisor: core_module.CommandSupervisor,
    root: Path,
    commands: list[dict[str, Any]],
    command: Sequence[str],
    *,
    phase: str,
    timeout: float = 120.0,
    allowed_exit_codes: set[int] | None = None,
    stdin_bytes: bytes | None = None,
    stdin_label: str | None = None,
) -> Any:
    record = supervisor.run(
        list(command),
        root,
        timeout_seconds=timeout,
        phase=phase,
        stdin_bytes=stdin_bytes,
        stdin_label=stdin_label,
    )
    commands.append(_record(record))
    accepted = allowed_exit_codes or {0}
    if record.exit_code not in accepted:
        raise SessionInitializationError(
            record.stderr.strip() or f"{phase} failed",
            evidence={"failed_command": commands[-1]},
        )
    return record


def _json_output(record: Any, phase: str) -> Any:
    try:
        return json.loads(record.stdout)
    except json.JSONDecodeError as exc:
        raise SessionInitializationError(
            f"{phase} returned malformed JSON"
        ) from exc


def _snapshot(
    supervisor: core_module.CommandSupervisor,
    root: Path,
    commands: list[dict[str, Any]],
) -> dict[str, Any]:
    origin = _run(
        supervisor, root, commands, ["git", "remote", "get-url", "origin"],
        phase="read repository origin",
    ).stdout.strip()
    branch = _run(
        supervisor, root, commands, ["git", "branch", "--show-current"],
        phase="read current branch",
    ).stdout.strip()
    head = _run(
        supervisor, root, commands, ["git", "rev-parse", "HEAD"],
        phase="read current head",
    ).stdout.strip()
    status = _run(
        supervisor,
        root,
        commands,
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        phase="read repository status",
    ).stdout.splitlines()
    return {
        "root": str(root),
        "origin": origin,
        "branch": branch,
        "head": head,
        "clean": not status,
        "status": status,
    }


def _create_comment(
    supervisor: core_module.CommandSupervisor,
    root: Path,
    commands: list[dict[str, Any]],
    slug: str,
    issue: int,
    body: str,
    label: str,
) -> dict[str, Any]:
    payload = json.dumps({"body": body}, ensure_ascii=False).encode("utf-8")
    endpoint = f"repos/{slug}/issues/{issue}/comments"
    record = _run(
        supervisor,
        root,
        commands,
        ["gh", "api", "--method", "POST", "--input", "-", endpoint],
        phase=f"create {label}",
        stdin_bytes=payload,
        stdin_label="github-issue-comment-json",
    )
    created = _json_output(record, f"create {label}")
    comment_id = created.get("id")
    if not isinstance(comment_id, int):
        raise SessionInitializationError(
            f"{label} creation returned no immutable identifier",
            remote_may_have_mutated=True,
        )
    read = _run(
        supervisor,
        root,
        commands,
        ["gh", "api", f"repos/{slug}/issues/comments/{comment_id}"],
        phase=f"verify {label}",
    )
    verified = _json_output(read, f"verify {label}")
    if verified.get("body") != body or verified.get("id") != comment_id:
        raise SessionInitializationError(
            f"{label} read-after-write verification failed",
            evidence={"comment_id": comment_id},
            remote_may_have_mutated=True,
        )
    user = verified.get("user")
    if not isinstance(user, dict) or not isinstance(user.get("login"), str):
        raise SessionInitializationError(
            f"{label} verification returned incomplete author evidence",
            evidence={"comment_id": comment_id},
            remote_may_have_mutated=True,
        )
    return {
        "comment_id": comment_id,
        "url": verified.get("html_url"),
        "author": user["login"],
        "body_sha256": _digest(body),
        "verified": True,
    }


def execute(
    operation: Mapping[str, Any],
    progress: core_module.TerminalProgress,
) -> tuple[dict[str, Any], Path]:
    result = core_module.base_result(operation)
    result["mutation"]["authorized"] = True
    supervisor = core_module.CommandSupervisor()
    configured_root = Path(operation["repository"]["root"]).expanduser().resolve()
    destination = core_module.result_destination(operation, configured_root)
    if destination.exists():
        raise core_module.ResultConflictError(f"result already exists: {destination}")

    commands: list[dict[str, Any]] = []
    root = configured_root
    local_mutation_started = False
    remote_mutation_possible = False
    comments: dict[str, Any] = {}

    try:
        progress.phase(2, "evaluating complete initialization preflight")
        resolved_root = _run(
            supervisor,
            configured_root,
            commands,
            ["git", "rev-parse", "--show-toplevel"],
            phase="resolve repository root",
        ).stdout.strip()
        root = Path(resolved_root).resolve()
        if root != configured_root:
            raise core_module.GuardError("repository root mismatch")

        starting = _snapshot(supervisor, root, commands)
        result["starting_state"] = starting
        if _canonical_origin(starting["origin"]) != _canonical_origin(
            operation["repository"]["origin"]
        ):
            raise core_module.GuardError("repository origin mismatch")
        if not starting["clean"]:
            raise core_module.GuardError("repository is not clean")

        local_main = _run(
            supervisor,
            root,
            commands,
            ["git", "rev-parse", "--verify", "refs/heads/main"],
            phase="resolve local main",
        ).stdout.strip()
        remote_before_line = _run(
            supervisor,
            root,
            commands,
            ["git", "ls-remote", "--heads", "origin", "refs/heads/main"],
            phase="inspect remote main",
        ).stdout.strip()
        if not remote_before_line:
            raise core_module.GuardError("remote main is absent")
        remote_before = remote_before_line.split()[0]
        if not SHA1.fullmatch(remote_before):
            raise core_module.GuardError("remote main returned an invalid commit id")

        issue = operation["inputs"]["issue"]
        slug = _repository_slug(operation["repository"]["origin"])
        issue_record = _run(
            supervisor,
            root,
            commands,
            ["gh", "api", f"repos/{slug}/issues/{issue}"],
            phase="read governing issue",
        )
        issue_value = _json_output(issue_record, "read governing issue")
        if issue_value.get("number") != issue or issue_value.get("state") != "open":
            raise core_module.GuardError("governing issue is absent or not open")

        comments_record = _run(
            supervisor,
            root,
            commands,
            ["gh", "api", f"repos/{slug}/issues/{issue}/comments?per_page=100"],
            phase="read existing issue comments",
        )
        existing_comments = _json_output(comments_record, "read existing issue comments")
        if not isinstance(existing_comments, list):
            raise SessionInitializationError(
                "issue comment inventory returned an invalid value"
            )
        for heading in (DETAILED_HEADING, PATCH_PLAN_HEADING):
            matches = [
                item
                for item in existing_comments
                if isinstance(item, dict)
                and isinstance(item.get("body"), str)
                and (
                    item["body"] == heading
                    or item["body"].startswith(heading + "\n")
                )
            ]
            if matches:
                raise core_module.GuardError(
                    f"designated planning comment already exists: {heading}"
                )

        branch = operation["inputs"]["branch"]
        branch_check = _run(
            supervisor,
            root,
            commands,
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
            phase="verify target branch absence",
            allowed_exit_codes={0, 1},
        )
        if branch_check.exit_code == 0:
            raise core_module.GuardError("target local branch already exists")

        progress.phase(3, "refreshing main and rechecking remote stability")
        result["mutation"]["attempted"] = True
        local_mutation_started = True
        _run(
            supervisor,
            root,
            commands,
            ["git", "fetch", "--prune", "origin"],
            phase="fetch canonical remote",
            timeout=300.0,
        )
        fetched_main = _run(
            supervisor,
            root,
            commands,
            ["git", "rev-parse", "--verify", "refs/remotes/origin/main"],
            phase="resolve fetched origin main",
        ).stdout.strip()
        if fetched_main != remote_before:
            raise core_module.GuardError(
                "fetched origin/main does not match observed remote main"
            )
        ancestry = _run(
            supervisor,
            root,
            commands,
            ["git", "merge-base", "--is-ancestor", local_main, fetched_main],
            phase="verify fast-forward relationship",
            allowed_exit_codes={0, 1},
        )
        if ancestry.exit_code != 0:
            reverse = _run(
                supervisor,
                root,
                commands,
                ["git", "merge-base", "--is-ancestor", fetched_main, local_main],
                phase="classify local main relationship",
                allowed_exit_codes={0, 1},
            )
            if reverse.exit_code == 0:
                raise core_module.GuardError(
                    "local main contains commits not present on remote main"
                )
            raise core_module.GuardError("local and remote main have diverged")

        current = _snapshot(supervisor, root, commands)
        if current != starting:
            raise core_module.GuardError(
                "checkout identity changed during initialization preflight"
            )

        if starting["branch"] != "main":
            _run(
                supervisor, root, commands, ["git", "switch", "main"],
                phase="switch to existing main",
            )
        if local_main != fetched_main:
            _run(
                supervisor,
                root,
                commands,
                ["git", "merge", "--ff-only", "refs/remotes/origin/main"],
                phase="fast-forward main",
            )

        remote_after_line = _run(
            supervisor,
            root,
            commands,
            ["git", "ls-remote", "--heads", "origin", "refs/heads/main"],
            phase="verify remote main remained stable",
        ).stdout.strip()
        remote_after = remote_after_line.split()[0] if remote_after_line else ""
        if remote_after != fetched_main:
            raise SessionInitializationError(
                "remote main changed during initialization"
            )

        progress.phase(4, "creating planning records and entering issue branch")
        remote_mutation_possible = True
        comments["detailed_scope"] = _create_comment(
            supervisor,
            root,
            commands,
            slug,
            issue,
            operation["inputs"]["detailed_scope_body"],
            "governed detailed-scope comment",
        )
        comments["patch_plan"] = _create_comment(
            supervisor,
            root,
            commands,
            slug,
            issue,
            operation["inputs"]["patch_plan_body"],
            "governed patch-plan comment",
        )

        _run(
            supervisor,
            root,
            commands,
            ["git", "switch", "-c", branch, fetched_main],
            phase="create exact local issue branch",
        )
        result["mutation"]["observed"] = True

        ending = _snapshot(supervisor, root, commands)
        result["ending_state"] = ending
        if (
            ending["branch"] != branch
            or ending["head"] != fetched_main
            or not ending["clean"]
        ):
            raise SessionInitializationError(
                "development initialization terminal repository state is invalid",
                remote_may_have_mutated=True,
            )

        result["publication"] = {
            "repository": slug,
            "issue": issue,
            "accepted_base": fetched_main,
            "branch": branch,
            "comments": comments,
            "verified": True,
        }
        result["mutation"]["completed"] = True
        result["terminal_status"] = "publication-completed"
        result["safest_next_interaction"] = (
            "Review the accepted base, planning comments, and created issue branch."
        )
    except core_module.GuardError as exc:
        result["terminal_status"] = (
            "partial-local-mutation" if local_mutation_started else "guard-failed"
        )
        result["diagnostics"].append(str(exc))
    except (SessionInitializationError, core_module.ExecutorError, OSError) as exc:
        remote_possible = remote_mutation_possible or getattr(
            exc, "remote_may_have_mutated", False
        )
        result["terminal_status"] = (
            "partial-remote-mutation"
            if remote_possible
            else (
                "partial-local-mutation"
                if local_mutation_started
                else "pre-mutation-failed"
            )
        )
        result["diagnostics"].append(str(exc))
        evidence = getattr(exc, "evidence", None)
        if evidence:
            result.setdefault("publication", {})["failure_evidence"] = evidence
    finally:
        result["commands"] = commands
        result["redaction_events"] = [
            event
            for command in commands
            for event in command.get("redaction_events", [])
        ]
        if not result.get("ending_state"):
            try:
                result["ending_state"] = _snapshot(supervisor, root, commands)
                result["commands"] = commands
            except (core_module.ExecutorError, OSError):
                pass
        result["finished_at"] = core_module.utc_now()

    progress.phase(5, "writing development initialization evidence")
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
        progress.phase(1, "validating development initialization description")
        operation = load_operation(operation_path)
        destination = core_module.result_destination(
            operation,
            Path(operation["repository"]["root"]).expanduser().resolve(),
        )
        progress.check("closed initialization contract verified")
        progress.check("combined authorization boundary verified")
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
