"""Explicit validation check registry."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Sequence

from .context import ValidationContext
from .diagnostics import Diagnostic

CheckFunction = Callable[[ValidationContext], list[Diagnostic]]
CHECK_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9-]*-[0-9]{3}$")


class RegistryError(ValueError):
    """The explicit validator registry is incomplete or malformed."""


@dataclass(frozen=True, slots=True)
class Check:
    check_id: str
    name: str
    function: CheckFunction


def validate_registry(
    checks: Sequence[Check],
    required_check_ids: Sequence[str],
) -> tuple[Check, ...]:
    """Validate exact ordered composition of the explicit check registry."""

    required = tuple(required_check_ids)
    if not required:
        raise RegistryError("required check inventory must not be empty")
    if len(required) != len(set(required)):
        raise RegistryError("required check inventory contains duplicate identifiers")

    validated = tuple(checks)
    actual_ids: list[str] = []
    for index, check in enumerate(validated):
        if not isinstance(check, Check):
            raise RegistryError(f"registry entry {index} is not a Check")
        if not CHECK_ID_PATTERN.fullmatch(check.check_id):
            raise RegistryError(
                f"registry entry {index} has invalid check identifier {check.check_id!r}"
            )
        if not check.name or not check.name.strip():
            raise RegistryError(f"registry entry {check.check_id} has an empty name")
        if not callable(check.function):
            raise RegistryError(
                f"registry entry {check.check_id} has a non-callable function"
            )
        actual_ids.append(check.check_id)

    if len(actual_ids) != len(set(actual_ids)):
        raise RegistryError("registered checks contain duplicate identifiers")
    if tuple(actual_ids) != required:
        missing = [item for item in required if item not in actual_ids]
        unexpected = [item for item in actual_ids if item not in required]
        details: list[str] = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if unexpected:
            details.append("unexpected: " + ", ".join(unexpected))
        if not missing and not unexpected:
            details.append("registered order does not match required inventory")
        raise RegistryError("registry composition mismatch; " + "; ".join(details))
    return validated
