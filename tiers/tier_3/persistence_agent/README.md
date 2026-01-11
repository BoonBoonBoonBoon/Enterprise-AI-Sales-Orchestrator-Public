# Persistence Agent - Database Write Specialist

**Tier 3 Operational Agent** | **WRITE ONLY Database Persistence**

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Write Tools Reference](#write-tools-reference)
4. [Usage Examples](#usage-examples)
5. [Configuration](#configuration)
6. [Comparison with RAG Agent](#comparison-with-rag-agent)

---

## Overview

### Purpose

The Persistence Agent is a **pure write specialist** responsible for creating and updating records in the Supabase database. It provides WRITE ONLY access to 4 core tables: `staging_leads`, `leads`, `conversations`, and `messages`.

### Key Characteristics

- ✅ **Pure Writes**: WRITE ONLY - no database reads
- ✅ **Schema-Specific Tools**: 12 specialized write tools
- ✅ **Validation Before Write**: Pre-write validation for data integrity
- ✅ **Batch Operations**: Efficient bulk inserts
- ✅ **Audit Logging**: Tracks all write operations
- ✅ **Minimal Payloads**: Returns only essential confirmation data
- ✅ **Production Ready**: Retry, timeout, checkpointing

### What It Does NOT Do

- ❌ **No Database Reads**: Reads handled by RAG Agent
- ❌ **No Data Queries**: Use RAG Agent for retrieval
- ❌ **No External APIs**: Strictly database writes

---

## Architecture

### Component Stack

```
┌─────────────────────────────────────────────────────────┐
│ Redis Streams                                           │
│ IN:  {tenant}:agents:persistence:tasks                  │
│ OUT: {tenant}:agents:persistence:results                │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│ Persistence Consumer (consumer.py)                      │
│ - Envelope parsing                                      │
│ - Checkpointing                                         │
│ - Auto-claim pending messages                           │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│ Persistence Agent Harness (persistence_agent_harness.py)│
│ - 3 retries, 90s timeout                                │
│ - Redis checkpointing                                   │
│ - Error recovery                                        │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│ Persistence Agent (persistence_agent.py)                │
│ - Deep Agent with 12 write tools                        │
│ - Validation before writes                              │
│ - Direct Supabase access (WRITE ONLY)                   │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│ SupabaseAdapter                                         │
│ (services/persistence/adapters/supabase_adapter.py)     │
│ - write(table, record)                                  │
│ - batch_write(table, records)                           │
│ - upsert(table, record, on_conflict)                    │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│ Supabase PostgreSQL (4 Core Tables)                     │
│ - staging_leads (22 fields) - Pre-qualification queue   │
│ - leads (27 fields) - Qualified leads + enrichment      │
│ - conversations (7 fields) - Email threads              │
│ - messages (7 fields) - Individual emails               │
└─────────────────────────────────────────────────────────┘
```

### Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    PERSISTENCE AGENT                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   HARNESS    │    │  DEEP AGENT  │    │   SUPABASE   │      │
│  │              │    │   (LLM)      │    │   ADAPTER    │      │
│  │ • Validation │───▶│ • Reasoning  │───▶│ • write()    │      │
│  │ • Fast-fail  │    │ • Tool calls │    │ • upsert()   │      │
│  │ • Retries    │    │ • Chaining   │    │ • batch()    │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                    │              │
│         ▼                   ▼                    ▼              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    12 WRITE TOOLS                        │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │ staging_leads: 3 tools (create, update, promote)        │   │
│  │ leads:         4 tools (create, update, enrich, link)   │   │
│  │ conversations: 2 tools (create, update_status)          │   │
│  │ messages:      2 tools (create, update_sentiment)       │   │
│  │ batch:         1 tool (batch_create_staging_leads)      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   4 SUPABASE TABLES                      │   │
│  │  staging_leads │ leads │ conversations │ messages        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │   WRITE CONFIRMATION          │
              │   {status, id, affected_rows} │
              └───────────────────────────────┘
```

### Separation of Concerns

| Component | Responsibility |
|-----------|----------------|
| **Persistence Agent** | ✅ Write to Supabase<br>✅ Validate before write<br>✅ Batch operations |
| **RAG Agent** | ✅ Read from Supabase<br>✅ Query data<br>✅ Search operations |
| **External Enrichment** | ✅ Crunchbase API<br>✅ LinkedIn API<br>✅ Data enrichment |

---

## Write Tools Reference

### Summary

| Category | Tool Count | Tables |
|----------|------------|--------|
| Staging Leads | 3 | staging_leads |
| Leads | 4 | leads |
| Conversations | 2 | conversations |
| Messages | 2 | messages |
| Batch Operations | 1 | staging_leads |
| **Total** | **12** | **4 tables** |

---

### Staging Leads Tools (3)

#### 1. `create_staging_lead`

**Purpose:** Create new lead in pre-qualification queue

**Parameters:**
- `email` (string, required) - Unique email address
- `first_name` (string, optional)
- `last_name` (string, optional)
- `company` (string, optional)
- `title` (string, optional)
- `source` (string, default: "manual")
- `**kwargs` - Additional fields

**Returns:**
```json
{
  "status": "success",
  "id": "uuid-here",
  "operation": "create",
  "affected_rows": 1
}
```

**Example:**
```python
create_staging_lead(
    email="john@acme.com",
    first_name="John",
    last_name="Doe",
    company="Acme Corp",
    title="CEO",
    source="website_form"
)
```

---

#### 2. `update_staging_lead`

**Purpose:** Update validation status and scores

**Parameters:**
- `lead_id` (uuid, required)
- `validation_status` (string: 'pending', 'complete', 'failed')
- `completeness_score` (float: 0.0-1.0)
- `**updates` - Additional fields to update

**Returns:**
```json
{
  "status": "success",
  "id": "uuid-here",
  "operation": "update",
  "affected_rows": 1
}
```

**Use Case:** After RAG Agent validates lead completeness

---

#### 3. `promote_staging_lead_to_lead`

**Purpose:** Promote validated staging lead to leads table

**Parameters:**
- `staging_lead_id` (uuid, required)
- `qualification_score` (int, default: 50)
- `campaign_id` (uuid, optional)

**Returns:**
```json
{
  "status": "success",
  "lead_id": "new-lead-uuid",
  "staging_lead_id": "staging-uuid",
  "operation": "promote",
  "affected_rows": 2
}
```

**Logic:**
1. Read staging lead data
2. Create lead record
3. Mark staging lead as "promoted"
4. Return both IDs

---

### Leads Tools (4)

#### 4. `create_lead`

**Purpose:** Create lead directly (bypass staging)

**Parameters:**
- `email` (string, required)
- `first_name`, `last_name`, `company`, `title` (optional)
- `status` (string, default: "active")
- `qualification_score` (int, default: 50)
- `campaign_id` (uuid, optional)
- `**kwargs` - Additional fields

**Returns:**
```json
{
  "status": "success",
  "id": "uuid-here",
  "operation": "create",
  "affected_rows": 1
}
```

**Use Case:** High-quality leads from trusted sources

---

#### 5. `update_lead`

**Purpose:** Update lead fields

**Parameters:**
- `lead_id` (uuid, required)
- `status` (string: 'active', 'contacted', 'converted', 'unqualified')
- `qualification_score` (int: 0-100)
- `**updates` - Additional fields

**Returns:**
```json
{
  "status": "success",
  "id": "uuid-here",
  "operation": "update",
  "affected_rows": 1
}
```

---

#### 6. `update_lead_enrichment_data`

**Purpose:** Update JSONB enrichment data

**Parameters:**
- `lead_id` (uuid, required)
- `enrichment_data` (dict) - Enrichment fields

**Returns:**
```json
{
  "status": "success",
  "id": "uuid-here",
  "operation": "enrich",
  "enrichment_keys": ["industry", "funding_stage"],
  "affected_rows": 1
}
```

**Example:**
```python
update_lead_enrichment_data(
    lead_id="uuid-here",
    enrichment_data={
        "industry": "SaaS",
        "funding_stage": "Series A",
        "employee_count": 50,
        "location": "San Francisco, CA"
    }
)
```

**Logic:**
1. Read current `raw_data` JSONB
2. Merge with new enrichment_data
3. Add `enriched_at` timestamp
4. Update record

---

#### 7. `link_lead_to_campaign`

**Purpose:** Link lead to campaign

**Parameters:**
- `lead_id` (uuid, required)
- `campaign_id` (uuid, required)

**Returns:**
```json
{
  "status": "success",
  "lead_id": "uuid",
  "campaign_id": "uuid",
  "operation": "link",
  "affected_rows": 1
}
```

---

### Conversations Tools (2)

#### 8. `create_conversation`

**Purpose:** Create new email thread

**Parameters:**
- `lead_id` (uuid, required)
- `subject` (string, required)
- `status` (string, default: "active")
- `**kwargs` - Additional fields

**Returns:**
```json
{
  "status": "success",
  "id": "conversation-uuid",
  "lead_id": "lead-uuid",
  "operation": "create",
  "affected_rows": 1
}
```

---

#### 9. `update_conversation_status`

**Purpose:** Update conversation status

**Parameters:**
- `conversation_id` (uuid, required)
- `status` (string: 'active', 'closed', 'archived')

**Returns:**
```json
{
  "status": "success",
  "id": "conversation-uuid",
  "operation": "update",
  "affected_rows": 1
}
```

---

### Messages Tools (2)

#### 10. `create_message`

**Purpose:** Create message in conversation

**Parameters:**
- `conversation_id` (uuid, required)
- `direction` (string: 'inbound' | 'outbound')
- `content` (string, required)
- `sentiment_score` (float, optional: -1.0 to 1.0)
- `**kwargs` - Additional fields

**Returns:**
```json
{
  "status": "success",
  "id": "message-uuid",
  "conversation_id": "conversation-uuid",
  "operation": "create",
  "affected_rows": 1
}
```

---

#### 11. `update_message_sentiment`

**Purpose:** Update sentiment analysis score

**Parameters:**
- `message_id` (uuid, required)
- `sentiment_score` (float: -1.0 to 1.0)

**Returns:**
```json
{
  "status": "success",
  "id": "message-uuid",
  "operation": "update",
  "affected_rows": 1
}
```

---

### Batch Operations (1)

#### 12. `batch_create_staging_leads`

**Purpose:** Bulk import staging leads

**Parameters:**
- `leads` (list of dicts, required)

**Returns:**
```json
{
  "status": "success",
  "created_count": 100,
  "operation": "batch_create",
  "affected_rows": 100
}
```

**Example:**
```python
batch_create_staging_leads(
    leads=[
        {
            "email": "john@acme.com",
            "first_name": "John",
            "company": "Acme"
        },
        {
            "email": "jane@beta.com",
            "first_name": "Jane",
            "company": "Beta Inc"
        }
        # ... up to 1000 records
    ]
)
```

---

## Usage Examples

### Example 1: Import Leads from CSV

```python
# Step 1: Batch create staging leads
result = batch_create_staging_leads(
    leads=[
        {"email": "john@acme.com", "first_name": "John", "company": "Acme"},
        {"email": "jane@beta.com", "first_name": "Jane", "company": "Beta"},
        # ... more leads
    ]
)

print(f"Created {result['created_count']} staging leads")

# Step 2: RAG Agent validates each lead
# (Separate process)

# Step 3: Promote validated leads
for staging_id in validated_lead_ids:
    result = promote_staging_lead_to_lead(
        staging_lead_id=staging_id,
        qualification_score=70
    )
    print(f"Promoted to lead: {result['lead_id']}")
```

---

### Example 2: Update Lead After Enrichment

```python
# External Enrichment Service returns data
enrichment = {
    "industry": "SaaS",
    "funding_stage": "Series A",
    "employee_count": 50,
    "location": "San Francisco, CA"
}

# Persistence Agent writes enrichment
result = update_lead_enrichment_data(
    lead_id="lead-uuid",
    enrichment_data=enrichment
)

print(f"Enriched fields: {result['enrichment_keys']}")
```

---

### Example 3: Create Conversation + First Message

```python
# Step 1: Create conversation
conv_result = create_conversation(
    lead_id="lead-uuid",
    subject="Partnership opportunity at Acme Corp"
)

conversation_id = conv_result["id"]

# Step 2: Create first message
msg_result = create_message(
    conversation_id=conversation_id,
    direction="outbound",
    content="Hi John, I wanted to reach out about..."
)

print(f"Conversation created: {conversation_id}")
print(f"First message: {msg_result['id']}")
```

---

### Example 4: Track Lead Engagement

```python
# Lead replies (inbound message)
msg_result = create_message(
    conversation_id="conv-uuid",
    direction="inbound",
    content="Thanks for reaching out! I'm interested...",
    sentiment_score=0.8  # Positive
)

# Update lead status
lead_result = update_lead(
    lead_id="lead-uuid",
    status="contacted",
    qualification_score=75
)
```

---

## Configuration

### Environment Variables

**Required:**
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-key  # or SUPABASE_KEY
```

**Optional:**
```bash
# Redis configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Persistence Agent configuration
PERSISTENCE_MODEL=gpt-4o-mini  # OpenAI model for Deep Agent
```

---

### Initialization

```python
import redis
from tiers.tier_3.persistence_agent.persistence_agent import PersistenceAgent

# Initialize Redis client
redis_client = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    decode_responses=True
)

# Initialize Persistence Agent
persistence_agent = PersistenceAgent(
    redis_client=redis_client,
    tenant_id="agentic-dev",
    model="gpt-4o-mini"
)

# Execute write task
result = await persistence_agent.execute(
    task_data_or_goal="Create staging lead for john@acme.com",
    context={"email": "john@acme.com", "company": "Acme"}
)
```

---

## Comparison with RAG Agent

| Aspect | RAG Agent | Persistence Agent |
|--------|-----------|-------------------|
| **Access** | READ ONLY | WRITE ONLY |
| **Operations** | Query, Search, Retrieve | Create, Update, Upsert |
| **Tool Count** | 12 retrieval tools | 12 write tools |
| **Tables** | 4 core tables | 4 core tables |
| **JSONB** | Python-side filtering | Merge + update |
| **Batch** | Query up to 500 | Write up to 1000 |
| **Returns** | Records + count | ID + affected_rows |

### Workflow Example

```
1. RAG Agent checks if lead exists
   ↓
2. RAG Agent validates lead completeness
   ↓
3. Persistence Agent creates staging lead
   ↓
4. RAG Agent queries pending staging leads
   ↓
5. External Service enriches lead
   ↓
6. Persistence Agent updates enrichment data
   ↓
7. RAG Agent checks enrichment history
   ↓
8. Persistence Agent promotes to leads table
```

---

## Testing

### Unit Tests

```bash
# Run Persistence Agent tests
pytest tiers/tier_3/persistence_agent/tests/ -v
```

### Manual Testing

```python
from tiers.tier_3.persistence_agent.persistence_agent import PersistenceAgent

persist = PersistenceAgent(redis_client, tenant_id="test")

# Test create
result = persist._create_create_staging_lead_tool()(
    email="test@example.com",
    first_name="Test"
)
print(result)

# Test update
result = persist._create_update_staging_lead_tool()(
    lead_id="uuid-here",
    validation_status="complete",
    completeness_score=0.9
)
print(result)
```

---

## Health Check

```python
# Check Persistence Agent health
result = await persistence_agent.health_check()

print(result)
# {
#   "status": "healthy",
#   "agent": "persistence",
#   "timestamp": "2025-11-30T10:00:00Z",
#   "components": {
#     "redis": "healthy",
#     "supabase": "healthy"
#   },
#   "write_tools": 12
# }
```

---

## Troubleshooting

### Issue: "SUPABASE_URL/SUPABASE_KEY not configured"

**Solution:** Set environment variables
```bash
export SUPABASE_URL=https://your-project.supabase.co
export SUPABASE_SERVICE_KEY=your-key
```

---

### Issue: "Write tools disabled"

**Cause:** Supabase adapter initialization failed

**Solution:**
1. Check environment variables
2. Verify Supabase connection
3. Check logs for adapter init errors

---

### Issue: Foreign key violations

**Cause:** Attempting to create conversation without valid lead_id

**Solution:**
1. Use RAG Agent to verify lead exists
2. Create lead first if needed
3. Check foreign key relationships

---

## Performance Optimization

### Write Guidelines

| Operation | Recommended | Maximum |
|-----------|-------------|---------|
| Single writes | < 10/sec | 50/sec |
| Batch writes | 100-500 | 1000 |
| Retry attempts | 3 | 5 |
| Timeout | 90s | 180s |

### Batch Best Practices

- **Use batch operations** for >10 records
- **Chunk large imports** (500-1000 per batch)
- **Validate before write** to avoid rollbacks
- **Monitor affected_rows** for confirmation

---

## Related Documentation

### Supabase Integration

For complete details on database authentication, RLS policies, and the SupabaseAdapter:

📖 **[Supabase Database Integration](../../../docs/architecture/supabase/DatabaseIntegration.md)**

Covers:
- 3-layer authentication stack (API Gateway → PostgreSQL GRANT → RLS)
- Agent permissions (`agent_writer` role for Persistence Agent)
- SupabaseAdapter CRUD methods: `write()`, `update()`, `delete()`, `batch_write()`
- Required fields for each table
- Foreign key dependencies
- Environment variables configuration

---

## References

- [RAG Agent Documentation](../rag_agent/README.md)
- [Supabase Schema Reference](../../../docs/SUPABASE_SCHEMA_REFERENCE.md)
- [MVP Implementation Plan](../../../docs/MVP_IMPLEMENTATION_PLAN.md)
- [Deep Agents Framework](https://github.com/deepagents/deepagents)

---

**Last Updated:** November 30, 2025  
**Version:** 2.0.0 (Refactored - Write Specialist)
