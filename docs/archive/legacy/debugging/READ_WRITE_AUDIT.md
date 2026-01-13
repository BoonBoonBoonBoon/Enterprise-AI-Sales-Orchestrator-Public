# Read/Write Audit (Redis Streams + Supabase)

This document inventories **every file in this repo that materially participates in reading/writing** to:

- **Redis Streams** (task/result flow across tiers)
- **Supabase/Postgres** (persistence reads/writes)

It is written to answer the recurring failure mode: **tests pass but the real system doesn’t**.

---

## 1) What “read/write” means in this audit

Included:
- Redis stream producers: `xadd`, and wrappers that call `xadd`
- Redis stream consumers: `xreadgroup`, `xack`, `xgroup_create`, and PEL inspection tools
- Supabase / persistence DB operations: `write`, `upsert`, `batch_write`, `delete`, `read`, `query` via adapters/services
- Helpers that materially affect DB/stream behavior (allowlists, schema filtering, namespacing)

Not included (unless they touch the above):
- Local file I/O, logging, and purely in-memory transforms

---

## 2) Canonical stream naming + namespacing (critical for “it ran but nothing happened”)

### 2.1 Canonical system keys (no extra namespace prefix)

The system’s canonical stream keys are **already fully-qualified** and must not be double-prefixed:

- `{tenant}:manager:tasks` → `{tenant}:manager:results`
- `{tenant}:orchestrators:{name}:tasks` → `{tenant}:orchestrators:{name}:results`
- `{tenant}:agents:{name}:tasks` → `{tenant}:agents:{name}:results`

### 2.2 Where the prefixing logic lives

**File:** `services/redis/client.py`
- `RedisStreamsClient._chan()` prefixes keys with `REDIS_NAMESPACE` **unless** the key already contains `:manager:`, `:orchestrators:`, or `:agents:`.

**Failure mode:** if producers use a non-canonical key (e.g., `persist:tasks`) it will be prefixed to `agentic:persist:tasks`, while consumers might listen to `{tenant}:agents:persistence:tasks`. That looks like “tests pass” (unit tests don’t hit real Redis), but prod never drains the expected stream.

### 2.3 Tier 2 vertical-only publish guard

**File:** `core/streams.py`
- `assert_agents_stream(stream_name)` prevents Tier 2 from publishing to anything except `*:agents:*` streams.

---

## 3) Supabase/Persistence core (DB read/write)

### 3.1 Central allowlists (what tables may be read/written)

**File:** `config/persistence_config.py`
- `get_write_allowlist()` / `get_read_allowlist()`
- Defines `ALL_TABLES` including:
  - `staging_leads`, `staging_conversations`, `staging_messages`
  - `leads`, `conversations`, `messages`
  - plus workflow/audit tables

Env overrides:
- `PERSIST_WRITE_TABLES` (full override)
- `PERSIST_WRITE_DENY` (subtract from default)
- `PERSIST_READ_TABLES` (full override)

**Failure mode:** staging tables not present in the write allowlist means inbound email can enqueue correctly, but writes are blocked by policy.

### 3.2 Persistence façade (policy enforcement + error wrapping)

**File:** `services/persistence/service.py`
- `PersistenceService` is the policy gate + wrapper around an adapter
  - enforces per-op allowlists: `read_allowlist`, `write_allowlist` (or legacy `allowed_tables`)
  - wraps backend errors as `AdapterError`
- `ReadOnlyPersistenceFacade` blocks writes (used for RAG/copywriter safety)
- `build_supabase_service()` constructs a `SupabaseAdapter` from env

Env (factory only):
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY` or `SUPABASE_KEY`
- `PERSIST_ALLOWED_TABLES` (legacy single allowlist)

**Failure mode:** tests often use `InMemoryAdapter` and never exercise real RLS/JWT, so `AdapterError` + RLS mismatches only appear in real runs.

### 3.3 Production DB adapter

**File:** `services/persistence/adapters/supabase_adapter.py`
- Implements `write/batch_write/upsert/delete/read/query`
- Has SDK vs REST fallback behavior (esp. when used with custom JWT + anon key)

Env (adapter):
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY` (needed for custom JWT REST path)
- `SUPABASE_SKIP_DNS_CHECK` (bypass DNS fail-fast)

**Failure modes:**
- DNS check blocks adapter init on certain hosts (unless `SUPABASE_SKIP_DNS_CHECK=1`)
- JWT/RLS mismatch allows reads but silently blocks writes depending on policies

### 3.4 RAG context assembly utility (read-only)

**File:** `services/persistence/rag_context.py`
- `build_rag_context(persistence, ...)` calls `query()` across `clients/leads/campaigns/conversations/messages`

**Failure mode:** if `ReadOnlyPersistenceFacade` or read allowlist doesn’t include a table, you’ll get `TableNotAllowedError`.

### 3.5 Staging promotion (writes to primary tables + archives staging)

**File:** `services/persistence/promotion/promote_staging_lead.py`
- `promote_staging_lead_to_lead(staging_lead_id, lead_id, service=None)`:
  - reads: `staging_conversations`, `staging_messages`
  - writes: `conversations`, `messages`
  - archives: `staging_messages`, `staging_conversations`, `staging_leads` via `archived_at`

**Failure mode:** promotion depends on `build_supabase_service()` which uses service key env vars; if you only set JWTs for agents, promotion scripts may fail.

### 3.6 Legacy/deprecated tools

**File:** `services/persistence/tools/supabase_tools.py`
- Marked legacy; guidance is to use `PersistenceService` + `SupabaseAdapter`.

---

## 4) Tier 3 agents (consume agent task streams, do DB reads/writes)

### 4.1 Persistence Agent (writes)

**Files:**
- `tiers/tier_3/persistence_agent/consumer.py` (async consumer)
- `tiers/tier_3/persistence_agent/persistence_agent.py` (tooling/agent wrapper)
- `tiers/tier_3/persistence_agent/compound_handler.py` (compound multi-table executor)
- `tiers/tier_3/persistence_agent/write_worker.py` (alternate/legacy worker)

**Streams:**
- consumes: `{tenant}:agents:persistence:tasks`
- publishes: `{tenant}:agents:persistence:results`

**Key behavior:**
- May run in “Supabase + Redis cache” hybrid mode, or “Redis-only” fallback mode depending on env.

**Critical env:**
- `SUPABASE_URL`
- `SUPABASE_PERSISTENCE_JWT` OR `SUPABASE_SERVICE_KEY` OR `SUPABASE_KEY`
- `SUPABASE_ANON_KEY` (when using custom JWT)
- `PERSISTENCE_ENABLE_SCHEMA_FILTERING` (compound handler schema introspection; default off)

**Failure modes that produce “tests pass but prod doesn’t”:**
- Supabase not configured: Persistence tools disabled or consumer falls back to Redis-only (no DB writes)
- Consumer group stuck (PEL): `xreadgroup` with `>` will not re-deliver pending messages
- Table allowlist denies staging writes
- Schema introspection (when enabled) can fail under certain JWT/RLS combinations

### 4.2 RAG Agent (reads)

**Files:**
- `tiers/tier_3/rag_agent/rag_agent.py` (deep agent; read-only adapter wrapper)
- `tiers/tier_3/rag_agent/query_strategy.py` (cascading multi-table retrieval + query trace)
- `tiers/tier_3/rag_agent/consumer.py` and `tiers/tier_3/rag_agent/worker.py` (stream workers)

**DB tables read (typical):**
- `leads`, `staging_leads`, `conversations`, `messages`, `staging_conversations`, `staging_messages`

**Env:**
- `SUPABASE_URL`
- `SUPABASE_RAG_JWT` (preferred) or `SUPABASE_SERVICE_KEY`/`SUPABASE_KEY`
- `SUPABASE_ANON_KEY` (when using custom JWT)

**Failure mode:** tests frequently monkeypatch `SupabaseAdapter` (no real Supabase), so real RLS/auth failures only show in production.

### 4.3 Copywriter Agent (streams + optional read-only persistence)

**File:** `tiers/tier_3/copywriter_agent/worker.py`
- Uses `ReadOnlyPersistenceFacade` (read-only) when Supabase is configured.

---

## 5) Tier 2 orchestrators (enqueue to Tier 3 agent streams)

### 5.1 Leads Orchestrator (publisher to persistence + rag)

**File:** `tiers/tier_2/leads_orchestrator/leads_orchestrator.py`
- Publishes to `{tenant}:agents:persistence:tasks` via:
  - `_enqueue_persistence_write_lead()`
  - `_enqueue_persistence_read_lead()`
  - `_enqueue_persistence_query_leads()`
  - `_enqueue_persistence_query_table()`
  - `_enqueue_persistence_compound()`
- Tool wrappers:
  - `delegate_to_persistence_agent_tool(...)`
  - `compound_persistence_tool(...)`
  - `store_inbound_email_tool(...)` (standard inbound email compound flow)

**Critical observation:** if the leads orchestrator produces tasks but you see no DB writes, the usual culprits are:
- persistence consumer not running / wrong stream key / wrong tenant id
- consumer group pending messages
- Supabase env not set in the persistence consumer process

### 5.2 Leads Orchestrator consumer

**File:** `tiers/tier_2/leads_orchestrator/consumer.py`
- Consumes `{tenant}:orchestrators:leads:tasks`
- Publishes `{tenant}:orchestrators:leads:results`
- Uses `services.redis.RedisStreamsClient` wrapper (namespacing rules apply)

### 5.3 Outreach Orchestrator (publisher to copywriter agent)

**Files:**
- `tiers/tier_2/outreach_orchestrator/outreach_orchestrator.py`
- `tiers/tier_2/outreach_orchestrator/consumer.py`

(Primarily stream read/write; not DB write.)

---

## 6) Tier 1 manager (routes by enqueuing orchestrator tasks)

**Files:**
- `tiers/tier_1/manager/manager_agent.py`
- `tiers/tier_1/manager/consumer.py`
- `tiers/tier_1/manager/tools/delegation_tools.py` (explicit `xadd` delegation)
- `tiers/tier_1/manager/policy/router.py` (stream name construction)

**Streams:**
- consumes: `{tenant}:manager:tasks`
- publishes: `{tenant}:manager:results`
- delegates to orchestrators: `{tenant}:orchestrators:*:tasks`

---

## 7) Frontend publisher (manual testing / UI-driven enqueue)

**File:** `int-frontend/app.py`
- Publishes tasks to streams via `xadd`
- Also reads via `xrange` for inspection

**Failure mode:** UI might enqueue to one stream key while consumers listen to another (tenant mismatch / namespace mismatch / old stream name).

---

## 8) Diagnostics and operations scripts (read/write touchpoints)

This folder is large. These are the scripts that directly impact diagnosis of “nothing is writing/reading” in production-like runs:

### 8.1 Supabase diagnostics
- `scripts/verify_supabase_setup.py`
- `scripts/diagnose_supabase.py`
- `scripts/decode_supabase_jwt.py`
- `scripts/test_supabase_direct.py`

### 8.2 Persistence stream diagnostics
- `scripts/check_persistence_streams.py`
- `scripts/reset_persistence_consumer_group.py`
- `scripts/publish_test_compound.py`
- `scripts/persistence_write_smoke.py`

### 8.3 Redis stream diagnostics (generic)
- `scripts/check_pending.py`
- `scripts/streams_health.py`
- `scripts/redis_stream_smoke.py`
- `scripts/manage_redis_streams.py`
- `scripts/dlq_requeue.py`

**Failure mode:** some scripts use legacy stream names or generic names that will be prefixed by `REDIS_NAMESPACE`; always confirm the exact resolved key name in Redis.

---

## 9) Tests that can mask real failures (“tests pass but they don’t”)

These tests commonly stub adapters and do not validate real Supabase + RLS:

- Many `tests/unit/tier_3/test_rag_*` tests monkeypatch `SupabaseAdapter`.
- Persistence tests often use `InMemoryAdapter` and bypass real network/auth.

**Practical implication:** a green test suite does not prove that:
- the persistence consumer is running,
- env vars are present in the *consumer process*,
- stream keys match (tenant/namespace),
- Supabase JWT/RLS allows writes,
- consumer groups are not stuck in pending.

---

## 10) Fast triage checklist (when staging tables don’t update)

1) Confirm the producer stream key being written (tenant/namespace).
2) Confirm the persistence consumer is running and listening to the same key.
3) Check consumer group pending (`XPENDING`) — stuck PEL will look like “no updates”.
4) Confirm persistence consumer env has Supabase vars (it can fall back to Redis-only).
5) Confirm `config/persistence_config.py` allowlists include staging tables and that env overrides aren’t removing them.

---

## Appendix: files explicitly referenced in this audit

- `config/persistence_config.py`
- `core/streams.py`
- `services/redis/__init__.py`
- `services/redis/client.py`
- `services/persistence/service.py`
- `services/persistence/adapters/supabase_adapter.py`
- `services/persistence/rag_context.py`
- `services/persistence/promotion/promote_staging_lead.py`
- `tiers/tier_1/manager/manager_agent.py`
- `tiers/tier_1/manager/consumer.py`
- `tiers/tier_1/manager/tools/delegation_tools.py`
- `tiers/tier_2/leads_orchestrator/leads_orchestrator.py`
- `tiers/tier_2/leads_orchestrator/consumer.py`
- `tiers/tier_2/outreach_orchestrator/outreach_orchestrator.py`
- `tiers/tier_2/outreach_orchestrator/consumer.py`
- `tiers/tier_3/persistence_agent/consumer.py`
- `tiers/tier_3/persistence_agent/persistence_agent.py`
- `tiers/tier_3/persistence_agent/compound_handler.py`
- `tiers/tier_3/persistence_agent/write_worker.py`
- `tiers/tier_3/rag_agent/rag_agent.py`
- `tiers/tier_3/rag_agent/query_strategy.py`
- `tiers/tier_3/rag_agent/consumer.py`
- `tiers/tier_3/rag_agent/worker.py`
- `tiers/tier_3/copywriter_agent/worker.py`
- `int-frontend/app.py`
- `scripts/*` (selected operational scripts listed above)
