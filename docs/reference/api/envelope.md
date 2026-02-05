# Envelope Schema

The Message Envelope is the standardized JSON structure for all inter-agent communication in the Agentic System.

## Overview

Every message flowing through Redis Streams uses a consistent envelope format, enabling:

- **Traceability** — Task IDs link requests to responses
- **Tenant isolation** — Tenant ID scopes all operations
- **Metadata propagation** — Context flows through the system
- **Type safety** — Pydantic models validate structure

## Envelope (Task)

Sent when requesting work from an agent or orchestrator. The canonical format is the typed
`Envelope` (core/envelope/typed_envelope.py).

### Schema

```python
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from datetime import datetime
from enum import Enum
import uuid

class Status(str, Enum):
  PENDING = "pending"
  SUCCESS = "success"
  ERROR = "error"
  RETRY = "retry"
  DLQ = "dlq"

class Metadata(BaseModel):
  message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
  task_id: str
  correlation_id: Optional[str] = None
  source: str
  destination: Optional[str] = None
  created_at: datetime = Field(default_factory=datetime.utcnow)
  processed_at: Optional[datetime] = None
  req_id: Optional[str] = None
  user_id: Optional[str] = None
  tenant_id: Optional[str] = None
  campaign_id: Optional[str] = None
  priority: str = "normal"
  retry_count: int = 0
  max_retries: int = 3
  tags: Dict[str, str] = Field(default_factory=dict)
  debug: Optional[Dict[str, Any]] = None

class Envelope(BaseModel):
  metadata: Metadata
  payload: Dict[str, Any] = Field(default_factory=dict)
  status: Status = Status.PENDING
  error: Optional[str] = None
  error_code: Optional[str] = None
  warnings: List[str] = Field(default_factory=list)
```

### Example

```json
{
  "metadata": {
    "message_id": "a1b2c3d4-e29b-41d4-a716-446655440000",
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "tenant_id": "agentic-dev",
    "source": "leads_orchestrator",
    "destination": "rag_agent",
    "correlation_id": "flow-abc-123",
    "created_at": "2026-01-13T10:30:00Z"
  },
  "payload": {
    "action": "get_lead_context",
    "lead_id": "lead-123",
    "include_conversations": true
  },
  "status": "pending"
}
```

### Fields

| Field                     | Type          | Required | Description                          |
| ------------------------- | ------------- | -------- | ------------------------------------ |
| `metadata.task_id`        | string (UUID) | ✅       | Unique identifier for this task      |
| `metadata.tenant_id`      | string        | ⚠️       | Tenant isolation key                 |
| `payload`                 | object        | ✅       | Task-specific data (varies by agent) |
| `metadata`                | object        | ✅       | Routing and tracing information      |
| `metadata.source`         | string        | ✅       | Component that created the task      |
| `metadata.destination`    | string        | ⚠️       | Intended recipient (optional)        |
| `metadata.correlation_id` | string        | ⚠️       | Links related tasks in a workflow    |
| `metadata.created_at`     | datetime      | ⚠️       | When task was created                |
| `metadata.debug`          | object        | ⚠️       | Debug info (kept brief)              |
| `status`                  | enum          | ✅       | `pending`, `success`, `error`, etc.  |

## Envelope (Result)

Returned after processing a task. Uses the same `Envelope` type with `status=success` or `status=error`.

### Success Example

```json
{
  "metadata": {
    "message_id": "b2c3d4e5-e29b-41d4-a716-446655440000",
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "tenant_id": "agentic-dev",
    "source": "rag_agent",
    "created_at": "2026-01-13T10:30:05Z"
  },
  "payload": {
    "lead_context": {
      "name": "John Doe",
      "company": "Acme Inc",
      "recent_messages": [...]
    },
    "completeness_score": 0.85
  },
  "status": "success"
}
```

### Error Example

```json
{
  "metadata": {
    "message_id": "b2c3d4e5-e29b-41d4-a716-446655440000",
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "tenant_id": "agentic-dev",
    "source": "rag_agent",
    "created_at": "2026-01-13T10:30:02Z"
  },
  "status": "error",
  "error": "Lead with ID 'lead-123' not found",
  "error_code": "LEAD_NOT_FOUND",
  "payload": {
    "searched_tables": ["leads", "staging_leads"]
  }
}
```

### Fields

| Field                | Type   | Required | Description                         |
| -------------------- | ------ | -------- | ----------------------------------- |
| `metadata.task_id`   | string | ✅       | Original task ID (for correlation)  |
| `metadata.tenant_id` | string | ⚠️       | Tenant isolation key                |
| `status`             | enum   | ✅       | `success`, `error`, `pending`, etc. |
| `payload`            | object | ⚠️       | Present for success results         |
| `error`              | string | ⚠️       | Present when status is `error`      |
| `error_code`         | string | ⚠️       | Machine-readable error code         |
| `metadata`           | object | ✅       | Routing and tracing information     |

## ReplyPacket

Special payload for chained workflows (e.g., Leads → Manager → Outreach).

### Schema

```python
class ReplyPacket(BaseModel):
    lead_id: str
    lead_source: Optional[str] = None
    context: dict = Field(default_factory=dict)
    thread_id: Optional[str] = None
    query_trace: Optional[dict] = None  # RAG query trace for debugging
```

### Example

```json
{
  "lead_id": "lead-123",
  "lead_source": "staging_leads",
  "context": {
    "name": "John Doe",
    "email": "john@acme.com",
    "enrichment": {...}
  },
  "thread_id": "conv-456",
  "query_trace": {
    "tables_queried": ["leads", "staging_leads", "conversations"],
    "steps": 3,
    "error_count": 0
  }
}
```

## Usage Examples

### Publishing a Task

```python
from core.envelope import task as create_task, to_redis_fields
from services.redis.client import get_redis_client

redis = get_redis_client()

envelope = create_task(
  source="my_component",
  task_id="my-task-001",
  payload={"action": "process", "data": {"key": "value"}},
  destination="my_agent",
  tenant_id="agentic-dev",
)

redis.xadd(
  "agentic-dev:agents:my_agent:tasks",
  to_redis_fields(envelope)
)
```

### Reading Results

```python
results = redis.xread(
    {"agentic-dev:agents:my_agent:results": "0"},
    count=10
)

for stream, messages in results:
    for msg_id, data in messages:
        result = json.loads(data["data"])
        if result.get("metadata", {}).get("task_id") == "my-task-001":
          if result["status"] == "success":
            print(result["payload"])
          else:
            print(f"Error: {result.get('error')}")
```

### Validation with Pydantic

```python
from core.envelope import Envelope

# Validate incoming envelope
env = Envelope.model_validate(raw_data)

# Create result (copy metadata fields as needed)
env.status = "success"
env.payload = {"processed": True}
```

## Best Practices

1. **Always include `task_id`** — Essential for tracing and correlation
2. **Use correlation_id for workflows** — Links multi-step operations
3. **Keep payloads focused** — One task = one responsibility
4. **Include error codes** — Enables programmatic error handling
5. **Propagate metadata** — Pass correlation_id through the chain
6. **Validate with Pydantic** — Catch schema issues early

## Related

- [Stream Keys](streams.md) — Stream naming conventions
- [Agent Payloads](payloads.md) — Per-agent payload schemas
- [Three-Tier Architecture](../../concepts/three-tier-architecture.md) — How envelopes flow
