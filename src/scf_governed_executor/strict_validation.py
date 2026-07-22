from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar


ErrorType = TypeVar("ErrorType", bound=Exception)


class StrictValidator:
    def __init__(self, error_type: type[ErrorType]) -> None:
        self._error_type = error_type

    def object(self, value: Any, location: str) -> dict[str, Any]:
        return require_object(
            value,
            location,
            error_type=self._error_type,
        )

    def exact_fields(
        self,
        value: Mapping[str, Any],
        allowed: set[str] | frozenset[str],
        required: set[str] | frozenset[str],
        location: str,
    ) -> None:
        require_exact_fields(
            value,
            allowed,
            required,
            location,
            error_type=self._error_type,
        )


def require_object(
    value: Any,
    location: str,
    *,
    error_type: type[ErrorType],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise error_type(f"{location} must be an object")
    return value


def require_exact_fields(
    value: Mapping[str, Any],
    allowed: set[str] | frozenset[str],
    required: set[str] | frozenset[str],
    location: str,
    *,
    error_type: type[ErrorType],
) -> None:
    unknown = set(value) - set(allowed)
    missing = set(required) - set(value)
    if unknown:
        raise error_type(
            f"{location} contains unknown fields: {', '.join(sorted(unknown))}"
        )
    if missing:
        raise error_type(
            f"{location} is missing required fields: {', '.join(sorted(missing))}"
        )
