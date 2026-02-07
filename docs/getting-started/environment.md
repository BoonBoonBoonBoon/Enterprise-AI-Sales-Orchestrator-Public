# Environment Setup

Complete guide to configuring all environment variables required by the Agentic System.

## Quick Setup

1. Copy the example environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Edit `.env` and fill in your values (see sections below)

3. Validate your configuration:
   ```powershell
   & ".venv/Scripts/python.exe" -c "from config.settings import settings; print('Config OK')"
   ```

## Required Variables

### Supabase (Database)

| Variable                    | Required | Example                      | Description                              |
| --------------------------- | -------- | ---------------------------- | ---------------------------------------- |
| `SUPABASE_URL`              | ✅       | `https://abc123.supabase.co` | Your Supabase project URL                |
| `SUPABASE_ANON_KEY`         | ✅       | `eyJhbGciOiJIUzI1NiIs...`    | Supabase anonymous/public key            |
| `SUPABASE_JWT_SECRET`       | ✅       | `your-jwt-secret`            | JWT secret for signing custom tokens     |
| `SUPABASE_SERVICE_ROLE_KEY` | ⚠️       | `eyJhbGciOiJIUzI1NiIs...`    | Service role key (admin operations only) |

**Where to find:**

1. Go to [Supabase Dashboard](https://supabase.com/dashboard)
2. Select your project → Settings → API
3. Copy the URL and keys

### Redis

| Variable         | Required | Example                    | Description                      |
| ---------------- | -------- | -------------------------- | -------------------------------- |
| `REDIS_URL`      | ✅       | `redis://localhost:6379/0` | Redis connection URL             |
| `REDIS_PASSWORD` | ⚠️       | `your-redis-password`      | Redis password (if auth enabled) |

**Local development:**

```
REDIS_URL=redis://localhost:6379/0
```

**Docker:**

```
REDIS_URL=redis://redis:6379/0
```

### LLM Providers

| Variable            | Required | Example      | Description                                   |
| ------------------- | -------- | ------------ | --------------------------------------------- |
| `OPENAI_API_KEY`    | ✅\*     | `sk-...`     | OpenAI API key                                |
| `ANTHROPIC_API_KEY` | ⚠️       | `sk-ant-...` | Anthropic API key (alternative)               |
| `LLM_PROVIDER`      | ⚠️       | `openai`     | Which provider to use (`openai`, `anthropic`) |
| `LLM_MODEL`         | ⚠️       | `gpt-4o`     | Model name to use                             |

\*At least one LLM provider key is required.

### Tenant Configuration

| Variable                  | Required | Example        | Description                             |
| ------------------------- | -------- | -------------- | --------------------------------------- |
| `TENANT_ID`               | ✅       | `agentic-dev`  | Default tenant identifier               |
| `CAMPAIGN_ID_PLACEHOLDER` | ⚠️       | `9646f98a-...` | Fallback campaign UUID for orphan leads |

### Email (Gmail)

| Variable              | Required | Example                            | Description          |
| --------------------- | -------- | ---------------------------------- | -------------------- |
| `GMAIL_CLIENT_ID`     | ⚠️       | `123...apps.googleusercontent.com` | OAuth client ID      |
| `GMAIL_CLIENT_SECRET` | ⚠️       | `GOCSPX-...`                       | OAuth client secret  |
| `GMAIL_REFRESH_TOKEN` | ⚠️       | `1//0g...`                         | OAuth refresh token  |
| `GMAIL_SENDER_EMAIL`  | ⚠️       | `you@gmail.com`                    | Sender email address |

### Observability

| Variable                      | Required | Example                 | Description                                         |
| ----------------------------- | -------- | ----------------------- | --------------------------------------------------- |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | ⚠️       | `http://localhost:4317` | OpenTelemetry collector endpoint                    |
| `OTEL_SERVICE_NAME`           | ⚠️       | `agentic-system`        | Service name for traces                             |
| `DATADOG_API_KEY`             | ⚠️       | `dd-api-...`            | Datadog API key                                     |
| `LOG_LEVEL`                   | ⚠️       | `INFO`                  | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

## Environment File Template

```bash
# .env - Agentic System Configuration

# === REQUIRED ===

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_JWT_SECRET=your-jwt-secret

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM
OPENAI_API_KEY=sk-your-openai-key

# Tenant
TENANT_ID=agentic-dev

# === OPTIONAL ===

# Supabase (admin)
# SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# Redis auth
# REDIS_PASSWORD=your-redis-password

# Alternative LLM
# ANTHROPIC_API_KEY=sk-ant-your-key
# LLM_PROVIDER=openai
# LLM_MODEL=gpt-4o

# Campaign fallback
# CAMPAIGN_ID_PLACEHOLDER=9646f98a-e987-4a8c-b786-9b82ea985d38

# Email
# GMAIL_CLIENT_ID=your-client-id
# GMAIL_CLIENT_SECRET=your-client-secret
# GMAIL_REFRESH_TOKEN=your-refresh-token
# GMAIL_SENDER_EMAIL=you@gmail.com

# Observability
# OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
# OTEL_SERVICE_NAME=agentic-system
# LOG_LEVEL=INFO
```

## Validation

Test your configuration:

```powershell
# Check config loads
& ".venv/Scripts/python.exe" -c "from config.settings import settings; print(f'Tenant: {settings.TENANT_ID}')"

# Check Redis connection
& ".venv/Scripts/python.exe" -c "from services.redis.client import get_redis_client; r = get_redis_client(); print(f'Redis: {r.ping()}')"

# Check Supabase connection
& ".venv/Scripts/python.exe" -c "from services.persistence.supabase_adapter import SupabaseAdapter; a = SupabaseAdapter('agent_reader'); print('Supabase: OK')"
```

## Troubleshooting

### "SUPABASE_URL not set"

Ensure `.env` is in the project root and Python-dotenv is loading it:

```python
from dotenv import load_dotenv
load_dotenv()
```

### "Redis connection refused"

Start Redis:

```powershell
# Docker
docker run -d -p 6379:6379 redis:7-alpine

# Or use the task
# Ctrl+Shift+P → Tasks: Run Task → "Redis: Start"
```

### "Invalid API key" (OpenAI)

- Check the key starts with `sk-`
- Ensure no trailing whitespace
- Verify the key is active at [platform.openai.com](https://platform.openai.com/api-keys)

## Security Notes

1. **Never commit `.env`** — It's in `.gitignore` by default
2. **Use secrets manager in production** — See [Secrets Management](../guides/deploy/secrets.md)
3. **Rotate keys regularly** — Especially after team changes
4. **Use minimal permissions** — `agent_reader` for RAG, `agent_writer` for Persistence only
