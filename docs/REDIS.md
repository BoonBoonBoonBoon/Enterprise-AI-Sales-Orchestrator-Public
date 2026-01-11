# Redis Infrastructure (current)

Namespace: `${REDIS_NAMESPACE}` (default: `agentic`). All keys are prefixed with this namespace, for example: `agentic:rag:tasks`.

## Streams and groups

- RAG
  - `rag:tasks` — group: `rag-workers`
  - `rag:results` — no group (read via XREAD)
  - `rag:dlq` — optional DLQ stream
- Persistence (writes)
  - `persist:tasks` — group: `persist-writers`
  - `persist:results` — no group
  - `persist:dlq` — DLQ for failed writes
- Ops
  - Heartbeats: `ops:hb:{service}:{id}` (STRING with TTL)
  - Idempotency locks: `ops:idemp:{stream}:{msg_id}` (STRING with TTL)

## Operational features (enabled in workers)

- Heartbeats: background SETEX on `ops:hb:{service}:{id}` every `OPS_HB_INTERVAL` seconds; TTL `OPS_HB_TTL`.
- Idempotency: `SET NX` lock per message `ops:idemp:{stream}:{msg_id}` with TTL `OPS_IDEMP_TTL`.
- Retries: up to `REDIS_MAX_RETRIES` with optional `REDIS_RETRY_BACKOFF_MS` delay; final failures go to DLQ if `ENABLE_DLQ=1`.
- Trimming: XADD to results/DLQ uses `MAXLEN ~` with `REDIS_STREAM_MAXLEN` (unset = no trimming).

## Key env vars

- Connection/namespace
  - `REDIS_URL` (preferred) or `REDIS_HOST/PORT/DB/PASSWORD`
  - `REDIS_NAMESPACE` (default: `agentic`)
- Streams (defaults)
  - RAG: `REDIS_STREAM_TASKS=rag:tasks`, `REDIS_STREAM_RESULTS=rag:results`, `REDIS_STREAM_DLQ=rag:dlq`
  - Persist: `REDIS_STREAM_TASKS_WRITE=persist:tasks`, `REDIS_STREAM_RESULTS_WRITE=persist:results`, `REDIS_STREAM_DLQ_WRITE=persist:dlq`
- Groups
  - `REDIS_GROUP=rag-workers`, `REDIS_GROUP_WRITERS=persist-writers`
- Ops toggles
  - `OPS_HB_ENABLED=1`, `OPS_HB_TTL=30`, `OPS_HB_INTERVAL=10`
  - `OPS_IDEMP_TTL=60`
  - `REDIS_STREAM_MAXLEN=20000` (example)
  - `REDIS_MAX_RETRIES=2`, `REDIS_RETRY_BACKOFF_MS=0`
  - `ENABLE_DLQ=1`

## Quick checks

- Group health: `XINFO GROUPS {ns}:rag:tasks` and `{ns}:persist:tasks`
- Pending: `XPENDING {ns}:rag:tasks rag-workers`
- DLQ peek: `XRANGE {ns}:rag:dlq - + COUNT 5`
- Heartbeats: `KEYS {ns}:ops:hb:*` (values expire if workers go down)

---

## Appendix: Streams-first topology and ops (from redis_struct.md)

High-level flows
- Command path
  - Campaign Manager publishes a command (cm:commands).
  - Orchestrator consumes commands, expands into tasks (orchestrator:tasks).
  - Orchestrator routes tasks to the right worker streams (rag:tasks, persist:tasks).
- Worker paths
  - RAG workers consume rag:tasks → publish rag:results.
  - Persist workers consume persist:tasks → write DB → publish persist:results.
- Observability
  - Every step emits audit events (audit:events) and tracing spans (audit:spans).
  - Services heartbeat via ops:hb:{service}:{id} and emit health changes to ops:health.
  - DLQ captures hard failures (persist:dlq, rag:dlq).

Keyspace layout (namespaced examples; prefix via REDIS_NAMESPACE)
- {ns}:cm:commands (STREAM) group=cm-managers
- {ns}:cm:events (STREAM) group=cm-subscribers
- {ns}:orchestrator:commands (STREAM) group=orchestrators
- {ns}:orchestrator:tasks (STREAM) group=orchestrators
- {ns}:orchestrator:results (STREAM) no group
- {ns}:rag:tasks (STREAM) group=rag-workers
- {ns}:rag:results (STREAM) no group
- {ns}:persist:tasks (STREAM) group=persist-writers
- {ns}:persist:results (STREAM) no group
- {ns}:persist:dlq (STREAM) group=dlq-readers
- {ns}:audit:events (STREAM) group=auditors
- {ns}:audit:spans (STREAM) group=auditors
- {ns}:ops:health (STREAM) group=ops
- {ns}:ops:hb:{service}:{id} (STRING) TTL=30s
- {ns}:ops:stats:{service}:m:{yyyymmddhhmm} (HASH)
- {ns}:locks:idemp:{stream}:{msg_id} (STRING) TTL for idempotency
- {ns}:cache:rag:chunks:{doc_id} (HASH) optional RAG cache

Operational guidance
- Trimming: set MAXLEN on high-volume streams (e.g., 20k–100k).
- Groups: create with SETID `$` for fresh runs; use `0-0` to replay.
- Idempotency: `SETNX locks:idemp:{stream}:{msg_id}` with TTL.
- Heartbeats: `SETEX ops:hb:{service}:{id} 30 1` every 10–15s.
- DLQ handling: XADD to DLQ on final failure; use `scripts/dlq_requeue.py` to requeue.

Quick health checks
- `XINFO GROUPS {ns}:persist:tasks`
- `XPENDING {ns}:rag:tasks rag-workers`
- `XINFO STREAM {ns}:audit:events`
- `SCAN 0 MATCH {ns}:ops:hb:*`
