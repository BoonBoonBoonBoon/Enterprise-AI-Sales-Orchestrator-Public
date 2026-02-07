# Environment Variables

Complete reference for all environment variables used by the Agentic System.

## Quick Reference

| Variable               | Required | Default                    | Category  |
| ---------------------- | -------- | -------------------------- | --------- |
| `SUPABASE_URL`         | ✅       | —                          | Database  |
| `SUPABASE_ANON_KEY`    | ✅       | —                          | Database  |
| `SUPABASE_JWT_SECRET`  | ✅       | —                          | Database  |
| `SUPABASE_SERVICE_KEY` | ⚠️       | —                          | Database  |
| `REDIS_URL`            | ✅       | `redis://localhost:6379/0` | Messaging |
| `OPENAI_API_KEY`       | ✅\*     | —                          | LLM       |
| `TENANT_ID`            | ✅       | `agentic-dev`              | Core      |

\*At least one LLM provider key required.

---

## Database (Supabase)

### SUPABASE_URL

- **Required:** ✅
- **Format:** `https://{project-id}.supabase.co`
- **Description:** Your Supabase project URL
- **Where to find:** Supabase Dashboard → Settings → API

### SUPABASE_ANON_KEY

- **Required:** ✅
- **Format:** JWT string starting with `eyJ`
- **Description:** Anonymous/public API key for client-side access
- **Where to find:** Supabase Dashboard → Settings → API → `anon` `public`

### SUPABASE_JWT_SECRET

- **Required:** ✅
- **Format:** String (typically 32+ characters)
- **Description:** Secret for signing custom JWTs (role-based auth)
- **Where to find:** Supabase Dashboard → Settings → API → JWT Secret

### SUPABASE_SERVICE_ROLE_KEY

- **Required:** ⚠️ (admin operations only)
- **Format:** JWT string starting with `eyJ`
- **Description:** Full admin access key (bypasses RLS)
- **Security:** Never expose client-side

### SUPABASE_SERVICE_KEY

- **Required:** ⚠️ (write paths / maintenance scripts)
- **Format:** JWT string starting with `eyJ`
- **Description:** Service role key used by backend components and scripts that must write.

This repo uses `SUPABASE_SERVICE_KEY` (or `SUPABASE_KEY`) in several components/scripts. If you already have `SUPABASE_SERVICE_ROLE_KEY`, set `SUPABASE_SERVICE_KEY` to the same value.

### SUPABASE_KEY

- **Required:** ⚠️ (legacy fallback)
- **Format:** JWT string starting with `eyJ`
- **Description:** Legacy fallback for service role key in older scripts.

### SUPABASE_REST_RETRIES

- **Required:** ❌
- **Default:** `3`
- **Format:** Integer
- **Description:** Number of retry attempts for Supabase REST fallback calls on transient errors (e.g., 429, 5xx).

### SUPABASE_REST_BACKOFF

- **Required:** ❌
- **Default:** `0.5`
- **Format:** Float (seconds)
- **Description:** Backoff factor used by REST retries (exponential backoff).

### SUPABASE_REST_TIMEOUT_S

- **Required:** ❌
- **Default:** `15`
- **Format:** Float (seconds)
- **Description:** Default timeout for Supabase REST fallback HTTP requests.

### SUPABASE_REST_RPC_TIMEOUT_S

- **Required:** ❌
- **Default:** `15`
- **Format:** Float (seconds)
- **Description:** Timeout for Supabase RPC REST calls. If unset, falls back to `SUPABASE_REST_TIMEOUT_S`.

---

## Messaging (Redis)

### REDIS_URL

- **Required:** ✅
- **Default:** `redis://localhost:6379/0`
- **Format:** `redis://[user:password@]host:port/db`
- **Examples:**
  ```
  redis://localhost:6379/0
  redis://redis:6379/0  # Docker
  redis://:mypassword@redis.example.com:6379/0
  ```

### REDIS_PASSWORD

- **Required:** ⚠️ (if Redis auth enabled)
- **Format:** String
- **Description:** Redis AUTH password

---

## LLM Providers

### OPENAI_API_KEY

- **Required:** ✅\*
- **Format:** `sk-...` (starts with `sk-`)
- **Description:** OpenAI API key
- **Where to find:** [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

### ANTHROPIC_API_KEY

- **Required:** ⚠️ (alternative to OpenAI)
- **Format:** `sk-ant-...`
- **Description:** Anthropic Claude API key

### LLM_PROVIDER

- **Required:** ⚠️
- **Default:** `openai`
- **Values:** `openai`, `anthropic`
- **Description:** Which LLM provider to use

### LLM_MODEL

- **Required:** ⚠️
- **Default:** `gpt-4o`
- **Examples:** `gpt-4o`, `gpt-4-turbo`, `claude-3-opus-20240229`
- **Description:** Specific model to use

### LLM_TEMPERATURE

- **Required:** ⚠️
- **Default:** `0.0`
- **Range:** `0.0` to `2.0`
- **Description:** Randomness in LLM responses

---

## Core Configuration

### TENANT_ID

- **Required:** ✅
- **Default:** `agentic-dev`
- **Format:** Alphanumeric with hyphens
- **Description:** Default tenant identifier for stream prefixes

### CAMPAIGN_ID_PLACEHOLDER

- **Required:** ⚠️
- **Default:** `9646f98a-e987-4a8c-b786-9b82ea985d38`
- **Format:** UUID
- **Description:** Fallback campaign ID for orphan leads

---

## Maintenance Scripts

These variables are used by standalone maintenance scripts (no Redis required).

### STAGING_STALE_DAYS

- **Required:** ❌
- **Default:** `14`
- **Format:** Integer days
- **Description:** Age threshold used by `scripts/maintenance/sweep_stale_staging_leads.py`.

### STAGING_SWEEP_LIMIT

- **Required:** ❌
- **Default:** `500`
- **Format:** Integer
- **Description:** Max rows fetched/processed per run by the sweeper.

---

### MAILBOX_CAMPAIGN_ID_MAP

- **Required:** ❌
- **Default:** unset
- **Format:** JSON object mapping mailbox email → campaign UUID
- **Description:** Maps inbound/outbound mailbox addresses to a campaign id for routing when `campaign_id` is missing.

**Example:**

```json
{
  "inbox@agency.com": "11111111-1111-1111-1111-111111111111",
  "sales@agency.com": "22222222-2222-2222-2222-222222222222"
}
```

When set, PersistenceAgent will infer `campaign_id` for `staging_leads`/`leads` during compound writes by scanning message metadata (`metadata.to` for inbound, `metadata.from` for outbound).

---

## Leads Orchestrator

### LEADS_WAIT_FOR_RAG_CONTEXT

- **Required:** ⚠️
- **Default:** `1`
- **Values:** `1|0`, `true|false`
- **Description:** If enabled, Leads will synchronously wait for a RAG reply-context result before building `reply_packet`.

### LEADS_RAG_CONTEXT_TIMEOUT_S

- **Required:** ⚠️
- **Default:** `20`
- **Format:** Integer seconds
- **Description:** Timeout for waiting on `{tenant}:agents:rag:results` when building reply context.

---

## Scheduling (SchedulerAgent)

### SCHEDULER_WEBHOOK_URL

- **Required:** ❌
- **Default:** unset
- **Description:** Fallback webhook endpoint for calendar scheduling requests (used if provider-specific URL is not set).

### SCHEDULER_GOOGLE_WEBHOOK_URL

- **Required:** ❌
- **Default:** unset
- **Description:** Provider-specific webhook for Google Calendar scheduling.

### SCHEDULER_OUTLOOK_WEBHOOK_URL

- **Required:** ❌
- **Default:** unset
- **Description:** Provider-specific webhook for Outlook scheduling.

### SCHEDULER_ICAL_WEBHOOK_URL

- **Required:** ❌
- **Default:** unset
- **Description:** Optional webhook for generating/store iCal events (if not set, iCal is generated locally).

### SCHEDULER_WEBHOOK_TIMEOUT_S

- **Required:** ❌
- **Default:** `15`
- **Description:** HTTP timeout for scheduler provider webhooks.

---

## Channel Dispatch (ChannelSequencerAgent)

### CHANNEL_DISPATCH_WEBHOOK_URL

- **Required:** ❌
- **Default:** unset
- **Description:** Fallback webhook used for non-email channels.

### CHANNEL_DISPATCH_SMS_WEBHOOK_URL

- **Required:** ❌
- **Default:** unset
- **Description:** Provider webhook for SMS dispatch.

### CHANNEL_DISPATCH_WHATSAPP_WEBHOOK_URL

- **Required:** ❌
- **Default:** unset
- **Description:** Provider webhook for WhatsApp dispatch.

### CHANNEL_DISPATCH_LINKEDIN_WEBHOOK_URL

- **Required:** ❌
- **Default:** unset
- **Description:** Provider webhook for LinkedIn dispatch.

### CHANNEL_DISPATCH_VOICE_WEBHOOK_URL

- **Required:** ❌
- **Default:** unset
- **Description:** Provider webhook for voice dispatch.

### CHANNEL_DISPATCH_TIMEOUT_S

- **Required:** ❌
- **Default:** `15`
- **Description:** HTTP timeout for channel dispatch webhooks.

---

## Email + Inbox Ingestion

This system supports:

- **Sending** via Gmail SMTP (App Password)
- **Inbound ingestion** via Gmail API (OAuth) or IMAP poller, plus FastAPI webhook backup

### GMAIL_SENDER_EMAIL

- **Required:** ⚠️ (for sending)
- **Format:** Email address
- **Description:** Sender email address for SMTP sending

### GMAIL_APP_PASSWORD

- **Required:** ⚠️ (for sending)
- **Format:** App password (spaces allowed)
- **Description:** Gmail App Password for SMTP auth

### GMAIL_READ_CREDENTIALS_PATH

- **Required:** ⚠️ (for Gmail inbox polling)
- **Format:** File path
- **Description:** Path to Google OAuth client secrets JSON (`credentials.json`) used by Gmail API reader

### GMAIL_TOKEN_PATH

- **Required:** ⚠️ (for Gmail inbox polling)
- **Default:** `gmail_token.json`
- **Format:** File path
- **Description:** Where OAuth token is stored after first consent

### GMAIL_INBOX_USER

- **Required:** ❌
- **Default:** `me`
- **Description:** Gmail userId (usually `me`). Used by inbox poller.

### INBOX_PROVIDER

- **Required:** ❌
- **Default:** `gmail`
- **Values:** `gmail|imap`
- **Description:** Provider used by `services.email.inbox_poller`

### INBOX_POLL_INTERVAL_S

- **Required:** ❌
- **Default:** `60`
- **Format:** Integer seconds
- **Description:** Polling interval for inbox monitor

### INBOX_DEDUP_TTL_SECONDS

- **Required:** ❌
- **Default:** `86400`
- **Format:** Integer seconds
- **Description:** Redis dedup TTL for processed inbound message ids

### INBOX_PRE_FILTER_ENABLED

- **Required:** ❌
- **Default:** `1`
- **Values:** `1|0` (or `true|false`)
- **Description:** Enables Tier-0 header-based pre-filtering in `services.email.inbox_poller`

### INBOX_PRE_FILTER_SKIP_CATEGORIES

- **Required:** ❌
- **Default:** `bounce,marketing,newsletter`
- **Format:** Comma-separated categories
- **Description:** Categories that are skipped entirely (not published to Manager) when confidence is above `INBOX_PRE_FILTER_SKIP_CONFIDENCE`

### INBOX_PRE_FILTER_SKIP_CONFIDENCE

- **Required:** ❌
- **Default:** `0.8`
- **Format:** Float (0.0–1.0)
- **Description:** Minimum confidence required to skip publishing based on pre-filter category

### CLASSIFIER_LLM_ENABLED

- **Required:** ❌
- **Default:** `0`
- **Values:** `1|0` (or `true|false`)
- **Description:** Enables optional LLM fallback inside the Tier-3 Classifier Agent for low-confidence cases

### IMAP_HOST / IMAP_USERNAME / IMAP_PASSWORD

- **Required:** ⚠️ (only if `INBOX_PROVIDER=imap`)
- **Description:** IMAP connection settings

### IMAP_MAILBOX

- **Required:** ❌
- **Default:** `INBOX`
- **Description:** IMAP mailbox to poll

### INBOX_WEBHOOK_SECRET

- **Required:** ❌
- **Description:** Optional shared secret validated via `X-Webhook-Secret` header by webhook receiver

### INBOX_WEBHOOK_HOST / INBOX_WEBHOOK_PORT

- **Required:** ❌
- **Defaults:** `0.0.0.0` / `8080`
- **Description:** Bind host/port for `services.email.webhook_receiver`

---

## Outbound Sending Safety (Channel Sequencer)

These flags control MVP-safe outbound execution inside the Tier-3 Channel Sequencer Agent.

### OUTBOUND_APPROVAL_MODE

- **Required:** ❌
- **Default:** `0`
- **Values:** `1|0` (or `true|false`)
- **Description:** If enabled, outbound steps are returned as `draft` (no send) with reason `approval_required`.

### OUTBOUND_MAX_PER_HOUR

- **Required:** ❌
- **Default:** unset (no limit)
- **Format:** Integer
- **Description:** Max outbound sends per tenant per hour. Requires `REDIS_URL`.

### OUTBOUND_MAX_NEW_THREADS_PER_DAY

- **Required:** ❌
- **Default:** unset (no limit)
- **Format:** Integer
- **Description:** Max new outbound threads per tenant per day. “New thread” applies when there is no known thread/conversation id. Requires `REDIS_URL`.

### OUTBOUND_HARD_STOP_KEYWORDS

- **Required:** ❌
- **Default:** unset
- **Format:** Comma-separated keywords
- **Description:** If set, the Channel Sequencer can scan recent inbound snippets and block sending when any keyword is present.

---

### Deprecated / Legacy Gmail OAuth Vars

Older docs referenced `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, and `GMAIL_REFRESH_TOKEN`.
Current implementation uses `GMAIL_READ_CREDENTIALS_PATH` + `GMAIL_TOKEN_PATH` (OAuth consent flow).

---

## Observability

### LOG_LEVEL

- **Required:** ⚠️
- **Default:** `INFO`
- **Values:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Description:** Python logging level

### OTEL_EXPORTER_OTLP_ENDPOINT

- **Required:** ⚠️
- **Default:** `http://localhost:4317`
- **Description:** OpenTelemetry collector endpoint

### OTEL_SERVICE_NAME

- **Required:** ⚠️
- **Default:** `agentic-system`
- **Description:** Service name for traces

### DATADOG_API_KEY

- **Required:** ⚠️
- **Description:** Datadog API key for metrics/traces

### DATADOG_APP_KEY

- **Required:** ⚠️
- **Description:** Datadog application key

---

## Vector Database

### CHROMA_HOST

- **Required:** ⚠️
- **Default:** `localhost`
- **Description:** ChromaDB host

### CHROMA_PORT

- **Required:** ⚠️
- **Default:** `8000`
- **Description:** ChromaDB port

### QDRANT_URL

- **Required:** ⚠️
- **Format:** `http://host:port`
- **Description:** Qdrant vector DB URL

### QDRANT_API_KEY

- **Required:** ⚠️
- **Description:** Qdrant API key (if auth enabled)

---

## External APIs

### CRUNCHBASE_API_KEY

- **Required:** ⚠️
- **Description:** Crunchbase API key for company enrichment

### LINKEDIN_CLIENT_ID

- **Required:** ⚠️
- **Description:** LinkedIn OAuth client ID

### LINKEDIN_CLIENT_SECRET

- **Required:** ⚠️
- **Description:** LinkedIn OAuth client secret

---

## Development

### DEBUG

- **Required:** ⚠️
- **Default:** `false`
- **Values:** `true`, `false`
- **Description:** Enable debug mode

### PYTHONIOENCODING

- **Required:** ⚠️
- **Default:** `utf-8`
- **Description:** Python I/O encoding (prevents Unicode errors)

---

## Example .env File

```bash
# === REQUIRED ===

# Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_JWT_SECRET=your-jwt-secret-here

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM
OPENAI_API_KEY=sk-your-openai-api-key

# Core
TENANT_ID=agentic-dev

# === OPTIONAL ===

# Alternative LLM
# ANTHROPIC_API_KEY=sk-ant-your-key
# LLM_PROVIDER=openai
# LLM_MODEL=gpt-4o

# Logging
LOG_LEVEL=INFO

# Email (enable for outreach)
# GMAIL_CLIENT_ID=...
# GMAIL_CLIENT_SECRET=...
# GMAIL_REFRESH_TOKEN=...
# GMAIL_SENDER_EMAIL=...

# Observability
# OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
# DATADOG_API_KEY=...
```

---

## Validation

Test your configuration:

```powershell
& ".venv/Scripts/python.exe" -c "
from config.settings import settings
print(f'Tenant: {settings.TENANT_ID}')
print(f'Supabase: {settings.SUPABASE_URL[:30]}...')
print(f'Redis: {settings.REDIS_URL}')
print(f'LLM: {settings.LLM_PROVIDER} / {settings.LLM_MODEL}')
"
```

## Related

- [Environment Setup](../../getting-started/environment.md) — Setup guide
- [Secrets Management](../../guides/deploy/secrets.md) — Production secrets
- [Settings](settings.md) — How settings.py loads config
