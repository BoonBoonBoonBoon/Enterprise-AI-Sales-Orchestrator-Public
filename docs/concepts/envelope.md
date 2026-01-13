# Message Envelope

The Message Envelope is the standardized JSON structure for all inter-component communication in the Agentic System.

## Why Envelopes?

Without standardization, every component would:

- Define its own message format
- Parse messages differently
- Lose traceability
- Struggle with error handling

The envelope provides:

- **Consistency** — Same structure everywhere
- **Traceability** — task_id links request to response
- **Metadata** — Context flows through the system
- **Validation** — Pydantic enforces structure

## Envelope Types

### TaskEnvelope

Sent when requesting work:

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "agentic-dev",
  "payload": {
    "action": "get_lead_context",
    "lead_id": "lead-123"
  },
  "metadata": {
    "source": "leads_orchestrator",
    "target": "rag_agent",
    "correlation_id": "flow-abc-123",
    "timestamp": "2026-01-13T10:30:00Z"
  }
}
```

### ResultEnvelope

Returned after processing:

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "agentic-dev",
  "status": "success",
  "result": {
    "lead_context": {...},
    "completeness_score": 0.85
  },
  "metadata": {
    "source": "rag_agent",
    "timestamp": "2026-01-13T10:30:05Z"
  }
}
```

## Anatomy

```
┌─────────────────────────────────────────────────────────┐
│                     ENVELOPE                            │
├─────────────────────────────────────────────────────────┤
│  task_id       │  Unique identifier (UUID)              │
│                │  Links request → response               │
├────────────────┼────────────────────────────────────────┤
│  tenant_id     │  Tenant scope                          │
│                │  Determines stream prefix               │
├────────────────┼────────────────────────────────────────┤
│  payload       │  Task-specific data                    │
│                │  Structure varies by action            │
├────────────────┼────────────────────────────────────────┤
│  metadata      │  Routing & tracing info                │
│                │  source, target, correlation_id        │
└────────────────┴────────────────────────────────────────┘
```

## Key Fields

### task_id

- **Type:** UUID string
- **Purpose:** Unique task identifier
- **Usage:** Correlate requests with responses

```python
import uuid

task_id = str(uuid.uuid4())
# "550e8400-e29b-41d4-a716-446655440000"
```

### tenant_id

- **Type:** String
- **Purpose:** Multi-tenant isolation
- **Usage:** Prefix for stream keys

```python
stream_key = f"{tenant_id}:agents:rag:tasks"
# "agentic-dev:agents:rag:tasks"
```

### payload

- **Type:** Object (dict)
- **Purpose:** Task-specific data
- **Structure:** Varies by action

```json
// RAG Agent
{"action": "get_lead_context", "lead_id": "..."}

// Persistence Agent
{"action": "create", "table": "leads", "data": {...}}

// Copywriter Agent
{"action": "draft_reply", "reply_packet": {...}}
```

### metadata

Routing and observability information:

| Field            | Purpose                           |
| ---------------- | --------------------------------- |
| `source`         | Component that created the task   |
| `target`         | Intended recipient (optional)     |
| `correlation_id` | Links related tasks in a workflow |
| `timestamp`      | When created                      |
| `debug`          | Debug info (e.g., llm_summary)    |

## Flow Example

```
1. Manager creates task
   ┌─────────────────────────────────────────┐
   │ task_id: "abc-123"                      │
   │ tenant_id: "agentic-dev"                │
   │ payload: {action: "process_inbound"}    │
   │ metadata: {source: "manager"}           │
   └─────────────────────────────────────────┘
                    │
                    ▼
2. Orchestrator creates sub-task (same correlation_id)
   ┌─────────────────────────────────────────┐
   │ task_id: "def-456"                      │
   │ tenant_id: "agentic-dev"                │
   │ payload: {action: "get_lead_context"}   │
   │ metadata: {                             │
   │   source: "leads_orchestrator",         │
   │   correlation_id: "abc-123"   ◄─────────│── Links to original
   │ }                                       │
   └─────────────────────────────────────────┘
                    │
                    ▼
3. Agent returns result
   ┌─────────────────────────────────────────┐
   │ task_id: "def-456"          ◄───────────│── Matches request
   │ status: "success"                       │
   │ result: {lead_context: {...}}           │
   │ metadata: {source: "rag_agent"}         │
   └─────────────────────────────────────────┘
```

## Pydantic Models

### TaskEnvelope

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid

class Metadata(BaseModel):
    source: str
    target: Optional[str] = None
    correlation_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    debug: Optional[dict] = None

class TaskEnvelope(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    payload: dict
    metadata: Metadata = Field(default_factory=Metadata)
```

### ResultEnvelope

```python
from typing import Literal

class ResultEnvelope(BaseModel):
    task_id: str
    tenant_id: str
    status: Literal["success", "error", "pending"]
    result: Optional[dict] = None
    error: Optional[dict] = None
    metadata: Metadata = Field(default_factory=Metadata)
```

## Error Envelope

When tasks fail:

```json
{
  "task_id": "abc-123",
  "tenant_id": "agentic-dev",
  "status": "error",
  "error": {
    "code": "LEAD_NOT_FOUND",
    "message": "Lead 'xyz' not found in any table",
    "details": {
      "searched_tables": ["leads", "staging_leads"]
    },
    "retryable": false
  }
}
```

### Error Fields

| Field       | Description                 |
| ----------- | --------------------------- |
| `code`      | Machine-readable error code |
| `message`   | Human-readable description  |
| `details`   | Additional context          |
| `retryable` | Can this be retried?        |

## Best Practices

1. **Always generate task_id** — Even for internal tasks
2. **Propagate correlation_id** — Through workflow chains
3. **Include source** — For debugging
4. **Keep payloads focused** — One action per task
5. **Validate with Pydantic** — Catch issues early
6. **Include error codes** — Enable programmatic handling

## Creating Envelopes

### Manual

```python
task = {
    "task_id": str(uuid.uuid4()),
    "tenant_id": "agentic-dev",
    "payload": {"action": "process", "data": {...}},
    "metadata": {"source": "my_component"}
}
```

### With Pydantic

```python
from core.envelope import TaskEnvelope, Metadata

envelope = TaskEnvelope(
    tenant_id="agentic-dev",
    payload={"action": "process", "data": {...}},
    metadata=Metadata(source="my_component")
)

task_dict = envelope.model_dump()
```

## Related

- [Envelope API Reference](../reference/api/envelope.md)
- [Redis Streams](redis-streams.md)
- [Three-Tier Architecture](three-tier-architecture.md)
