"""Unified factory helpers for operational agents.

Purpose
-------
- Provide a single composition point for adapters → services → façades → agents.
- Eliminate duplicated boot logic (env parsing, allowlists, adapter choice).
- Guarantee RAG agents are constructed with a read-only persistence façade.

Why this matters
----------------
- Governance: central place to enforce allow-lists and read-only policy.
- Observability: one place to attach tracing/metrics in the future.
- Testability: swap the backend via `kind='memory'` without touching callers.

Deprecations
------------
- `create_readonly_rag_facade` is retained for backward-compatibility but
    is considered deprecated. Prefer `create_rag_agent(kind)` which wires the
    façade into the agent directly.
"""

from __future__ import annotations

from typing import Optional, List
import warnings

from agent.config.persistence_config import get_write_allowlist, get_read_allowlist
from agent.tools.persistence.service import (
    PersistenceService,
    ReadOnlyPersistenceFacade,
    build_supabase_service,
)
from agent.operational_agents.persistence_agent.persistence_agent import PersistenceAgent


def _build_service(kind: str, write_tables: List[str], read_tables: List[str]) -> PersistenceService:
    # For now only 'supabase' and 'memory' are supported; memory uses an in-memory adapter.
    if kind == "supabase":
        svc = build_supabase_service()
        # Override with dual allowlists (legacy allowed_tables replaced)
        svc.read_allowlist = set(t.lower() for t in read_tables)
        svc.write_allowlist = set(t.lower() for t in write_tables)
        return svc
    elif kind == "memory":
        from agent.tools.persistence.adapters.in_memory_adapter import InMemoryAdapter

        adapter = InMemoryAdapter()
        return PersistenceService(
            adapter,
            read_allowlist=read_tables,
            write_allowlist=write_tables,
        )
    else:
        raise ValueError(f"Unknown persistence backend kind '{kind}'")


def create_persistence_agent(kind: str = "supabase", allowed_tables: Optional[List[str]] = None) -> PersistenceAgent:
    write_tables = allowed_tables or get_write_allowlist()
    # For persistence agent we allow reads over all read tables but restrict writes
    read_tables = get_read_allowlist()
    svc = _build_service(kind, write_tables, read_tables)
    return PersistenceAgent(svc)


def create_readonly_rag_facade(kind: str = "supabase", allowed_tables: Optional[List[str]] = None) -> ReadOnlyPersistenceFacade:
    """DEPRECATED: Build a read-only façade for RAG.

    Prefer using `create_rag_agent(kind)` which returns a fully-wired agent.
    This function remains to avoid breaking older call sites and will be
    removed in a future cleanup phase.
    """
    warnings.warn(
        "create_readonly_rag_facade is deprecated; use create_rag_agent(kind) instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    read_tables = allowed_tables or get_read_allowlist()
    # Provide an empty write list to ensure writes always blocked even if facade bypassed
    svc = _build_service(kind, write_tables=[], read_tables=read_tables)
    return ReadOnlyPersistenceFacade(svc)


__all__ = [
    "create_persistence_agent",
    "create_readonly_rag_facade",
    "create_rag_agent",
]


def create_rag_agent(kind: str = "supabase"):
    """Build a RAGAgent backed by a read-only persistence facade.

    Falls back to legacy direct Supabase path only if facade construction fails.
    """
    # Lazy import to avoid importing legacy modules unless actually creating RAG
    from agent.operational_agents.rag_agent.rag_agent import RAGAgent  # type: ignore
    facade = create_readonly_rag_facade(kind=kind)
    return RAGAgent(read_only_persistence=facade)
