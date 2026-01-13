# Persistence Agent

The Persistence Agent handles all database write operations (INSERT, UPDATE, DELETE) across the system.

## Overview

| Property          | Value                                                 |
| ----------------- | ----------------------------------------------------- |
| **Tier**          | 3 (Execution)                                         |
| **Stream**        | `{tenant}:agents:persistence:tasks`                   |
| **Database Role** | `agent_writer` (full CRUD)                            |
| **Core File**     | `tiers/tier_3/persistence_agent/persistence_agent.py` |

## Responsibilities

- Create, update, and delete records in Supabase
- Handle foreign key relationships
- Validate data before persistence
- Inject default values (e.g., campaign_id placeholder)

## Actions

### `create`

Insert a new record.

**Request:**

```json
{
  "action": "create",
  "table": "leads",
  "data": {
    "name": "John Doe",
    "email": "john@example.com",
    "client_id": "uuid-client",
    "campaign_id": "uuid-campaign"
  }
}
```

**Response:**

```json
{
  "status": "success",
  "result": {
    "id": "uuid-new-lead",
    "created_at": "2026-01-13T10:00:00Z"
  }
}
```

### `update`

Update an existing record.

**Request:**

```json
{
  "action": "update",
  "table": "leads",
  "id": "uuid-lead",
  "data": {
    "status": "qualified",
    "score": 85
  }
}
```

**Response:**

```json
{
  "status": "success",
  "result": {
    "id": "uuid-lead",
    "updated_at": "2026-01-13T10:05:00Z"
  }
}
```

### `delete`

Delete a record.

**Request:**

```json
{
  "action": "delete",
  "table": "leads",
  "id": "uuid-lead"
}
```

**Response:**

```json
{
  "status": "success",
  "result": {
    "deleted": true
  }
}
```

### `batch_create`

Insert multiple records.

**Request:**

```json
{
  "action": "batch_create",
  "table": "messages",
  "records": [
    { "conversation_id": "uuid-conv", "content": "Hello", "metadata": {} },
    { "conversation_id": "uuid-conv", "content": "World", "metadata": {} }
  ]
}
```

**Response:**

```json
{
  "status": "success",
  "result": {
    "created_count": 2,
    "ids": ["uuid-1", "uuid-2"]
  }
}
```

### `store_message`

Specialized action for storing conversation messages.

**Request:**

```json
{
  "action": "store_message",
  "conversation_id": "uuid-conv",
  "content": "Email body here",
  "direction": "inbound",
  "metadata": {
    "from": "sender@example.com",
    "subject": "Re: Your inquiry"
  }
}
```

## Supported Tables

| Table                   | FK Dependencies              | Notes                   |
| ----------------------- | ---------------------------- | ----------------------- |
| `clients`               | None                         | Top-level tenant        |
| `campaigns`             | `clients.id`                 | Marketing campaigns     |
| `leads`                 | `clients.id`, `campaigns.id` | Qualified leads         |
| `staging_leads`         | None                         | Pre-qualification       |
| `conversations`         | `leads.id`                   | Lead conversations      |
| `messages`              | `conversations.id`           | Requires `metadata: {}` |
| `staging_conversations` | `staging_leads.id`           | Pre-qual threads        |
| `staging_messages`      | `staging_conversations.id`   | Pre-qual messages       |

## Campaign ID Placeholder

For inbound leads without campaign context:

```python
# Environment variable
CAMPAIGN_ID_PLACEHOLDER = "9646f98a-e987-4a8c-b786-9b82ea985d38"
```

The agent injects this placeholder when `campaign_id` is not provided. Ensure this UUID exists in the `campaigns` table.

## FK Order

When creating related records, respect the FK chain:

```
clients → campaigns → leads → conversations → messages
```

**Example flow:**

```python
# 1. Create lead
lead_result = await persistence_agent.create("leads", {...})
lead_id = lead_result["id"]

# 2. Create conversation
conv_result = await persistence_agent.create("conversations", {
    "lead_id": lead_id,
    ...
})

# 3. Create message
await persistence_agent.create("messages", {
    "conversation_id": conv_result["id"],
    "metadata": {}  # Required!
})
```

## File Structure

```
tiers/tier_3/persistence_agent/
├── persistence_agent.py     # Core logic
├── persistence_harness.py   # Redis wrapper
├── consumer.py              # Entry point
├── validators.py            # Pydantic models
└── README.md
```

## Configuration

### Environment Variables

| Variable                  | Default   | Description       |
| ------------------------- | --------- | ----------------- |
| `SUPABASE_URL`            | —         | Database URL      |
| `SUPABASE_ANON_KEY`       | —         | API key           |
| `SUPABASE_JWT_SECRET`     | —         | For role JWTs     |
| `CAMPAIGN_ID_PLACEHOLDER` | See above | Fallback campaign |

## Error Codes

| Code               | Description                          |
| ------------------ | ------------------------------------ |
| `FK_VIOLATION`     | Foreign key constraint failed        |
| `NOT_FOUND`        | Record to update/delete not found    |
| `DUPLICATE_KEY`    | Unique constraint violation          |
| `INVALID_TABLE`    | Unknown table name                   |
| `VALIDATION_ERROR` | Required fields missing              |
| `RLS_DENIED`       | Row-level security blocked operation |

## Usage Example

### From Orchestrator

```python
async def store_lead(self, lead_data: dict) -> str:
    task = {
        "task_id": str(uuid.uuid4()),
        "tenant_id": self.tenant_id,
        "payload": {
            "action": "create",
            "table": "leads",
            "data": lead_data
        },
        "metadata": {"source": "leads_orchestrator"}
    }

    await self.redis.xadd(
        f"{self.tenant_id}:agents:persistence:tasks",
        {"data": json.dumps(task)}
    )

    # Wait for result...
    return result["id"]
```

### Running Consumer

```powershell
& ".venv/Scripts/python.exe" -m tiers.tier_3.persistence_agent.consumer
```

## Validation

All data is validated before persistence:

```python
from pydantic import BaseModel, Field

class LeadCreate(BaseModel):
    name: str
    email: str
    client_id: str
    campaign_id: str = None  # Will use placeholder
    status: str = "new"
    metadata: dict = Field(default_factory=dict)
```

## Related

- [RAG Agent](rag.md) — For read operations
- [Database Schema](../../reference/database/schema.md)
- [Supabase RLS](../../reference/database/rls.md)
- [Creating Agents](../../guides/dev/new-agent.md)
