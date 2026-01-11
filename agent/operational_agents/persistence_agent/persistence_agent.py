from typing import Any, Dict, List, Optional
from agent.tools.persistence.service import PersistenceService
from agent.config.persistence_config import get_write_allowlist

# Backwards compatibility: expose constant for external imports while delegating
DEFAULT_PERSISTENCE_ALLOWED_TABLES = get_write_allowlist()


class PersistenceAgent:
    """Operational agent exposing persistence methods (restricted domain).

    Provides a façade over the underlying `PersistenceService` with a *default*
    principle-of-least-privilege table allowlist aligned to core operational
    write surfaces (lead lifecycle, communication logging, funnel metrics).

    Methods intentionally mirror the service for ergonomic usage by workflows.
    """

    def __init__(self, service: PersistenceService):
        self.service = service

    # ---------------------------- Write Operations ------------------------- #
    def write(self, table: str, record: Dict[str, Any]) -> Dict[str, Any]:
        return self.service.write(table, record)

    def batch_write(self, table: str, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self.service.batch_write(table, records)

    def upsert(
        self, table: str, record: Dict[str, Any], on_conflict: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        return self.service.upsert(table, record, on_conflict=on_conflict)

    # ----------------------------- Read Operations ------------------------- #
    def read(
        self, table: str, id_value: Any, id_column: str = "id"
    ) -> Optional[Dict[str, Any]]:
        return self.service.read(table, id_value, id_column)

    def query(
        self,
        table: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        order_by: Optional[str] = None,
        descending: bool = False,
        select: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        return self.service.query(
            table,
            filters=filters,
            limit=limit,
            order_by=order_by,
            descending=descending,
            select=select,
        )

    def get_columns(self, table: str) -> Optional[List[str]]:
        return self.service.get_columns(table)


def create_persistence_agent(*args, **kwargs):  # pragma: no cover - retained for compatibility
    """Deprecated direct factory.

    Prefer `agent.operational_agents.factory.create_persistence_agent` for unified
    construction logic. This shim delegates to the new factory to avoid breaking imports.
    """
    from agent.operational_agents.factory import create_persistence_agent as _f

    return _f(*args, **kwargs)


__all__ = [
    "PersistenceAgent",
    "create_persistence_agent",
    "DEFAULT_PERSISTENCE_ALLOWED_TABLES",
]
