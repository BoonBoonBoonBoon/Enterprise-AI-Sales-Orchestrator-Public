# Persistence Service

Database operations via Supabase with role-based access control.

## Components

| Directory    | Purpose                                   |
| ------------ | ----------------------------------------- |
| `adapters/`  | Supabase adapter with JWT-based auth      |
| `models/`    | Database models (Pydantic)                |
| `promotion/` | Lead staging → production promotion logic |
| `queries/`   | Query builders                            |
| `tools/`     | LangChain tool wrappers for agents        |

## Usage

```python
from services.persistence.supabase_adapter import SupabaseAdapter

# Writer role (for Persistence Agent)
adapter = SupabaseAdapter(role="agent_writer")

# CRUD operations
adapter.write("leads", {"name": "John", "email": "john@example.com"})
lead = adapter.read("leads", "uuid-here")
leads = adapter.query("leads", {"status": "new"}, limit=10)
adapter.update("leads", "uuid-here", {"status": "contacted"})
adapter.delete("leads", "uuid-here")

# Batch operations
adapter.batch_write("leads", [{"name": "A"}, {"name": "B"}])
```

## Database Roles

| Role           | Permissions                    | Used By           |
| -------------- | ------------------------------ | ----------------- |
| `agent_reader` | SELECT only                    | RAG Agent         |
| `agent_writer` | SELECT, INSERT, UPDATE, DELETE | Persistence Agent |

## Core Tables

| Table           | FK Dependencies    | Notes                   |
| --------------- | ------------------ | ----------------------- |
| `clients`       | None               | Top-level tenant        |
| `staging_leads` | None               | Pre-processed leads     |
| `leads`         | `clients.id`       | Qualified leads         |
| `conversations` | `leads.id`         | Lead conversations      |
| `messages`      | `conversations.id` | Requires `metadata: {}` |

## 3-Layer Security

1. **API Gateway:** Supabase anon_key + custom JWT
2. **PostgreSQL GRANT:** Role-based permissions
3. **RLS Policies:** Row-level security with JWT claims

## Configuration

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_JWT_SECRET=your-jwt-secret
```

## See Also

- [Supabase Architecture](../../docs/architecture/supabase/)
- [Persistence Agent](../../tiers/tier_3/persistence_agent/README.md)
