# Roadmap (Developer Guide)

This document tracks near-term tasks, ongoing work, and design intentions. It consolidates the prior Developer README into a concise, actionable roadmap.

## High priority

1) JSON Envelope Standard
- Purpose: Standardize data exchange between agents.
- Action: Keep `agent/utils/envelope.py` as the canonical definition; ensure provenance helpers cover source, row_id/hash, retrieved_at.

2) Copywriter Agent
- Purpose: Deterministic text generation for email/text replies.
- Action: Continue building prompt templates and unit tests under `agent/operational_agents/copywriter/`.

3) Orchestration
- Purpose: Manage flows and route tasks to operational agents.
- Action: Maintain a thin orchestrator surface now; future option to migrate orchestration to LangGraph nodes while keeping tool contracts stable.

4) Communication layer
- Purpose: Flexible transport between components.
- Action: Local dev uses direct calls + in-memory queue; optional Redis Streams for distributed workers; formalize queue protocol and add group reset/replay tooling.

## Medium priority

1) Registry tests
- Expand discovery validation for agents/tools. Add edge-case checks for missing exports.

2) GitHub Actions
- CI for offline tests + secret scan; optional coverage badge.

3) Delivery safety
- Keep delivery disabled by default (feature flag). Provide a `NoOpDeliveryAdapter` and clearly document how to enable in private deployments.

## Design notes

- Envelope: metadata + records + provenance + status/error. Used at boundaries for auditability and stable testing.
- Agent hierarchy: management/control layer → domain orchestrators → operational agents (RAG, copywriter, persistence).
- Communication: start simple (function calls/in-memory); scale with Streams; keep contracts stable.

## Learning resources

- Registries: `agent/operational_agents/registry.py`, `agent/tools/registry.py`.
- Supabase adapter: `agent/tools/persistence/adapters/supabase_adapter.py` (if present) and service `agent/tools/persistence/service.py`.
- Tests: `tests/` (focus on rag/persistence and orchestrator/queue).

## Developer tips

- Follow the envelope standard for inter-agent IO.
- Prefer unit tests with in-memory adapters; gate live runs behind `USE_REAL_TESTS=1`.
- Use feature flags to disable side effects.
- Keep logs and audits PII-safe; use redaction helpers in `platform_monitoring/exporters.py`.
