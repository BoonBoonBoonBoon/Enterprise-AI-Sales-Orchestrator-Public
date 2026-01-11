"""SupaBase Tools (LEGACY / DEPRECATED)

DEPRECATION STATUS:
-------------------
This module is retained only for backward compatibility with legacy agents
that instantiated a direct Supabase client (e.g., old RAGAgent fallback and
DBWriteAgent). The modern path routes all data access through
`PersistenceService` + (optionally) `ReadOnlyPersistenceFacade`.

Planned Removal: Phase 2 cleanup (see `docs/cleanup/README.md`).

DO NOT introduce new dependencies on this module. Prefer the persistence
adapter layer (`agent.tools.persistence.adapters.supabase_adapter`).
"""
from supabase import create_client
from config.settings import SUPABASE_URL, SUPABASE_KEY
import warnings

# Emit a module-level deprecation warning once at import time
warnings.warn(
    "agent.tools.supabase_tools is deprecated and will be removed in a future release. "
    "Use PersistenceService + SupabaseAdapter instead (agent.tools.persistence).",
    DeprecationWarning,
    stacklevel=2,
)

# Suppress noisy deprecation warnings emitted by underlying HTTP libs (non-actionable here).
warnings.filterwarnings("ignore", message="The 'timeout' parameter is deprecated", category=DeprecationWarning)
warnings.filterwarnings("ignore", message="The 'verify' parameter is deprecated", category=DeprecationWarning)
from typing import Any, Dict, List, Optional


class SupabaseClient:
    """Light wrapper around the Supabase python client to query arbitrary tables.

    Methods accept table name and optional filters. Filters should be a dict where
    keys are column names and values are either exact values or dicts describing
    operations (e.g. {'name': {'ilike': '%john%'}}).
    """

    def __init__(self):
        warnings.warn(
            "SupabaseClient is deprecated. Use PersistenceService + SupabaseAdapter via ReadOnlyPersistenceFacade.",
            DeprecationWarning,
            stacklevel=2,
        )
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise EnvironmentError("SUPABASE_URL and SUPABASE_KEY must be set in env")
        self.client = create_client(SUPABASE_URL, SUPABASE_KEY)

    def _apply_filters(self, query_builder, filters: Optional[Dict[str, Any]]):
        if not filters:
            return query_builder
        for col, cond in filters.items():
            if isinstance(cond, dict):
                # support single - op: value
                for op, val in cond.items():
                    op = op.lower()
                    # prefer direct builder methods when available, fall back to .filter
                    method = getattr(query_builder, op, None)
                    if callable(method):
                        try:
                            query_builder = method(col, val)
                        except TypeError:
                            # some builder methods accept single arg like (col, val) or different signatures
                            query_builder = method(col, val)
                    else:
                        # many postgrest/supabase clients support a generic .filter(col, op, val)
                        try:
                            query_builder = query_builder.filter(col, op, val)
                        except Exception:
                            # last resort: try eq
                            query_builder = query_builder.eq(col, val)
            else:
                query_builder = query_builder.eq(col, cond)
        return query_builder

    def query_table(self, table: str, filters: Optional[Dict[str, Any]] = None, select: str = '*') -> List[Dict[str, Any]]:
        qb = self.client.table(table).select(select)
        qb = self._apply_filters(qb, filters)
        # Some supabase clients return a SyncPostgrestClient that supports execute();
        # others may return different shapes — keep using execute() but handle result shapes.
        result = qb.execute()
        # Result shape can vary by supabase client version. Handle common shapes safely.
        data = None
        error = None
        # pydantic/attribute access
        if hasattr(result, 'data'):
            data = result.data
        if hasattr(result, 'error'):
            error = result.error
        # dict-like access
        if data is None and isinstance(result, dict):
            data = result.get('data')
            error = error or result.get('error')

        if error:
            # error might be an object with message or a string
            msg = error.message if hasattr(error, 'message') else str(error)
            raise RuntimeError(f"Supabase query error: {msg}")

        return data or []


def format_records(records: List[Dict[str, Any]], limit: int = 20) -> str:
    """Return a short human-readable summary for a list of dict records."""
    if not records:
        return "(no records)"
    out_lines = []
    for i, r in enumerate(records[:limit], 1):
        items = ', '.join(f"{k}={v}" for k, v in r.items())
        out_lines.append(f"{i}. {items}")
    if len(records) > limit:
        out_lines.append(f"...and {len(records)-limit} more records")
    return '\n'.join(out_lines)


# predictable export for discovery
TOOL = SupabaseClient
