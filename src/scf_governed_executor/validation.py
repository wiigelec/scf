from __future__ import annotations

from typing import Any, Mapping

from . import strict_validation


INPUT_FIELDS = {"profiles"}
EXPECTED_FIELDS = {"profiles"}
PROFILE_COMMANDS = {
    "governed-executor-tests": [
        "python-executable", "-m", "unittest", "discover",
        "-s", "tests/governed_executor",
    ],
    "permanent-validation-tests": [
        "python-executable", "-m", "unittest", "discover",
        "-s", "tests/validation",
    ],
    "repository-complete": [
        "./scripts/validate", "--mode", "complete", "--format", "json",
    ],
    "whitespace": ["git", "diff", "--check"],
}


class GovernedValidationError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        commands: list[dict[str, Any]] | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.commands = list(commands or [])
        self.evidence = dict(evidence or {})


_STRICT = strict_validation.StrictValidator(GovernedValidationError)


def _exact(
    value: Mapping[str, Any],
    allowed: set[str],
    required: set[str],
    location: str,
) -> None:
    _STRICT.exact_fields(value, allowed, required, location)


def validate_governed_validation_inputs(
    inputs: Any,
    expected_mutations: Any,
    publication: Any,
) -> None:
    if not isinstance(inputs, dict):
        raise GovernedValidationError("inputs must be an object")
    _exact(inputs, INPUT_FIELDS, INPUT_FIELDS, "inputs")
    profiles = inputs["profiles"]
    if not isinstance(profiles, list) or not profiles:
        raise GovernedValidationError("inputs.profiles must be a non-empty array")
    if profiles != sorted(set(profiles)):
        raise GovernedValidationError(
            "inputs.profiles must be unique and lexicographically sorted"
        )
    unknown = [profile for profile in profiles if profile not in PROFILE_COMMANDS]
    if unknown:
        raise GovernedValidationError(
            "unsupported validation profiles: " + ", ".join(unknown)
        )

    if not isinstance(expected_mutations, dict):
        raise GovernedValidationError("expected_mutations must be an object")
    _exact(expected_mutations, EXPECTED_FIELDS, EXPECTED_FIELDS, "expected_mutations")
    if expected_mutations["profiles"] != profiles:
        raise GovernedValidationError(
            "expected_mutations.profiles must exactly match inputs.profiles"
        )

    if not isinstance(publication, dict) or publication:
        raise GovernedValidationError(
            "publication must be an empty object for governed validation"
        )


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


def run_governed_validation(
    root: Any,
    supervisor: Any,
    inputs: Mapping[str, Any],
    expected_mutations: Mapping[str, Any],
    publication: Mapping[str, Any],
) -> dict[str, Any]:
    validate_governed_validation_inputs(inputs, expected_mutations, publication)
    commands: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []

    for profile in inputs["profiles"]:
        template = PROFILE_COMMANDS[profile]
        command = [
            __import__("sys").executable if part == "python-executable" else part
            for part in template
        ]
        record = supervisor.run(
            command,
            root,
            timeout_seconds=600,
            phase=f"governed validation: {profile}",
        )
        record_dict = _record_dict(record)
        commands.append(record_dict)
        profile_evidence = {
            "profile": profile,
            "command": command,
            "exit_code": record.exit_code,
            "passed": record.exit_code == 0,
        }
        profiles.append(profile_evidence)
        if record.exit_code != 0:
            raise GovernedValidationError(
                f"validation profile failed: {profile}",
                commands=commands,
                evidence={
                    "requested_profiles": list(inputs["profiles"]),
                    "profiles": profiles,
                    "verified": False,
                },
            )

    return {
        "requested_profiles": list(inputs["profiles"]),
        "profiles": profiles,
        "verified": True,
        "commands": commands,
    }
