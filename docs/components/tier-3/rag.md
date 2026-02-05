# RAG Agent

The RAG (Retrieval-Augmented Generation) Agent retrieves contextual information from the database to enrich lead data and support decision-making.

## Overview

| Property          | Value                                 |
| ----------------- | ------------------------------------- |
| **Tier**          | 3 (Execution)                         |
| **Stream**        | `{tenant}:agents:rag:tasks`           |
| **Database Role** | `agent_reader` (SELECT only)          |
| **Core File**     | `tiers/tier_3/rag_agent/rag_agent.py` |

## Responsibilities

- Retrieve lead context from database
- Cascade lookup across tables (leads → staging_leads → conversations → messages)
- Return structured context with query trace
- Support vector similarity search (when enabled)

## Actions

### `build_reply_context` (deterministic fast-path)

Build reply-ready context for an inbound email thread.

This is the preferred operation for inbound reply workflows because it returns a structured payload suitable for downstream reply generation (Copywriter).

**Request (recommended):**

```json
{
  "operation": "build_reply_context",
  "task_id": "rag_ctx_<uuid>",
  "email": "lead@example.com",
  "lead_id": "optional-lead-uuid",
  "thread_id": "optional-thread-id",
  "subject": "optional-subject",
  "max_messages": 200,
  "include_lead_profile": true,
  "include_all_threads": true
}
```

**Response (shape):**

```json
{
  "status": "found|no_conversations|not_found|error",
  "task_id": "rag_ctx_<uuid>",
  "lead": { "id": "...", "email": "..." },
  "lead_source": "leads|staging_leads",
  "conversation": { "conversation_id": "...", "recent_messages": [] },
  "conversations": [{ "conversation_id": "..." }],
  "messages": [{ "role": "lead", "content": "..." }],
  "query_trace": { "operation": "build_reply_context", "error_count": 0 },
  "match_reason": "email_exact|lead_id|...",
  "error": null
}
```

### `get_lead_context`

Retrieve general lead context (lead + conversations + messages). Used for enrichment/lookup; reply flows should prefer `build_reply_context`.

### `search_similar`

Vector similarity search (requires vector DB).

**Request:**

```json
{
  "action": "search_similar",
  "query": "enterprise software decision maker",
  "limit": 5,
  "threshold": 0.7
}
```

**Response:**

```json
{
  "status": "success",
  "result": {
    "matches": [
      { "id": "lead-1", "score": 0.92, "snippet": "..." },
      { "id": "lead-2", "score": 0.85, "snippet": "..." }
    ]
  }
}
```

## Cascade Lookup

The agent uses a cascading strategy to find lead data:

```
1. Query `leads` table by ID
   ↓ (if not found)
2. Query `staging_leads` table by ID
   ↓ (if not found)
3. Return NOT_FOUND error
```

For context enrichment:

```
Lead found → Query `conversations` → Query `messages`
```

## Configuration

### Environment Variables

| Variable               | Default | Description                               |
| ---------------------- | ------- | ----------------------------------------- |
| `SUPABASE_URL`         | —       | Database URL                              |
| `SUPABASE_ANON_KEY`    | —       | API key                                   |
| `SUPABASE_RAG_JWT`     | —       | Custom JWT for `agent_reader` (preferred) |
| `SUPABASE_SERVICE_KEY` | —       | Service key fallback when JWT is invalid  |
| `RAG_MAX_MESSAGES`     | `50`    | Max messages to return                    |
| `RAG_INCLUDE_STAGING`  | `true`  | Search staging tables                     |

### Settings

```python
# config/rag_entities.py
RAG_CONFIG = {
    "max_context_tokens": 4000,
    "include_staging": True,
    "cascade_lookup": True,
}
```

## File Structure

```
tiers/tier_3/rag_agent/
├── rag_agent.py           # Core logic (LangGraph StateGraph)
├── rag_agent_harness.py   # Redis wrapper
├── consumer.py            # Entry point
├── validators.py          # Pydantic models
├── worker.py              # Sync execution
└── README.md
```

## Usage Example

### From Orchestrator

```python
# In LeadsOrchestrator
async def get_lead_context(self, lead_id: str) -> dict:
    task = {
        "task_id": str(uuid.uuid4()),
        "tenant_id": self.tenant_id,
        "payload": {
            "action": "get_lead_context",
            "lead_id": lead_id,
            "include_conversations": True
        },
        "metadata": {"source": "leads_orchestrator"}
    }

    # Publish to RAG agent stream
    await self.redis.xadd(
        f"{self.tenant_id}:agents:rag:tasks",
        {"data": json.dumps(task)}
    )

    # Wait for result...
```

### Running Consumer

```powershell
& ".venv/Scripts/python.exe" -m tiers.tier_3.rag_agent.consumer
```

## Error Codes

| Code              | Description                 |
| ----------------- | --------------------------- |
| `LEAD_NOT_FOUND`  | Lead not found in any table |
| `DATABASE_ERROR`  | Supabase query failed       |
| `INVALID_PAYLOAD` | Missing required fields     |
| `RATE_LIMITED`    | Too many requests           |

## Query Trace

The `query_trace` field provides debugging visibility:

```json
{
  "query_trace": {
    "tables_queried": ["leads", "staging_leads", "conversations"],
    "steps": 3,
    "error_count": 0,
    "timing_ms": 45
  }
}
```

This is propagated through `ReplyPacket` for end-to-end tracing.

## Database Access

Uses `agent_reader` role with SELECT-only permissions:

```python
from services.persistence.supabase_adapter import SupabaseAdapter

adapter = SupabaseAdapter(role="agent_reader")
lead = adapter.read("leads", lead_id)
```

## Related

- [Persistence Agent](persistence.md) — For write operations
- [Envelope Schema](../../reference/api/envelope.md)
- [Database Schema](../../reference/database/schema.md)
- [Creating Agents](../../guides/dev/new-agent.md)
