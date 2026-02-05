# Agentic System - TODO Tracker

## Work Log (Jan 24, 2026)

- Added atomic promotion RPC migration (staging → leads) with idempotent copy + archive
- Added Supabase RPC support in adapter + InMemoryAdapter stub
- Updated promotion helper to prefer RPC and fall back to legacy flow
- Added approval-mode guard in ChannelSequencerAgent (draft instead of send when enabled)
- Added outbound hard-stop rules + Redis throttles (per-hour + new threads/day)
- Added tests for hard-stop blocking + throttling in ChannelSequencerAgent
- Hardened qualification lifecycle persistence (normalize scorer decision → stored `qualification_status`)
- Added stale staging lead sweeper script + docs

## Completed (This Session)

### ✅ Outbound Email Persistence

- Channel Sequencer Agent now persists sent emails via PersistenceAgent
- Compound write creates conversation + message with direction=outbound
- correlation_id preserved in message metadata
- Test: `test_channel_sequencer_persistence.py`

### ✅ Correlation ID Propagation

- Persistence consumer injects envelope correlation_id into task payload
- Compound handler injects correlation_id into messages/staging_messages metadata
- Tests: `test_persistence_correlation.py`

### ✅ New Unit Tests Added

- `tests/unit/services/test_gmail_reader.py` - MIME decoding, email parsing
- `tests/unit/services/test_redis_client.py` - Stream namespacing, xadd/xread
- `tests/unit/services/test_supabase_adapter.py` - REST headers, ilike, upsert
- `tests/unit/services/test_webhook_receiver.py` - Secret validation, publish flow
- `tests/unit/tier_3/test_compound_handler.py` - Refs, CRUD steps, rollback, retry

### ✅ Qualification Lifecycle Hardening

- Centralized decision → persisted state mapping in `tiers/tier_2/leads_orchestrator/qualification/lifecycle.py`
- Added `scripts/maintenance/sweep_stale_staging_leads.py` (dry-run default, `--apply` to write)
- Docs updated in MkDocs (Leads + Staging guide + env vars + scripts reference)

---

## URGENT (Pre-MVP Release)

### 🔥 Data Integrity: Atomic Promotion

- Implement Supabase RPC for atomic promotion (staging → leads) so history never “half moves”
- Enforce idempotency (re-running promotion must not duplicate conversations/messages)
- Status: RPC migration added + promotion helper wired; deploy migration pending

### 🔥 Outbound Safety + Control

- Add approval mode (draft-only + explicit user send) as MVP-safe default
- Add sending throttles/limits per tenant (max/hour, max new threads/day)
- Add hard stop rules: unsubscribe/stop, legal threats, angry/abusive, sensitive data → never auto-send
- Status: approval guard added (OUTBOUND_APPROVAL_MODE); throttles + hard-stop rules added

### 🔥 Campaign / Mailbox Routing

- Remove reliance on `CAMPAIGN_ID_PLACEHOLDER` by creating a real “Inbound Default Campaign” per tenant or mapping mailbox → campaign
- Ensure every inbound/outbound persistence write has a valid `campaign_id`

### 🔥 Observability + Supportability

- Add trace-by-`correlation_id` tooling (inbound → persistence → reply/draft → send → persistence)
- Alert on DLQ growth + repeated failures; add basic consumer health summary

### 🔥 Qualification Lifecycle

- Define a minimal qualification state machine (new → nurturing → qualified → disqualified → promoted)
- Add scheduled handling for stale staging leads (re-score, archive, escalate)
- Status: decision normalization + stale-lead archival backstop implemented; automated re-score cadence still pending

## Remaining TODOs (Low Priority Stubs)

### Inbound Orchestrator

- `tools/__init__.py` - Empty stub, but core logic exists in `inbound_orchestrator.py`
- `schemas/__init__.py` - Empty stub (Pydantic models not yet defined)
- Status: **Functional** - ClassifierAgent integration works

### Audit Orchestrator

- `audit_orchestrator.py` - Skeleton with TODO placeholders
- `run_compliance_check()` - Not implemented
- `generate_audit_trail()` - Not implemented
- Status: **Skeleton** - Needs implementation if audit features required

### Other Code TODOs (from grep)

- `classifier_agent.py:290` - "Call LLM for classification"
- `scheduler_agent.py:17` - "integrate provider SDKs (Google/Outlook)"
- `rag_agent.py:645` - "Implement LLM-based repair logic"
- `rag_agent.py:1496` - "Implement actual vector search"
- `leads_orchestrator.py:1128,1332` - "Integrate with actual persistence layer"

---

## Test Commands

```powershell
# Run all new session tests
pytest tests/unit/services/test_gmail_reader.py tests/unit/services/test_redis_client.py tests/unit/services/test_supabase_adapter.py tests/unit/services/test_webhook_receiver.py tests/unit/tier_3/test_compound_handler.py -v --no-cov

# Run persistence/correlation tests
pytest tests/unit/tier_3/test_channel_sequencer_persistence.py tests/unit/tier_3/test_persistence_correlation.py -v --no-cov
```
