# RAG Architecture - Multi-Entity Retrieval & Enrichment

**Date:** November 23, 2025  
**Status:** Implemented (Skeleton)

## Overview

The RAG (Retrieval Augmented Generation) system provides intelligent data enrichment and similarity search across all business entities using a **deterministic-first** strategy with **LLM fallback** for malformed data.

## Supported Entity Types

| Entity Type | Table | Required Fields | Text Fields for Embedding | Use Cases |
|-------------|-------|-----------------|---------------------------|-----------|
| `lead` | `leads` | id, client_id, email, first_name, last_name | company_name, job_title, current_status, qualification_status | Lead enrichment, deduplication, scoring |
| `staging_lead` | `staging_leads` | id, client_id | company_name, industry, job_title, location | Pre-validation, enrichment queue |
| `conversation` | `conversations` | id, client_id, channel | summary, channel | Thread summarization, sentiment analysis |
| `message` | `messages` | id, conversation_id, sender_type | text_content | Semantic search, intent classification |
| `client` | `clients` | id, name | name | Client matching, account management |
| `campaign` | `campaigns` | id, client_id, campaign_name | campaign_name, campaign_type | Campaign analytics, performance tracking |
| `sequence` | `sequences` | id, client_id, sequence_name | sequence_name | Touchpoint optimization, A/B testing |
| `agent_task` | `agent_tasks` | task_id, client_id | N/A | Workflow tracking (not embedded) |
| `agent_subtask` | `agent_subtasks` | sub_task_id | N/A | Decomposition tracking (not embedded) |
| `audit_log` | `audit_log` | id, client_id | N/A | Compliance, debugging (not embedded) |

## Entity Lifecycle

```
┌─────────────────────────────────────────────────────────────────────┐
│                    1. INGEST & VALIDATE                              │
│                                                                       │
│  Orchestrator → RAG Agent                                            │
│  Envelope: { entity_type, payload, operation }                       │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ validate_entity_payload_tool(entity_type, payload)           │   │
│  │ Returns: { completeness_score, can_use_deterministic, ... } │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    2. ROUTING DECISION                               │
│                                                                       │
│  IF completeness >= 0.7:                                             │
│    → DETERMINISTIC PATH (Tier 2)                                     │
│                                                                       │
│  ELSE IF 0.3 < completeness < 0.7:                                   │
│    → LLM REPAIR PATH (Tier 3)                                        │
│                                                                       │
│  ELSE (completeness < 0.3):                                          │
│    → ERROR ENVELOPE (too incomplete)                                 │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│              3A. DETERMINISTIC PATH (Fast)                           │
│                                                                       │
│  ┌────────────────────────────────────────────┐                     │
│  │ index_entity_tool(entity_type, record)      │                     │
│  │  → Extract text fields                      │                     │
│  │  → Generate embedding (cached in Redis)     │                     │
│  │  → Upsert to VectorDB                       │                     │
│  └────────────────────────────────────────────┘                     │
│                    ↓                                                  │
│  ┌────────────────────────────────────────────┐                     │
│  │ enrich_entity_tool(entity_type, record)     │                     │
│  │  → Crunchbase lookup                        │                     │
│  │  → LinkedIn lookup                          │                     │
│  │  → Funding data (if requested)              │                     │
│  │  → Merge with confidence scoring            │                     │
│  └────────────────────────────────────────────┘                     │
│                    ↓                                                  │
│  ┌────────────────────────────────────────────┐                     │
│  │ Persistence Agent Write                     │                     │
│  │  → Store enriched_data in raw_data JSONB   │                     │
│  │  → Update enrichment_status = "completed"  │                     │
│  └────────────────────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│              3B. LLM REPAIR PATH (Fallback)                          │
│                                                                       │
│  ┌────────────────────────────────────────────┐                     │
│  │ repair_entity_data_tool(partial_payload)    │                     │
│  │  → Analyze missing required fields          │                     │
│  │  → Extract context from envelope metadata   │                     │
│  │  → LLM inference of missing values          │                     │
│  │  → Apply business rules (heuristics)        │                     │
│  └────────────────────────────────────────────┘                     │
│                    ↓                                                  │
│  ┌────────────────────────────────────────────┐                     │
│  │ Re-validate repaired payload                 │                     │
│  │  → completeness_score > 0.7?                │                     │
│  │    YES → Retry DETERMINISTIC PATH           │                     │
│  │    NO  → Return partial enrichment          │                     │
│  └────────────────────────────────────────────┘                     │
│                                                                       │
│  Max 2 repair attempts per payload                                   │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    4. RETRIEVAL & SEARCH                             │
│                                                                       │
│  ┌────────────────────────────────────────────┐                     │
│  │ retrieve_similar_entities_tool(query)       │                     │
│  │  → Generate query embedding                 │                     │
│  │  → Search VectorDB namespace (per entity)   │                     │
│  │  → Return matches with similarity scores    │                     │
│  └────────────────────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Two-Tier Execution Strategy

### Tier 1: Validation (Always First)

**Tool:** `validate_entity_payload_tool`

**Purpose:** Deterministically check data quality before processing.

**Returns:**
```json
{
  "is_valid": bool,
  "completeness_score": 0.0-1.0,
  "can_use_deterministic": bool,
  "needs_repair": bool,
  "is_hopeless": bool,
  "errors": [{"field": str, "message": str}],
  "missing_required_fields": [str]
}
```

### Tier 2: Deterministic Path (Fast & Cheap)

**When:** `completeness_score >= 0.7 AND no blocking errors`

**Tools:**
- `index_entity_tool` - Vector DB indexing
- `retrieve_similar_entities_tool` - Similarity search
- `enrich_entity_tool` - External API enrichment (Crunchbase, LinkedIn)

**Characteristics:**
- Fast execution (< 2s typical)
- Low cost (no LLM reasoning)
- High reliability (deterministic)
- Cached embeddings (7-day TTL in Redis)

### Tier 3: LLM Repair (Fallback)

**When:** `0.3 < completeness_score < 0.7 AND needs_repair = true`

**Tool:** `repair_entity_data_tool`

**Strategy:**
1. Analyze missing required fields
2. Extract context from envelope metadata (campaign_id, client_id, etc.)
3. Query Persistence Agent for related records (e.g., fetch client when repairing campaign)
4. Use LLM to infer missing values from available data
5. Apply business rules (e.g., `email = first_name.last_name@company.com`)
6. Return repaired payload with provenance

**Limits:**
- Max 2 repair attempts per payload
- If still invalid after 2 attempts → return error envelope

### Error Path

**When:** `completeness_score < 0.3` (too incomplete to repair)

**Action:** Return error envelope immediately with detailed validation report.

## Confidence Scoring Rubric

All enriched data includes a confidence score (0.0-1.0):

| Score | Meaning | Criteria |
|-------|---------|----------|
| 1.0 | Verified | Found in 3+ authoritative sources, no conflicts |
| 0.9 | Very High | Found in 2 sources, perfect match |
| 0.8 | High | Found in 2 sources, minor conflicts (e.g., outdated funding amount) |
| 0.7 | Good | Found in 1 authoritative source (Crunchbase, LinkedIn) |
| 0.6 | Moderate | Found in 1 source, reasonable quality |
| 0.5 | Fair | Single source, some uncertainty |
| 0.4 | Low | Inferred from partial data |
| 0.3 | Very Low | Estimated, high uncertainty |
| 0.2 | Unreliable | Guessed, do not use for decisions |
| 0.0 | No Data | No information available |

## Envelope Payload Contract

### Standard Fields (All Operations)

```python
{
  "entity_type": "lead",  # EntityType enum value
  "record_id": "uuid",    # Primary key
  "operation": "enrich",  # index, retrieve, enrich, repair
  "validation_status": {  # From validate_entity_payload_tool
    "is_valid": bool,
    "completeness_score": float,
    "missing_required_fields": [str]
  },
  "provenance": [         # List of data sources
    {
      "source": "crunchbase",
      "timestamp": "ISO",
      "confidence": 0.8
    }
  ],
  "repair_attempts": 0    # Count of LLM repair attempts
}
```

### Enrichment Operation Payload

```python
{
  "entity_type": "lead",
  "record": {
    "id": "uuid",
    "email": "john@acme.com",
    "first_name": "John",
    "last_name": "Doe",
    "company_name": "Acme Corp"
  },
  "enrichment_fields": [  # Which fields to enrich
    "company_funding",
    "linkedin_profile",
    "job_title_verified"
  ],
  "include_funding": true,
  "include_social": true
}
```

### Similarity Search Payload

```python
{
  "entity_type": "lead",
  "query": "AI startup CEO in San Francisco",
  "limit": 10,
  "filters": {
    "enrichment_status": "completed",
    "lead_score": {"$gte": 70}
  }
}
```

## Vector Database Architecture

### Namespace Isolation

Each entity type has its own namespace:
- `leads` - Lead records
- `conversations` - Conversation threads
- `messages` - Individual messages
- `campaigns` - Marketing campaigns
- etc.

**Rationale:** Prevents cross-entity contamination in similarity search.

### Metadata Indexing

Key fields stored as metadata for filtering:
- `entity_type` - Type of entity
- `record_id` - Primary key
- `tenant_id` - Multi-tenant isolation
- `indexed_at` - Timestamp
- Entity-specific fields (e.g., `enrichment_status`, `campaign_type`)

### Embedding Strategy

**Text Field Extraction:** Per entity type (see table above)

**Embedding Model:** OpenAI `text-embedding-3-small` (default)
- Dimension: 1536
- Cost: $0.00002 / 1K tokens
- Quality: High for business text

**Caching:** Redis, 7-day TTL
- Key: `{tenant}:embeddings:{text_hash}`
- Value: JSON array of floats

## Integration Points

### Leads Orchestrator Integration

```python
# Delegation pattern
envelope = create_task_envelope(
    source="leads_orchestrator",
    task_id=task_id,
    payload={
        "entity_type": "lead",
        "operation": "enrich",
        "record": lead_data,
        "enrichment_fields": ["company_funding", "linkedin_profile"]
    },
    destination="rag_agent",
    tenant_id=tenant_id
)

redis.xadd(f"{tenant_id}:agents:rag:tasks", to_redis_fields(envelope))
```

### Persistence Agent Integration

```python
# Store enriched data
persistence_payload = {
    "operation": "upsert",
    "table": "leads",
    "record": {
        "id": lead_id,
        "enrichment_status": "completed",
        "raw_data": {
            "crunchbase": {...},
            "linkedin": {...},
            "confidence_scores": {...}
        }
    },
    "on_conflict": ["id"]
}
```

## Performance Characteristics

### Deterministic Path (Tier 2)

- **Validation:** < 50ms (in-memory checks)
- **Embedding Generation:** 100-300ms (cached: < 5ms)
- **Vector Search:** 50-200ms (depends on index size)
- **External API:** 500-2000ms (Crunchbase/LinkedIn)
- **Total (cached):** ~1-2s per enrichment

### LLM Repair Path (Tier 3)

- **LLM Inference:** 1-3s (GPT-4o-mini)
- **Context Retrieval:** 100-500ms (Persistence queries)
- **Re-validation:** < 50ms
- **Total:** 2-5s per repair attempt

### Cache Hit Rates (Expected)

- Embedding Cache: 70-80% (repeated company names)
- Vector Search: N/A (always query)
- External API: 50-60% (popular companies)

## Error Handling

### Validation Failures

```python
# Return error envelope
{
  "status": "error",
  "error_code": "VALIDATION_FAILED",
  "validation_result": {
    "completeness_score": 0.4,
    "missing_required_fields": ["client_id", "last_name"],
    "errors": [...]
  }
}
```

### Repair Exhaustion

After 2 repair attempts:
```python
{
  "status": "error",
  "error_code": "REPAIR_EXHAUSTED",
  "repair_attempts": 2,
  "final_completeness": 0.5,
  "message": "Could not repair to required completeness threshold"
}
```

### External API Failures

Graceful degradation:
```python
{
  "status": "partial_success",
  "enriched_data": {...},  # From successful sources only
  "confidence": 0.6,        # Reduced due to missing data
  "warnings": [
    "Crunchbase API timeout - funding data unavailable"
  ]
}
```

## Future Enhancements

1. **API Buffer Service** - Rate-limited proxy for Crunchbase/LinkedIn (Railway deployment)
2. **Embedding Model Selection** - Support local models (BERT, Sentence Transformers)
3. **Multi-Modal Embeddings** - Image + text for profile photos
4. **Active Learning** - Feedback loop for repair quality
5. **Distributed Tracing** - OpenTelemetry integration
6. **Batch Enrichment** - Parallel processing for bulk imports

## Testing

### Validation Testing

```python
result = validate_entity_payload(
    EntityType.LEAD,
    {"email": "test@example.com", "first_name": "John"}
)

assert result.completeness_score == 0.6  # Missing: last_name, client_id, id
assert result.needs_llm_repair() == True
```

### Embedding Pipeline Testing

```python
pipeline = EmbeddingPipeline(redis_client=redis)

success = await pipeline.index_entity(
    EntityType.LEAD,
    {"id": "123", "company_name": "Acme Corp", "job_title": "CEO"}
)

assert success == True
```

### Similarity Search Testing

```python
results = await pipeline.search_similar(
    EntityType.LEAD,
    "AI startup founder in San Francisco",
    limit=10,
    filters={"enrichment_status": "completed"}
)

assert len(results) <= 10
assert all(r["similarity_score"] >= 0.0 for r in results)
```

## Monitoring & Observability

### Key Metrics

- **Validation Pass Rate:** % of payloads passing validation (target: > 80%)
- **Repair Success Rate:** % of repairs reaching completeness >= 0.7 (target: > 60%)
- **Embedding Cache Hit Rate:** % of cached embeddings (target: > 70%)
- **Average Enrichment Latency:** P50, P95, P99 (target: < 3s P95)
- **External API Error Rate:** % of failed API calls (target: < 5%)

### Logging

All RAG operations logged with:
- `task_id` - Correlation ID
- `entity_type` - Entity being processed
- `completeness_score` - Validation score
- `execution_path` - deterministic | repair | error
- `latency_ms` - Total processing time

---

**Implementation Status:** Skeleton Complete (Nov 23, 2025)
**Next Steps:** Implement actual enrichment logic, external API integration, LLM repair strategy
