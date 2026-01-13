# Envelope Format Specification

Complete specification of the message envelope format used across all tiers and services.

## Overview

All inter-component communication uses a standardized **Envelope** format:
- Typed, validated message structure
- Includes routing, metadata, and tracing
- Supports status tracking and error handling
- Backward compatible across versions

## Complete Envelope Schema

### Python Dataclass (Production - Typed)

```python
class Metadata(BaseModel):
    """Core routing and tracking metadata"""
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
    priority: Priority = Priority.NORMAL  # low, normal, high, critical
    retry_count: int = 0
    max_retries: int = 3
    tags: Dict[str, str] = Field(default_factory=dict)

class TraceSpan(BaseModel):
    """Optional distributed tracing span"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    service_name: str
    duration_ms: Optional[float] = None

class Envelope(BaseModel):
    """Universal message envelope"""
    metadata: Metadata
    payload: Dict[str, Any] = Field(default_factory=dict)
    status: Status = Status.PENDING  # pending, success, error, retry, dlq
    error: Optional[str] = None
    error_code: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    trace: Optional[TraceSpan] = None
```

### JSON Serialization Example

```json
{
  "metadata": {
    "message_id": "550e8400-e29b-41d4-a716-446655440000",
    "task_id": "task-123",
    "correlation_id": "cor-456",
    "source": "tier_1.manager",
    "destination": "tier_2.leads_orchestrator",
    "created_at": "2025-01-15T10:30:00Z",
    "processed_at": null,
    "req_id": "req-789",
    "user_id": "user-001",
    "tenant_id": "agentic-prod",
    "campaign_id": "camp-101",
    "priority": "high",
    "retry_count": 0,
    "max_retries": 3,
    "tags": {
      "workflow": "lead_discovery",
      "batch_id": "batch-001"
    }
  },
  "payload": {
    "action": "discover_leads",
    "industry": "fintech",
    "region": "US",
    "funding_min": 5000000,
    "filters": {
      "stage": "Series A"
    }
  },
  "status": "pending",
  "error": null,
  "error_code": null,
  "warnings": [],
  "trace": {
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "span_id": "00f067aa0ba902b7",
    "parent_span_id": null,
    "service_name": "manager",
    "duration_ms": null
  }
}
```

## Status Enum

```python
class Status(str, Enum):
    PENDING = "pending"          # Waiting to be processed
    SUCCESS = "success"          # Successfully processed
    ERROR = "error"              # Failed, won't retry
    RETRY = "retry"              # Failed, will retry
    DLQ = "dlq"                  # Dead-letter queue
```

## Priority Enum

```python
class Priority(str, Enum):
    LOW = "low"                  # Background tasks
    NORMAL = "normal"            # Standard processing (default)
    HIGH = "high"                # Expedited processing
    CRITICAL = "critical"        # Immediate processing
```

## Field Descriptions

### Metadata Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message_id` | UUID | ✓ | Unique message identifier |
| `task_id` | UUID | ✓ | Original task identifier |
| `correlation_id` | UUID | ✗ | Links related messages |
| `source` | string | ✓ | Originating component |
| `destination` | string | ✗ | Target component (optional) |
| `created_at` | datetime | ✓ | Message creation time |
| `processed_at` | datetime | ✗ | Processing completion time |
| `req_id` | string | ✗ | Original request ID (external) |
| `user_id` | string | ✗ | User who initiated task |
| `tenant_id` | string | ✗ | Tenant for multi-tenancy |
| `campaign_id` | string | ✗ | Campaign identifier |
| `priority` | enum | ✓ | Processing priority |
| `retry_count` | int | ✓ | Failed attempts (0 initially) |
| `max_retries` | int | ✓ | Maximum retry attempts |
| `tags` | dict | ✓ | Custom key-value metadata |

### Payload Field

- **Type:** Dictionary (any JSON-serializable structure)
- **Purpose:** Task-specific data
- **Example:**

```json
"payload": {
  "action": "search",
  "query": "AI startups",
  "filters": {"industry": "AI", "funding_stage": "Series A"}
}
```

### Trace Fields (Optional)

| Field | Type | Purpose |
|-------|------|---------|
| `trace_id` | string | OpenTelemetry trace ID (W3C format) |
| `span_id` | string | OpenTelemetry span ID |
| `parent_span_id` | string | Parent span (for nesting) |
| `service_name` | string | Service generating span |
| `duration_ms` | float | Processing duration |

## Builder Functions

### Create Task

```python
from core.envelope import task

t = task(
    source="tier_1.manager",
    task_id="t-123",
    payload={"action": "discover_leads", "industry": "fintech"},
    destination="tier_2.leads_orchestrator",
    priority=Priority.HIGH,
    correlation_id="cor-456",
    user_id="user-001",
    tenant_id="agentic-prod"
)
```

### Create Result

```python
from core.envelope import result

r = result(
    original=task_envelope,
    payload={"leads": [...], "count": 42},
    source="tier_3.rag_agent"
)
```

### Create Error

```python
from core.envelope import error

e = error(
    original=task_envelope,
    error_msg="Database connection timeout",
    source="tier_3.persistence_agent",
    code="db_timeout"
)
```

## Methods

### Mark Processing

```python
envelope.mark_processed()
# Sets status to SUCCESS, processed_at to now

envelope.mark_error(error_msg="...", code="...")
# Sets status to ERROR, adds error details

envelope.increment_retry()
# Increments retry_count
# If retry_count >= max_retries, sets status to DLQ
```

## Usage Patterns

### Manager Creating Task

```python
from core.envelope import task, Priority

# Create delegated task
delegate_task = task(
    source="tier_1.manager",
    task_id="t-123",
    payload={"workflow": "lead_discovery", "industry": "fintech"},
    destination="tier_2.leads_orchestrator",
    priority=Priority.HIGH,
    correlation_id=original_request.correlation_id,
    user_id=original_request.user_id,
    tenant_id=original_request.tenant_id
)

# Send to stream
redis.xadd(
    "tier_2.leads_orchestrator:tasks",
    {"data": delegate_task.to_json()}
)
```

### Orchestrator Receiving and Delegating

```python
from core.envelope import result, error, task

# Receive from stream
envelope = Envelope.model_validate_json(raw_data)

# Validate
assert envelope.status == Status.PENDING
assert envelope.destination == "tier_2.leads_orchestrator"

# Create sub-tasks for agents
sub_tasks = [
    task(
        source="tier_2.leads_orchestrator",
        task_id=f"{envelope.task_id}:rag",
        payload={"type": "search", "query": "..."},
        destination="tier_3.rag_agent",
        correlation_id=envelope.correlation_id,
        user_id=envelope.user_id,
        tenant_id=envelope.tenant_id
    ),
    task(
        source="tier_2.leads_orchestrator",
        task_id=f"{envelope.task_id}:persist",
        payload={"type": "store", "data": {...}},
        destination="tier_3.persistence_agent",
        correlation_id=envelope.correlation_id
    )
]

# Send to agents
for sub_task in sub_tasks:
    redis.xadd(f"{sub_task.destination}:tasks", {"data": sub_task.to_json()})

# Acknowledge original
redis.xack(consumer_stream, consumer_group, envelope.metadata.message_id)
```

### Agent Receiving and Responding

```python
from core.envelope import result, error, Status

# Process envelope
try:
    output = agent.process(envelope.payload)
    
    # Mark success
    envelope.mark_processed()
    result_env = result(envelope, output, source="tier_3.rag_agent")
    
    redis.xadd("tier_3.rag_agent:results", {"data": result_env.to_json()})
    
except Exception as e:
    # Mark error
    error_env = error(
        envelope,
        error_msg=str(e),
        source="tier_3.rag_agent",
        code=type(e).__name__
    )
    
    # Increment retry
    envelope.increment_retry()
    
    if envelope.status == Status.DLQ:
        redis.xadd("tier_3.rag_agent:dlq", {"data": error_env.to_json()})
    else:
        # Re-queue for retry
        redis.xadd(f"{envelope.destination}:tasks", {"data": error_env.to_json()})
```

## Backward Compatibility

### Old Envelope (Legacy Dataclass)

```python
@dataclass
class Envelope:
    metadata: Dict[str, Any]
    records: List[Dict[str, Any]]
    status: str = "SUCCESS"
    error: Optional[str] = None
```

### Migration Path

```python
# Old code still works via fallback imports
from agent.utils.envelope import Envelope as LegacyEnvelope

# New code uses typed version
from core.envelope import Envelope

# Both can coexist during migration
```

## Validation

### Type Validation

```python
from core.envelope import Envelope
from pydantic import ValidationError

try:
    env = Envelope.model_validate(raw_dict)
except ValidationError as e:
    print(f"Invalid envelope: {e}")
```

### Schema Validation

```python
# Ensure all required fields
envelope = Envelope(
    metadata=Metadata(
        message_id="...",
        task_id="...",
        source="tier_1.manager"
    ),
    payload={...}
)

# Attempt invalid priority
try:
    envelope.metadata.priority = "urgent"  # Invalid
except ValueError:
    print("Priority must be: low, normal, high, critical")
```

## Serialization

### To JSON

```python
envelope.model_dump_json(exclude_none=True)

# Output:
# '{"metadata": {...}, "payload": {...}, "status": "pending"}'
```

### From JSON

```python
data = '{"metadata": {...}, "payload": {...}}'
envelope = Envelope.model_validate_json(data)
```

### To Redis Fields

```python
# For XADD storage
redis_fields = {
    "data": envelope.model_dump_json(exclude_none=True)
}
```

## Examples by Use Case

### Lead Discovery Workflow

```json
{
  "metadata": {
    "source": "tier_1.manager",
    "task_id": "lead_discovery_1",
    "correlation_id": "api_request_123",
    "priority": "high"
  },
  "payload": {
    "workflow": "lead_discovery",
    "industry": "fintech",
    "region": "US",
    "funding_stage": "Series A"
  },
  "status": "pending"
}
```

### Data Enrichment Task

```json
{
  "metadata": {
    "source": "tier_2.leads_orchestrator",
    "task_id": "lead_discovery_1:enrich",
    "correlation_id": "api_request_123",
    "priority": "normal"
  },
  "payload": {
    "type": "enrich",
    "company_names": ["Acme Inc", "TechCorp LLC"],
    "data_sources": ["crunchbase", "linkedin"]
  },
  "status": "pending"
}
```

### Error Response

```json
{
  "metadata": {
    "source": "tier_3.persistence_agent",
    "task_id": "lead_discovery_1:persist",
    "correlation_id": "api_request_123",
    "retry_count": 3
  },
  "payload": {...},
  "status": "dlq",
  "error": "Database connection timeout after 3 retries",
  "error_code": "db_timeout"
}
```

## See Also

- `ARCHITECTURE.md` - System design overview
- `REDIS_STREAMS.md` - Redis Streams protocol
- `core/envelope/` - Source code

---

**Last Updated:** Task 17  
**Version:** 2.0 (Typed with Pydantic)  
**Backward Compatibility:** Yes (legacy dataclass still supported)
