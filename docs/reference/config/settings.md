# Settings Reference

This reference documents the `config/settings.py` module and application configuration.

## Overview

Settings are loaded from environment variables with fallbacks to defaults.

```python
from config.settings import settings

print(settings.tenant_id)
print(settings.redis_url)
```

## Settings Class

### Location

```
config/settings.py
```

### Implementation

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Core
    tenant_id: str = "agentic-dev"
    environment: str = "development"
    log_level: str = "INFO"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_password: str | None = None

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_jwt_secret: str

    # LLM
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.1

    # Email
    gmail_credentials_path: str = "credentials.json"
    gmail_token_path: str = "token.json"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

## Configuration Categories

### Core Settings

| Setting       | Env Var       | Default       | Description                            |
| ------------- | ------------- | ------------- | -------------------------------------- |
| `tenant_id`   | `TENANT_ID`   | `agentic-dev` | Multi-tenant identifier                |
| `environment` | `ENVIRONMENT` | `development` | `development`, `staging`, `production` |
| `log_level`   | `LOG_LEVEL`   | `INFO`        | `DEBUG`, `INFO`, `WARNING`, `ERROR`    |

### Redis Settings

| Setting          | Env Var          | Default                    | Description          |
| ---------------- | ---------------- | -------------------------- | -------------------- |
| `redis_url`      | `REDIS_URL`      | `redis://localhost:6379/0` | Redis connection URL |
| `redis_password` | `REDIS_PASSWORD` | `None`                     | Password if required |
| `redis_ssl`      | `REDIS_SSL`      | `false`                    | Enable TLS           |

### Supabase Settings

| Setting               | Env Var               | Default      | Description        |
| --------------------- | --------------------- | ------------ | ------------------ |
| `supabase_url`        | `SUPABASE_URL`        | **required** | Project URL        |
| `supabase_anon_key`   | `SUPABASE_ANON_KEY`   | **required** | Anonymous API key  |
| `supabase_jwt_secret` | `SUPABASE_JWT_SECRET` | **required** | JWT signing secret |

### LLM Settings

| Setting             | Env Var             | Default  | Description       |
| ------------------- | ------------------- | -------- | ----------------- |
| `openai_api_key`    | `OPENAI_API_KEY`    | `None`   | OpenAI API key    |
| `anthropic_api_key` | `ANTHROPIC_API_KEY` | `None`   | Anthropic API key |
| `llm_model`         | `LLM_MODEL`         | `gpt-4o` | Default model     |
| `llm_temperature`   | `LLM_TEMPERATURE`   | `0.1`    | Model temperature |
| `llm_max_tokens`    | `LLM_MAX_TOKENS`    | `4096`   | Max output tokens |

### Email Settings

| Setting                  | Env Var                  | Default            | Description       |
| ------------------------ | ------------------------ | ------------------ | ----------------- |
| `gmail_credentials_path` | `GMAIL_CREDENTIALS_PATH` | `credentials.json` | OAuth credentials |
| `gmail_token_path`       | `GMAIL_TOKEN_PATH`       | `token.json`       | Refresh token     |
| `email_batch_size`       | `EMAIL_BATCH_SIZE`       | `50`               | Emails per batch  |

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
REDIS_URL=redis://<REDACTED_REDIS_URL>
LLM_MODEL=gpt-4o
```

### Production

```bash
# .env.production
ENVIRONMENT=production
LOG_LEVEL=WARNING
REDIS_URL=redis://<REDACTED_REDIS_URL>
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

