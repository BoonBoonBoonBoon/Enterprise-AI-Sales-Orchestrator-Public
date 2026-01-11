"""Simple DB write agent backed by the in-memory persistence adapter.

This module exists to satisfy tests that import
`agent.operational_agents.db_write_agent.db_write_agent`.
It provides a minimal agent exposing write, batch_write operations
using the same adapter shape as the PersistenceService for consistency.
"""
from __future__ import annotations

from typing import Dict, Any, List
from agent.tools.persistence.adapters.in_memory_adapter import InMemoryAdapter


class DBWriteAgent:
    def __init__(self) -> None:
        self.adapter = InMemoryAdapter()

    # write APIs matching tests' expectations
    def write(self, table: str, record: Dict[str, Any]) -> Dict[str, Any]:
        return self.adapter.write(table, record)

    def batch_write(self, table: str, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self.adapter.batch_write(table, records)


def create_in_memory_agent() -> DBWriteAgent:
    return DBWriteAgent()
