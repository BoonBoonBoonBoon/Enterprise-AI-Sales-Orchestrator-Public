# Copywriter LLM Integration Guide

Complete guide for integrating and using LLM providers (OpenAI, Anthropic) with the Copywriter agent.

---

## Table of Contents

1. [Overview](#overview)
2. [Supported Providers](#supported-providers)
3. [Configuration](#configuration)
4. [Lead Context Enrichment](#lead-context-enrichment)
5. [Usage Examples](#usage-examples)
6. [API Models](#api-models)
7. [Cost Optimization](#cost-optimization)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The Copywriter worker supports multiple LLM providers for generating personalized email copy:

- **OpenAI** (GPT-4, GPT-3.5-turbo, GPT-4o-mini)
- **Anthropic** (Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Haiku)
- **Placeholder** (Template-based fallback for testing/development)

Key features:

- Automatic provider selection based on configuration
- Lead context enrichment from database
- A/B testing variant support
- Cost tracking (tokens used per generation)
- Graceful fallback to placeholder on API errors

---

## Supported Providers

### OpenAI

**Recommended models:**

- `gpt-4o` - Latest GPT-4 optimized model (best quality)
- `gpt-4o-mini` - Fast, cost-effective (default)
- `gpt-4-turbo` - Previous generation GPT-4
- `gpt-3.5-turbo` - Budget option

**Pricing (as of Oct 2024):**

- GPT-4o: $5.00/1M input tokens, $15.00/1M output tokens
- GPT-4o-mini: $0.15/1M input tokens, $0.60/1M output tokens
- GPT-3.5-turbo: $0.50/1M input tokens, $1.50/1M output tokens

**Average email generation:**

- Prompt: ~400 tokens
- Output: ~150 tokens
- Cost per email (gpt-4o-mini): ~$0.0001 (0.01¢)

### Anthropic

**Recommended models:**

- `claude-3-5-sonnet-20241022` - Best for creative copy (default)
- `claude-3-opus-20240229` - Highest quality, slower
- `claude-3-haiku-20240307` - Fast, budget option

**Pricing (as of Oct 2024):**

- Claude 3.5 Sonnet: $3.00/1M input tokens, $15.00/1M output tokens
- Claude 3 Opus: $15.00/1M input tokens, $75.00/1M output tokens
- Claude 3 Haiku: $0.25/1M input tokens, $1.25/1M output tokens

**Average email generation:**

- Prompt: ~400 tokens
- Output: ~150 tokens
- Cost per email (Claude 3.5 Sonnet): ~$0.0034 (0.34¢)

### Placeholder Mode

Template-based generation for:

- Development/testing without API costs
- Fallback when API fails
- Preview mode for A/B test variants

---

## Configuration

### Environment Variables

**Required (choose one provider):**

```bash
# For OpenAI
export OPENAI_API_KEY="sk-..."
export LLM_PROVIDER="openai"

# For Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
export LLM_PROVIDER="anthropic"

# For placeholder (no API key needed)
export LLM_PROVIDER="placeholder"
```

**Optional:**

```bash
# Enable lead context enrichment from database
export ENABLE_LEAD_CONTEXT_ENRICHMENT="1"  # default: 1 (enabled)

# Supabase for persistence (required for context enrichment)
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_KEY="eyJh..."
export PERSIST_ALLOWED_TABLES="leads,lead_interactions"
```

### Worker Startup

The worker automatically detects available providers on startup:

```bash
$ python -m agent.operational_agents.copywriter.worker

[CopyWorker 12345] OpenAI client initialized
[CopyWorker 12345] Lead context enrichment enabled
[CopyWorker 12345] listening on stream copy:tasks in group copy-workers...
```

**Startup warnings:**

```
WARNING: OPENAI_API_KEY not set, using placeholder
  → Set API key to enable real LLM generation

WARNING: Could not initialize persistence for context enrichment: SUPABASE_URL not set
  → Lead data will not be enriched from database
```

---

## Lead Context Enrichment

When `ENABLE_LEAD_CONTEXT_ENRICHMENT=1` and persistence is configured, the worker automatically enriches lead data before generation:

### What Gets Enriched

1. **Full Lead Record**

   - All database fields (industry, location, company size, etc.)
   - Custom fields and enrichment data
   - Overrides any fields in the task payload

2. **Recent Interactions** (last 5)
   - Email opens/clicks
   - Previous email sends
   - Meeting bookings
   - Replies

### Database Schema

**Expected tables:**

```sql
-- Leads table
CREATE TABLE leads (
    id TEXT PRIMARY KEY,
    email TEXT,
    first_name TEXT,
    last_name TEXT,
    name TEXT,
    company_name TEXT,
    company TEXT,
    title TEXT,
    industry TEXT,
    location TEXT,
    company_size TEXT,
    -- ... custom fields
);

-- Lead interactions table
CREATE TABLE lead_interactions (
    id TEXT PRIMARY KEY,
    lead_id TEXT REFERENCES leads(id),
    type TEXT,  -- 'email_sent', 'email_opened', 'clicked', 'replied', 'meeting_booked'
    summary TEXT,
    created_at TIMESTAMP,
    metadata JSONB
);
```

### Example: Before vs After Enrichment

**Task payload (minimal):**

```json
{
  "lead_data": {
    "id": "lead-123",
    "first_name": "Sarah",
    "email": "sarah@example.com"
  }
}
```

**After enrichment (from database):**

```json
{
  "lead_data": {
    "id": "lead-123",
    "first_name": "Sarah",
    "email": "sarah@example.com",
    "company_name": "TechStartup Inc",
    "title": "VP of Engineering",
    "industry": "Software",
    "location": "San Francisco, CA",
    "company_size": "50-200",
    "recent_interactions": [
      {
        "type": "email_opened",
        "created_at": "2024-10-25T14:30:00Z",
        "summary": "Opened initial outreach email"
      },
      {
        "type": "email_sent",
        "created_at": "2024-10-24T09:00:00Z",
        "summary": "Initial outreach about AI code review platform"
      }
    ]
  }
}
```

---

## Usage Examples

### 1. Basic Usage (OpenAI)

```python
from agent.tools.redis.client import RedisPubSub
from agent.utils.typed_envelope import task
import json

# Build task envelope
envelope = task(
    payload={
        "lead_data": {
            "id": "lead-123",
            "first_name": "Sarah",
            "email": "sarah@example.com",
            "company_name": "TechStartup Inc"
        },
        "campaign_context": {
            "campaign_id": "camp-456",
            "sequence_step": 1,
            "product_name": "AI Platform"
        },
        "instructions": {
            "template": "cold_email",
            "tone": "professional",
            "word_count": 150
        }
    },
    source="api",
    campaign_id="camp-456",
    lead_id="lead-123"
)

# Send to Redis
redis = RedisPubSub()
redis.xadd("copy:tasks", {
    "metadata": json.dumps(envelope.metadata.model_dump()),
    "payload": json.dumps(envelope.payload),
    "status": envelope.status.value
})
```

### 2. Custom Model Selection

```python
# Use GPT-4 for high-value leads
envelope = task(
    payload={
        "lead_data": {...},
        "campaign_context": {...},
        "instructions": {
            "template": "cold_email",
            "tone": "professional",
            "word_count": 150,
            "model": "gpt-4o",  # Override default model
            "temperature": 0.8  # More creative
        }
    },
    source="api",
    campaign_id="camp-456",
    lead_id="lead-123"
)
```

### 3. A/B Testing Variants

```python
# Variant A: Professional tone
envelope_a = task(
    payload={
        "lead_data": {...},
        "campaign_context": {
            "campaign_id": "camp-456",
            "variant": "A"  # For A/B test tracking
        },
        "instructions": {
            "tone": "professional",
            "word_count": 150
        }
    },
    source="api",
    campaign_id="camp-456",
    lead_id="lead-123"
)

# Variant B: Casual tone
envelope_b = task(
    payload={
        "lead_data": {...},
        "campaign_context": {
            "campaign_id": "camp-456",
            "variant": "B"
        },
        "instructions": {
            "tone": "casual",
            "word_count": 120
        }
    },
    source="api",
    campaign_id="camp-456",
    lead_id="lead-124"
)
```

### 4. Multi-Step Sequence

```python
# Step 1: Initial outreach
step1 = task(
    payload={
        "lead_data": {...},
        "campaign_context": {
            "sequence_step": 1,
            "product_name": "AI Platform",
            "value_proposition": "Automate 80% of tasks"
        },
        "instructions": {
            "template": "cold_email",
            "tone": "professional"
        }
    },
    source="api"
)

# Step 2: Follow-up (3 days later)
step2 = task(
    payload={
        "lead_data": {...},
        "campaign_context": {
            "sequence_step": 2,
            "days_since_last_contact": 3,
            "previous_subject": "AI Platform for your team",
            "previous_body_summary": "Introduced AI platform benefits"
        },
        "instructions": {
            "template": "followup_email",
            "tone": "professional"
        }
    },
    source="api"
)
```

### 5. Demo Script

```bash
# Run the included demo script
cd examples

# With OpenAI (default)
python copywriter_llm_demo.py --provider openai

# With Anthropic
python copywriter_llm_demo.py --provider anthropic

# With specific model
python copywriter_llm_demo.py --provider openai --model gpt-4o

# Placeholder mode (no API calls)
python copywriter_llm_demo.py --provider placeholder
```

---

## API Models

### Recommended Configurations by Use Case

**High-volume outreach (cost-optimized):**

```python
"instructions": {
    "model": "gpt-4o-mini",  # OpenAI
    # OR
    "model": "claude-3-haiku-20240307",  # Anthropic
    "temperature": 0.7,
    "max_tokens": 400
}
# Cost: ~$0.0001 per email
```

**High-value leads (quality-optimized):**

```python
"instructions": {
    "model": "gpt-4o",  # OpenAI
    # OR
    "model": "claude-3-5-sonnet-20241022",  # Anthropic
    "temperature": 0.8,
    "max_tokens": 600
}
# Cost: ~$0.001 per email
```

**Creative campaigns (tone-sensitive):**

```python
"instructions": {
    "model": "claude-3-5-sonnet-20241022",  # Best for creative copy
    "temperature": 0.9,
    "max_tokens": 500
}
# Cost: ~$0.0034 per email
```

---

## Cost Optimization

### 1. Model Selection Strategy

**Tiered approach by lead value:**

```python
def select_model(lead_value: float) -> str:
    if lead_value > 10000:
        return "gpt-4o"  # $0.001/email
    elif lead_value > 1000:
        return "gpt-4o-mini"  # $0.0001/email
    else:
        return "gpt-3.5-turbo"  # $0.00005/email
```

### 2. Batch Processing

Process leads in batches to reduce overhead:

```python
# Send 100 tasks at once
for lead in batch_of_100_leads:
    redis.xadd("copy:tasks", envelope_fields)

# Worker processes in parallel (scale to N workers)
```

### 3. Caching Strategies

**Cache common elements:**

- Campaign templates
- Industry-specific value propositions
- Tone/style guidelines

**Example:**

```python
# Cache prompt templates per campaign
prompt_cache = {
    "campaign-123": build_base_prompt(campaign_123_config)
}

# Reuse for each lead
full_prompt = prompt_cache["campaign-123"] + lead_specific_context
```

### 4. Token Budget Monitoring

Track tokens used per campaign:

```python
# In result payload
{
  "metadata": {
    "model": "gpt-4o-mini",
    "tokens": 547,
    "prompt_tokens": 412,
    "completion_tokens": 135
  }
}

# Aggregate for cost tracking
total_cost = (prompt_tokens * INPUT_PRICE + completion_tokens * OUTPUT_PRICE) / 1_000_000
```

### 5. Smart Fallback

Use placeholder mode during testing:

```bash
# Development: Free
export LLM_PROVIDER="placeholder"

# Staging: Budget model
export LLM_PROVIDER="openai"
export DEFAULT_MODEL="gpt-4o-mini"

# Production: Best model
export DEFAULT_MODEL="gpt-4o"
```

---

## Troubleshooting

### Issue: "WARNING: OPENAI_API_KEY not set, using placeholder"

**Cause:** API key not configured in environment

**Fix:**

```bash
# Set API key
export OPENAI_API_KEY="sk-..."

# Restart worker
python -m agent.operational_agents.copywriter.worker
```

### Issue: "OpenAI API error: Rate limit exceeded"

**Cause:** Too many API calls, exceeded quota

**Fix:**

```bash
# 1. Reduce request rate (add delay between batches)
# 2. Upgrade OpenAI plan
# 3. Use multiple API keys with round-robin

# Add rate limiting
export COPY_WORKER_BATCH_SIZE=10
export COPY_WORKER_BATCH_DELAY_MS=1000
```

### Issue: "Could not initialize persistence for context enrichment"

**Cause:** Supabase credentials not set

**Fix:**

```bash
# Set Supabase credentials
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_KEY="eyJh..."
export PERSIST_ALLOWED_TABLES="leads,lead_interactions"

# Or disable enrichment
export ENABLE_LEAD_CONTEXT_ENRICHMENT="0"
```

### Issue: Generated copy is too generic

**Cause:** Not enough lead context or poor prompt engineering

**Fix:**

1. **Enable context enrichment:**

   ```bash
   export ENABLE_LEAD_CONTEXT_ENRICHMENT="1"
   ```

2. **Add more lead fields:**

   ```python
   "lead_data": {
       "id": "lead-123",
       "first_name": "Sarah",
       "company_name": "TechStartup Inc",
       "title": "VP of Engineering",
       "industry": "Software",  # Add industry
       "location": "San Francisco",  # Add location
       "company_size": "50-200"  # Add company size
   }
   ```

3. **Provide campaign context:**
   ```python
   "campaign_context": {
       "product_name": "AI Code Review Platform",
       "value_proposition": "Reduce code review time by 60%",
       "previous_subject": "...",  # Reference previous email
       "days_since_last_contact": 3
   }
   ```

### Issue: High API costs

**Cause:** Using expensive models for all leads

**Fix:**

1. **Use tiered model selection:**

   - High-value leads → GPT-4o
   - Medium-value → GPT-4o-mini
   - Low-value → GPT-3.5-turbo or placeholder

2. **Optimize token usage:**

   ```python
   "instructions": {
       "word_count": 100,  # Shorter = fewer tokens
       "max_tokens": 300   # Limit output length
   }
   ```

3. **Monitor costs:**
   ```bash
   # Track tokens per campaign
   python scripts/ops.py inspect copy:results --count 100 | \
     jq '[.[] | .payload.metadata.tokens] | add'
   ```

### Issue: Worker processing is slow

**Cause:** Single worker, API latency

**Fix:**

1. **Scale workers:**

   ```bash
   # Run 5 workers in parallel
   docker-compose up -d --scale copy-worker=5
   ```

2. **Use faster models:**

   - OpenAI: `gpt-4o-mini` (fast)
   - Anthropic: `claude-3-haiku-20240307` (fastest)

3. **Reduce timeout:**
   ```python
   "timeout_ms": 30000  # 30s instead of 60s
   ```

---

## Best Practices

### 1. Always Include Context

✅ **Good:**

```python
{
  "lead_data": {
    "id": "lead-123",
    "first_name": "Sarah",
    "company_name": "TechStartup Inc",
    "title": "VP of Engineering",
    "industry": "Software"
  },
  "campaign_context": {
    "product_name": "AI Platform",
    "value_proposition": "Automate 80% of tasks",
    "sequence_step": 2,
    "days_since_last_contact": 3
  }
}
```

❌ **Bad:**

```python
{
  "lead_data": {
    "id": "lead-123",
    "first_name": "Sarah"  # Not enough context!
  }
}
```

### 2. Use Appropriate Models

- **Cold outreach at scale:** `gpt-4o-mini`
- **Follow-ups to engaged leads:** `gpt-4o` or `claude-3-5-sonnet`
- **Testing/development:** `placeholder`

### 3. Monitor Token Usage

Track cost per campaign to optimize budget:

```python
# After each result
tokens_used = result["metadata"]["tokens"]
cost = calculate_cost(tokens_used, model)
track_campaign_cost(campaign_id, cost)
```

### 4. Implement Retries

Worker automatically retries on API errors (3 attempts with exponential backoff), but implement circuit breaker for extended outages:

```python
if api_error_rate > 0.5:
    switch_to_placeholder_mode()
    alert_ops_team()
```

---

## Next Steps

1. **Set up API keys** for your chosen provider
2. **Run the demo script** to test integration
3. **Start worker** and monitor logs
4. **Send test tasks** using examples above
5. **Enable context enrichment** for better personalization
6. **Configure A/B testing** to optimize conversion

**Related Documentation:**

- [API Reference](../../api/reference.md) - Complete payload schemas
- [A/B Testing Guide](AB_TESTING.md) - Optimize variant performance
- [Type Safety Guide](../../TYPE_SAFETY.md) - Validate payloads with Pydantic

---

**Questions?** Check [INCIDENT_PLAYBOOKS.md](../../INCIDENT_PLAYBOOKS.md) for troubleshooting common issues.
