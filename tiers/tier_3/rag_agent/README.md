# RAG Agent - Retrieval Augmented Generation

**Tier 3 Operational Agent** | **READ ONLY Database Retrieval Specialist**

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Database Schema](#database-schema)
4. [Tools Reference](#tools-reference)
5. [Query Strategies](#query-strategies)
6. [Usage Examples](#usage-examples)
7. [Configuration](#configuration)
8. [Testing](#testing)

---

## Overview

### Purpose

The RAG Agent is a **pure retrieval specialist** responsible for querying the Supabase database. It provides READ ONLY access to 4 core tables: `staging_leads`, `leads`, `conversations`, and `messages`.

### Key Characteristics

- ✅ **Pure Retrieval**: READ ONLY - no database writes
- ✅ **Schema-Specific Tools**: 12 specialized retrieval tools
- ✅ **JSONB Support**: Python-side filtering for enriched data fields
- ✅ **Validation System**: Entity completeness scoring (0.0-1.0)
- ✅ **Optional Vector Search**: Embedding-based similarity search
- ✅ **Minimal Payloads**: Returns only essential fields
- ✅ **Production Ready**: Retry, timeout, checkpointing

### What It Does NOT Do

- ❌ **No Database Writes**: Writes handled by Persistence Agent
- ❌ **No External APIs**: Enrichment handled by External Service Department
- ❌ **No Data Mutations**: Strictly read-only operations

---

## Architecture

staging_leads → leads → conversations → messages
     ↓            ↓           ↓            ↓
  (queue)    (qualified)  (threads)   (replies)

  These 4 tables are the core data flow for:

Finding leads to enrich
Checking enrichment history
Monitoring conversations
Analyzing replies/sentiment

┌─────────────────────────────────────────────────────────────────┐
│                         RAG AGENT                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   HARNESS    │    │  DEEP AGENT  │    │   SUPABASE   │      │
│  │              │    │   (LLM)      │    │   ADAPTER    │      │
│  │ • Validation │───▶│ • Reasoning  │───▶│ • query()    │      │
│  │ • Fast-fail  │    │ • Tool calls │    │ • read()     │      │
│  │ • Retries    │    │ • Chaining   │    │              │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                    │              │
│         ▼                   ▼                    ▼              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    12 TOOLS                              │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │ staging_leads: 3 tools (pending, ready, by_id)          │   │
│  │ leads:         4 tools (search, jsonb, history, by_id)  │   │
│  │ conversations: 2 tools (by_lead, by_id)                 │   │
│  │ messages:      2 tools (by_conv, latest_replies)        │   │
│  │ validation:    1 tool (completeness check)              │   │
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
              │   MINIMAL RESULT UPSTREAM     │
              │   {status, data, duration_ms} │
              └───────────────────────────────┘


### Component Stack

```
┌─────────────────────────────────────────────────────────┐
│ Redis Streams                                           │
│ IN:  {tenant}:agents:rag:tasks                          │
│ OUT: {tenant}:agents:rag:results                        │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│ RAG Consumer (consumer.py)                              │
│ - Envelope parsing                                      │
│ - Checkpointing                                         │
│ - Auto-claim pending messages                           │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│ RAG Agent Harness (rag_agent_harness.py)                │
│ - 3 retries, 90s timeout                                │
│ - 500 req/hr quota (production)                         │
│ - Redis checkpointing                                   │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│ RAG Agent (rag_agent.py)                                │
│ - Deep Agent with 12 retrieval tools                    │
│ - Validation (completeness scoring)                     │
│ - Direct Supabase access (READ ONLY)                    │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│ SupabaseAdapter                                         │
│ (services/persistence/adapters/supabase_adapter.py)     │
│ - read(table, id_value)                                 │
│ - query(table, filters, limit, order_by, descending)    │
│ - Note: No JSONB operators (Python-side filtering)      │
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

### Separation of Concerns

| Component | Responsibility |
|-----------|----------------|
| **RAG Agent** | ✅ Retrieve from Supabase<br>✅ Validate payloads<br>✅ Vector search (optional) |
| **Persistence Agent** | ✅ Write to Supabase<br>✅ Update records<br>✅ Batch operations |
| **External Enrichment** | ✅ Crunchbase API<br>✅ LinkedIn API<br>✅ Data enrichment |

---

## Database Schema

### 1. staging_leads (22 fields)

**Purpose:** Pre-qualification queue for lead validation

**Core Fields:**
- `id` (uuid, PK)
- `email`, `first_name`, `last_name`, `company`, `title`
- `validation_status` (null | 'pending' | 'complete' | 'failed')
- `completeness_score` (float 0.0-1.0)
- `source` (string - lead origin)
- `created_at`, `updated_at`

**Query Patterns:**
```python
# FIFO queue (oldest first, pending enrichment)
filters = {"validation_status": None}
order_by = "created_at", descending = False

# Promotion ready (validated + high quality)
filters = {"validation_status": "complete"}
# Python filter: completeness_score >= 0.7
```

---

### 2. leads (27 fields)

**Purpose:** Qualified leads with enrichment data

**Core Fields:**
- `id` (uuid, PK)
- `email`, `first_name`, `last_name`, `company`, `title`
- `status` ('active' | 'contacted' | 'converted' | 'unqualified')
- `qualification_score` (int 0-100)
- `campaign_id` (uuid, FK)
- `raw_data` (jsonb) - **Enriched API data**
- `created_at`, `updated_at`

**JSONB Structure (raw_data):**
```json
{
  "industry": "SaaS",
  "funding_stage": "Series A",
  "employee_count": 50,
  "location": "San Francisco, CA",
  "crunchbase_data": {...},
  "linkedin_data": {...},
  "enriched_at": "2025-11-30T10:00:00Z"
}
```

**Query Patterns:**
```python
# Standard fields: Direct SQL
filters = {"email": "john@example.com", "status": "active"}

# JSONB fields: Python-side filtering
# 1. Query up to 500 records
# 2. Filter raw_data in Python
```

---

### 3. conversations (7 fields)

**Purpose:** Email thread containers

**Core Fields:**
- `id` (uuid, PK)
- `lead_id` (uuid, FK)
- `subject` (email subject)
- `status` ('active' | 'closed' | 'archived')
- `embedding` (vector - optional)
- `created_at`, `updated_at`

---

### 4. messages (7 fields)

**Purpose:** Individual email messages

**Core Fields:**
- `id` (uuid, PK)
- `conversation_id` (uuid, FK)
- `direction` ('inbound' | 'outbound')
- `content` (email body)
- `sentiment_score` (float -1.0 to 1.0)
- `created_at`, `updated_at`

---

## Tools Reference

### Summary

| Category | Tool Count | Tables |
|----------|------------|--------|
| Staging Leads | 3 | staging_leads |
| Leads | 4 | leads |
| Conversations | 2 | conversations |
| Messages | 2 | messages |
| Validation | 1 | all entities |
| **Total** | **12** | **4 tables** |

---

### Staging Leads Tools (3)

#### 1. `get_staging_leads_pending_enrichment`

**Purpose:** FIFO queue of leads needing enrichment

**Parameters:**
- `limit` (int, default 50, max 500)

**Returns:**
```json
{
  "status": "success",
  "records": [...],
  "count": 25
}
```

**Use Case:** Pull next batch for enrichment processing

---

#### 2. `get_staging_leads_promotion_ready`

**Purpose:** Validated leads ready to promote

**Parameters:**
- `limit` (int, default 50, max 500)

**Returns:**
```json
{
  "status": "success",
  "records": [...],
  "count": 10
}
```

**Criteria:**
- `validation_status = 'complete'`
- `completeness_score >= 0.7`

---

#### 3. `get_staging_lead_by_id`

**Purpose:** Single record retrieval

**Parameters:**
- `lead_id` (uuid)

**Returns:**
```json
{
  "status": "success",
  "record": {...}
}
```

---

### Leads Tools (4)

#### 4. `search_leads`

**Purpose:** Search by standard fields (non-JSONB)

**Parameters:**
- `email` (string, optional)
- `company` (string, optional)
- `title` (string, optional)
- `status` (string, optional)
- `min_score` (float, optional)
- `campaign_id` (uuid, optional)
- `limit` (int, default 50, max 500)

**Logic:**
- All filters combine with AND
- Direct SQL filtering
- Python filter for `min_score`

**Example:**
```python
search_leads(
    email="john@example.com",
    status="active",
    min_score=70.0,
    limit=10
)
```

---

#### 5. `search_leads_by_enriched_data`

**Purpose:** Search JSONB enriched data

**Parameters:**
- `industry` (string, optional)
- `funding_stage` (string, optional)
- `min_employee_count` (int, optional)
- `max_employee_count` (int, optional)
- `location` (string, optional)
- `limit` (int, default 50, max 500)

**Logic (JSONB Limitation):**
1. Query up to 500 leads (broad)
2. Python-side filter on `raw_data`
3. Return matches up to limit

**Example:**
```python
search_leads_by_enriched_data(
    industry="SaaS",
    min_employee_count=50,
    location="San Francisco",
    limit=20
)
```

---

#### 6. `check_lead_enrichment_history`

**Purpose:** Avoid duplicate API calls

**Parameters:**
- `lead_id` (uuid)

**Returns:**
```json
{
  "status": "success",
  "enriched": true,
  "sources": ["crunchbase", "linkedin"],
  "last_enriched_at": "2025-11-30T10:00:00Z",
  "raw_data_keys": ["industry", "funding_stage"]
}
```

**Use Case:** Check before calling external APIs

---

#### 7. `get_lead_by_id`

**Purpose:** Single lead retrieval

**Parameters:**
- `lead_id` (uuid)

**Returns:**
```json
{
  "status": "success",
  "record": {...}
}
```

---

### Conversations Tools (2)

#### 8. `get_lead_conversations`

**Purpose:** All email threads for a lead

**Parameters:**
- `lead_id` (uuid)
- `limit` (int, default 50, max 100)

**Returns:**
```json
{
  "status": "success",
  "records": [
    {
      "id": "conv-uuid",
      "subject": "RE: Partnership",
      "status": "active",
      "message_count": 5,
      "created_at": "..."
    }
  ],
  "count": 3
}
```

**Enrichment:** Includes `message_count` per conversation

---

#### 9. `get_conversation_by_id`

**Purpose:** Single conversation retrieval

**Parameters:**
- `conversation_id` (uuid)

**Returns:**
```json
{
  "status": "success",
  "record": {..., "message_count": 5}
}
```

---

### Messages Tools (2)

#### 10. `get_conversation_messages`

**Purpose:** All messages in thread (chronological)

**Parameters:**
- `conversation_id` (uuid)
- `limit` (int, default 100, max 500)

**Returns:**
```json
{
  "status": "success",
  "records": [...],
  "count": 5
}
```

**Ordering:** Oldest first (chronological)

---

#### 11. `get_latest_lead_replies`

**Purpose:** Latest inbound messages from lead

**Parameters:**
- `lead_id` (uuid)
- `limit` (int, default 10, max 50)

**Returns:**
```json
{
  "status": "success",
  "records": [
    {
      "id": "msg-uuid",
      "direction": "inbound",
      "content": "Thanks for reaching out...",
      "sentiment_score": 0.8,
      "created_at": "..."
    }
  ],
  "count": 3
}
```

**Use Case:** Sentiment analysis, response monitoring

---

### Validation Tool (1)

#### 12. `validate_entity_payload_tool`

**Purpose:** Completeness scoring for entity data

**Parameters:**
- `entity_type` (string: 'lead', 'conversation', etc.)
- `payload` (dict)

**Returns:**
```json
{
  "is_valid": true,
  "completeness_score": 0.85,
  "can_use_deterministic_path": true,
  "needs_llm_repair": false,
  "is_hopeless": false,
  "errors": [],
  "warnings": [],
  "missing_required_fields": [],
  "present_fields": ["email", "first_name", "company"]
}
```

**Decision Gates:**
- ≥0.7: High quality (deterministic path)
- 0.3-0.7: Needs repair
- <0.3: Hopeless (reject)

---

## Query Strategies

### 1. Standard Field Queries (Direct SQL)

**Use When:** Querying non-JSONB fields

**Pattern:**
```python
filters = {
    "email": "john@example.com",
    "status": "active",
    "campaign_id": "uuid-here"
}

result = supabase.query(
    table="leads",
    filters=filters,
    limit=50,
    order_by="created_at",
    descending=True
)
```

**Advantages:**
- ✅ Fast SQL execution
- ✅ Database-side filtering
- ✅ Efficient for large datasets

---

### 2. JSONB Field Queries (Python-Side Filtering)

**Use When:** Querying `raw_data` JSONB fields

**Limitation:** SupabaseAdapter doesn't support JSONB operators yet

**Pattern:**
```python
# Step 1: Query broader pool (up to 500)
result = supabase.query(
    table="leads",
    filters={},  # No SQL filters
    limit=500,
    order_by="created_at",
    descending=True
)

# Step 2: Python-side filter
all_leads = result.get("data", [])
filtered_leads = []

for lead in all_leads:
    raw_data = lead.get("raw_data", {})
    
    # Check JSONB fields
    if raw_data.get("industry") == "SaaS":
        if raw_data.get("employee_count", 0) >= 50:
            filtered_leads.append(lead)
    
    if len(filtered_leads) >= limit:
        break
```

**Trade-offs:**
- ⚠️ Query 500 records max (pool size)
- ⚠️ Python-side filtering (memory)
- ✅ Flexible JSONB queries
- ✅ Works with adapter limitations

---

### 3. Enrichment History Checks

**Purpose:** Avoid duplicate external API calls

**Pattern:**
```python
# Check if lead was enriched before
result = check_lead_enrichment_history(lead_id="uuid")

if result["enriched"] and "crunchbase" in result["sources"]:
    # Skip Crunchbase call - already enriched
    pass
else:
    # Need enrichment - delegate to External Service
    pass
```

---

### 4. Latest Lead Replies

**Purpose:** Sentiment analysis, response monitoring

**Pattern:**
```python
# Get latest 10 inbound messages from lead
result = get_latest_lead_replies(lead_id="uuid", limit=10)

for message in result["records"]:
    sentiment = message.get("sentiment_score", 0.0)
    if sentiment < -0.5:
        # Negative sentiment - flag for review
        pass
```

---

## Usage Examples

### Example 1: Get Next Batch for Enrichment

```python
# Pull 50 oldest leads pending enrichment
result = get_staging_leads_pending_enrichment(limit=50)

for lead in result["records"]:
    # Process each lead
    lead_id = lead["id"]
    email = lead["email"]
    company = lead["company"]
    
    # Delegate to enrichment service
    ...
```

---

### Example 2: Search SaaS Companies with 50+ Employees

```python
# Search enriched data
result = search_leads_by_enriched_data(
    industry="SaaS",
    min_employee_count=50,
    limit=100
)

print(f"Found {result['count']} matching leads")

for lead in result["records"]:
    raw_data = lead.get("raw_data", {})
    print(f"{lead['company']}: {raw_data.get('employee_count')} employees")
```

---

### Example 3: Monitor Lead Engagement

```python
# Get all conversations for a lead
result = get_lead_conversations(lead_id="uuid", limit=10)

for conversation in result["records"]:
    conv_id = conversation["id"]
    message_count = conversation["message_count"]
    
    if message_count > 5:
        # High engagement - flag as hot lead
        print(f"Hot lead: {message_count} messages in thread")
```

---

### Example 4: Sentiment Analysis

```python
# Get latest replies from lead
result = get_latest_lead_replies(lead_id="uuid", limit=10)

sentiments = [msg.get("sentiment_score", 0.0) for msg in result["records"]]
avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0

if avg_sentiment >= 0.5:
    print("Positive engagement")
elif avg_sentiment <= -0.5:
    print("Negative engagement - review needed")
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

# RAG Agent configuration
RAG_MODEL=gpt-4o-mini  # OpenAI model for Deep Agent
RAG_QUOTA=500  # Requests per hour (production)
```

---

### Initialization

```python
import redis
from tiers.tier_3.rag_agent.rag_agent import RAGAgent

# Initialize Redis client
redis_client = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    decode_responses=True
)

# Initialize RAG Agent
rag_agent = RAGAgent(
    redis_client=redis_client,
    tenant_id="agentic-dev",
    model="gpt-4o-mini"
)

# Execute task
result = await rag_agent.execute(
    task_data_or_goal="Get pending staging leads",
    context={"limit": 50}
)
```

---

## Testing

### Unit Tests

```bash
# Run RAG agent tests
pytest tiers/tier_3/rag_agent/tests/ -v
```

### Integration Tests

```bash
# Run E2E flow test
python test_e2e_flow.py
```

### Manual Testing

```python
# Test individual tools
from tiers.tier_3.rag_agent.rag_agent import RAGAgent

rag = RAGAgent(redis_client, tenant_id="test")

# Test staging leads query
result = rag._create_get_staging_leads_pending_enrichment_tool()(limit=10)
print(result)

# Test lead search
result = rag._create_search_leads_tool()(
    email="john@example.com",
    status="active"
)
print(result)
```

---

## Health Check

```python
# Check RAG Agent health
result = await rag_agent.health_check()

print(result)
# {
#   "status": "healthy",
#   "agent": "rag",
#   "timestamp": "2025-11-30T10:00:00Z",
#   "components": {
#     "redis": "healthy",
#     "supabase": "healthy",
#     "embedding_pipeline": "healthy"
#   }
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

### Issue: "Retrieval tools disabled"

**Cause:** Supabase adapter initialization failed

**Solution:**
1. Check environment variables
2. Verify Supabase connection
3. Check logs for adapter init errors

---

### Issue: JSONB queries returning no results

**Cause:** Python-side filtering too restrictive

**Solution:**
1. Increase pool size (up to 500)
2. Broaden filter criteria
3. Check JSONB field names in `raw_data`

---

## Performance Optimization

### Limit Guidelines

| Operation | Recommended | Maximum |
|-----------|-------------|---------|
| Staging leads | 50 | 500 |
| Lead search | 50 | 500 |
| Conversations | 50 | 100 |
| Messages | 100 | 500 |
| Latest replies | 10 | 50 |

### Caching Strategy

- **Redis TTL:** 7 days for vector embeddings
- **Query caching:** In-run cache (filter+pagination key)
- **Avoid duplicate queries:** Check enrichment history first

---

## Migration Notes

### From Old RAG Agent (External API Version)

**Removed:**
- ❌ External API clients (Crunchbase, LinkedIn)
- ❌ Enrichment tools (enrich_entity_tool, etc.)
- ❌ Data repair tools (repair_entity_data_tool)
- ❌ Multi-step enrichment pipelines

**Added:**
- ✅ Direct Supabase access
- ✅ 12 schema-specific retrieval tools
- ✅ JSONB query support (Python-side)
- ✅ Enrichment history checking

**Migration Path:**
1. External API calls → Delegate to External Enrichment Service
2. Data writes → Delegate to Persistence Agent
3. Data retrieval → Use new RAG Agent tools

---

## Roadmap

### Phase 1 (Current)
- ✅ 4 core tables (staging_leads, leads, conversations, messages)
- ✅ 12 retrieval tools
- ✅ Validation system
- ✅ JSONB support (Python-side)

### Phase 2 (Future)
- ⏳ JSONB operators in SupabaseAdapter (database-side filtering)
- ⏳ Expand to all 11 tables
- ⏳ Advanced vector search (semantic similarity)
- ⏳ Query optimization (caching, indexing)

---

## Related Documentation

### Supabase Integration

For complete details on database authentication, RLS policies, and the SupabaseAdapter:

📖 **[Supabase Database Integration](../../../docs/architecture/supabase/DatabaseIntegration.md)**

Covers:
- 3-layer authentication stack (API Gateway → PostgreSQL GRANT → RLS)
- Agent permissions (`agent_reader` role for RAG Agent - read-only access)
- SupabaseAdapter query methods: `read()`, `query()`
- Table schemas and required fields
- Environment variables configuration

---

## References

- [Supabase Schema Reference](../../docs/SUPABASE_SCHEMA_REFERENCE.md)
- [MVP Implementation Plan](../../docs/MVP_IMPLEMENTATION_PLAN.md)
- [Agent Harness Documentation](../../core/harness/README.md)
- [Deep Agents Framework](https://github.com/deepagents/deepagents)

---

**Last Updated:** November 30, 2025  
**Version:** 2.0.0 (Refactored - Retrieval Specialist)
