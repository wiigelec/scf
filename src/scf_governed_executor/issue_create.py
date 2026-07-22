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


_STRICT = strict_validation.StrictValidator(core_module.SchemaError)

OPERATION_TYPE = "issue-create"
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class IssueCreateError(core_module.ExecutorError):
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


def _string(value: Any, location: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise core_module.SchemaError(f"{location} must be a non-empty string")
    encoded = value.encode("utf-8")
    if "\x00" in value or len(encoded) > maximum:
        raise core_module.SchemaError(f"{location} exceeds its bounded size")
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
        raise core_module.SchemaError("issue-create requires a GitHub repository origin")
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
        raise core_module.SchemaError("unsupported issue operation type")
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
    _string(repository["root"], "repository.root", 4096)
    _string(repository["origin"], "repository.origin", 4096)
    _repository_slug(repository["origin"])

    guards = _object(operation["guards"], "guards")
    _exact(guards, core_module.GUARD_FIELDS, core_module.GUARD_FIELDS, "guards")
    _string(guards["branch"], "guards.branch", 255)
    if not isinstance(guards["head"], str) or not re.fullmatch(
        r"[0-9a-f]{40}", guards["head"]
    ):
        raise core_module.SchemaError("guards.head must be a lowercase full commit id")
    if guards["clean"] is not True:
        raise core_module.SchemaError("issue-create requires guards.clean=true")

    authorization = _object(operation["authorization"], "authorization")
    _exact(
        authorization,
        core_module.AUTHORIZATION_FIELDS,
        core_module.AUTHORIZATION_FIELDS,
        "authorization",
    )
    if any(not isinstance(value, bool) for value in authorization.values()):
        raise core_module.SchemaError("authorization values must be boolean")
    required = {"interrogate", "issue"}
    if not all(authorization[field] for field in required):
        raise core_module.SchemaError(
            "issue-create requires interrogate and issue authorization"
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
    _exact(inputs, {"issues"}, {"issues"}, "inputs")
    issues = inputs["issues"]
    if not isinstance(issues, list) or not issues:
        raise core_module.SchemaError("inputs.issues must be a non-empty array")
    if len(issues) > 25:
        raise core_module.SchemaError("inputs.issues exceeds maximum length")
    normalized: list[dict[str, str]] = []
    expected: list[dict[str, str]] = []
    for index, item in enumerate(issues):
        location = f"inputs.issues[{index}]"
        item = _object(item, location)
        _exact(item, {"title", "body"}, {"title", "body"}, location)
        title = _string(item["title"], f"{location}.title", 256)
        body = _string(item["body"], f"{location}.body", 65536)
        if "\r" in title or "\n" in title:
            raise core_module.SchemaError(f"{location}.title must be one line")
        normalized.append({"title": title, "body": body})
        expected.append(
            {"title_sha256": _digest(title), "body_sha256": _digest(body)}
        )
    inputs["issues"] = normalized

    expected_mutations = _object(
        operation["expected_mutations"], "expected_mutations"
    )
    _exact(expected_mutations, {"issues"}, {"issues"}, "expected_mutations")
    if expected_mutations["issues"] != expected:
        raise core_module.SchemaError(
            "expected_mutations.issues must exactly match issue inputs"
        )
    if _object(operation["validation"], "validation"):
        raise core_module.SchemaError("validation must be empty for issue-create")
    if _object(operation["publication"], "publication"):
        raise core_module.SchemaError("publication must be empty for issue-create")

    result = _object(operation["result"], "result")
    _exact(result, core_module.RESULT_FIELDS, core_module.RESULT_FIELDS, "result")
    _string(result["directory"], "result.directory", 4096)
    filename = _string(result["filename"], "result.filename", 256)
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
    stdin_bytes: bytes | None = None,
    stdin_label: str | None = None,
) -> Any:
    record = supervisor.run(
        list(command),
        root,
        timeout_seconds=120.0,
        phase=phase,
        stdin_bytes=stdin_bytes,
        stdin_label=stdin_label,
    )
    commands.append(_record(record))
    if record.exit_code != 0:
        raise IssueCreateError(
            record.stderr.strip() or f"{phase} failed",
            evidence={"failed_command": commands[-1]},
        )
    return record


def _json_output(record: Any, phase: str) -> Any:
    try:
        return json.loads(record.stdout)
    except json.JSONDecodeError as exc:
        raise IssueCreateError(f"{phase} returned malformed JSON") from exc


def _create_issue(
    supervisor: core_module.CommandSupervisor,
    root: Path,
    commands: list[dict[str, Any]],
    slug: str,
    title: str,
    body: str,
) -> dict[str, Any]:
    payload = json.dumps(
        {"title": title, "body": body}, ensure_ascii=False
    ).encode("utf-8")
    created_record = _run(
        supervisor,
        root,
        commands,
        ["gh", "api", "--method", "POST", "--input", "-", f"repos/{slug}/issues"],
        phase=f"create issue {title!r}",
        stdin_bytes=payload,
        stdin_label="github-issue-json",
    )
    created = _json_output(created_record, "create issue")
    number = created.get("number")
    node_id = created.get("node_id")
    if not isinstance(number, int) or not isinstance(node_id, str) or not node_id:
        raise IssueCreateError(
            "issue creation returned no immutable identifier",
            remote_may_have_mutated=True,
        )
    verify_record = _run(
        supervisor,
        root,
        commands,
        ["gh", "api", f"repos/{slug}/issues/{number}"],
        phase=f"verify issue #{number}",
    )
    verified = _json_output(verify_record, "verify issue")
    if (
        verified.get("number") != number
        or verified.get("node_id") != node_id
        or verified.get("title") != title
        or verified.get("body") != body
        or verified.get("state") != "open"
    ):
        raise IssueCreateError(
            f"issue #{number} read-after-write verification failed",
            evidence={"number": number, "node_id": node_id},
            remote_may_have_mutated=True,
        )
    return {
        "number": number,
        "node_id": node_id,
        "url": verified.get("html_url"),
        "title_sha256": _digest(title),
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
    created_issues: list[dict[str, Any]] = []
    remote_mutation_started = False
    root = configured_root

    try:
        progress.phase(2, "evaluating issue-creation guards")
        root, guard_commands, starting = core_module.evaluate_repository_guards(
            operation, supervisor, progress
        )
        commands.extend(guard_commands)
        result["starting_state"] = starting
        progress.check("repository identity and exact state verified")

        slug = _repository_slug(operation["repository"]["origin"])
        progress.phase(3, "creating bounded GitHub issues")
        result["mutation"]["attempted"] = True
        for item in operation["inputs"]["issues"]:
            remote_mutation_started = True
            created_issues.append(
                _create_issue(
                    supervisor,
                    root,
                    commands,
                    slug,
                    item["title"],
                    item["body"],
                )
            )
            progress.check(f"created and verified issue #{created_issues[-1]['number']}")

        progress.phase(4, "verifying terminal repository and remote state")
        state_commands, ending = core_module.capture_repository_state(root, supervisor)
        commands.extend(state_commands)
        result["ending_state"] = ending
        if ending != starting:
            raise IssueCreateError(
                "local repository state changed during issue creation",
                remote_may_have_mutated=bool(created_issues),
            )
        result["publication"] = {
            "repository": slug,
            "issues": created_issues,
            "verified": True,
        }
        result["mutation"]["observed"] = True
        result["mutation"]["completed"] = True
        result["terminal_status"] = "publication-completed"
        result["safest_next_interaction"] = (
            "Review every created issue and its read-after-write evidence."
        )
    except core_module.GuardError as exc:
        result["terminal_status"] = "guard-failed"
        result["diagnostics"].append(str(exc))
    except (IssueCreateError, core_module.ExecutorError, OSError) as exc:
        remote_possible = remote_mutation_started or getattr(
            exc, "remote_may_have_mutated", False
        )
        result["terminal_status"] = (
            "partial-remote-mutation" if remote_possible else "pre-mutation-failed"
        )
        result["diagnostics"].append(str(exc))
        evidence = getattr(exc, "evidence", None)
        if created_issues or evidence:
            result["publication"] = {
                "repository": _repository_slug(operation["repository"]["origin"]),
                "issues": created_issues,
                "failure_evidence": dict(evidence or {}),
                "verified": False,
            }
    finally:
        result["commands"] = commands
        result["redaction_events"] = [
            event
            for command in commands
            for event in command.get("redaction_events", [])
        ]
        if result["ending_state"] is None:
            try:
                state_commands, ending = core_module.capture_repository_state(
                    root, supervisor
                )
                commands.extend(state_commands)
                result["commands"] = commands
                result["ending_state"] = ending
            except (core_module.ExecutorError, OSError):
                pass
        result["finished_at"] = core_module.utc_now()

    progress.phase(5, "writing issue-creation evidence")
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
        progress.phase(1, "validating issue-creation description")
        operation = load_operation(operation_path)
        destination = core_module.result_destination(
            operation,
            Path(operation["repository"]["root"]).expanduser().resolve(),
        )
        progress.check("closed issue-creation contract verified")
        progress.check("issue-only authorization boundary verified")
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


if __name__ == "__main__":
    raise SystemExit(main())
