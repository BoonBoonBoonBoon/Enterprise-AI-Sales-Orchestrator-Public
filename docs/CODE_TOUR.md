# Code Tour (10 minutes)

Skim these in order:

1) `agent/tools/persistence/service.py`
- Adapter + Service + ReadOnly facade, with read/write allowlists and light metrics.
- Central contract: `query/read/get_columns` for reads; writes guarded by policy.

2) `agent/operational_agents/rag_agent/rag_agent.py`
- Lean RAG Agent (no import-time LLM). Tools wrap read-only queries; envelopes everywhere.
- Filter parsing (id/email/company/client_id), pagination, cache, reformulation, and safe fallbacks.

3) `agent/Infastructure/queue/interface.py`
- Protocol for queue semantics used by Worker/Dispatcher.
- InMemory and Redis Streams adapters live under `agent/Infastructure/queue/`.

4) `platform_monitoring/exporters.py`
- Event emitter with key-based redaction and token masking to avoid logging secrets/PII.

5) `tests/test_rag_public_leads_integration.py`
- Live tests gated by `USE_REAL_TESTS=1` and env keys (Supabase); mock path uses in-memory adapter.

6) `agent/operational_agents/db_write_agent/db_write_agent.py`
- Minimal DB writer used by tests. Uses the in-memory adapter and mirrors write APIs.

Optional deep dives
- `agent/tools/persistence/adapters/*` — Supabase vs InMemory implementations and capability surface.
- `agent/operational_agents/factory.py` — composition helpers (facade injection, etc.).
