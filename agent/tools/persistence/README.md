Persistence Layer (Service + Agent + RAG Support)
=================================================

Purpose
-------
Provide a single, modular, least‑privilege persistence layer decoupled from orchestration logic. It centralizes database access (currently via Supabase PostgREST) and exposes a clean API for both write and read/query operations, plus a RAG (Retrieval Augmented Generation) context builder that only consumes read‑safe operations.

Core Design Goals
-----------------
1. Security: Table allow‑lists + optional read‑only façades.
2. Composability: Adapter protocol enables multiple storage backends.
3. Observability: Central instrumentation hook for timing and later metrics.
4. Extensibility: Clear seams for retries, validation, masking, auditing.
5. Testability: In‑memory adapter + deterministic query semantics.
 6. Centralized Configuration: Single source (`agent.config.persistence_config`) for read/write allow‑lists & env overrides.

Key Modules / Classes
---------------------
`service.py`
- `PersistenceAdapter` (Protocol): Shape required by persistence layer (write, batch_write, upsert, read, query, get_columns).
- `PersistenceService`: Enforces allow‑lists, strips None values, wraps adapter calls in instrumentation (`_invoke`).
- `ReadOnlyPersistenceFacade`: Blocks writes while forwarding read/query/get_columns (used in RAG / analytics contexts).

`exceptions.py`
- `PersistenceError`: Root error class.
- `PersistencePermissionError` / `TableNotAllowedError`: Policy violations.
- `AdapterError`: Underlying backend/transport failure.
- `ValidationError`: (Reserved) Input shape / semantic issues.

`persistence_agent.py`
- `PersistenceAgent`: Operational façade with default restricted table list.
- `create_persistence_agent(...)`: Factory supporting `supabase` or `memory` kinds; merges custom table list with defaults if requested.
 - Delegates to centralized factory (`agent.operational_agents.factory`) to ensure consistent config injection.

`rag_context.py`
- `RAGContext`: Structured containers for clients, leads, campaigns, conversations, messages.
- `build_rag_context(...)`: Pulls slices from allowed tables to construct RAG input; intentionally simple (recency-first) for predictable behavior.

Data Flow (Write)
-----------------
App Code → `PersistenceAgent.write()` → `PersistenceService.write()` → adapter (Supabase or memory) → Supabase REST (JSON over HTTPS) → Postgres.

Data Flow (RAG Retrieval)
-------------------------
LLM Workflow / Orchestrator → `ReadOnlyPersistenceFacade.query()` (multiple tables) → aggregate into `RAGContext` → `.to_prompt()` for model consumption.

Environment Variables
---------------------
- `SUPABASE_URL` – base URL (https://<project>.supabase.co)
- `SUPABASE_SERVICE_KEY` or `SUPABASE_KEY` – service role (preferred) or anon key
- `PERSIST_ALLOWED_TABLES` – optional comma‑separated list (overrides defaults for factories that use it)
- `PERSIST_LOGGING` – if set (to any value), basic stdout timing logs emitted

Public Service API
------------------
```
write(table, record) -> dict
batch_write(table, records) -> list[dict]
upsert(table, record, on_conflict=list[str]|None) -> dict
read(table, id_value, id_column='id') -> dict|None
query(table, filters=None, limit=None, order_by=None, descending=False, select=None) -> list[dict]
get_columns(table) -> list[str]|None
```

Filters & Query Semantics
-------------------------
Current adapter contract treats `filters` as an equality map (`{column: value}`) for in‑memory backend; Supabase adapter (future enhancement) can expand to comparison operators. Keep the abstraction conservative until multi‑operator semantics are standardized.

Security & Least Privilege
--------------------------
Current policy (2025-10):
* READ: All known business tables are readable by default (`campaigns`, `clients`, `conversations`, `leads`, `messages`, `sequences`, `staging_leads`, `inquiries`).
* WRITE: All of the above EXCEPT governance/reference tables `clients` and `campaigns`.

Override precedence (env):
* `PERSIST_WRITE_TABLES` – full write allowlist override (comma separated)
* `PERSIST_WRITE_DENY` – subtractive deny list applied to default (ignored if WRITE_TABLES set)
* `PERSIST_READ_TABLES` – full read allowlist override

RAG flows always build on `get_read_allowlist()` via the `ReadOnlyPersistenceFacade`, ensuring no accidental writes.

Instrumentation
---------------
`_invoke` wrapper measures latency per op and (optionally) prints `[persistence] op=<op> table=<t> ms=<dur>`. Replace with structured logger / metrics exporter when available.

Exception Strategy
------------------
Catch adapter errors, wrap in `AdapterError`, leave policy errors explicit. Upstream callers can pattern‑match on class to decide retry / user feedback.

Testing Patterns
----------------
Use `InMemoryAdapter` for unit tests: deterministic ordering + no network. Add Supabase integration tests separately (guarded by env var) to avoid CI flakiness.

Extending the Layer
-------------------
| Concern | Extension Point |
|---------|------------------|
| Retries | Wrap `_invoke` with retry on transient `AdapterError` classification |
| Metrics | Swap print with histogram/counter emitter |
| Auditing | Add callback hook in `_invoke` success branch |
| Validation | Pre-validate records/filters before `_invoke` |
| Masking | Transform record fields in `_clean` or decorator |
| Multi-Tenancy | Inject tenant_id filter automatically in `query`/`write` |
| Caching (reads) | Layer a small read-through cache above `read/query` |

Adapter Capabilities
--------------------
Each adapter now exposes a `capabilities` dict (introspected by higher layers):
```
{
	'equality_filters': True,
	'ordering': True,
	'limit': True,
	'projections': True,
	'ilike': False,
	'range_operators': False,
	'in_operator': False,
}
```
Use this to branch logic in RAG planners before attempting unsupported operators.

Metrics
-------
`metrics.py` accumulates per (op, table) counters + min/max/avg latency. Snapshot:
```python
from agent.tools.persistence import metrics
print(metrics.snapshot())
```
Enable lightweight logging with `PERSIST_LOGGING=1`.

CI Guard
--------
`scripts/ci_guard_persistence.py` fails the build if:
* Direct `SupabaseAdapter(` usage appears outside factories
* Writes to governance tables (`clients`, `campaigns`) are detected in non-test code
Integrate by adding a pipeline step invoking the script.

RAG Enhancement Roadmap
-----------------------
1. Token budget aware truncation.
2. Scoring (recency + entity weighting) for pruning.
3. Optional embeddings (vector store) hybrid retrieval.
4. Field-level redaction (PII) prior to prompt assembly.

Migration Guidance (Legacy DBWriteAgent)
----------------------------------------
Search for `DBWriteAgent` imports; replace with `create_persistence_agent()`. Use `upsert` instead of custom merge logic. Remove direct Supabase client creation from orchestration layers.

Future Considerations
---------------------
- Separate read vs write allow‑lists.
- Pluggable operator DSL for advanced filtering (gt, lt, ilike, in).
- Bulk import / COPY pathway for large dataset ingestion.
- Schema registry file to pre‑validate `select` projections.

Example – Read + RAG Flow
-------------------------
```
from agent.operational_agents.factory import create_persistence_agent, create_readonly_rag_facade
from agent.tools.persistence.rag_context import build_rag_context

agent = create_persistence_agent(kind='memory')
agent.write('leads', {'email': 'a@x.io'})
ro = create_readonly_rag_facade(kind='memory')  # shares underlying service instance if you wire a singleton
ctx = build_rag_context(ro, lead_filters={'email': 'a@x.io'}, limits={'leads': 10})
print(ctx.to_prompt())
```

Ownership / Contacts
--------------------
Data Platform / Agent Infrastructure maintainers.

Change Log
----------
- v0.1: Write-only abstraction.
- v0.2: Added reads/query, allow‑lists.
- v0.3: RAG context builder.
- v0.4: Exception hierarchy, read-only facade, instrumentation.

End.