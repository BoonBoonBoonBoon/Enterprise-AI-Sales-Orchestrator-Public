Adapters Layer
==============

Purpose
-------
Provide interchangeable backends implementing the `PersistenceAdapter` protocol so higher layers (service, agents, RAG context builder) remain storage-agnostic.

Current Adapters
----------------
1. `InMemoryAdapter` (`in_memory_adapter.py`)
   - Test/deterministic backend.
   - Stores rows per-table in a list; assigns incremental string `id` values.
   - Supports: write, batch_write, upsert (conflict merge), read, query (equality filters, ordering, projection), get_columns.
   - Intended for: unit tests, offline development, fast prototype flows.

2. `SupabaseAdapter` (`supabase_adapter.py`)
   - Production-facing adapter leveraging Supabase PostgREST.
   - Uses the `supabase-py` client if available; falls back to raw REST for certain operations (e.g., upsert) if client reply is ambiguous.
   - Responsibilities:
     * Insert / batch insert with returned rows.
     * Upsert with conflict columns.
     * Read single row (id equality) via filters.
     * Query set with ordering, projection, and limit.
     * Column introspection (future: may use information_schema or cached schema).
   - Future expansions: advanced filter operators (ilike, in, gt/lt), pagination helpers.

Design Principles
-----------------
- Minimal surface: Keep adapter semantics narrow; richer logic (validation, auditing, retries) belongs in `PersistenceService`.
- Idempotency: Upsert should be safe to retry if network ambiguity occurs (goal: make underlying calls idempotent via conflict keys).
- Clear failure signals: Raise (wrapped) exceptions; avoid returning sentinel error dicts.
- Progressive enhancement: Start with basic equality filters; extend via capability flags.

`PersistenceAdapter` Contract (summarized)
-----------------------------------------
```
write(table: str, record: dict) -> dict
batch_write(table: str, records: list[dict]) -> list[dict]
upsert(table: str, record: dict, on_conflict: list[str]|None) -> dict
read(table: str, id_value: Any, id_column: str='id') -> dict|None
query(table: str, filters=None, limit=None, order_by=None, descending=False, select=None) -> list[dict]
get_columns(table: str) -> list[str]|None
```

Error Handling Expectations
---------------------------
- Adapters may raise generic exceptions; `PersistenceService` converts them to `AdapterError`.
- For planned, adapter-specific recoverable errors (e.g., transient network), we will classify later for retry logic.

Extending with a New Adapter
----------------------------
1. Create `your_adapter_name_adapter.py` implementing the contract above.
2. Avoid importing heavy/optional dependencies at module import—lazy import in `__init__` to keep cold start small.
3. Provide any factory helper if configuration differs from Supabase (e.g., credentials object, cluster endpoints).
4. Add short section below documenting capabilities & limitations.
5. Write unit tests using a fixture verifying at least write, upsert (conflict), query (filter + order), get_columns.

Performance Considerations
--------------------------
- In-memory adapter is O(n) for query filtering; acceptable for tests but not for performance benchmarks.
- Supabase queries pay network + PostgREST overhead; batch writes should be preferred over single calls when ingesting many rows.
- Future: consider bulk COPY (or Supabase import) path for large data loads.

Future Adapter Roadmap
----------------------
- Read Replica Adapter: direct read-only Postgres connection for lower-latency queries.
- Vector Store Adapter: hybrid retrieval (metadata + embeddings) for advanced RAG.
- Caching Layer Adapter: wrap another adapter to add local memory / Redis caching of hot reads.
- Multi-Tenant Partition Adapter: auto-inject tenant filters for isolation.

Capability Extensions (Proposed Flags)
-------------------------------------
Adapters can expose a `capabilities` dict (not yet implemented) to advertise features:
```
{
  'filter_ops': ['eq', 'ilike', 'in'],
  'supports_order_nulls_last': True,
  'supports_projection': True,
  'max_batch_size': 1000
}
```
This lets higher layers adapt dynamically without hard-coding conditionals.

Testing Strategy
----------------
- In-memory: Fast path; exercise logic branches of service.
- Supabase: Optional integration suite guarded by environment variables (skip if creds absent).
- Contract Parity: A shared test module can parametrize over adapters to ensure consistent behavior.

Security & Secret Handling
--------------------------
- Do not log raw credentials (URL, keys) at adapter level.
- In Supabase adapter, redact keys if emitting debug traces.
- Provide explicit method to rotate credentials without re-instantiating (future enhancement: `refresh_credentials`).

Operational Hardening Ideas
---------------------------
- Add circuit breaker wrapper (trip after consecutive AdapterError spikes).
- Add request ID / correlation context propagation (trace headers).
- Add structured logging (JSON) for every external call (latency, table, op, row_count).

Example: Minimal New Adapter Skeleton
-------------------------------------
```
class NewBackendAdapter:
    def __init__(self, endpoint: str, token: str):
        self.endpoint = endpoint
        self.token = token

    def write(self, table, record):
        # POST /{table}
        return {...}

    def batch_write(self, table, records):
        # POST /{table}/bulk
        return [...]

    def upsert(self, table, record, on_conflict=None):
        # PUT /{table}?conflict=...
        return {...}

    def read(self, table, id_value, id_column='id'):
        # GET /{table}?{id_column}=eq.{id_value}
        return {...} or None

    def query(self, table, filters=None, limit=None, order_by=None, descending=False, select=None):
        # Build query params from filters
        return [...]

    def get_columns(self, table):
        # Introspect or cache
        return ['id', '...']
```

Maintenance Checklist
---------------------
- [ ] Keep dependency versions pinned (Supabase client) for reproducibility.
- [ ] Run integration tests before upgrading adapter libs.
- [ ] Benchmark large batch ingest quarterly.
- [ ] Review error logs for unclassified exceptions; promote patterns to first-class handling.

Change Log
----------
- v0.1: InMemory + Supabase adapters introduced.
- v0.2: Added read/query/get_columns support.
- v0.3: Adapter error wrapping via service instrumentation.

End.
