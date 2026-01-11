"""Custom exception hierarchy for the persistence layer.

Having explicit exception types lets higher layers distinguish between
permission issues, adapter/backend failures, validation problems, and
generic internal errors.
"""

from __future__ import annotations

class PersistenceError(Exception):
    """Base class for all persistence related errors."""


class PersistencePermissionError(PersistenceError):
    """Raised when an operation is not permitted (table not allow‑listed or read-only)."""


class TableNotAllowedError(PersistencePermissionError):
    """Specific permission error for a disallowed table access."""


class ValidationError(PersistenceError):
    """Raised when inputs (filters, records, etc.) are invalid."""


class AdapterError(PersistenceError):
    """Raised when the underlying adapter/backend fails irrecoverably."""


__all__ = [
    "PersistenceError",
    "PersistencePermissionError",
    "TableNotAllowedError",
    "ValidationError",
    "AdapterError",
]
