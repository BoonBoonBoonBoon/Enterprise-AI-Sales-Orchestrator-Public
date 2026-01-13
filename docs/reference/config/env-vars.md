# Environment Variables

Complete reference for all environment variables used by the Agentic System.

## Quick Reference

| Variable              | Required | Default                    | Category  |
| --------------------- | -------- | -------------------------- | --------- |
| `SUPABASE_URL`        | âœ…       | â€”                          | Database  |
| `SUPABASE_ANON_KEY`   | âœ…       | â€”                          | Database  |
| `SUPABASE_JWT_SECRET` | âœ…       | â€”                          | Database  |
| `REDIS_URL`           | âœ…       | `redis://localhost:6379/0` | Messaging |
| `OPENAI_API_KEY`      | âœ…\*     | â€”                          | LLM       |
| `TENANT_ID`           | âœ…       | `agentic-dev`              | Core      |

\*At least one LLM provider key required.

---

## Database (Supabase)

### SUPABASE_URL

- **Required:** âœ…
- **Format:** `https://{project-id}.supabase.co`
- **Description:** Your Supabase project URL
- **Where to find:** Supabase Dashboard â†’ Settings â†’ API

### SUPABASE_ANON_KEY

- **Required:** âœ…
- **Format:** JWT string starting with `eyJ`
- **Description:** Anonymous/public API key for client-side access
- **Where to find:** Supabase Dashboard â†’ Settings â†’ API â†’ `anon` `public`

### SUPABASE_JWT_SECRET

- **Required:** âœ…
- **Format:** String (typically 32+ characters)
- **Description:** Secret for signing custom JWTs (role-based auth)
- **Where to find:** Supabase Dashboard â†’ Settings â†’ API â†’ JWT Secret

### SUPABASE_SERVICE_ROLE_KEY

- **Required:** âš ï¸ (admin operations only)
- **Format:** JWT string starting with `eyJ`
- **Description:** Full admin access key (bypasses RLS)
- **Security:** Never expose client-side

---

## Messaging (Redis)

### REDIS_URL

- **Required:** âœ…
- **Default:** `redis://localhost:6379/0`
- **Format:** `redis://<REDACTED_REDIS_URL>
- **Examples:**
  ```
  redis://localhost:6379/0
  redis://<REDACTED_REDIS_URL>  # Docker
  redis://<REDACTED_REDIS_URL>
  ```

### REDIS_PASSWORD

- **Required:** âš ï¸ (if Redis auth enabled)
- **Format:** String
- **Description:** Redis AUTH password

---

## LLM Providers

### OPENAI_API_KEY

- **Required:** âœ…\*
- **Format:** `sk-...` (starts with `sk-`)
- **Description:** OpenAI API key
- **Where to find:** [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

### ANTHROPIC_API_KEY

- **Required:** âš ï¸ (alternative to OpenAI)
- **Format:** `sk-ant-...`
- **Description:** Anthropic Claude API key

### LLM_PROVIDER

- **Required:** âš ï¸
- **Default:** `openai`
- **Values:** `openai`, `anthropic`
- **Description:** Which LLM provider to use

### LLM_MODEL

- **Required:** âš ï¸
- **Default:** `gpt-4o`
- **Examples:** `gpt-4o`, `gpt-4-turbo`, `claude-3-opus-20240229`
- **Description:** Specific model to use

### LLM_TEMPERATURE

- **Required:** âš ï¸
- **Default:** `0.0`
- **Range:** `0.0` to `2.0`
- **Description:** Randomness in LLM responses

---

## Core Configuration

### TENANT_ID

- **Required:** âœ…
- **Default:** `agentic-dev`
- **Format:** Alphanumeric with hyphens
- **Description:** Default tenant identifier for stream prefixes

### CAMPAIGN_ID_PLACEHOLDER

- **Required:** âš ï¸
- **Default:** `9646f98a-e987-4a8c-b786-9b82ea985d38`
- **Format:** UUID
- **Description:** Fallback campaign ID for orphan leads

---

## Email (Gmail)

### GMAIL_CLIENT_ID

- **Required:** âš ï¸ (for email features)
- **Format:** `{number}-{hash}.apps.googleusercontent.com`
- **Description:** Google OAuth client ID

### GMAIL_CLIENT_SECRET

- **Required:** âš ï¸
- **Format:** `GOCSPX-...`
- **Description:** Google OAuth client secret

### GMAIL_REFRESH_TOKEN

- **Required:** âš ï¸
- **Description:** OAuth refresh token for offline access

### GMAIL_SENDER_EMAIL

- **Required:** âš ï¸
- **Format:** Email address
- **Description:** Sender email address

---

## Observability

### LOG_LEVEL

- **Required:** âš ï¸
- **Default:** `INFO`
- **Values:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Description:** Python logging level

### OTEL_EXPORTER_OTLP_ENDPOINT

- **Required:** âš ï¸
- **Default:** `http://localhost:4317`
- **Description:** OpenTelemetry collector endpoint

### OTEL_SERVICE_NAME

- **Required:** âš ï¸
- **Default:** `agentic-system`
- **Description:** Service name for traces

### DATADOG_API_KEY

- **Required:** âš ï¸
- **Description:** Datadog API key for metrics/traces

### DATADOG_APP_KEY

- **Required:** âš ï¸
- **Description:** Datadog application key

---

## Vector Database

### CHROMA_HOST

- **Required:** âš ï¸
- **Default:** `localhost`
- **Description:** ChromaDB host

### CHROMA_PORT

- **Required:** âš ï¸
- **Default:** `8000`
- **Description:** ChromaDB port

### QDRANT_URL

- **Required:** âš ï¸
- **Format:** `http://host:port`
- **Description:** Qdrant vector DB URL

### QDRANT_API_KEY

- **Required:** âš ï¸
- **Description:** Qdrant API key (if auth enabled)

---

## External APIs

### CRUNCHBASE_API_KEY

- **Required:** âš ï¸
- **Description:** Crunchbase API key for company enrichment

### LINKEDIN_CLIENT_ID

- **Required:** âš ï¸
- **Description:** LinkedIn OAuth client ID

### LINKEDIN_CLIENT_SECRET

- **Required:** âš ï¸
- **Description:** LinkedIn OAuth client secret

---

## Development

### DEBUG

- **Required:** âš ï¸
- **Default:** `false`
- **Values:** `true`, `false`
- **Description:** Enable debug mode

### PYTHONIOENCODING

- **Required:** âš ï¸
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
# ANTHROPIC_API_KEY=sk-ant-...
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

- [Environment Setup](../../getting-started/environment.md) â€” Setup guide
- [Secrets Management](../../guides/deploy/secrets.md) â€” Production secrets
- [Settings](settings.md) â€” How settings.py loads config


