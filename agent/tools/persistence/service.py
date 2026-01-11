from typing import Any, Dict, List, Optional, Protocol, Callable
import os, time
from .exceptions import (
    # PersistenceError,  # unused
    PersistencePermissionError,
    TableNotAllowedError,
    AdapterError,
)
from . import metrics
from .adapters.in_memory_adapter import InMemoryAdapter  # re-export for convenience


class PersistenceAdapter(Protocol):
    """Protocol for adapters (Supabase / in-memory)."""

    def write(self, table: str, record: Dict[str, Any]) -> Dict[str, Any]: ...
    def batch_write(self, table: str, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]: ...
    def upsert(
        self, table: str, record: Dict[str, Any], on_conflict: Optional[List[str]] = None
    ) -> Dict[str, Any]: ...
    # read/query API (used by tests & RAG context builder)
    def read(self, table: str, id_value: Any, id_column: str = "id") -> Optional[Dict[str, Any]]: ...
    def query(
        self,
        table: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        order_by: Optional[str] = None,
        descending: bool = False,
        select: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]: ...
    def get_columns(self, table: str) -> Optional[List[str]]: ...


class PersistenceService:
    """High-level persistence façade adding validation & cross-cutting hooks.

    Responsibilities
    ----------------
    - Enforce allow-lists per operation (read vs write).
    - Strip None fields before writes for cleaner records.
    - Wrap adapter calls to add timing, metrics, and optional deep traces.

    Compatibility
    -------------
    - Supports a legacy single `allowed_tables` list. If provided alone, it
      applies to both read and write for backward compatibility.
    - Preferred usage is dual allowlists via `read_allowlist` and
      `write_allowlist`.
    """

    def __init__(
        self,
        adapter: PersistenceAdapter,
        allowed_tables: Optional[List[str]] = None,
        read_allowlist: Optional[List[str]] = None,
        write_allowlist: Optional[List[str]] = None,
    ):
        self.adapter = adapter
        # Backward compat: if explicit read/write lists not provided, fall back.
        if read_allowlist is None and write_allowlist is None:
            # legacy path: single allowlist governs both
            self.read_allowlist = set(t.lower() for t in allowed_tables) if allowed_tables else None
            self.write_allowlist = set(t.lower() for t in allowed_tables) if allowed_tables else None
        else:
            # modern path: independent lists; allowed_tables ignored if provided jointly
            self.read_allowlist = set(t.lower() for t in (read_allowlist or [])) or None
            self.write_allowlist = set(t.lower() for t in (write_allowlist or [])) or None

    # -------- internal helpers --------
    def _check_table(self, table: str, *, write: bool):
        tbl = table.lower()
        if write:
            if self.write_allowlist and tbl not in self.write_allowlist:
                raise TableNotAllowedError(f"Write access to table '{table}' is not permitted by policy")
        else:
            if self.read_allowlist and tbl not in self.read_allowlist:
                raise TableNotAllowedError(f"Read access to table '{table}' is not permitted by policy")

    def _clean(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in record.items() if v is not None}

    # -------- write APIs --------
    def write(self, table: str, record: Dict[str, Any]) -> Dict[str, Any]:
        self._check_table(table, write=True)
        return self._invoke("write", table, lambda: self.adapter.write(table, self._clean(record)))

    def batch_write(self, table: str, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self._check_table(table, write=True)
        cleaned = [self._clean(r) for r in records]
        return self._invoke("batch_write", table, lambda: self.adapter.batch_write(table, cleaned))

    def upsert(
        self, table: str, record: Dict[str, Any], on_conflict: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        self._check_table(table, write=True)
        return self._invoke(
            "upsert",
            table,
            lambda: self.adapter.upsert(table, self._clean(record), on_conflict=on_conflict),
        )

    # -------- read/query APIs --------
    def read(self, table: str, id_value: Any, id_column: str = "id") -> Optional[Dict[str, Any]]:
        self._check_table(table, write=False)
        return self._invoke("read", table, lambda: self.adapter.read(table, id_value, id_column=id_column))

    def query(
        self,
        table: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        order_by: Optional[str] = None,
        descending: bool = False,
        select: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        self._check_table(table, write=False)
        return self._invoke(
            "query",
            table,
            lambda: self.adapter.query(
                table,
                filters=filters,
                limit=limit,
                order_by=order_by,
                descending=descending,
                select=select,
            ),
        )

    def get_columns(self, table: str) -> Optional[List[str]]:  # convenience
        self._check_table(table, write=False)
        return self._invoke("get_columns", table, lambda: self.adapter.get_columns(table))

    # -------- instrumentation wrapper --------
    def _invoke(self, op: str, table: str, func: Callable[[], Any]):
        start = time.time()
        deep = os.environ.get("RAG_DEEP_DEBUG", "0").lower() in ("1", "true", "yes")
        if deep:
            try:
                print(f"[PERSIST TRACE] begin op={op} table={table}")
            except Exception:
                pass
        try:
            result = func()
            if deep:
                try:
                    size = None
                    if isinstance(result, list):
                        size = len(result)
                    print(f"[PERSIST TRACE] end op={op} table={table} size={size}")
                except Exception:
                    pass
            return result
        except TableNotAllowedError:
            raise
        except PersistencePermissionError:
            raise
        except Exception as e:  # wrap generic adapter/backend exceptions
            # Adapter/transport classification could be added later; we keep a
            # minimal surface now to avoid leaking backend-specific exceptions.
            raise AdapterError(f"Adapter error during {op} on {table}: {e}") from e
        finally:
            duration = (time.time() - start) * 1000.0
            # Metrics + optional logging
            metrics.inc(op, table)
            metrics.observe(op, table, duration)
            if os.environ.get("PERSIST_LOGGING"):
                print(f"[persistence] op={op} table={table} ms={duration:.1f}", flush=True)


class ReadOnlyPersistenceFacade:
    """Read-only façade forwarding read/query/get_columns only.

    Any attempt to call a write method raises PersistencePermissionError.
    Useful for RAG context building or analytics flows enforcing least-privilege.
    """

    def __init__(self, service: PersistenceService):
        self._svc = service

    # write attempts blocked
    def write(self, *a, **k):  # pragma: no cover - trivial guard
        raise PersistencePermissionError("Write not permitted on read-only facade")

    def batch_write(self, *a, **k):  # pragma: no cover
        raise PersistencePermissionError("Write not permitted on read-only facade")

    def upsert(self, *a, **k):  # pragma: no cover
        raise PersistencePermissionError("Write not permitted on read-only facade")

    # allowed methods
    def read(self, table: str, id_value: Any, id_column: str = "id"):
        return self._svc.read(table, id_value, id_column)

    def query(
        self,
        table: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        order_by: Optional[str] = None,
        descending: bool = False,
        select: Optional[List[str]] = None,
    ):
        return self._svc.query(
            table,
            filters=filters,
            limit=limit,
            order_by=order_by,
            descending=descending,
            select=select,
        )

    def get_columns(self, table: str):
        return self._svc.get_columns(table)

    # Capability surface (optional)
    def capabilities(self):  # pragma: no cover - thin wrapper
        return getattr(getattr(self._svc, 'adapter', None), 'capabilities', {})


# Factory helpers ---------------------------------------------------------
def build_supabase_service() -> PersistenceService:
    """Build a Supabase-backed service using environment configuration.

    Environment:
    - SUPABASE_URL
    - SUPABASE_SERVICE_KEY (preferred) or SUPABASE_KEY
    - PERSIST_ALLOWED_TABLES (comma separated list, optional)
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_KEY not configured for persistence")
    # Directly construct the modern persistence SupabaseAdapter instead of
    # going through the deprecated DBWriteAgent factory.
    from agent.tools.persistence.adapters.supabase_adapter import SupabaseAdapter  # local import to avoid heavy deps at module import

    adapter = SupabaseAdapter(url, key)
    allowed = os.environ.get("PERSIST_ALLOWED_TABLES")
    tables = [t.strip() for t in allowed.split(",") if t.strip()] if allowed else None
    return PersistenceService(adapter, allowed_tables=tables)


__all__ = ["PersistenceService", "build_supabase_service", "PersistenceAdapter", "InMemoryAdapter", "ReadOnlyPersistenceFacade"]
