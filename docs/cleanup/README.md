Cleanup & Hardening Tasks (Phase 2+)
===================================

This document tracks pending refactors, deprecations, and hardening activities following the Phase 1 consolidation (central config + factory + read-only facade).

Legend
------
- [ ] Not Started
- [~] In Progress / Partially Complete
- [x] Done

High-Priority (Phase 2)
-----------------------
- [~] Remove legacy `DBWriteAgent` and `agent/tools/db_write/` directory.
- [ ] Add tombstone stub raising `ImportError` with migration guidance if old import path used.
- [ ] Purge direct Supabase client bootstrap from `RAGAgent` (require injected facade).
- [ ] Add test asserting `RAGAgent` performs zero writes (facade denies writes intentionally).
- [ ] Introduce CI check to fail build if any file under `db_write` is reintroduced.
- [ ] Add empty-file / zero-length detector script in CI (prevents silent truncation regressions).

Medium Priority (Phase 3)
------------------------
- [ ] Capability flags on adapters (e.g. `filter_ops`, `max_batch_size`, `supports_projection`).
- [ ] Schema registry JSON (`schema/persistence_tables.json`) with column list + required fields.
- [ ] Validation layer: verify `select` projections & reject unknown columns early.
- [ ] Retry/backoff strategy (decorated `_invoke`) with transient classification (e.g. network, 5xx).
- [ ] Metrics integration: counters (`persistence_ops_total`), histograms (`persistence_op_latency_ms`).
- [ ] Structured JSON logging for persistence operations (replace print instrumentation).
- [ ] RAG token budget manager (truncate records to fit model context window).
- [ ] RAG multi-entity context assembly (clients, campaigns, conversations, messages) with scoring.

Lower Priority / Nice to Have (Phase 4)
--------------------------------------
- [ ] Vector / embedding adapter (hybrid retrieval).
- [ ] Read replica read-only adapter (direct Postgres / psycopg).
- [ ] Caching decorator (LRU or Redis) for hot read/query outcomes.
- [ ] Field-level redaction / masking (PII scrubbing) before envelope emission.
- [ ] Circuit breaker around adapter to shed load on persistent failures.
- [ ] Audit trail persistence (append-only events for each write/upsert).

Testing Enhancements
--------------------
- [ ] Parametrize persistence tests over memory + (optional) Supabase when creds present.
- [ ] Add test for `get_columns` on both adapters (memory vs Supabase skip if unavailable).
- [ ] Add descending order query test.
- [ ] Add RAG integration test verifying filter parsing -> deterministic query path.
- [ ] Add test for schema validation error (after registry introduced).

Tooling & CI
------------
- [ ] Pre-commit hook: block commits with large deletions unless `ALLOW_MASS_DELETE=1` set.
- [ ] Pre-commit: run lightweight secret scan & refuse high-risk patterns.
- [ ] GitHub workflow: run empty-file detector + adapter contract tests.
- [ ] GitHub workflow: mark build failed if deprecated import (`DBWriteAgent`) detected by grep.

Security & Secrets
------------------
- [ ] Add `SECURITY.md` explaining key handling, rotation expectations.
- [ ] Add secret scanning configuration (e.g. `detect-secrets` baseline) to repo.
- [ ] Ensure Supabase service keys never logged (mask in adapters).

Documentation Updates
---------------------
- [ ] Root README: mention factory usage for RAG & persistence (post cleanup completion).
- [ ] Persistence README: add section for schema registry once implemented.
- [ ] RAGAgent README: update when multi-table context shipped.

Operational Readiness
---------------------
- [ ] Add smoke script: issue sample RAG query + assert non-empty prompt generation.
- [ ] Add health endpoint (simple HTTP) for persistence service (lightweight readiness check).
- [ ] Add Grafana dashboard JSON for persistence latency distribution.

Ownership
---------
Agent Infrastructure / Data Platform. Update this file as tasks evolve.

Change Log
----------
- v0.1: Initial task list created after Phase 1 consolidation.

End.
