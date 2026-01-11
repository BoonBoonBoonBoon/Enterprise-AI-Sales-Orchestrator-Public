from __future__ import annotations

from typing import Protocol, Dict, Any, List


class AuditStore(Protocol):
    """Protocol for persisting envelopes and failure traces."""

    def save_envelope(self, run_id: str, envelope: Dict[str, Any]) -> None:
        ...

    def save_failure(self, run_id: str, error: str, envelope: Dict[str, Any] | None = None) -> None:
        ...


class InMemoryAuditStore:
    """Simple in-memory audit store for tests and local runs."""

    def __init__(self):
        self.envelopes: List[Dict[str, Any]] = []
        self.failures: List[Dict[str, Any]] = []

    def save_envelope(self, run_id: str, envelope: Dict[str, Any]) -> None:
        self.envelopes.append({"run_id": run_id, "envelope": envelope})

    def save_failure(self, run_id: str, error: str, envelope: Dict[str, Any] | None = None) -> None:
        self.failures.append({"run_id": run_id, "error": error, "envelope": envelope})


__all__ = ["AuditStore", "InMemoryAuditStore"]
