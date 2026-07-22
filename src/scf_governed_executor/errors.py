from __future__ import annotations


class ExecutorError(RuntimeError):
    """Base executor failure."""


class SchemaError(ExecutorError):
    """Operation schema failure."""


class GuardError(ExecutorError):
    """Repository guard failure."""


class ResultConflictError(ExecutorError):
    """Result output would overwrite an existing path."""


class CommandTimeoutError(ExecutorError):
    """Supervised command exceeded its timeout."""
