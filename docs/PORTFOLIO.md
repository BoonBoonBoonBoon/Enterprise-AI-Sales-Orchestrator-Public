# Portfolio One‑Pager

Problem
- Build agentic workflows (ingest → orchestrate → generate → deliver) with safety and auditability.

Approach
- Clear seams via Protocols and Adapters.
- Deterministic envelope for inter-agent IO.
- Read-only façade for RAG querying; provenance per record.
- Default to offline tests and sanitized logging.

Impact
- Faster iteration with mockable infra; less test flakiness (offline-first tests).
- Easier audits and debugging with per-record provenance and deterministic envelopes.
- Safer public demo suitable for interviews; CI enforces secret scans.

Your role
- Architecture, implementation, tests, and documentation.
- CI hygiene and repository sanitization for public sharing.

What to review
- `agent/tools/persistence/service.py` (adapter/service/facade seam)
- `agent/operational_agents/rag_agent/rag_agent.py` (agent envelope pattern)
- `platform_monitoring/exporters.py` (redaction)
- `docs/ARCHITECTURE.md` (diagram)

Talking prompts
- How would you evolve the orchestration engine?
- Where to add retries/backoff and idempotency?
- How to extend the envelope for delivery/feedback loops?
 - What metrics would you add to the persistence/service layers?
 - How would you scale the queue layer (visibility timeouts, DLQs)?

Notes
- Real integrations are intentionally gated and not required to understand the design.
 - Delivery tools are disabled by default in public code to avoid side-effects.
