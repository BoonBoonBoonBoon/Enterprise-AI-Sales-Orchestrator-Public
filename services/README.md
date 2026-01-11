# Services - Shared Infrastructure Services

The `services/` directory contains shared infrastructure services used by agents and orchestrators across all tiers.

## Directory Structure

```
services/
├── README.md           ← You are here
├── __init__.py
│
├── email/              # Email sending service
│   └── gmail_sender.py # Gmail API integration
│
├── external_apis/      # Third-party API integrations
│   ├── adapters/       # API client adapters
│   ├── models/         # Response models
│   └── tools/          # LangChain tool wrappers
│
├── persistence/        # Database operations
│   ├── adapters/       # Supabase adapter
│   ├── models/         # Database models
│   ├── promotion/      # Lead staging → production promotion
│   ├── queries/        # Query builders
│   └── tools/          # LangChain tool wrappers
│
├── redis/              # Redis client & utilities
│   ├── consumer_group/ # Consumer group management
│   └── pubsub/         # Pub/sub utilities
│
└── vector_db/          # Vector database integration
    ├── client/         # Vector DB client
    └── models/         # Embedding models
```

## Service Overview

### Email Service (`email/`)

Gmail integration for sending outreach emails:

```python
from services.email.gmail_sender import GmailSender

sender = GmailSender(credentials_path="credentials.json")
sender.send(to="lead@example.com", subject="...", body="...")
```

### Persistence Service (`persistence/`)

Database operations via Supabase with role-based access:

```python
from services.persistence.supabase_adapter import SupabaseAdapter

# Writer role for Persistence Agent
adapter = SupabaseAdapter(role="agent_writer")
adapter.write("leads", {"name": "John", "email": "john@example.com"})

# Reader role for RAG Agent
adapter = SupabaseAdapter(role="agent_reader")
leads = adapter.query("leads", {"status": "new"}, limit=10)
```

**Database Roles:**
| Role | Permissions | Used By |
|------|-------------|---------|
| `agent_reader` | SELECT only | RAG Agent |
| `agent_writer` | SELECT, INSERT, UPDATE, DELETE | Persistence Agent |

### Redis Service (`redis/`)

Redis stream utilities for agent communication:

```python
from services.redis import get_redis_client

redis = get_redis_client()
redis.xadd("agentic-dev:agents:rag:tasks", {"payload": "..."})
```

### Vector DB Service (`vector_db/`)

Vector search for semantic retrieval (used by RAG Agent):

```python
from services.vector_db import VectorDBClient

client = VectorDBClient()
results = client.search("AI automation for sales", limit=5)
```

### External APIs (`external_apis/`)

Third-party integrations (CRM, enrichment, etc.):

- **Adapters:** API client wrappers
- **Models:** Pydantic response models
- **Tools:** LangChain tool wrappers for agent use

## Configuration

Services are configured via environment variables:

```bash
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_JWT_SECRET=your-jwt-secret

# Redis
REDIS_URL=redis://localhost:6379

# Email
GMAIL_CREDENTIALS_PATH=credentials.json
```

## 3-Layer Authentication (Supabase)

All database access uses a 3-layer security model:

1. **API Gateway:** Supabase anon_key + custom JWT
2. **PostgreSQL GRANT:** Role-based permissions
3. **RLS Policies:** Row-level security with JWT claims

## See Also

- [Supabase Integration](../docs/architecture/supabase/)
- [Persistence Agent](../tiers/tier_3/persistence_agent/README.md)
- [RAG Agent](../tiers/tier_3/rag_agent/README.md)
