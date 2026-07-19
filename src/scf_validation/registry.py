"""Explicit validation check registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .context import ValidationContext
from .diagnostics import Diagnostic

CheckFunction = Callable[[ValidationContext], list[Diagnostic]]


@dataclass(frozen=True, slots=True)
class Check:
    check_id: str
    name: str
    function: CheckFunction
