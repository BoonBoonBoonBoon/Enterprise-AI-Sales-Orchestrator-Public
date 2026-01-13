# Envelope Schema

The Message Envelope is the standardized JSON structure for all inter-agent communication in the Agentic System.

## Overview

Every message flowing through Redis Streams uses a consistent envelope format, enabling:

- **Traceability** — Task IDs link requests to responses
- **Tenant isolation** — Tenant ID scopes all operations
- **Metadata propagation** — Context flows through the system
- **Type safety** — Pydantic models validate structure

## TaskEnvelope

Sent when requesting work from an agent or orchestrator.

### Schema

```python
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
import uuid

class Metadata(BaseModel):
    source: str = Field(..., description="Component that created this task")
    target: Optional[str] = Field(None, description="Intended recipient")
    correlation_id: Optional[str] = Field(None, description="Links related tasks")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    debug: Optional[dict] = Field(None, description="Debug info (e.g., llm_summary)")

class TaskEnvelope(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = Field(..., description="Tenant identifier")
    payload: dict = Field(..., description="Task-specific data")
    metadata: Metadata = Field(default_factory=Metadata)
```

### Example

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "agentic-dev",
  "payload": {
    "action": "get_lead_context",
    "lead_id": "lead-123",
    "include_conversations": true
  },
  "metadata": {
    "source": "leads_orchestrator",
    "target": "rag_agent",
    "correlation_id": "flow-abc-123",
    "timestamp": "2026-01-13T10:30:00Z"
  }
}
```

### Fields

| Field                     | Type          | Required | Description                          |
| ------------------------- | ------------- | -------- | ------------------------------------ |
| `task_id`                 | string (UUID) | ✅       | Unique identifier for this task      |
| `tenant_id`               | string        | ✅       | Tenant isolation key                 |
| `payload`                 | object        | ✅       | Task-specific data (varies by agent) |
| `metadata`                | object        | ✅       | Routing and tracing information      |
| `metadata.source`         | string        | ✅       | Component that created the task      |
| `metadata.target`         | string        | ⚠️       | Intended recipient (optional)        |
| `metadata.correlation_id` | string        | ⚠️       | Links related tasks in a workflow    |
| `metadata.timestamp`      | datetime      | ⚠️       | When task was created                |
| `metadata.debug`          | object        | ⚠️       | Debug info (kept brief)              |

## ResultEnvelope

Returned after processing a task.

### Schema

```python
class ResultEnvelope(BaseModel):
    task_id: str = Field(..., description="Original task ID")
    tenant_id: str = Field(..., description="Tenant identifier")
    status: Literal["success", "error", "pending"] = Field(...)
    result: Optional[dict] = Field(None, description="Successful result data")
    error: Optional[dict] = Field(None, description="Error details if failed")
    metadata: Metadata = Field(default_factory=Metadata)
```

### Success Example

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "agentic-dev",
  "status": "success",
  "result": {
    "lead_context": {
      "name": "John Doe",
      "company": "Acme Inc",
      "recent_messages": [...]
    },
    "completeness_score": 0.85
  },
  "metadata": {
    "source": "rag_agent",
    "timestamp": "2026-01-13T10:30:05Z"
  }
}
```

### Error Example

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "agentic-dev",
  "status": "error",
  "error": {
    "code": "LEAD_NOT_FOUND",
    "message": "Lead with ID 'lead-123' not found",
    "details": {
      "searched_tables": ["leads", "staging_leads"]
    }
  },
  "metadata": {
    "source": "rag_agent",
    "timestamp": "2026-01-13T10:30:02Z"
  }
}
```

### Fields

| Field           | Type   | Required | Description                        |
| --------------- | ------ | -------- | ---------------------------------- |
| `task_id`       | string | ✅       | Original task ID (for correlation) |
| `tenant_id`     | string | ✅       | Tenant isolation key               |
| `status`        | enum   | ✅       | `success`, `error`, or `pending`   |
| `result`        | object | ⚠️       | Present when status is `success`   |
| `error`         | object | ⚠️       | Present when status is `error`     |
| `error.code`    | string | ⚠️       | Machine-readable error code        |
| `error.message` | string | ⚠️       | Human-readable error message       |
| `error.details` | object | ⚠️       | Additional error context           |
| `metadata`      | object | ✅       | Routing and tracing information    |

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
import json
from services.redis.client import get_redis_client

redis = get_redis_client()

task = {
    "task_id": "my-task-001",
    "tenant_id": "agentic-dev",
    "payload": {
        "action": "process",
        "data": {"key": "value"}
    },
    "metadata": {
        "source": "my_component"
    }
}

redis.xadd(
    "agentic-dev:agents:my_agent:tasks",
    {"data": json.dumps(task)}
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
        if result["task_id"] == "my-task-001":
            if result["status"] == "success":
                print(result["result"])
            else:
                print(f"Error: {result['error']['message']}")
```

### Validation with Pydantic

```python
from core.envelope.task_envelope import TaskEnvelope, ResultEnvelope

# Validate incoming task
task = TaskEnvelope(**raw_data)

# Create result
result = ResultEnvelope(
    task_id=task.task_id,
    tenant_id=task.tenant_id,
    status="success",
    result={"processed": True}
)
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
