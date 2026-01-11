# Architecture (One Pager)

```mermaid
flowchart LR
  subgraph Control
    CM[CampaignManager]
  end

  subgraph Infra
    Q[Queue (InMemory)] --> W[Worker]
    W -->|dispatch| ORCH[Orchestrator]
  end

  subgraph Operational
    RAG[RAGAgent]
    COPY[Copywriter]
    DBW[DB Write Agent]
  end

  subgraph Tools
    PSVC[PersistenceService]\n(ReadOnly Facade)
    COORD[DataCoordinator]
  end

  CM -->|enqueue job| Q
  ORCH -->|tool calls| RAG
  ORCH --> COPY
  ORCH --> DBW
  RAG -->|query| PSVC
  COORD -.-> PSVC
```

## Components and contracts
- Infra seams via Protocols: `QueueInterface`, worker, and orchestration engine are swappable and test-friendly.
- Persistence layering: Adapters (Supabase/InMemory) behind a `PersistenceService` with a `ReadOnlyPersistenceFacade` for least-privilege reads.
- Operational agents: RAG agent (offline-first), Copywriter (placeholder), and a minimal DB write agent used by tests.
- Monitoring: `platform_monitoring.exporters.log_event` masks secrets/PII at the edge.

## End-to-end flow (high level)
Derived from a mock email ingress scenario; this is the control-plane to data-plane overview:
- Ingress: A mock email arrives as an event and is handed to the control plane (`CampaignManager.ingest_event`).
- Enqueue: `CampaignManager` creates a job envelope and calls a `QueueInterface.enqueue` (InMemory/Redis).
- Worker pickup: A `Worker` dequeues the job, resolves the orchestrator via `Registry`, and calls `orchestrator.run`.
- Orchestration: The orchestrator coordinates tools (RAGAgent, DataCoordinator, delivery) to process the payload and produce a canonical envelope.
- RAG/Data access: `RAGAgent` / `DataCoordinator` query DB/vector store (Supabase wrapper) as needed and return records with provenance.
- Envelope output & delivery: Orchestrator returns an envelope (metadata + `records[]`) which the `Worker` can persist to audit and call the delivery tool (currently disabled by default).
- Monitoring & ack: `Worker` emits platform_monitoring events, then acks or requeues on failure.

## Envelope pattern (deterministic IO)
All agent inputs/outputs converge on a JSON envelope:
- metadata: source, retrieved_at, query_filters, total_count, fallback, cache, pagination.
- records: list of dicts. Each record may include a `provenance` block (row_id/hash, source, retrieved_at; optional raw_row when explicitly requested).

Benefits
- Stable shapes for testing and composition across agents.
- Auditable: per-record provenance enables debugging and compliance.

## RAG agent behavior (lean and safe)
- No import-time or init-time LLM; `self.llm` and `self.agent` are optional and can be injected.
- Fast-path: parse simple filters (id, email, company, client_id) from text; call `query_leads` via the read-only facade.
- Pagination & caching: manual offset/limit and an in-memory cache keyed by a stable filter hash. Limits are clamped by env (`RAG_MAX_LIMIT`).
- Reformulation: optional, bounded attempts to relax filters (e.g., drop email, shorten company suffix) before fallbacks.
- Fallbacks: rate-limited agent fallback (`MAX_FALLBACKS_PER_MIN`) when queries return 0 rows; never throws on planner errors.
- Debug flags: `RAG_DEBUG_IO=1` prints I/O envelopes; `RAG_DEEP_DEBUG=1` prints step-by-step traces (safely truncated).

## Persistence capabilities
- `ReadOnlyPersistenceFacade` exposes read/query/get_columns only; write APIs raise `PersistencePermissionError`.
- Adapters can advertise capabilities (e.g., `ilike`) used by the RAG agent to decide between contains vs. equality.
- Service wraps calls with allowlists, light metrics, and optional traces.

## Testing posture
- Offline by default: unit/integration tests that hit live services are gated by `USE_REAL_TESTS=1` and required env keys.
- Mock path uses `InMemoryAdapter` with small seeded datasets for deterministic behavior.

## CI and safety
- GitHub Actions runs: `pytest` (offline suite) and `scripts/secret_scan.py` to catch obvious credential patterns.
- Monitoring exporters sanitize keys and token-like values before logging.

## Optional queue backend: Redis Streams
- The infra queue protocol (`agent/Infastructure/queue/interface.py`) can be backed by Redis Streams for distributed workers.
- See `docs/REDIS.md` for stream/group naming, ops patterns (heartbeats, idempotency, DLQ), and environment variables.

## Extensibility notes
- Orchestration engine is a thin local runner; can be replaced by LangGraph/N8N/etc.
- `deliver_data` tool is intentionally disabled in public code to avoid side-effects; wire it to your registry/bus in private deployments.

---

## Infrastructure overview

- Queue contract: `agent/Infastructure/queue/interface.py`
  - Local development queue: `agent/Infastructure/queue/in_memory.py`
  - Factory/helper: `agent/Infastructure/queue/factory.py`
- Worker and dispatch
  - Worker: `agent/Infastructure/worker/worker.py` (consumes from queue and invokes orchestrators/agents)
  - Dispatcher: `agent/Infastructure/dispatcher/dispatcher.py` (simple routing)
- Orchestration engine
  - Interface/stub: `agent/Infastructure/orchestration_engine/__init__.py`
  - Runner: `agent/Infastructure/orchestration_engine/runner.py` (local flow runner)
- Optional distributed queue
  - See Redis section above; details in `docs/REDIS.md`.

## Operational orchestration (high level)

- Control layer
  - `agent/high_level_agents/control_layer/campaign_manager.py`
  - `agent/high_level_agents/control_layer/scheduler.py`
- Orchestrators (domain flows)
  - Base and registries under `agent/high_level_agents/orchestrators/`
  - Examples: `lead_orchestrator.py`, `reply_orchestrator.py`, `delivery_orchestrator.py`
  - Plugin surface under `agent/high_level_agents/orchestrators/plugins/`

## Operational agents (I/O focused)

- RAG Agent: `agent/operational_agents/rag_agent/rag_agent.py`
  - Offline-first, deterministic envelopes, read-only persistence use.
  - Tools: `query_leads`, `query_table`, `rag_agent`, and a disabled `deliver_data`.
- Copywriter: `agent/operational_agents/copywriter` (lightweight placeholder)
- Persistence write agent: `agent/operational_agents/persistence_agent/` (write worker)
- Minimal DB writer for tests: `agent/operational_agents/db_write_agent/db_write_agent.py`

## Tools

- Persistence service and adapters
  - Service/façade: `agent/tools/persistence/service.py` (allowlists, metrics, read-only facade)
  - Adapters: `agent/tools/persistence/adapters/` (InMemory, Supabase)
  - RAG context helpers: `agent/tools/persistence/rag_context.py`
  - Metrics + exceptions: `agent/tools/persistence/metrics.py`, `exceptions.py`
- Data coordination
  - `agent/tools/data_coordinator.py` (coalesce/query helpers used by agents)
- Delivery interfaces
  - `agent/tools/delivery/interface.py` and simple adapters (e.g., `noop_adapter.py`)
- Redis tools (for Streams-based flows)
  - `agent/tools/redis/` client/messages/config helpers

## Utils

- Envelopes: `agent/utils/envelope.py` (canonical shape, provenance helpers)
- Schemas: `agent/utils/schemas.py` (optional typing/validation aids)
- Mocks: `agent/utils/mock_leads.py` (sample data for tests/demos)

## Monitoring and telemetry

- Event/log exporters: `platform_monitoring/exporters.py` (key-based redaction + token masking)
- Prometheus metric hook: `platform_monitoring/exporters.py::prometheus_metric` (placeholder for client wiring)
- Monitoring README: `platform_monitoring/README.md`

## Tests

- Offline by default; live integrations gated by env:
  - Set `USE_REAL_TESTS=1` and provide credentials to run real Supabase tests.
- Key suites
  - RAG behavior and NLP parsing: `tests/test_rag_agent*.py`
  - Persistence and write paths: `tests/test_db_write_agent.py`, `tests/test_persistence_agent.py`
  - Orchestrators/queues/workers: `tests/test_queue_in_memory.py`, `tests/test_worker.py`, `tests/test_worker_audit.py`
  - Registry and envelope utilities: various `tests/test_registry.py`, `tests/test_envelope.py`

## Scripts

- Demo and examples
  - `scripts/rag_demo.py` — offline RAG demo using in-memory persistence
  - `scripts/orchestrator_write_demo.py`, `scripts/orchestrator_redis_demo.py` — orchestration examples
- Persistence and data
  - `scripts/mock_ingest.py`, `scripts/generate_mock_leads.py`, `scripts/workflow_lead_upsert_example.py`
  - `scripts/migrate_db_write.py` — migration utility for persistence layer
- Redis and streams
  - `scripts/streams_health.py`, `scripts/streams_write_benchmark.py`, `scripts/streams_group_reset.py`, `scripts/redis_health.py`, `scripts/redis_stream_smoke.py`
- CI and safety
  - `scripts/secret_scan.py` — lightweight secret scanner
  - `scripts/ci_guard_persistence.py` — guardrails and checks for persistence config

---

## Practical test plan (local, fast)
Minimal steps to validate the end-to-end wiring without live services:
1) Create a tiny fake orchestrator that returns an envelope with the incoming email as a record; register it in `Registry`.
2) Use `InMemoryQueue` and `Worker` to run the job:
  - Call `CampaignManager.ingest_event(mock_email)` to enqueue.
  - Run `worker.run_once()` to process.
3) Assert:
  - Queue is empty after run (no pending).
  - Audit store contains the envelope.
  - platform_monitoring events were emitted at start/success.
