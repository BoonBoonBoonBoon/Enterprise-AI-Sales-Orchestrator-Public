# Redis Streams for RAG orchestration

This package provides a Redis client wrapper and message envelopes for orchestration using Redis Streams.

Streams (namespaced by `REDIS_NAMESPACE`, default `agentic`):
- `rag:tasks` — Orchestrator appends `QueryTask` entries (JSON in `data` field)
- `rag:results` — Workers append `QueryResponse` entries (JSON in `data` field)

Consumer groups:
- Group: `rag-workers`
- Each worker uses a unique consumer name (e.g., PID)

Environment variables:
- `REDIS_URL` (preferred) e.g. `redis://127.0.0.1:6379/0`
- or `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD`
- `REDIS_NAMESPACE` (default: `agentic`)
- `PERSIST_KIND` for worker backend: `supabase` (default) or `memory`

Run a worker:
```
python -m agent.operational_agents.rag_agent.worker
```

Send a test round-trip from the orchestrator side (enqueue + await result):
```
python scripts/orchestrator_redis_demo.py
```

You should see `received: true` and the response payload with records and metadata.