# API Reference

Complete reference for the Agentic System's envelope-based messaging API. This document covers envelope structure, payload schemas for all agents, error codes, and integration examples.

---

## Table of Contents

1. [Envelope Structure](#envelope-structure)
2. [Agent APIs](#agent-apis)
   - [RAG Agent](#rag-agent)
   - [Copywriter Agent](#copywriter-agent)
   - [Persistence Agent](#persistence-agent)
3. [Error Handling](#error-handling)
4. [Integration Examples](#integration-examples)
5. [Best Practices](#best-practices)

---

## Envelope Structure

All messages in the agentic system use a universal envelope format defined in `agent/utils/typed_envelope.py`.

### Core Envelope

```python
class Envelope(BaseModel):
    metadata: Metadata
    payload: Dict[str, Any]
    status: Status
    error: Optional[str] = None
    error_code: Optional[str] = None
    warnings: List[str] = []
    trace: Optional[TraceSpan] = None
```

### Metadata

```python
class Metadata(BaseModel):
    # Identity
    message_id: str  # Auto-generated UUID
    task_id: str     # Client-provided task identifier
    correlation_id: Optional[str]  # Links related messages

    # Routing
    source: str  # e.g., "orchestrator", "rag_worker"
    destination: Optional[str]  # Target stream/worker

    # Timing
    created_at: datetime  # Auto-set to UTC now
    processed_at: Optional[datetime]

    # Context
    req_id: Optional[str]      # Original client request ID
    user_id: Optional[str]     # End user identifier
    tenant_id: Optional[str]   # Multi-tenancy isolation
    campaign_id: Optional[str] # Campaign tracking

    # Operations
    priority: Priority  # LOW, NORMAL, HIGH, CRITICAL
    retry_count: int = 0
    max_retries: int = 3
    tags: Dict[str, str] = {}
```

### Status Enum

```python
class Status(str, Enum):
    PENDING = "pending"  # Task not yet processed
    SUCCESS = "success"  # Task completed successfully
    ERROR = "error"      # Task failed
    RETRY = "retry"      # Retrying after failure
    DLQ = "dlq"          # Sent to dead letter queue
```

### Priority Enum

```python
class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"
```

### Trace Span (Optional)

```python
class TraceSpan(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    service_name: str
    duration_ms: Optional[float]
```

---

## Agent APIs

### RAG Agent

Retrieves records from the database based on query specifications. Supports filtering, pagination, and forwarding results to other agents.

#### Task Payload Schema

```python
from agent.schemas import RAGTaskPayload, QuerySpec, ForwardSpec, FilterOperator

class RAGTaskPayload(BaseModel):
    query: QuerySpec
    forward_to: Optional[ForwardSpec] = None
    cache_key: Optional[str] = None
    timeout_ms: int = 30000
```

#### QuerySpec

```python
class QuerySpec(BaseModel):
    table: str                          # Target table (alphanumeric + underscore)
    filters: Dict[str, Any] = {}        # Filter conditions
    limit: int = 100                    # Max rows (1-10000)
    offset: int = 0                     # Pagination offset
    columns: Optional[List[str]] = None # Columns to select (None = all)
    order_by: Optional[str] = None      # Sort column
    descending: bool = False            # Sort direction
```

**Filter Operators:**

```python
class FilterOperator(str, Enum):
    EQ = "eq"              # Equal
    NEQ = "neq"            # Not equal
    GT = "gt"              # Greater than
    GTE = "gte"            # Greater than or equal
    LT = "lt"              # Less than
    LTE = "lte"            # Less than or equal
    IN = "in"              # In list
    NOT_IN = "not_in"      # Not in list
    LIKE = "like"          # Pattern match (case-sensitive)
    ILIKE = "ilike"        # Pattern match (case-insensitive)
    IS_NULL = "is_null"    # Is NULL
    IS_NOT_NULL = "is_not_null"  # Is NOT NULL
```

**Filter Examples:**

```python
# Simple equality
filters = {"status": "active"}

# Operator syntax
filters = {
    "email": {"ilike": "%@example.com"},
    "created_at": {"gte": "2024-01-01"},
    "age": {"in": [25, 30, 35]}
}
```

#### ForwardSpec

```python
class ForwardSpec(BaseModel):
    agent: str                              # Target agent (e.g., "copywriter")
    campaign_context: Dict[str, Any] = {}   # Campaign metadata
    instructions: Dict[str, Any] = {}       # Agent-specific instructions
    transform: Optional[str] = None         # Data transformation
```

#### Result Payload Schema

```python
class RAGResultPayload(BaseModel):
    records: List[Dict[str, Any]] = []
    count: int                              # Number of records returned
    table: str                              # Source table
    query_time_ms: Optional[float] = None
    cached: bool = False
    provenance: Optional[List[RecordProvenance]] = None
```

#### RecordProvenance

```python
class RecordProvenance(BaseModel):
    source: str                             # e.g., "supabase.leads"
    row_id: Any                             # Primary key
    row_hash: str                           # SHA256 of record
    retrieved_at: str                       # ISO 8601 timestamp
    query_filters: Dict[str, Any] = {}
    raw_row: Optional[Dict[str, Any]] = None
```

#### Example Task

```json
{
  "metadata": {
    "task_id": "rag-001",
    "source": "orchestrator",
    "destination": "rag:tasks",
    "campaign_id": "campaign-123",
    "priority": "normal"
  },
  "payload": {
    "query": {
      "table": "leads",
      "filters": {
        "email": { "ilike": "%@example.com" },
        "created_at": { "gte": "2024-01-01" }
      },
      "limit": 50,
      "order_by": "created_at",
      "descending": true
    },
    "forward_to": {
      "agent": "copywriter",
      "campaign_context": {
        "campaign_id": "campaign-123",
        "variant": "A"
      },
      "instructions": {
        "template": "followup_email",
        "tone": "professional"
      }
    }
  },
  "status": "pending"
}
```

#### Example Result

```json
{
  "metadata": {
    "message_id": "msg-abc123",
    "task_id": "rag-001",
    "correlation_id": "corr-xyz",
    "source": "rag_worker",
    "campaign_id": "campaign-123"
  },
  "payload": {
    "records": [
      {
        "id": "lead-123",
        "email": "john@example.com",
        "name": "John Doe",
        "company": "Acme Corp"
      }
    ],
    "count": 1,
    "table": "leads",
    "query_time_ms": 45.2,
    "cached": false
  },
  "status": "success"
}
```

---

### Copywriter Agent

Generates personalized copy (emails, messages) for leads using AI language models.

#### Task Payload Schema

```python
from agent.schemas import (
    CopywriterTaskPayload, LeadData, CampaignContext,
    CopyInstructions, CopyTone, CopyTemplate
)

class CopywriterTaskPayload(BaseModel):
    lead_data: LeadData
    campaign_context: CampaignContext
    instructions: CopyInstructions
    previous_interactions: List[Dict[str, Any]] = []
    timeout_ms: int = 60000
```

#### LeadData

```python
class LeadData(BaseModel):
    id: str
    email: Optional[str] = None
    name: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    industry: Optional[str] = None
    custom_fields: Dict[str, Any] = {}
```

#### CampaignContext

```python
class CampaignContext(BaseModel):
    campaign_id: str
    variant: Optional[str] = None           # A/B test variant (A, B, etc.)
    sequence_step: int = 1                  # Step in email sequence
    product_name: Optional[str] = None
    value_proposition: Optional[str] = None
    call_to_action: Optional[str] = None
    custom_variables: Dict[str, str] = {}
```

#### CopyInstructions

```python
class CopyInstructions(BaseModel):
    template: CopyTemplate
    tone: CopyTone = CopyTone.PROFESSIONAL
    word_count: Optional[int] = None        # 10-5000
    include_subject: bool = True
    personalization_level: int = 2          # 1-5 (1=generic, 5=highly personalized)
    constraints: List[str] = []
```

**Copy Tones:**

```python
class CopyTone(str, Enum):
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    FRIENDLY = "friendly"
    FORMAL = "formal"
    ENTHUSIASTIC = "enthusiastic"
    PERSUASIVE = "persuasive"
```

**Copy Templates:**

```python
class CopyTemplate(str, Enum):
    COLD_EMAIL = "cold_email"
    FOLLOWUP_EMAIL = "followup_email"
    SMS = "sms"
    LINKEDIN_MESSAGE = "linkedin_message"
    CUSTOM = "custom"
```

#### Result Payload Schema

```python
class CopywriterResultPayload(BaseModel):
    generated_copy: GeneratedCopy
    lead_id: str
    campaign_id: str
    variant: Optional[str] = None
    generation_time_ms: Optional[float] = None
    model_used: Optional[str] = None        # e.g., "gpt-4", "claude-3"
    tokens_used: Optional[int] = None
    quality_score: Optional[float] = None   # 0.0-1.0
```

#### GeneratedCopy

```python
class GeneratedCopy(BaseModel):
    subject: Optional[str] = None
    body: str                               # Min 10 characters
    preview_text: Optional[str] = None
    word_count: int
    personalization_tokens: List[str] = []  # e.g., ["{{name}}", "{{company}}"]
```

#### Example Task

```json
{
  "metadata": {
    "task_id": "copy-001",
    "source": "rag_worker",
    "correlation_id": "corr-xyz",
    "campaign_id": "campaign-123",
    "priority": "high"
  },
  "payload": {
    "lead_data": {
      "id": "lead-123",
      "email": "john@example.com",
      "name": "John Doe",
      "company": "Acme Corp",
      "title": "VP of Engineering"
    },
    "campaign_context": {
      "campaign_id": "campaign-123",
      "variant": "A",
      "sequence_step": 1,
      "product_name": "AI Platform",
      "value_proposition": "Automate 80% of customer support",
      "call_to_action": "Schedule a demo"
    },
    "instructions": {
      "template": "cold_email",
      "tone": "professional",
      "word_count": 150,
      "personalization_level": 4,
      "constraints": ["no pricing", "mention recent funding"]
    }
  },
  "status": "pending"
}
```

#### Example Result

```json
{
  "metadata": {
    "message_id": "msg-def456",
    "task_id": "copy-001",
    "correlation_id": "corr-xyz",
    "source": "copywriter_worker",
    "campaign_id": "campaign-123"
  },
  "payload": {
    "generated_copy": {
      "subject": "Quick question about Acme Corp's engineering workflow",
      "body": "Hi John,\n\nI noticed Acme Corp recently raised Series B funding...",
      "preview_text": "Congrats on the recent funding round",
      "word_count": 147,
      "personalization_tokens": ["{{name}}", "{{company}}"]
    },
    "lead_id": "lead-123",
    "campaign_id": "campaign-123",
    "variant": "A",
    "generation_time_ms": 3200.5,
    "model_used": "gpt-4",
    "tokens_used": 450,
    "quality_score": 0.87
  },
  "status": "success"
}
```

---

### Persistence Agent

Writes data to the database with support for insert, update, upsert, and delete operations.

#### Task Payload Schema

```python
from agent.schemas import (
    PersistenceTaskPayload, WriteSpec, ValidationRule,
    WriteOperation, ConflictResolution
)

class PersistenceTaskPayload(BaseModel):
    write: WriteSpec
    validation_rules: List[ValidationRule] = []
    timeout_ms: int = 30000
    atomic: bool = True                     # Use transaction
    dry_run: bool = False                   # Validate without writing
```

#### WriteSpec

```python
class WriteSpec(BaseModel):
    table: str                              # Target table
    operation: WriteOperation
    data: List[Dict[str, Any]]              # Min 1 record
    conflict_columns: Optional[List[str]] = None  # For upsert
    conflict_resolution: ConflictResolution = ConflictResolution.ERROR
    returning: Optional[List[str]] = None   # Columns to return
```

**Write Operations:**

```python
class WriteOperation(str, Enum):
    INSERT = "insert"
    UPDATE = "update"
    UPSERT = "upsert"
    DELETE = "delete"
```

**Conflict Resolution:**

```python
class ConflictResolution(str, Enum):
    ERROR = "error"    # Fail on conflict
    IGNORE = "ignore"  # Skip conflicting rows
    UPDATE = "update"  # Update on conflict
    MERGE = "merge"    # Merge fields on conflict
```

#### ValidationRule

```python
class ValidationRule(BaseModel):
    field: str                              # Field to validate
    rule: str                               # e.g., "required", "email", "min_length"
    params: Dict[str, Any] = {}
    error_message: Optional[str] = None
```

#### Result Payload Schema

```python
class PersistenceResultPayload(BaseModel):
    write_result: WriteResult
    table: str
    write_time_ms: Optional[float] = None
    validation_errors: List[str] = []
    dry_run: bool = False
    transaction_id: Optional[str] = None
```

#### WriteResult

```python
class WriteResult(BaseModel):
    operation: WriteOperation
    rows_affected: int
    rows_returned: Optional[List[Dict[str, Any]]] = None
    conflicts_detected: int = 0
    conflicts_resolved: int = 0
    skipped_rows: int = 0
```

#### Example Task

```json
{
  "metadata": {
    "task_id": "persist-001",
    "source": "copywriter_worker",
    "correlation_id": "corr-xyz",
    "campaign_id": "campaign-123",
    "priority": "normal"
  },
  "payload": {
    "write": {
      "table": "generated_copy",
      "operation": "upsert",
      "data": [
        {
          "id": "copy-abc123",
          "lead_id": "lead-123",
          "campaign_id": "campaign-123",
          "subject": "Quick question...",
          "body": "Hi John...",
          "created_at": "2024-01-15T10:30:00Z"
        }
      ],
      "conflict_columns": ["id"],
      "conflict_resolution": "update",
      "returning": ["id", "updated_at"]
    },
    "validation_rules": [
      {
        "field": "lead_id",
        "rule": "required",
        "error_message": "lead_id is required"
      }
    ],
    "atomic": true,
    "dry_run": false
  },
  "status": "pending"
}
```

#### Example Result

```json
{
  "metadata": {
    "message_id": "msg-ghi789",
    "task_id": "persist-001",
    "correlation_id": "corr-xyz",
    "source": "persistence_worker",
    "campaign_id": "campaign-123"
  },
  "payload": {
    "write_result": {
      "operation": "upsert",
      "rows_affected": 1,
      "rows_returned": [
        {
          "id": "copy-abc123",
          "updated_at": "2024-01-15T10:30:05Z"
        }
      ],
      "conflicts_detected": 1,
      "conflicts_resolved": 1,
      "skipped_rows": 0
    },
    "table": "generated_copy",
    "write_time_ms": 125.3,
    "validation_errors": [],
    "dry_run": false,
    "transaction_id": "txn-xyz123"
  },
  "status": "success"
}
```

---

## Error Handling

### Error Codes

Error codes follow PostgreSQL conventions where applicable:

| Code               | Meaning                     | Retry? | Example                        |
| ------------------ | --------------------------- | ------ | ------------------------------ |
| `23505`            | Duplicate key violation     | No     | Unique constraint violation    |
| `23503`            | Foreign key violation       | No     | Referenced row doesn't exist   |
| `42P01`            | Undefined table             | No     | Table doesn't exist            |
| `42703`            | Undefined column            | No     | Column doesn't exist           |
| `22P02`            | Invalid text representation | No     | Type conversion error          |
| `57014`            | Query canceled              | Yes    | Timeout or manual cancellation |
| `53300`            | Too many connections        | Yes    | Connection pool exhausted      |
| `TIMEOUT`          | Operation timeout           | Yes    | Exceeded timeout_ms            |
| `VALIDATION_ERROR` | Schema validation failed    | No     | Invalid payload structure      |
| `NETWORK_ERROR`    | Network failure             | Yes    | Redis/DB connection lost       |

### Error Envelope

When a task fails, the envelope's `error` and `error_code` fields are populated:

```json
{
  "metadata": {
    "message_id": "msg-error123",
    "task_id": "copy-001",
    "source": "copywriter_worker",
    "retry_count": 1,
    "max_retries": 3
  },
  "payload": {
    /* original payload */
  },
  "status": "error",
  "error": "LLM API rate limit exceeded",
  "error_code": "429",
  "warnings": ["Token budget 90% consumed"]
}
```

### Retry Logic

Errors are classified into categories for retry decisions:

- **Transient**: Network errors, timeouts, rate limits → **Retry**
- **Permanent**: Validation errors, constraint violations → **DLQ**
- **Duplicate**: Already processed → **Skip**
- **Validation**: Schema/data issues → **DLQ**

See `docs/INCIDENT_PLAYBOOKS.md` for recovery procedures.

---

## Integration Examples

### Python Client

```python
from agent.utils.typed_envelope import task
from agent.schemas import RAGTaskPayload, QuerySpec
from agent.tools.redis.client import RedisPubSub
from agent.tools.redis import config as rconf

# Create Redis client
redis = RedisPubSub()
stream_name = rconf.full_key("rag:tasks")

# Create task payload
payload = RAGTaskPayload(
    query=QuerySpec(
        table="leads",
        filters={"status": "active"},
        limit=100
    )
)

# Validate payload
validated = payload.model_dump()

# Create envelope
envelope = task(
    source="api_client",
    task_id="api-task-001",
    payload=validated,
    destination="rag:tasks",
    priority="high",
    user_id="user-123",
    campaign_id="camp-456"
)

# Send to stream
message_id = redis.client.xadd(stream_name, {"data": envelope.to_json()})
print(f"Sent task: {message_id}")

# Wait for result
result_stream = rconf.full_key("rag:results")
messages = redis.client.xread({result_stream: "0-0"}, count=1, block=5000)

if messages:
    for stream, entries in messages:
        for msg_id, fields in entries:
            from agent.utils.typed_envelope import from_redis_message
            result_envelope = from_redis_message(fields)

            if result_envelope.status == "success":
                print(f"Records: {result_envelope.payload['count']}")
            else:
                print(f"Error: {result_envelope.error}")
```

### TypeScript/Node.js Client (Future Codegen)

```typescript
import { createClient } from "@agency/agentic-client";
import { RAGTaskPayload, QuerySpec } from "@agency/agentic-schemas";

const client = createClient({
  redis: { host: "localhost", port: 6379 },
});

// Type-safe payload construction
const payload: RAGTaskPayload = {
  query: {
    table: "leads",
    filters: { status: "active" },
    limit: 100,
  },
};

// Send task
const result = await client.rag.query(payload, {
  taskId: "api-task-001",
  priority: "high",
  userId: "user-123",
});

console.log(`Retrieved ${result.payload.count} records`);
```

---

## Best Practices

### 1. Always Set Task ID

Use meaningful, unique task IDs for tracking and debugging:

```python
task_id = f"rag-{campaign_id}-{timestamp}-{uuid.uuid4().hex[:8]}"
```

### 2. Use Correlation IDs for Multi-Step Workflows

Link related messages across agents:

```python
correlation_id = str(uuid.uuid4())  # Generate once
# Use same correlation_id for RAG → Copywriter → Persistence
```

### 3. Set Appropriate Priorities

Reserve `CRITICAL` for time-sensitive, business-critical tasks:

- `LOW`: Batch jobs, analytics
- `NORMAL`: Standard campaigns
- `HIGH`: User-triggered actions
- `CRITICAL`: Real-time responses, escalations

### 4. Validate Payloads Before Sending

Use schema validation to catch errors early:

```python
from agent.schemas import RAGTaskPayload, validate_payload

try:
    validated = validate_payload(raw_data, RAGTaskPayload)
except ValidationError as e:
    print(f"Invalid payload: {e}")
```

### 5. Handle Timeouts

Set realistic timeouts based on operation complexity:

- RAG queries: 10-30 seconds
- Copywriter (LLM calls): 30-60 seconds
- Persistence writes: 10-30 seconds

### 6. Monitor DLQ

Check dead letter queues regularly:

```bash
python scripts/ops_cli.py dlq inspect rag:dlq
```

### 7. Use Tags for Filtering

Add custom tags for filtering and analytics:

```python
tags = {
    "environment": "production",
    "ab_test": "variant_a",
    "source_campaign": "email_blast_jan"
}
```

### 8. Leverage Tracing

Enable distributed tracing for complex workflows:

```python
from agent.utils.tracing import get_tracer

tracer = get_tracer("my_service")
with tracer.start_as_current_span("custom_operation"):
    # Your code here
```

See `docs/updates/TRACING_SETUP.md` for details.

### 9. Set Tenant ID for Multi-Tenancy

Always include tenant_id when operating in multi-tenant mode:

```python
metadata_overrides = {"tenant_id": "tenant-abc123"}
```

### 10. Use Dry Run for Testing

Test persistence operations without modifying data:

```python
payload = PersistenceTaskPayload(
    write=WriteSpec(...),
    dry_run=True  # Validates without writing
)
```

---

## See Also

- [Type Safety Guide](../TYPE_SAFETY.md) - Pydantic schema details
- [Tracing Setup](../updates/TRACING_SETUP.md) - Distributed tracing
- [Incident Playbooks](../INCIDENT_PLAYBOOKS.md) - Error recovery procedures
- [Enhancements](../updates/ENHANCEMENTS.md) - System changes and ops notes

---

**Last Updated:** October 26, 2025  
**Version:** 1.0.0
