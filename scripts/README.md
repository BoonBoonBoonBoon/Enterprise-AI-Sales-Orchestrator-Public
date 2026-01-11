# Scripts (quick guide for reviewers)

These scripts are small, purposeful tools to demo and diagnose the system locally. They’re written to be safe-by-default (no side‑effects unless you opt in) and to help you understand the moving pieces quickly.

## Conventions & safety
- Most scripts support .env loading (or are fully offline) and avoid mutating data unless a flag is provided.
- Anything that can write to external systems is either a no‑op by default or clearly labeled.
- Redis scripts respect namespacing from `agent.tools.redis.config`.

## Quick picks
- RAG demo (offline-first): `scripts/rag_demo.py`
- Redis Streams health: `scripts/streams_health.py`
- Generate mock leads (optional enqueue): `scripts/generate_mock_leads.py`
- DLQ helper (safe requeue): `scripts/dlq_requeue.py`
- Secret scan (sanity): `scripts/secret_scan.py`

Run examples (PowerShell):
```powershell
# RAG offline demo
python scripts/rag_demo.py --email alice@example.com

# Streams overview
python scripts/streams_health.py --section both

# Generate 5 mock leads, print JSON only (no writes)
python scripts/generate_mock_leads.py --count 5

# Requeue up to 3 from persist DLQ as upserts (CAUTION: writes)
python scripts/dlq_requeue.py --stream persist --limit 3 --transform-upsert --delete

# Secret scan (offline)
python scripts/secret_scan.py
```

## Script summaries

- `rag_demo.py`
  - Offline RAGAgent run. Prints input filters and output envelope. Uses an in‑memory sample dataset.

- `streams_health.py`
  - Summarizes Redis Streams (RAG + persist) sizes, consumer groups, consumers, and pending stats. Uses env‑driven namespacing.

- `generate_mock_leads.py`
  - Creates realistic mock lead profiles. Prints JSON by default. With `--enqueue`, publishes write tasks to the streams write path (requires a running writer).

- `dlq_requeue.py`
  - Re-enqueues messages from DLQ to their task streams with optional upsert transformation. Dry-run by default; provide flags to actually requeue and delete.

- `secret_scan.py`
  - Lightweight pattern-based scanner to catch obvious secrets in the repo.

- `orchestrator_redis_demo.py`
  - Publishes a sample RAG query task and waits for the matching result, illustrating the task/results streams flow.

- `orchestrator_write_demo.py`
  - Enqueues a write task (insert) and optionally waits for the result; then reads back via the persistence agent.

- `redis_stream_smoke.py`
  - Minimal produce/consume example for the generic tasks stream (smoke test).

- `streams_group_reset.py`
  - SAFE helper to (re)create consumer groups and set their cursors (new-only or replay). Does not delete messages.

- `streams_write_benchmark.py`
  - Push N write tasks and block-read results to estimate throughput. Useful for local tuning.

- `redis_health.py`
  - Quick XINFO stats for a single topic using the RedisStreamsQueue adapter.

- `migrate_db_write.py`
  - Finds potential `DBWriteAgent` usage and points at the new persistence agent for migration.

- `ingest_cli.py`
  - Unified CLI for mock lead ingestion or direct REST diagnostics (Supabase). DEV‑only IDs are guarded by `ENV=production` checks.

- `diagnose_supabase.py`
  - Legacy direct REST insert check. Useful when debugging schema/permission issues. Preferred path is `ingest_cli.py --mode diagnose`.

- `decode_supabase_jwt.py`
  - Decodes a Supabase JWT from env to inspect payload fields locally.

- `get_lead_by_email.py`
  - Looks up a lead by email using the persistence factory (supports `kind=memory|supabase`).

- `persistence_write_smoke.py`
  - Simple smoke test to write a mock lead using the persistence agent (requires Supabase env).

- `supabase_smoke.py`
  - Select * limit 1 against a Supabase table to validate connectivity (no mutations).

- `mock_ingest.py` (legacy)
  - End-to-end application flow demo via `CampaignManager.ingest_event`. Kept for historical comparison with `ingest_cli.py`.

## Environment
- See per-script flags (`--help`) and `docs/REDIS.md` for Streams settings.
- For CI and badge details: `docs/CI.md`.
