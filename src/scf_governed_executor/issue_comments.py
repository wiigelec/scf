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


ISSUE_COMMENT_OPERATION_TYPE = "issue-comment-mutation"
ACTIONS = frozenset({"create", "update"})
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMENT_ID = re.compile(r"^[1-9][0-9]*$")
MAX_BODY_BYTES = 65536


class IssueCommentError(core_module.ExecutorError):
    def __init__(
        self,
        message: str,
        *,
        evidence: Mapping[str, Any] | None = None,
        mutation_observed: bool = False,
    ) -> None:
        super().__init__(message)
        self.evidence = dict(evidence or {})
        self.mutation_observed = mutation_observed


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


def _body(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise core_module.SchemaError(f"{location} must be a non-empty string")
    if "\x00" in value or len(value.encode("utf-8")) > MAX_BODY_BYTES:
        raise core_module.SchemaError(f"{location} is invalid")
    return value


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _repository_slug(origin: str) -> str:
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise core_module.SchemaError("issue comments require a canonical GitHub HTTPS origin")
    path = parsed.path.removesuffix(".git").strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", path):
        raise core_module.SchemaError("repository origin does not identify one GitHub repository")
    return path


def validate_issue_comment_contract(
    operation: Mapping[str, Any],
) -> dict[str, Any]:
    if operation["operation_type"] != ISSUE_COMMENT_OPERATION_TYPE:
        raise core_module.SchemaError("unsupported issue-comment operation type")

    authorization = _object(operation["authorization"], "authorization")
    required_authorization = {"interrogate", "issue"}
    if not all(authorization[field] for field in required_authorization):
        raise core_module.SchemaError(
            "issue-comment-mutation requires interrogate and issue authorization"
        )
    broadened = sorted(
        field
        for field in core_module.AUTHORIZATION_FIELDS - required_authorization
        if authorization[field]
    )
    if broadened:
        raise core_module.SchemaError(
            "operation broadens authorization: " + ", ".join(broadened)
        )

    inputs = _object(operation["inputs"], "inputs")
    action = inputs.get("action")
    if action not in ACTIONS:
        raise core_module.SchemaError("inputs.action is unsupported")

    common = {"action", "issue", "body", "required_heading", "expected_issue_state"}
    if action == "create":
        allowed = common
        required = {"action", "issue", "body"}
    else:
        allowed = common | {"comment_id", "expected_body_sha256"}
        required = {"action", "issue", "body", "comment_id"}
    _exact(inputs, allowed, required, "inputs")

    if not isinstance(inputs["issue"], int) or isinstance(inputs["issue"], bool):
        raise core_module.SchemaError("inputs.issue must be a positive integer")
    if inputs["issue"] <= 0:
        raise core_module.SchemaError("inputs.issue must be a positive integer")
    body = _body(inputs["body"], "inputs.body")

    heading = inputs.get("required_heading")
    if heading is not None:
        if not isinstance(heading, str) or not heading.startswith("## "):
            raise core_module.SchemaError(
                "inputs.required_heading must be an exact level-two Markdown heading"
            )
        if not body.startswith(heading + "\n") and body != heading:
            raise core_module.SchemaError(
                "inputs.body must begin with inputs.required_heading"
            )

    state = inputs.get("expected_issue_state")
    if state is not None and state not in {"open", "closed"}:
        raise core_module.SchemaError(
            "inputs.expected_issue_state must be open or closed"
        )

    if action == "update":
        comment_id = inputs["comment_id"]
        if not isinstance(comment_id, int) or isinstance(comment_id, bool):
            raise core_module.SchemaError("inputs.comment_id must be a positive integer")
        if comment_id <= 0:
            raise core_module.SchemaError("inputs.comment_id must be a positive integer")
        expected_digest = inputs.get("expected_body_sha256")
        if expected_digest is not None and (
            not isinstance(expected_digest, str) or not SHA256.fullmatch(expected_digest)
        ):
            raise core_module.SchemaError(
                "inputs.expected_body_sha256 must be lowercase SHA-256"
            )

    expected = _object(operation["expected_mutations"], "expected_mutations")
    expected_fields = {"action", "issue", "body_sha256"}
    if action == "update":
        expected_fields.add("comment_id")
    _exact(expected, expected_fields, expected_fields, "expected_mutations")
    required_expected = {
        "action": action,
        "issue": inputs["issue"],
        "body_sha256": _digest(body),
    }
    if action == "update":
        required_expected["comment_id"] = inputs["comment_id"]
    if expected != required_expected:
        raise core_module.SchemaError(
            "expected_mutations must exactly match the issue-comment request"
        )

    for name in ("validation", "publication"):
        if _object(operation[name], name):
            raise core_module.SchemaError(
                f"{name} must be empty for issue-comment-mutation"
            )

    _repository_slug(operation["repository"]["origin"])
    return dict(operation)


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
    stdin_bytes: bytes | None = None,
    stdin_label: str | None = None,
) -> str:
    record = supervisor.run(
        list(command),
        root,
        timeout_seconds=timeout,
        phase=phase,
        stdin_bytes=stdin_bytes,
        stdin_label=stdin_label,
    )
    commands.append(_record(record))
    if record.exit_code != 0:
        raise IssueCommentError(
            record.stderr.strip() or f"{phase} failed",
            evidence={"failed_command": commands[-1]},
        )
    return record.stdout.strip()


def _api_json(
    supervisor: core_module.CommandSupervisor,
    root: Path,
    commands: list[dict[str, Any]],
    endpoint: str,
    *,
    phase: str,
) -> Any:
    output = _run(
        supervisor,
        root,
        ["gh", "api", endpoint],
        commands,
        phase=phase,
    )
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise IssueCommentError(f"{phase} returned malformed JSON") from exc


def _comment_evidence(comment: Mapping[str, Any], issue: int) -> dict[str, Any]:
    body = comment.get("body")
    user = comment.get("user")
    if (
        not isinstance(comment.get("id"), int)
        or not isinstance(comment.get("html_url"), str)
        or not isinstance(body, str)
        or not isinstance(user, dict)
        or not isinstance(user.get("login"), str)
    ):
        raise IssueCommentError("GitHub returned an incomplete comment object")
    return {
        "comment_id": comment["id"],
        "url": comment["html_url"],
        "body": body,
        "body_sha256": _digest(body),
        "author": user["login"],
        "issue": issue,
    }


def execute_issue_comment(
    operation: Mapping[str, Any],
    progress: core_module.TerminalProgress,
) -> tuple[dict[str, Any], Path]:
    result = core_module.base_result(operation)
    result["mutation"]["authorized"] = True
    supervisor = core_module.CommandSupervisor()
    repository_root = Path(operation["repository"]["root"]).expanduser().resolve()
    destination = core_module.result_destination(operation, repository_root)
    if destination.exists():
        raise core_module.ResultConflictError(f"result already exists: {destination}")

    commands: list[dict[str, Any]] = []
    evidence: dict[str, Any] = {}
    root: Path | None = None
    mutation_observed = False
    try:
        progress.phase(2, "evaluating repository and remote issue guards")
        root, guard_commands, state = core_module.evaluate_repository_guards(
            operation, supervisor, progress
        )
        commands.extend(guard_commands)
        result["starting_state"] = state
        slug = _repository_slug(operation["repository"]["origin"])
        inputs = operation["inputs"]
        issue_number = inputs["issue"]

        issue = _api_json(
            supervisor,
            root,
            commands,
            f"repos/{slug}/issues/{issue_number}",
            phase="read target issue",
        )
        if issue.get("pull_request") is not None:
            raise core_module.GuardError("target number identifies a pull request")
        if issue.get("number") != issue_number:
            raise core_module.GuardError("target issue identity mismatch")
        expected_state = inputs.get("expected_issue_state")
        if expected_state is not None and issue.get("state") != expected_state:
            raise core_module.GuardError("target issue state mismatch")
        evidence["issue_before"] = {
            "number": issue.get("number"),
            "state": issue.get("state"),
            "url": issue.get("html_url"),
        }

        action = inputs["action"]
        body = inputs["body"]
        heading = inputs.get("required_heading")
        target_before: dict[str, Any] | None = None
        if action == "create":
            comments = _api_json(
                supervisor,
                root,
                commands,
                f"repos/{slug}/issues/{issue_number}/comments?per_page=100",
                phase="read existing issue comments",
            )
            if not isinstance(comments, list):
                raise IssueCommentError("GitHub returned malformed comment inventory")
            if heading is not None:
                matches = [
                    item
                    for item in comments
                    if isinstance(item, dict)
                    and isinstance(item.get("body"), str)
                    and (
                        item["body"] == heading
                        or item["body"].startswith(heading + "\n")
                    )
                ]
                if matches:
                    raise core_module.GuardError(
                        "a comment with the required heading already exists"
                    )
        else:
            raw = _api_json(
                supervisor,
                root,
                commands,
                f"repos/{slug}/issues/comments/{inputs['comment_id']}",
                phase="read target comment",
            )
            target_before = _comment_evidence(raw, issue_number)
            issue_url = raw.get("issue_url")
            if not isinstance(issue_url, str) or not issue_url.endswith(
                f"/issues/{issue_number}"
            ):
                raise core_module.GuardError(
                    "target comment does not belong to the declared issue"
                )
            expected_digest = inputs.get("expected_body_sha256")
            if (
                expected_digest is not None
                and target_before["body_sha256"] != expected_digest
            ):
                raise core_module.GuardError("target comment body digest mismatch")
            evidence["comment_before"] = target_before

        progress.phase(3, f"performing issue comment {action}")
        result["mutation"]["attempted"] = True
        payload = json.dumps({"body": body}, ensure_ascii=False).encode("utf-8")
        if action == "create":
            method = "POST"
            endpoint = f"repos/{slug}/issues/{issue_number}/comments"
        else:
            method = "PATCH"
            endpoint = f"repos/{slug}/issues/comments/{inputs['comment_id']}"
        output = _run(
            supervisor,
            root,
            [
                "gh",
                "api",
                "--method",
                method,
                "--input",
                "-",
                endpoint,
            ],
            commands,
            phase=f"{action} issue comment",
            timeout=120.0,
            stdin_bytes=payload,
            stdin_label="github-issue-comment-json",
        )

        mutation_observed = True
        result["mutation"]["observed"] = True
        try:
            mutation_response = json.loads(output)
        except json.JSONDecodeError as exc:
            raise IssueCommentError(
                "GitHub mutation returned malformed JSON",
                mutation_observed=True,
            ) from exc
        comment_id = mutation_response.get("id")
        if not isinstance(comment_id, int):
            raise IssueCommentError(
                "GitHub mutation did not return a comment identifier",
                mutation_observed=True,
            )
        if action == "update" and comment_id != inputs["comment_id"]:
            raise IssueCommentError(
                "GitHub updated an unexpected comment identifier",
                mutation_observed=True,
            )

        progress.phase(4, "verifying remote comment state")
        verified_raw = _api_json(
            supervisor,
            root,
            commands,
            f"repos/{slug}/issues/comments/{comment_id}",
            phase="read comment after mutation",
        )
        verified = _comment_evidence(verified_raw, issue_number)
        issue_url = verified_raw.get("issue_url")
        if not isinstance(issue_url, str) or not issue_url.endswith(
            f"/issues/{issue_number}"
        ):
            raise IssueCommentError(
                "comment read-after-write issue identity mismatch",
                mutation_observed=True,
            )
        if verified["body"] != body:
            raise IssueCommentError(
                "comment read-after-write body mismatch",
                evidence={"comment_after": verified},
                mutation_observed=True,
            )

        evidence["repository"] = slug
        evidence["action"] = action
        evidence["comment_after"] = verified
        evidence["expected_body_sha256"] = _digest(body)
        evidence["verified"] = True
        result["publication"] = evidence
        result["mutation"]["completed"] = True
        ending_commands, ending_state = core_module.capture_repository_state(
            root, supervisor
        )
        commands.extend(ending_commands)
        result["ending_state"] = ending_state
        result["terminal_status"] = "publication-completed"
        result["safest_next_interaction"] = (
            "Review exact issue-comment read-after-write evidence."
        )
    except core_module.GuardError as exc:
        result["terminal_status"] = "guard-failed"
        result["diagnostics"].append(str(exc))
    except (IssueCommentError, OSError, ValueError) as exc:
        result["mutation"]["observed"] = mutation_observed or getattr(
            exc, "mutation_observed", False
        )
        if isinstance(exc, IssueCommentError) and exc.evidence:
            evidence.update(exc.evidence)
        result["publication"] = evidence
        result["terminal_status"] = (
            "partial-remote-mutation"
            if result["mutation"]["observed"]
            else "pre-mutation-failed"
        )
        result["diagnostics"].append(str(exc))
        try:
            ending_commands, ending_state = core_module.capture_repository_state(
                root or repository_root, supervisor
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

def load_issue_comment_operation(path: Path) -> dict[str, Any]:
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
    if operation["operation_type"] != ISSUE_COMMENT_OPERATION_TYPE:
        raise core_module.SchemaError("unsupported issue-comment operation type")
    if not isinstance(operation["operation_id"], str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}", operation["operation_id"]
    ):
        raise core_module.SchemaError("operation_id has invalid form")
    if not isinstance(operation["operation_digest"], str) or not SHA256.fullmatch(
        operation["operation_digest"]
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
        if not isinstance(repository[field], str) or not repository[field]:
            raise core_module.SchemaError(
                f"repository.{field} must be a non-empty string"
            )

    guards = _object(operation["guards"], "guards")
    _exact(
        guards,
        core_module.GUARD_FIELDS,
        core_module.GUARD_FIELDS,
        "guards",
    )
    if not isinstance(guards["branch"], str) or not guards["branch"]:
        raise core_module.SchemaError(
            "guards.branch must be a non-empty string"
        )
    if not isinstance(guards["head"], str) or not re.fullmatch(
        r"[0-9a-f]{40}", guards["head"]
    ):
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
    if any(not isinstance(value, bool) for value in authorization.values()):
        raise core_module.SchemaError("authorization values must be boolean")

    result = _object(operation["result"], "result")
    _exact(
        result,
        core_module.RESULT_FIELDS,
        core_module.RESULT_FIELDS,
        "result",
    )
    if not isinstance(result["directory"], str) or not result["directory"]:
        raise core_module.SchemaError(
            "result.directory must be a non-empty string"
        )
    if not isinstance(result["filename"], str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{7,191}\.result\.json",
        result["filename"],
    ):
        raise core_module.SchemaError("result.filename has invalid form")
    return validate_issue_comment_contract(operation)


def issue_comment_main(argv: Sequence[str] | None = None) -> int:
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
        progress.phase(1, "validating issue-comment operation description")
        operation = load_issue_comment_operation(operation_path)
        destination = core_module.result_destination(
            operation,
            Path(operation["repository"]["root"]).expanduser().resolve(),
        )
        progress.check("closed issue-comment contract verified")
        progress.check("authorization separation verified")
        progress.check("operation digest verified")
        print("", flush=True)
        print(f"Repository : {operation['repository']['root']}", flush=True)
        print(f"Revision   : {operation['guards']['head']}", flush=True)
        print(f"Operation  : {operation['operation_id']}", flush=True)
        print(f"Type       : {operation['operation_type']}", flush=True)
        print(f"Result     : {destination}", flush=True)
        print("", flush=True)
        result, destination = execute_issue_comment(operation, progress)
        print("", flush=True)
        print("-" * 60, flush=True)
        print(f"STATUS: {result['terminal_status']}", flush=True)
        print("", flush=True)
        print("Result:", flush=True)
        print(f"  {destination}", flush=True)
        print("", flush=True)
        print("Next step:", flush=True)
        print(f"  {result['safest_next_interaction']}", flush=True)
        return 0 if result["terminal_status"] == "publication-completed" else 1
    except core_module.ExecutorError as exc:
        print("", file=sys.stderr, flush=True)
        print("-" * 60, file=sys.stderr, flush=True)
        print("STATUS: executor-failed", file=sys.stderr, flush=True)
        print(f"Reason: {exc}", file=sys.stderr, flush=True)
        if destination is not None:
            print(f"Result: {destination}", file=sys.stderr, flush=True)
        return 1
