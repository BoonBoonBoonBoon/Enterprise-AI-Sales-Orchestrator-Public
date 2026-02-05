# Settings Reference

This reference documents the `config/settings.py` module and application configuration.

## Overview

Settings are loaded from environment variables with fallbacks to defaults.

```python
import config.settings as settings

print(settings.SUPABASE_URL)
print(settings.INBOX_PROVIDER)
```

## Implementation

### Location

```
config/settings.py
```

### Implementation

`config/settings.py` currently exposes module-level configuration values loaded via `os.getenv()`.

Key exports include:

- `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_ANON_KEY`
- `OPENAI_API_KEY`
- Inbox/email ingestion: `INBOX_PROVIDER`, `INBOX_POLL_INTERVAL_S`, `GMAIL_READ_CREDENTIALS_PATH`, `IMAP_HOST`, etc.

There is also a `validate_keys()` helper to check required credentials.

## Configuration Categories

### Core Settings

Core settings are primarily configured via `.env` and consumed where needed.

### Redis Settings

See [env-vars.md](env-vars.md) for the authoritative list.

### Supabase Settings

`SUPABASE_URL` and keys are required for persistence/RAG flows.

### LLM Settings

| Setting             | Env Var             | Default  | Description       |
| ------------------- | ------------------- | -------- | ----------------- |
| `openai_api_key`    | `OPENAI_API_KEY`    | `None`   | OpenAI API key    |
| `anthropic_api_key` | `ANTHROPIC_API_KEY` | `None`   | Anthropic API key |
| `llm_model`         | `LLM_MODEL`         | `gpt-4o` | Default model     |
| `llm_temperature`   | `LLM_TEMPERATURE`   | `0.1`    | Model temperature |
| `llm_max_tokens`    | `LLM_MAX_TOKENS`    | `4096`   | Max output tokens |

### Email + Inbox Settings

Inbound ingestion settings (Tier-0 poller/webhook):

- `INBOX_PROVIDER` (`gmail|imap`)
- `INBOX_POLL_INTERVAL_S`
- `INBOX_DEDUP_TTL_SECONDS`
- `GMAIL_READ_CREDENTIALS_PATH`, `GMAIL_TOKEN_PATH`, `GMAIL_INBOX_USER`
- `IMAP_HOST`, `IMAP_USERNAME`, `IMAP_PASSWORD`, `IMAP_MAILBOX`
- `INBOX_WEBHOOK_SECRET`, `INBOX_WEBHOOK_HOST`, `INBOX_WEBHOOK_PORT`

Outbound sending (SMTP):

- `GMAIL_SENDER_EMAIL`
- `GMAIL_APP_PASSWORD`

### Agent Settings

| Setting                 | Env Var                 | Default | Description      |
| ----------------------- | ----------------------- | ------- | ---------------- |
| `agent_timeout_seconds` | `AGENT_TIMEOUT_SECONDS` | `120`   | Task timeout     |
| `agent_max_retries`     | `AGENT_MAX_RETRIES`     | `3`     | Retry attempts   |
| `consumer_block_ms`     | `CONSUMER_BLOCK_MS`     | `5000`  | XREAD block time |

---

## Usage Examples

### Access Settings

```python
from config.settings import settings

# Use in code
redis_client = redis.from_url(settings.redis_url)

# Check environment
if settings.environment == "production":
    enable_strict_mode()
```

### Override for Testing

```python
import os

# In test setup
os.environ["TENANT_ID"] = "test-tenant"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"

# Reload settings
from config.settings import Settings
test_settings = Settings()
```

### Validate Required Settings

```python
from config.settings import settings

def validate_settings():
    required = [
        settings.supabase_url,
        settings.supabase_anon_key,
        settings.supabase_jwt_secret,
    ]

    if settings.environment == "production":
        required.append(settings.openai_api_key)

    missing = [k for k, v in zip(
        ["supabase_url", "supabase_anon_key", "supabase_jwt_secret"],
        required
    ) if not v]

    if missing:
        raise ValueError(f"Missing required settings: {missing}")
```

---

## Environment-Specific Config

### Development

```bash
# .env.development
ENVIRONMENT=development
LOG_LEVEL=DEBUG
REDIS_URL=redis://localhost:6379/0
LLM_MODEL=gpt-4o-mini  # Cheaper for testing
```

### Staging

```bash
# .env.staging
ENVIRONMENT=staging
LOG_LEVEL=INFO
REDIS_URL=redis://redis-staging:6379/0
LLM_MODEL=gpt-4o
```

### Production

```bash
# .env.production
ENVIRONMENT=production
LOG_LEVEL=WARNING
REDIS_URL=redis://redis-prod:6379/0
REDIS_SSL=true
LLM_MODEL=gpt-4o
```

---

## Persistence Config

### Location

```
config/persistence_config.py
```

### Settings

```python
class PersistenceConfig:
    # Table configurations
    TABLES = {
        "leads": {
            "primary_key": "id",
            "required_fields": ["client_id", "email"],
            "soft_delete": True
        },
        "messages": {
            "primary_key": "id",
            "required_fields": ["conversation_id", "body", "metadata"],
            "soft_delete": False
        }
    }

    # Batch limits
    MAX_BATCH_SIZE = 1000
    DEFAULT_QUERY_LIMIT = 100
```

---

## RAG Config

### Location

```
config/rag_entities.py
```

### Settings

```python
class RAGConfig:
    # Vector DB settings
    EMBEDDING_MODEL = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS = 1536

    # Search defaults
    DEFAULT_TOP_K = 5
    SIMILARITY_THRESHOLD = 0.7

    # Chunking
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200
```

---

## Manager Config

### Location

```
config/manager/
```

### Intent Classification

```python
# config/manager/intents.py
INTENTS = {
    "inbound_reply": {
        "patterns": ["re:", "replied", "response"],
        "priority": "high",
        "actions": ["store", "enrich", "reply"]
    },
    "new_lead": {
        "patterns": ["new lead", "prospect"],
        "priority": "normal",
        "actions": ["store", "enrich"]
    }
}
```

### Routing Rules

```python
# config/manager/routing.py
ROUTING = {
    "inbound_reply": {
        "orchestrator": "leads",
        "action": "process_inbound"
    },
    "send_campaign": {
        "orchestrator": "outreach",
        "action": "send_campaign"
    }
}
```

## Related

- [Environment Variables](env-vars.md)
- [Harness Configuration](harness.md)
- [Secrets Management](../../guides/deploy/secrets.md)
