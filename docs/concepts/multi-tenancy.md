# Multi-Tenancy

The Agentic System supports multiple tenants with complete data isolation through Redis stream prefixes and Supabase RLS.

## Overview

Multi-tenancy enables:

- **Multiple clients** on a single deployment
- **Data isolation** between tenants
- **Independent workflows** per tenant
- **Separate configurations** per tenant

## Architecture

```
                          ┌─────────────────────┐
                          │   Shared Infra      │
                          │                     │
   ┌──────────────────────┼──────────────────┐  │
   │                      │                  │  │
   ▼                      ▼                  ▼  │
┌──────────┐      ┌──────────┐      ┌──────────┐│
│ Tenant A │      │ Tenant B │      │ Tenant C ││
│          │      │          │      │          ││
│ Streams: │      │ Streams: │      │ Streams: ││
│ a:*:*    │      │ b:*:*    │      │ c:*:*    ││
│          │      │          │      │          ││
│ Data:    │      │ Data:    │      │ Data:    ││
│ Isolated │      │ Isolated │      │ Isolated ││
└──────────┘      └──────────┘      └──────────┘│
                                                │
└───────────────────────────────────────────────┘
```

## Redis Stream Isolation

Every stream is prefixed with `tenant_id`:

```
# Tenant: acme-corp
acme-corp:manager:tasks
acme-corp:orchestrators:leads:tasks
acme-corp:agents:rag:tasks

# Tenant: techstart-io
techstart-io:manager:tasks
techstart-io:orchestrators:leads:tasks
techstart-io:agents:rag:tasks
```

### Key Construction

```python
def build_stream_key(tenant_id: str, tier: str, component: str, direction: str) -> str:
    """Build properly scoped stream key."""
    return f"{tenant_id}:{tier}:{component}:{direction}"

# Usage
key = build_stream_key("acme-corp", "agents", "rag", "tasks")
# Returns: "acme-corp:agents:rag:tasks"
```

### Consumer Binding

Each consumer binds to a specific tenant:

```python
class RAGAgentHarness(AgentHarness):
    def __init__(self, tenant_id: str):
        super().__init__(
            tenant_id=tenant_id,  # Scopes all operations
            agent_name="rag"
        )
```

## Database Isolation

### Option 1: Shared Tables with client_id

```sql
-- All leads have client_id
SELECT * FROM leads WHERE client_id = 'uuid-for-acme';

-- RLS enforces isolation
CREATE POLICY tenant_isolation ON leads
    USING (client_id::text = current_setting('request.jwt.claims')::json->>'client_id');
```

### Option 2: Schema per Tenant

```sql
-- Separate schemas
CREATE SCHEMA acme;
CREATE SCHEMA techstart;

-- Tenant-specific tables
CREATE TABLE acme.leads (...);
CREATE TABLE techstart.leads (...);
```

### Current Approach

We use **Option 1** (shared tables with RLS) for simplicity:

```python
class SupabaseAdapter:
    def __init__(self, role: str, client_id: str = None):
        self.role = role
        self.client_id = client_id

    def query(self, table: str, filters: dict) -> list:
        # client_id automatically enforced via RLS
        return self.client.table(table).select("*").match(filters).execute()
```

## Envelope Scoping

Every message envelope includes `tenant_id`:

```json
{
  "task_id": "uuid",
  "tenant_id": "acme-corp",  // Always present
  "payload": {...},
  "metadata": {...}
}
```

This enables:

- **Routing** — Correct stream prefix
- **Logging** — Tenant-scoped logs
- **Metrics** — Per-tenant monitoring

## Running Multi-Tenant

### Single Consumer per Tenant

```powershell
# Terminal 1: Tenant A
$env:TENANT_ID = "acme-corp"
& ".venv/Scripts/python.exe" -m tiers.tier_3.rag_agent.consumer

# Terminal 2: Tenant B
$env:TENANT_ID = "techstart-io"
& ".venv/Scripts/python.exe" -m tiers.tier_3.rag_agent.consumer
```

### Shared Consumer (Multiple Tenants)

```python
# Process all tenants in one consumer
TENANTS = ["acme-corp", "techstart-io", "other-tenant"]

async def run_multi_tenant():
    consumers = [
        RAGAgentHarness(tenant_id=t).run_async()
        for t in TENANTS
    ]
    await asyncio.gather(*consumers)
```

## Configuration per Tenant

### Tenant Settings

```python
# config/tenants.py
TENANT_CONFIG = {
    "acme-corp": {
        "llm_model": "gpt-4o",
        "email_rate_limit": 100,
        "features": ["enrichment", "outreach"]
    },
    "techstart-io": {
        "llm_model": "gpt-3.5-turbo",
        "email_rate_limit": 50,
        "features": ["outreach"]
    }
}
```

### Using Config

```python
def get_tenant_config(tenant_id: str) -> dict:
    return TENANT_CONFIG.get(tenant_id, DEFAULT_CONFIG)

# In agent
config = get_tenant_config(self.tenant_id)
model = config["llm_model"]
```

## Best Practices

1. **Always scope streams** — Never use bare stream names
2. **Include tenant_id in envelopes** — Required field
3. **Use RLS** — Database-level enforcement
4. **Log with tenant context** — For debugging
5. **Monitor per tenant** — Separate metrics

## Observability

### Tenant-Scoped Logging

```python
import structlog

logger = structlog.get_logger().bind(tenant_id=tenant_id)
logger.info("Processing task", task_id=task_id)
# Output: {"tenant_id": "acme-corp", "task_id": "...", ...}
```

### Tenant Metrics

```python
from prometheus_client import Counter

tasks_processed = Counter(
    'tasks_processed_total',
    'Total tasks processed',
    ['tenant_id', 'agent_name']
)

tasks_processed.labels(tenant_id="acme-corp", agent_name="rag").inc()
```

## Related

- [ADR-004: Supabase RLS](../architecture/decisions/004-supabase-rls-3-layer-auth.md)
- [Redis Streams](redis-streams.md)
- [Database Schema](../reference/database/schema.md)
- [Environment Variables](../reference/config/env-vars.md)
