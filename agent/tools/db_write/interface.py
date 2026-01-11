from __future__ import annotations

from typing import Protocol, Dict, Any, List, Optional


class DBWriteAdapter(Protocol):
    """Protocol for DB write adapters.

    Simple interface for writing a record to a named table and returning an id or result.
    
    DEPRECATED: Use PersistenceAdapter from agent.tools.persistence.service instead.
    This interface will be removed in a future version.
    """

    def write(self, table: str, record: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def batch_write(self, table: str, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ...

    def upsert(self, table: str, record: Dict[str, Any], on_conflict: Optional[List[str]] = None) -> Dict[str, Any]:
        ...


__all__ = ["DBWriteAdapter"]
