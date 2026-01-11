```markdown
# Persistence / Staging Writes Debug Plan

Goal: reliably write inbound-email persistence into Supabase tables (especially `staging_conversations` + `staging_messages`) and prove correctness end-to-end.

This plan is **bottom-up**: validate Supabase first, then the PersistenceAgent logic, then Redis-stream consumer behavior, then the full pipeline.

---

## Quick Reality Check (What we observed)

- Leads orchestrator reports `status=enqueued_for_persistence`, but exports showed **no** `agents:persistence:*` events.
- When we manually published persistence tasks into Redis, we saw **tasks accumulate** (`tasks > 0`) but **no results** (`results = 0`) until the consumer is confirmed running and able to process.
- A separate issue was found in the persistence consumer: it previously hard-coded allowlists and did not include `staging_conversations` / `staging_messages`. This has been corrected to use `config/persistence_config.py`.
- Another common trap: if you run ad-hoc `xreadgroup` tests using the same group, you can “steal” tasks into PEL (pending entries list). The consumer reads `>` (new messages) and will not process those pending messages.

---

## Layers to Validate (from lowest to highest)

### Layer 0 — Supabase table + RLS readiness
Potential causes:
- JWT invalid/expired
- RLS policies missing for staging tables
- NOT NULL constraints failing (e.g., `client_id`, `metadata`)
- Column-name mismatch (schema drift)

Validation approach:
- **Write directly via SupabaseAdapter** (no Redis, no agents)

Expected pass criteria:
- Insert/upsert succeeds and record can be queried/seen (depending on role/policy).

---

### Layer 1 — PersistenceAgent can write directly (no Redis streams)
Potential causes:
- Compound handler reference resolution ($ref) issues
- Allowlist blocks tables
- Client scoping injection issues
- Adapter selection falls back to cache unexpectedly

Validation approach:
- Instantiate `PersistenceAgent` and call `execute()` with a known-good `compound` payload.

Expected pass criteria:
- Compound returns `status=success` and step results show inserted/upserted rows.

---

### Layer 2 — Persistence consumer drains Redis tasks and publishes results
Potential causes:
- Consumer not running / being killed by environment
- Consumer group PEL issues (messages pending to another consumer)
- Misconfigured `TENANT_ID` / `REDIS_URL`
- Consumer exits due to an exception (needs logs)

Validation approach:
- Start consumer in one terminal.
- Publish a small test compound task.
- Confirm `agents:persistence:results` receives a result.

Expected pass criteria:
- `results` stream increments; task gets acked.

---

### Layer 3 — Full inbound email flow writes to staging
Potential causes:
- Leads orchestrator never actually publishes the persistence task (silent exception)
- Wrong routing target (lead_existing vs staging_new)
- Staging write steps missing required fields

Validation approach:
- Run manager/leads/persistence (+ optionally rag/outbound) and submit an inbound email.
- Verify rows in `staging_*` tables.

Expected pass criteria:
- New `staging_conversations` + `staging_messages` rows appear for unknown lead inbound.

---

## Concrete Step-by-Step Checklist

### Step A — Confirm env vars (minimum)
In `.env` / environment:
- `SUPABASE_URL`
- One of: `SUPABASE_PERSISTENCE_JWT` (preferred) or `SUPABASE_SERVICE_KEY` / `SUPABASE_KEY`
- If using custom JWT pattern: `SUPABASE_ANON_KEY`
- `REDIS_URL`
- `TENANT_ID=agentic-dev` (or your tenant)

Also confirm staging table schemas match what we write:
- `staging_conversations`: `staging_lead_id`, `thread_id`, `subject`, `channel`, `status`, `metadata`
- `staging_messages`: `staging_conversation_id`, `sender`, `receiver`, `content`, `sent_at`, `message_id`, `metadata`

---

### Step B — Direct Supabase write test (no agents)
Purpose: isolate **Supabase auth/RLS/schema**.

Run:
- `& ".venv/Scripts/python.exe" scripts/test_supabase_direct.py`

Pass criteria:
- Script prints `OK` and the inserted/upserted row id.

If it fails:
- `401/403`: JWT or RLS policies
- `23502`: missing NOT NULL field
- `column does not exist`: schema mismatch

---

### Step C — Direct PersistenceAgent write test (no Redis streams)
Purpose: isolate **PersistenceAgent logic + compound handler**.

Run:
- `& ".venv/Scripts/python.exe" scripts/test_persistence_agent_direct.py`

Pass criteria:
- Script prints `status=success` and step results show successful upserts.

---

### Step D — Consumer drain test (Redis streams)
Purpose: verify stream processing is working.

1) Reset consumer group (prevents PEL/pending issues):
- `& ".venv/Scripts/python.exe" scripts/reset_persistence_consumer_group.py`

2) Start consumer (leave running):
- `& ".venv/Scripts\python.exe" -m tiers.tier_3.persistence_agent.consumer`

3) Publish a test compound task:
- `& ".venv/Scripts\python.exe" scripts/publish_test_compound.py`

4) Confirm results:
- `& ".venv/Scripts\python.exe" scripts/check_persistence_streams.py`

Pass criteria:
- `results > 0` and latest result indicates success.

If consumer runs but results remain 0:
- Capture last ~200 lines of consumer logs (there should be an exception).

---

### Step E — Full inbound email end-to-end test
Purpose: validate orchestration and routing.

Prereqs:
- persistence consumer is running and proven by Step D.

Run inbound test:
- Submit inbound email event via your internal frontend.

Verify:
- `staging_leads` upserted/created
- `staging_conversations` created/upserted
- `staging_messages` created/upserted

---

## Possible Root Causes (with fast signals)

1) **Persistence consumer allowlist blocks staging tables**
- Signal: results show error like “table not allowed”
- Fix: ensure consumer uses `config/persistence_config.py` allowlists

2) **RLS blocks staging writes**
- Signal: Supabase write returns `401/403` or silent empty writes depending on adapter
- Fix: add INSERT/UPDATE policies for `agent_writer`

3) **NOT NULL constraint failures**
- Signal: `23502` on insert/upsert
- Fix: include required fields; ensure `metadata` defaults `{}`

4) **Consumer group / pending entries**
- Signal: tasks pile up; consumer reads nothing; `xinfo_consumers` shows pending
- Fix: reset group; avoid ad-hoc `xreadgroup` using production group

5) **Consumer not actually running / being killed**
- Signal: consumer log shows shutdown without processing; no results
- Fix: run in stable terminal/session; check container/task manager

---

## Direct “Single-Agent” Test Targets (without full system)

Use these to test writing without involving manager/leads/outbound:

- **SupabaseAdapter only:** `scripts/test_supabase_direct.py`
- **PersistenceAgent only:** `scripts/test_persistence_agent_direct.py`
- **Persistence consumer only:** Step D scripts

---

## Notes (Windows / PowerShell)

- Avoid multi-line here-strings (`@" ... "@`) in interactive terminals if PSReadLine is unstable; use scripts instead.
- If you see PSReadLine buffer errors, open a fresh terminal or run scripts from VS Code Task/Terminal.

---

## Findings (current session)

- Step B (test_supabase_direct): **blocked** — missing SUPABASE_URL (env not set). Need Supabase env (URL + JWT/service key) before continuing downstream tests.
- RAG enhancement added: if no lead is found, it now falls back to staging_messages by sender to recover staging_conversation → staging_lead, and enriches with that conversation/message context. This should prevent duplicate staging_conversations for repeat senders whose lead wasn’t initially resolved.
- E2E manager business flows (tests/end-to-end/test_e2e_manager_business_flows.py) **passed** end-to-end:
	- Manager → Leads → Persistence (WRITE)
	- Manager → Leads → Persistence (READ)
	- Manager reconnect email (copywriter) flow

```
