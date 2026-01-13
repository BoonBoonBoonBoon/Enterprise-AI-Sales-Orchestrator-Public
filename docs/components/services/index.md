# Services

The shared infrastructure layer of the Agentic System. Services provide common functionality used by agents and orchestrators across all tiers.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              TIER 1, 2, 3 - Agents & Orchestrators              │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                          SERVICES                               │
│                                                                 │
│  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────────┐ │
│  │   Redis     │  │   Persistence   │  │     Vector DB       │ │
│  │   Service   │  │     Service     │  │                     │ │
│  │             │  │                 │  │  • Embeddings       │ │
│  │  • Streams  │  │  • Supabase     │  │  • Similarity       │ │
│  │  • Pub/Sub  │  │    Adapter      │  │    search           │ │
│  │  • Groups   │  │  • Queries      │  │  • ChromaDB/        │ │
│  │             │  │  • Promotion    │  │    Qdrant           │ │
│  └─────────────┘  └─────────────────┘  └─────────────────────┘ │
│                                                                 │
│  ┌─────────────┐  ┌─────────────────┐                          │
│  │   Email     │  │  External APIs  │                          │
│  │   Service   │  │                 │                          │
│  │             │  │  • Crunchbase   │                          │
│  │  • Gmail    │  │  • LinkedIn     │                          │
│  │  • SMTP     │  │  • Enrichment   │                          │
│  └─────────────┘  └─────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

## Service Inventory

| Service                               | Path                      | Purpose                                     | Used By               |
| ------------------------------------- | ------------------------- | ------------------------------------------- | --------------------- |
| [Redis Service](redis.md)             | `services/redis/`         | Stream management, pub/sub, consumer groups | All tiers             |
| [Persistence Service](persistence.md) | `services/persistence/`   | Supabase adapter, database queries          | Persistence Agent     |
| [Vector DB](vector-db.md)             | `services/vector_db/`     | Embeddings, similarity search               | RAG Agent             |
| [Email Service](email.md)             | `services/email/`         | Gmail integration, SMTP sending             | Outreach Orchestrator |
| External APIs                         | `services/external_apis/` | Crunchbase, LinkedIn adapters               | Leads Orchestrator    |

## Service Patterns

### Singleton Clients

Services typically provide singleton client instances:

```python
from services.redis.client import get_redis_client

# Returns cached connection
redis = get_redis_client()
```

### Adapter Pattern

Complex integrations use adapters to abstract vendor-specific APIs:

```python
from services.persistence.supabase_adapter import SupabaseAdapter

adapter = SupabaseAdapter(role="agent_writer")
adapter.write("leads", {"name": "John", "email": "john@example.com"})
```

### Configuration

All services read configuration from environment variables via `config/settings.py`:

```python
from config.settings import settings

supabase_url = settings.SUPABASE_URL
redis_url = settings.REDIS_URL
```

## Quick Links

- [Redis Service](redis.md) — Stream operations, consumer groups, pub/sub
- [Persistence Service](persistence.md) — Supabase adapter, CRUD operations
- [Vector DB](vector-db.md) — Embeddings and similarity search
- [Email Service](email.md) — Gmail OAuth, SMTP configuration

## Environment Variables

See [Reference → Environment Variables](../../reference/config/env-vars.md) for all service configuration options.
