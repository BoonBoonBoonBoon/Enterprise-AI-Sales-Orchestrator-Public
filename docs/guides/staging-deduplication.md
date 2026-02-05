# Staging Tables - Deduplication & Schema Guide

## Overview

The staging tables (`staging_leads`, `staging_conversations`, `staging_messages`) hold pre-qualification data for inbound leads before they are promoted to the main `leads`/`conversations`/`messages` tables.

This document explains:

1. How deduplication works to prevent duplicates
2. When new records are created vs updated
3. Schema field descriptions

It also clarifies:

4. When inbound data goes to staging vs live tables
5. How promotion from staging → leads works

---

## Routing: staging vs live tables

Inbound email events are stored in one of two places:

- **Staging (`staging_*`)**: Default intake path for new/unknown leads before qualification.
- **Live (`leads`, `conversations`, `messages`)**: Used when the lead is already qualified, or when the inbound event is **fast-tracked**.

Qualification thresholds and fast-track rules are defined in `config/manager/qualification.yaml`:

- `thresholds.auto_promote`: score ≥ 70 → promote staging → `leads`
- `thresholds.fast_track`: score ≥ 85 → skip staging entirely and write directly to `leads`
- `thresholds.disqualify`: score ≤ 20 → disqualify (archive staging lead)

These thresholds are applied by the LeadsOrchestrator scoring pipeline (hybrid rules-first, optional LLM fallback for ambiguous cases).

## Deduplication Rules

### staging_leads

**Unique Constraint:** `(client_id, email)` where `archived_at IS NULL`

| Scenario                              | Action                                       |
| ------------------------------------- | -------------------------------------------- |
| Same email, same client, not archived | **UPDATE** existing lead                     |
| Same email, different client          | **CREATE** new lead (multi-tenant isolation) |
| Same email, but previous was archived | **CREATE** new lead (re-engagement)          |
| New email                             | **CREATE** new lead                          |

**Key Fields for Matching:**

- `client_id` - Auto-injected by PersistenceAgent
- `email` - From the inbound email sender

**Example:** If `john@acme.com` contacts us 3 times, we have 1 staging_lead with 3 messages across potentially multiple conversations.

---

### staging_conversations

**Unique Constraints:**

1. `(staging_lead_id, thread_id)` where `thread_id IS NOT NULL AND archived_at IS NULL`
2. `(staging_lead_id, subject)` where `subject IS NOT NULL AND archived_at IS NULL`

| Scenario                               | Action                           |
| -------------------------------------- | -------------------------------- |
| Same lead, same thread_id              | **UPDATE** existing conversation |
| Same lead, same subject (no thread_id) | **UPDATE** existing conversation |
| Same lead, new subject                 | **CREATE** new conversation      |
| Same lead, new thread_id               | **CREATE** new conversation      |

**What qualifies as a NEW conversation?**

1. ✅ A new `thread_id` from email headers (definitive new thread)
2. ✅ A new `subject` line from the same lead
3. ✅ First message from a brand new lead

**What DOES NOT create a new conversation?**

1. ❌ Reply to existing thread (same thread_id)
2. ❌ Reply with same subject (when no thread_id available)
3. ❌ Re: or Fwd: versions of same subject (normalized)

---

### staging_messages

**Unique Constraint:** `(staging_conversation_id, message_id)` where `message_id IS NOT NULL`

| Scenario                           | Action                    |
| ---------------------------------- | ------------------------- |
| Same conversation, same message_id | **SKIP** (already stored) |
| Same conversation, new message_id  | **CREATE** new message    |

**The `message_id`:**

- From email headers (e.g., `<unique-id@mail.example.com>`)
- Guaranteed unique per email
- If missing, a deterministic hash is generated from sender + content

---

## Schema Reference

### staging_leads

| Column                         | Type        | Description                                                         |
| ------------------------------ | ----------- | ------------------------------------------------------------------- |
| `id`                           | UUID        | Primary key                                                         |
| `client_id`                    | UUID        | **FK to clients** - tenant isolation                                |
| `campaign_id`                  | UUID        | FK to campaigns (placeholder if unknown)                            |
| `email`                        | TEXT        | Lead's email address - **primary dedup key**                        |
| `first_name`, `last_name`      | TEXT        | Contact name (may be enriched later)                                |
| `company_name`, `job_title`    | TEXT        | Professional info                                                   |
| `phone_number`, `linkedin_url` | TEXT        | Additional contact methods                                          |
| `source`                       | TEXT        | How lead was acquired: `inbound_email`, `import`, `manual`          |
| `enrichment_status`            | TEXT        | `pending` → `completed` or `failed`                                 |
| `qualification_status`         | TEXT        | `pending` → `qualified` / `nurture` / `disqualified` / `fast_track` |
| `promotion_ready`              | BOOL        | Ready to move to `leads` table                                      |
| `archived_at`                  | TIMESTAMPTZ | Soft delete / promotion marker                                      |

### staging_conversations

| Column             | Type         | Description                                               |
| ------------------ | ------------ | --------------------------------------------------------- |
| `id`               | UUID         | Primary key                                               |
| `staging_lead_id`  | UUID         | **FK to staging_leads**                                   |
| `thread_id`        | TEXT         | Email thread ID from headers (primary dedup when present) |
| `subject`          | TEXT         | Email subject line (secondary dedup when no thread_id)    |
| `channel`          | TEXT         | `email`, `linkedin`, `phone`, etc.                        |
| `status`           | VARCHAR(50)  | `open`, `closed`, `pending_reply`, `needs_attention`      |
| `message_count`    | INT          | Auto-updated count of messages                            |
| `first_message_at` | TIMESTAMPTZ  | When first message was received                           |
| `last_message_at`  | TIMESTAMPTZ  | When last message was received (for sorting)              |
| `last_sender`      | VARCHAR(255) | Who sent the last message                                 |
| `summary`          | TEXT         | AI-generated or manual conversation summary               |
| `metadata`         | JSONB        | Additional data (labels, tags, etc.)                      |
| `archived_at`      | TIMESTAMPTZ  | Soft delete marker                                        |

### staging_messages

| Column                    | Type         | Description                                             |
| ------------------------- | ------------ | ------------------------------------------------------- |
| `id`                      | UUID         | Primary key                                             |
| `staging_conversation_id` | UUID         | **FK to staging_conversations**                         |
| `message_id`              | TEXT         | Email message ID from headers (dedup key)               |
| `sender`                  | VARCHAR(255) | Email sender address                                    |
| `receiver`                | VARCHAR(255) | Email recipient address                                 |
| `content`                 | TEXT         | Full message body                                       |
| `direction`               | VARCHAR(20)  | `inbound` (from lead) or `outbound` (our reply)         |
| `email_type`              | VARCHAR(50)  | `inquiry`, `reply`, `follow_up`, `auto_reply`, `bounce` |
| `sent_at`                 | TIMESTAMPTZ  | When the email was sent                                 |
| `metadata`                | JSONB        | Headers, attachments info, etc.                         |
| `archived_at`             | TIMESTAMPTZ  | Soft delete marker                                      |

---

## Trigger: Auto-Update Conversation Stats

When a new message is inserted into `staging_messages`, a trigger automatically:

1. Increments `message_count`
2. Sets `first_message_at` if not set
3. Updates `last_message_at`
4. Updates `last_sender`

This keeps conversation metadata accurate without extra queries.

---

## Example Flow

**Scenario:** `john@acme.com` sends 3 emails over 2 days:

1. **Email 1:** Subject "Question about pricing"
   - Creates 1 `staging_lead` (id: lead-1)
   - Creates 1 `staging_conversation` (id: conv-1, subject: "Question about pricing")
   - Creates 1 `staging_message` (id: msg-1)

2. **Email 2:** Subject "Re: Question about pricing"
   - **Updates** existing `staging_lead` (lead-1)
   - **Updates** existing `staging_conversation` (conv-1) - same subject base
   - Creates 1 `staging_message` (id: msg-2)

3. **Email 3:** Subject "New partnership opportunity"
   - **Updates** existing `staging_lead` (lead-1) - same email
   - Creates **NEW** `staging_conversation` (id: conv-2) - different subject
   - Creates 1 `staging_message` (id: msg-3)

**Result:**

- 1 staging_lead
- 2 staging_conversations
- 3 staging_messages

---

## Migration

Apply the migration to enable these features:

```sql
-- Run this in Supabase SQL editor or via CLI
\i supabase/migrations/20260113_staging_dedup_and_schema.sql
```

Or via Supabase CLI:

```bash
supabase db push
```

---

## Promotion: staging → leads

Promotion is typically triggered by `intent: qualify_lead` (enqueued by Manager after enrichment or manual review).
It can also be triggered immediately after storing a high-intent inbound email (when scoring indicates `promote=True`).

High-level flow:

1. LeadsOrchestrator fetches the staging lead and messages via RAG (deep context)
2. LeadsOrchestrator scores the lead (0–100)
3. If qualified (score ≥ `thresholds.auto_promote`), LeadsOrchestrator enqueues a Persistence operation:
   - `operation: promote_staging_lead`
   - `staging_lead_id: <uuid>`

Promotion behavior:

- Creates a row in `leads`
- Replays staging conversations/messages into `conversations`/`messages`
- Soft-archives staging rows (`archived_at`) to preserve audit history (no hard deletes)

!!! important

Do not hard-delete staging rows as part of inbound handling. If your schema uses cascading foreign keys, a delete of `staging_leads` can remove `staging_conversations`/`staging_messages` and make history appear to “disappear”.

The system uses `archived_at` updates to retain the thread for audit and debugging.

---

## Autonomous readiness (when to promote)

Staging leads are promoted automatically by scoring them and comparing the score to thresholds in `config/manager/qualification.yaml`.

### Scoring inputs

The scorer evaluates a staging lead using:

- **Conversation signals** (e.g., asked a question, mentioned pricing/budget, mentioned timeline, requested meeting/demo, multiple messages)
- **Email classification** (e.g., business inquiry vs newsletter/spam/bounce)
- **Profile/enrichment signals** (e.g., company, title, known domain vs freemail)
- **Negative signals** (unsubscribe, not interested, wrong contact)

### Decision thresholds

- If score ≥ `thresholds.auto_promote` (default 70): **promote** staging → `leads`
- If score ≤ `thresholds.disqualify` (default 20): **disqualify** (archive staging lead)
- Otherwise: keep in staging and re-evaluate on new info

### How promotion is triggered

Typical triggers for enqueuing `intent: qualify_lead`:

- **Event-driven:** after storing a new inbound staging message (new evidence)
- **Scheduled sweep:** periodically re-score staging leads that have changed recently (new messages or enrichment)

If you want a conservative backstop for leads that appear “stuck” forever, use the stale-lead sweeper script (below).

In both cases, the `qualify_lead` task is handled by LeadsOrchestrator, which will enqueue a Persistence promotion operation (`operation: promote_staging_lead`) when the lead is ready.

When promotion is triggered directly from inbound persistence, LeadsOrchestrator enqueues the same Persistence operation immediately after the inbound compound write.

!!! note

The `leads` table may have required NOT NULL fields (dates/flags). The PersistenceAgent promotion tool injects safe defaults to avoid promotion failures due to missing columns.

---

## Maintenance: Sweep stale staging leads

For operational hygiene, this repo includes a standalone script to find (and optionally archive) staging leads that have remained unarchived and stuck in conservative pending states past a threshold.

- Script: `scripts/maintenance/sweep_stale_staging_leads.py`

**Default filter (intentionally conservative):**

- `archived_at IS NULL`
- `enrichment_status == "pending"`
- `qualification_status == "pending"`
- `promotion_ready == false`
- `created_at < now - N days`

**Dry-run (default):**

```powershell
python -m scripts.maintenance.sweep_stale_staging_leads --days 14
```

**Apply updates:**

```powershell
python -m scripts.maintenance.sweep_stale_staging_leads --days 14 --apply
```

**Env vars (optional):**

- `STAGING_STALE_DAYS` (default `14`)
- `STAGING_SWEEP_LIMIT` (default `500`)

**Supabase credentials:**

- Requires `SUPABASE_URL` and a service key (`SUPABASE_SERVICE_KEY` or `SUPABASE_KEY`).

When applying, the script archives by setting:

- `archived_at = now`
- `enrichment_status = "failed"`
- `qualification_status = "nurture"`
