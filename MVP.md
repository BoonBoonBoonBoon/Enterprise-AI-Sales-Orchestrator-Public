# Agentic System — MVP Scope (Jan 2026)

This document defines the **minimum viable product** for the Agentic System. The MVP is narrowly scoped around one thing:

**A reliable inbound email reply loop that pulls real lead/conversation context and can draft + (optionally) auto-send a reply.**

The goal is operational confidence: if it fails, we know exactly where and why.

---

## MVP Definition (What “Done” Means)

### Core loop (must work end-to-end)

**Inbound email** → **Leads Orchestrator** (build `reply_packet`) → **Outreach Orchestrator** (delegate to Copywriter) → **Copywriter Agent** (draft reply) → **Sequencer** (enqueue send) → **Email delivery result**

Acceptance criteria:

- A single inbound email event produces a `reply_packet` with:
  - `facts.email` populated
  - `facts.first_name` populated when present in DB
  - `facts.company` / `facts.role` populated when present in DB (supports DB fields `company_name` and `job_title`)
  - `conversation.recent_messages` populated when deep context is available
  - `query_trace` present (for debugging)
- Outreach delegates to Copywriter with the embedded `reply_packet`.
- When `auto_send=true`, Outreach enqueues a sequencing task and a Sequencer result is emitted with status `sent` or `failed`.

Recommended validation:

- Run the built-in validator (Docker):
  - `cd deployment`
  - `docker compose exec -T outreach_orchestrator python scripts/testing/validate_rag_to_copywriter_flow.py --auto-send`

---

## Components Included in MVP

### 1) Reply context retrieval (RAG)

**Purpose:** deterministically assemble lead + conversation + messages for reply generation.

- Operation: `build_reply_context`
- Selection logic: `thread_id` → `subject` → most recent
- Output must include:
  - `lead` (optional if configured)
  - selected `conversation` and `messages` (chronological)
  - `query_trace`

### 2) Leads Orchestrator reply packet builder

**Purpose:** convert retrieval results into a stable `reply_packet` for downstream.

- Must normalize conversation format (`conversation` vs `conversations` list)
- Must forward `query_trace` into the packet
- Must be able to wait for RAG result when configured:
  - `LEADS_WAIT_FOR_RAG_CONTEXT`
  - `LEADS_RAG_CONTEXT_TIMEOUT_S`

### 3) Outreach Orchestrator + auto-send gating

**Purpose:** draft replies and optionally auto-send.

- Delegates to Copywriter
- When auto-send is enabled:
  - Stores routing context keyed by copywriter task id in Redis hash: `{tenant}:outreach:auto_send`
  - On copywriter completion, enqueues `{tenant}:agents:sequencing:tasks`

### 4) Copywriter placeholder safety

**Purpose:** prevent template placeholders in outbound content.

- If the model emits bracket placeholders like `[Your Name]`, post-processing must remove/replace them.
- Output should never contain raw square-bracket placeholders.

### 5) Sequencer send result

**Purpose:** execute email step(s) and produce an explicit result.

- Must emit a result envelope with a clear `status` and error details on failure.

---

## Inbox Monitoring (MVP Priority #1)

### Goal

Continuously monitor an inbox and turn incoming messages into Manager tasks so the core loop runs automatically.

### Minimal feature set

- Poll an inbox on a fixed interval (or via provider push webhook if available later).
- For each **new** inbound message:
  - Normalize into an `inbound_email_event` payload (`from`, `to`, `subject`, `body`, `thread_id`, `message_id`, `received_at`, optional `from_name`)
  - Publish to `{tenant}:manager:tasks`
  - Record a dedup marker so the same message is not processed twice.

### Acceptance criteria

- Monitoring process runs continuously and logs:
  - last poll time
  - number of messages scanned
  - number of new messages published
- No duplicates across restarts:
  - dedup key is persisted (Redis or DB)
  - re-processing the same message id is a no-op
- Each published Manager task includes enough data for Leads to retrieve context:
  - `from` email
  - `thread_id` and/or `subject`

### Recommended implementation (fits current architecture)

- Implement as a **Tier 0 / external ingress** process that only publishes to Manager:
  - Publishes envelopes to `{tenant}:manager:tasks`
  - Does not call orchestrators directly
- Provider approach (MVP):
  - **Primary path: Poller** (one inbox account) with a provider adapter abstraction.
    - Support/consider both **Gmail API** and **IMAP**.
    - Implement Gmail API first if possible (better threading/labels); keep IMAP adapter as a drop-in fallback.
  - **Backup path: FastAPI webhook receiver** that accepts an `inbound_email_event` payload and publishes the same Manager task envelope.
    - This is the safety valve when polling is down or a provider push source is available.
- Store dedup state in Redis (simple) or DB (auditable):
  - Redis key suggestion: `{tenant}:inbox:seen:{provider}:{message_id}` with TTL

### Operational knobs

- `INBOX_POLL_INTERVAL_S` (default: 30–60s)
- `INBOX_PROVIDER` (gmail/imap)
- Provider credentials (kept in `.env` / secrets manager)
- Webhook receiver (backup path): bind/port + optional shared secret

### MVP Non-goals (explicitly out of scope)

- Multi-inbox routing rules (roadmap item; single inbox only for MVP)
- Attachment parsing
- Thread reconstruction beyond `thread_id`
- Human-in-the-loop UI

---

## MVP Test Plan

### 1) Deterministic path test

- Run `validate_rag_to_copywriter_flow.py --auto-send` and require:
  - copywriter task exists
  - outbound result status `sent_enqueued`
  - sequencer result status `sent`

### 2) Inbox monitoring smoke test

- Start inbox monitor in a dev tenant
- Send one email to the monitored inbox
- Confirm:
  - one Manager task published
  - one Leads result produced with `reply_packet`
  - no duplicate tasks on subsequent polls

---

## MVP Milestones

1. **Inbox monitoring** (Tier 0 ingress + dedup + publishing to Manager; FastAPI webhook backup)
2. **Core loop reliability** (context → draft → enqueue send)
3. **Observability** (traceable failures and fast diagnosis)

---

## Roadmap: B2B-Sellable MVP (Productization)

This roadmap takes the engineering MVP defined above and adds the **minimum product surface** required to sell B2B.

**Assumption:** we ship the current “golden path” (Inbound → Manager → Leads → Outreach → Copywriter → Sequencer → Persistence) and productize around it.

### Phase 0 — Lock the contract (2–4 days)

- [x]- Freeze canonical flow + payload contracts: `inbound_email_event`, `reply_packet`, `query_trace`, `correlation_id`.
- [x]- Choose default safety posture: ship with `OUTBOUND_APPROVAL_MODE=1` as the default for all tenants.
- [x]- Define “Done”: 1 inbound email reliably produces a draft; send requires explicit approval or explicit `auto_send=true` in controlled modes.

### Phase 1 — Golden-path reliability (Week 1)

- [x]- Implement/standardize Tier-0 inbox monitoring (poller primary + webhook backup) exactly as specified in “Inbox Monitoring”.
- [x]- Harden dedup across restarts (Redis TTL acceptable for MVP; DB audit optional later).
- [x]- Make the validator script the canonical demo/runbook:
  - `cd deployment`
  - `docker compose exec -T outreach_orchestrator python scripts/testing/validate_rag_to_copywriter_flow.py --auto-send`

**Exit criteria:** repeatable run succeeds twice; failures are diagnosable via `query_trace` + `correlation_id`.

### Phase 2 — Data integrity + routing cleanup (Week 2)

- [x]- Deploy and enforce atomic promotion RPC (staging → leads) and idempotency guarantees.
- [x]- Remove reliance on `CAMPAIGN_ID_PLACEHOLDER` by creating a real “Inbound Default Campaign” per tenant or mailbox→campaign mapping.

**Exit criteria:** no writes occur without a valid `campaign_id`; promotion cannot half-move history.

### Phase 3 — Approval workflow + minimal operator surface (Week 3)

- [x]- Implement the minimal approval loop that matches the safety model:
  - Draft queue
  - Approve/send
  - Reject (with reason)
  - Edit-before-send
- [x]- UI approach (fastest-first): extend the existing internal UI entrypoint (`int-frontend/app.py`) into a “Customer Beta Console”, or replace with a minimal web dashboard.

**Exit criteria:** customer can review drafts and explicitly approve sends; no auto-send bypasses approval.

### Phase 4 — Customer auth + tenant provisioning (Week 4)

- [x]- Add customer authentication (recommended: Supabase Auth to match Supabase persistence stack).
- [x]- Enforce tenant isolation end-to-end (tenant derived from auth context; not user input).
- [x]- Add basic RBAC roles (at minimum: admin vs viewer).

**Exit criteria:** a new tenant can onboard without manual DB edits; tenant A cannot read/write tenant B.

### Phase 5 — Public API gateway (Week 5)

- [x]- Add a customer-facing REST API (recommended: FastAPI) for:
  - campaign config
  - mailbox config
  - leads/conversations access
  - approval actions
  - ingestion webhook
- [x]- Add API keys + rate limiting for customer integrations.

**Exit criteria:** customers integrate without touching Redis directly; OpenAPI is published.

### Phase 6 — Billing + plan limits (Week 6)

- [x]- Integrate Stripe (or equivalent): checkout, subscription webhooks, cancel/renew/upgrade flows.
- [x]- Enforce plan limits at the API boundary (e.g., messages/day, leads/month, seats).

**Exit criteria:** you can charge + automatically gate usage.

### Phase 7 — Production deployability + operability (Weeks 6–7, in parallel)

- [x]- Complete production deployment assets (K8s/Helm/Terraform) per `deployment/IAC_SETUP_TODO.md`.
- [x]- Add basic operational tooling:
  - trace-by-`correlation_id`
  - alerting on DLQ growth
  - consumer health summaries

**Exit criteria:** one-command deploy to a real cloud environment; failures are triageable quickly.

---

## Modularity Principles (for Post-MVP Extensibility)

The MVP must be built to evolve. Apply these constraints now so post-MVP features don't require rewrites.

### 1. Keep the 3-tier boundary strict

- **Tier 1 (Manager):** routing + policy only—never generate content or call external services directly.
- **Tier 2 (Orchestrators):** workflow decomposition—never call other orchestrators directly; all cross-workflow coordination goes through Manager.
- **Tier 3 (Agents):** atomic execution—single responsibility, no orchestration logic.

Adding a new feature should be "add a new agent or orchestrator", not "patch the Manager".

### 2. Envelope-first communication

- Every task and result uses the typed envelope (`task_id`, `tenant_id`, `payload`, `metadata`, `correlation_id`).
- New fields go into `payload` or `metadata`; never break the envelope schema.
- This enables tracing, replay, and future event-sourcing without migration.

### 3. Adapter pattern for external services

- Wrap every external dependency (email provider, vector DB, LLM, billing, calendar) behind an abstract adapter interface.
- MVP can ship with one concrete adapter (e.g., Gmail, Supabase, OpenAI, Stripe); post-MVP adds alternatives (Outlook, Pinecone, Anthropic, Paddle) without touching orchestrators.

### 4. Feature flags over branching logic

- Use env-var flags (`ENABLE_<FEATURE>=1`) to gate new behaviors (e.g., `ENABLE_VECTOR_SEARCH`, `ENABLE_CALENDAR_BOOKING`).
- Default to off for new features; default to safe for safety-critical features (`OUTBOUND_APPROVAL_MODE=1`).

### 5. Tenant-scoped configuration

- Store per-tenant config (plan limits, feature flags, mailbox mappings, campaign defaults) in a `tenant_config` table or Redis hash—not hard-coded.
- MVP can start with env vars or a single JSON file per tenant; post-MVP migrates to DB-backed config without code changes.

### 6. Pluggable channels

- The Channel Sequencer already abstracts "send via X"; treat this as the extension point for SMS, LinkedIn, WhatsApp, etc.
- New channel = new adapter + new sequencer step type; existing orchestrators remain untouched.

### 7. API versioning from day one

- Prefix all customer-facing endpoints with `/api/v1/`.
- When breaking changes are required, stand up `/api/v2/` and deprecate v1 gracefully.

### 8. Observability as a first-class citizen

- Every agent emits structured logs with `tenant_id`, `correlation_id`, `task_id`.
- Metrics are labeled by tier, agent, and tenant.
- Tracing spans cover the full envelope lifecycle (ingress → result).
- This ensures post-MVP scale-up doesn't sacrifice debuggability.

---

### Phase 8 — Post-MVP (v1.1)

- [x]- Real vector search for RAG (semantic retrieval), if required by customer value.
- [x]- Audit orchestrator implementation (compliance trail), if required by customer procurement.
- [x]- Scheduler agent/calendar integrations, if “booking” is part of your initial promise.

### Critical path (what gates “sellable”)

1. Approval workflow + safe defaults
2. Auth + tenant isolation
3. Public API gateway
4. Billing
5. Production deployability + operability basics

### Decisions to lock early

- Primary inbox provider for MVP: Gmail API vs IMAP.
- Default send mode: draft-only vs controlled auto-send.
- UI strategy: Streamlit “Beta Console” vs Next.js dashboard.
- Pricing metric: per inbox, per seat, or per message volume.

---

## Open Questions (to lock MVP behavior)

- Which provider is the primary poller for MVP: Gmail API or IMAP?
- Do we auto-send by default for inbound replies, or only in explicit modes (e.g., `auto_send=true`)?
- Where should dedup state live long-term: Redis (fast) or Postgres/Supabase (auditable)?
