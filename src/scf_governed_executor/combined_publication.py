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
from . import git_publication


_STRICT = strict_validation.StrictValidator(core_module.SchemaError)

OPERATION_TYPE = "git-publication"
SHA1 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
BRANCH = re.compile(
    r"^(?!/)(?!.*(?:\.\.|//|@\{|\\))(?!.*[/.]$)[A-Za-z0-9._/-]+$"
)


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
            "combined git publication requires a canonical GitHub HTTPS origin"
        )
    slug = parsed.path.strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", slug):
        raise core_module.SchemaError("repository origin is not a GitHub repository")
    return slug


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
        raise core_module.SchemaError("unsupported combined publication type")
    if operation["executor_version"] != core_module.EXECUTOR_VERSION:
        raise core_module.SchemaError("incompatible executor version")
    if not isinstance(operation["operation_id"], str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}", operation["operation_id"]
    ):
        raise core_module.SchemaError("operation_id has invalid form")
    if not isinstance(operation["operation_digest"], str) or not SHA256.fullmatch(
        operation["operation_digest"]
    ):
        raise core_module.SchemaError("operation_digest must be lowercase SHA-256")
    if operation["operation_digest"] != core_module.operation_digest(operation):
        raise core_module.SchemaError("operation digest mismatch")

    repository = _object(operation["repository"], "repository")
    _exact(repository, {"root", "origin"}, {"root", "origin"}, "repository")
    _string(repository["root"], "repository.root")
    _string(repository["origin"], "repository.origin")
    _repository_slug(repository["origin"])

    guards = _object(operation["guards"], "guards")
    _exact(guards, {"branch", "head", "clean"}, {"branch", "head", "clean"}, "guards")
    if not isinstance(guards["branch"], str) or not BRANCH.fullmatch(guards["branch"]):
        raise core_module.SchemaError("guards.branch has invalid form")
    if not isinstance(guards["head"], str) or not SHA1.fullmatch(guards["head"]):
        raise core_module.SchemaError("guards.head must be a lowercase full commit id")
    if guards["clean"] is not False:
        raise core_module.SchemaError(
            "combined publication requires guards.clean=false for reviewed changes"
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
    required = {"interrogate", "stage", "commit", "push", "pull_request"}
    if not all(authorization[field] for field in required):
        raise core_module.SchemaError(
            "combined publication requires interrogate, stage, commit, push, "
            "and pull_request authorization"
        )
    broadened = sorted(
        field for field in core_module.AUTHORIZATION_FIELDS - required
        if authorization[field]
    )
    if broadened:
        raise core_module.SchemaError(
            "operation broadens authorization: " + ", ".join(broadened)
        )

    inputs = _object(operation["inputs"], "inputs")
    _exact(inputs, {"paths", "message"}, {"paths", "message"}, "inputs")

    expected = _object(operation["expected_mutations"], "expected_mutations")
    _exact(
        expected,
        {"paths", "parent_head"},
        {"paths", "parent_head"},
        "expected_mutations",
    )
    if expected["parent_head"] != guards["head"]:
        raise core_module.SchemaError(
            "expected_mutations.parent_head must match guards.head"
        )

    publication = _object(operation["publication"], "publication")
    _exact(
        publication,
        {"push", "remote", "branch", "pull_request"},
        {"push", "remote", "branch", "pull_request"},
        "publication",
    )
    if publication["push"] is not True:
        raise core_module.SchemaError("combined publication requires push=true")
    if publication["branch"] != guards["branch"]:
        raise core_module.SchemaError(
            "publication.branch must match the guarded branch"
        )
    request = _object(publication["pull_request"], "publication.pull_request")
    _exact(
        request,
        {"base", "head", "title", "body", "draft"},
        {"base", "head", "title", "body", "draft"},
        "publication.pull_request",
    )
    for field in ("base", "head"):
        if not isinstance(request[field], str) or not BRANCH.fullmatch(request[field]):
            raise core_module.SchemaError(
                f"publication.pull_request.{field} has invalid form"
            )
    if request["head"] != publication["branch"]:
        raise core_module.SchemaError(
            "pull-request head must match publication branch"
        )
    _string(request["title"], "publication.pull_request.title", maximum=256)
    _string(request["body"], "publication.pull_request.body")
    if not isinstance(request["draft"], bool):
        raise core_module.SchemaError(
            "publication.pull_request.draft must be boolean"
        )

    validation = _object(operation["validation"], "validation")
    fields = {
        "result_path",
        "result_sha256",
        "required_terminal_status",
        "required_branch",
        "required_head",
    }
    _exact(validation, fields, fields, "validation")
    _string(validation["result_path"], "validation.result_path")
    if not isinstance(validation["result_sha256"], str) or not SHA256.fullmatch(
        validation["result_sha256"]
    ):
        raise core_module.SchemaError(
            "validation.result_sha256 must be lowercase SHA-256"
        )
    if validation["required_terminal_status"] != "validation-completed":
        raise core_module.SchemaError(
            "validation requires terminal status validation-completed"
        )
    if validation["required_branch"] != guards["branch"]:
        raise core_module.SchemaError(
            "validation.required_branch must match guards.branch"
        )
    if validation["required_head"] != guards["head"]:
        raise core_module.SchemaError(
            "validation.required_head must match guards.head"
        )

    result = _object(operation["result"], "result")
    _exact(result, core_module.RESULT_FIELDS, core_module.RESULT_FIELDS, "result")
    _string(result["directory"], "result.directory")
    if not isinstance(result["filename"], str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{7,191}\.result\.json",
        result["filename"],
    ):
        raise core_module.SchemaError("result.filename has invalid form")

    git_publication.validate_git_publication_inputs(
        inputs,
        expected,
        {
            "push": True,
            "remote": publication["remote"],
            "branch": publication["branch"],
        },
        push_authorized=True,
    )
    return operation


def _command(
    supervisor: core_module.CommandSupervisor,
    root: Path,
    command: Sequence[str],
    *,
    phase: str,
    timeout: float = 120.0,
) -> tuple[dict[str, Any], str]:
    record = supervisor.run(
        list(command),
        root,
        timeout_seconds=timeout,
        phase=phase,
    )
    evidence = core_module.command_record_dict(record)
    if record.exit_code != 0:
        raise core_module.ExecutorError(
            record.stderr.strip() or f"{phase} failed"
        )
    return evidence, record.stdout.strip()


def _verify_validation(operation: Mapping[str, Any]) -> dict[str, Any]:
    validation = operation["validation"]
    path = Path(validation["result_path"]).expanduser().resolve()
    if not path.is_file():
        raise core_module.GuardError("validation evidence result does not exist")
    actual_digest = _sha256_file(path)
    if actual_digest != validation["result_sha256"]:
        raise core_module.GuardError("validation evidence digest mismatch")
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise core_module.GuardError("validation evidence is unreadable") from exc
    if evidence.get("terminal_status") != validation["required_terminal_status"]:
        raise core_module.GuardError("validation evidence terminal status mismatch")
    ending = evidence.get("ending_state")
    if not isinstance(ending, dict):
        ending = evidence.get("starting_state")
    if not isinstance(ending, dict):
        raise core_module.GuardError("validation evidence lacks repository state")
    if ending.get("branch") != validation["required_branch"]:
        raise core_module.GuardError("validation evidence branch mismatch")
    if ending.get("head") != validation["required_head"]:
        raise core_module.GuardError("validation evidence head mismatch")
    return {
        "path": str(path),
        "sha256": actual_digest,
        "terminal_status": evidence.get("terminal_status"),
        "branch": ending.get("branch"),
        "head": ending.get("head"),
        "verified": True,
    }


def _pull_request(
    operation: Mapping[str, Any],
    commit: str,
    supervisor: core_module.CommandSupervisor,
    root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    publication = operation["publication"]
    request = publication["pull_request"]
    slug = _repository_slug(operation["repository"]["origin"])
    commands: list[dict[str, Any]] = []

    def list_matching() -> list[dict[str, Any]]:
        record, output = _command(
            supervisor,
            root,
            [
                "gh", "pr", "list",
                "--repo", slug,
                "--state", "open",
                "--base", request["base"],
                "--head", request["head"],
                "--json",
                "number,url,title,body,isDraft,headRefName,baseRefName,headRefOid",
            ],
            phase="read matching pull requests",
        )
        commands.append(record)
        try:
            value = json.loads(output)
        except json.JSONDecodeError as exc:
            raise core_module.ExecutorError(
                "pull-request inventory returned malformed JSON"
            ) from exc
        if not isinstance(value, list):
            raise core_module.ExecutorError(
                "pull-request inventory returned an invalid value"
            )
        return value

    matches = list_matching()
    if len(matches) > 1:
        raise core_module.GuardError(
            "multiple open pull requests match the publication branch"
        )
    created = False
    if not matches:
        command = [
            "gh", "pr", "create",
            "--repo", slug,
            "--base", request["base"],
            "--head", request["head"],
            "--title", request["title"],
            "--body", request["body"],
        ]
        if request["draft"]:
            command.append("--draft")
        record, _ = _command(
            supervisor, root, command, phase="create pull request"
        )
        commands.append(record)
        created = True
        matches = list_matching()

    if len(matches) != 1:
        raise core_module.ExecutorError(
            "pull-request read-after-write verification failed"
        )
    pull = matches[0]
    expected = {
        "headRefName": request["head"],
        "baseRefName": request["base"],
        "title": request["title"],
        "body": request["body"],
        "isDraft": request["draft"],
        "headRefOid": commit,
    }
    for field, value in expected.items():
        if pull.get(field) != value:
            raise core_module.ExecutorError(
                f"pull-request verification failed for {field}"
            )
    if not isinstance(pull.get("number"), int) or not isinstance(
        pull.get("url"), str
    ):
        raise core_module.ExecutorError(
            "pull-request verification returned incomplete identity"
        )
    return {
        "number": pull["number"],
        "url": pull["url"],
        "created": created,
        "base": pull["baseRefName"],
        "head": pull["headRefName"],
        "head_sha": pull["headRefOid"],
        "title": pull["title"],
        "draft": pull["isDraft"],
        "verified": True,
    }, commands


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
        progress.phase(2, "evaluating repository and validation guards")
        root, commands, starting = core_module.evaluate_repository_guards(
            operation, supervisor, progress
        )
        result["commands"].extend(commands)
        result["starting_state"] = starting
        result["validation_evidence"] = _verify_validation(operation)
        progress.check("reviewed validation evidence verified")

        progress.phase(3, "staging, committing, and pushing exact changes")
        result["mutation"]["attempted"] = True
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
        result["mutation"]["observed"] = True
        result["commands"].extend(git_evidence.pop("commands", []))
        commit = git_evidence["commit"]

        progress.phase(4, "creating or verifying pull request")
        pull_request, pr_commands = _pull_request(
            operation, commit, supervisor, root
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
        if ending["branch"] != operation["guards"]["branch"]:
            raise core_module.ExecutorError(
                "ending branch differs from guarded branch"
            )
        if ending["head"] != commit or not ending["clean"]:
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
        mutation_observed = result["mutation"]["observed"] or getattr(
            exc, "mutation_observed", False
        )
        result["mutation"]["observed"] = mutation_observed
        result["terminal_status"] = (
            "partial-remote-mutation"
            if mutation_observed
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
            result.setdefault("publication", {})["failure_evidence"] = extra_evidence
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
        progress.phase(1, "validating combined Git publication description")
        operation = load_operation(operation_path)
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
