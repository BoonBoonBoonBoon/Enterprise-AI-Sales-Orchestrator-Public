# End-to-End Test Guide

Complete guide for testing the orchestrator → RAG → copywriter pipeline with enhanced envelope system.

## Prerequisites

1. **Redis Running**: Ensure Redis server is accessible
2. **Environment**: `.env` configured with Redis connection details and database credentials
3. **Workers Started**: RAG worker, copywriter worker running (orchestrator consumes commands directly)

## Test Scenario: Campaign Followup Batch

Test the full context-forwarding pipeline where:
1. Orchestrator receives `campaign_followup_batch` command
2. Fans out to RAG worker with `forward_to` instructions
3. RAG fetches lead data and forwards to copywriter with context
4. Copywriter generates email using `lead_data + campaign_context + instructions`

### Step 1: Start Workers

```bash
# Terminal 1: RAG Worker
python -m agent.operational_agents.rag_agent.worker

# Terminal 2: Copywriter Worker
python -m agent.operational_agents.copywriter.worker

# Terminal 3: Orchestrator (optional - can enqueue command directly)
python -m agent.orchestrators.workflow_manager
```

### Step 2: Enqueue Test Command

Use Python REPL or script to enqueue a test command:

```python
from agent.tools.redis.client import RedisPubSub
from agent.tools.redis import config as rconf
from agent.utils.typed_envelope import task, to_redis_fields
import json

redis = RedisPubSub()

# Create orchestrator command envelope
cmd_envelope = task(
    source="test_client",
    task_id="test-campaign-001",
    destination="orchestrator:commands",
    payload={
        "type": "campaign_followup_batch",
        "campaign_id": "camp-001",
        "lead_ids": [1, 2, 3],  # Replace with actual lead IDs from your DB
        "step": 3,
        "context": {
            "campaign_name": "Q1 Outreach",
            "product": "AI Platform",
            "value_prop": "10x productivity gains"
        },
        "instructions": {
            "tone": "professional",
            "subject_hint": "Quick follow-up",
            "length": "short",
            "cta": "Schedule demo"
        }
    },
    campaign_id="camp-001",
    tags={"test": "e2e", "client": "manual"}
)

# Enqueue to orchestrator:commands
redis.xadd(
    rconf.full_key(rconf.STREAM_COMMANDS),
    to_redis_fields(cmd_envelope),
    maxlen=rconf.STREAM_MAXLEN
)

print(f"Enqueued command: {cmd_envelope.metadata.task_id}")
print(f"Correlation ID: {cmd_envelope.metadata.correlation_id}")
```

### Step 3: Monitor Streams

Check each stream to verify message flow:

```bash
# Use redis-cli or Python
redis-cli

# 1. Check orchestrator:commands (should have your test command)
XREAD COUNT 1 STREAMS agentic:orchestrator:commands 0

# 2. Check rag:tasks (orchestrator should create RAG task with forward_to)
XREAD COUNT 5 STREAMS agentic:rag:tasks 0

# 3. Check copy:tasks (RAG should forward with lead_data + context)
XREAD COUNT 5 STREAMS agentic:copy:tasks 0

# 4. Check rag:results and copy:results
XREAD COUNT 5 STREAMS agentic:rag:results 0
XREAD COUNT 5 STREAMS agentic:copy:results 0
```

### Step 4: Verify Context Forwarding

#### Expected RAG Task (in `rag:tasks`)

```json
{
  "metadata": {
    "task_id": "rag-lead-1",
    "correlation_id": "<same as original command>",
    "campaign_id": "camp-001",
    "tags": {"test": "e2e", "client": "manual", "parent_task_id": "test-campaign-001"}
  },
  "payload": {
    "query": {
      "table": "leads",
      "filters": {"id": 1}
    },
    "forward_to": {
      "agent": "copywriter",
      "campaign_context": {
        "campaign_name": "Q1 Outreach",
        "step": 3,
        "product": "AI Platform"
      },
      "instructions": {
        "tone": "professional",
        "subject_hint": "Quick follow-up",
        "length": "short",
        "cta": "Schedule demo"
      }
    }
  }
}
```

#### Expected Copywriter Task (in `copy:tasks`)

```json
{
  "metadata": {
    "task_id": "copy-1",
    "correlation_id": "<same correlation_id>",
    "campaign_id": "camp-001",
    "tags": {"test": "e2e", "parent_task_id": "rag-lead-1", "worker_id": "<rag_worker_pid>"}
  },
  "payload": {
    "lead_data": {
      "id": 1,
      "first_name": "John",
      "last_name": "Doe",
      "email": "john@example.com",
      "company_name": "Acme Corp"
    },
    "campaign_context": {
      "campaign_name": "Q1 Outreach",
      "step": 3,
      "product": "AI Platform"
    },
    "instructions": {
      "tone": "professional",
      "subject_hint": "Quick follow-up",
      "length": "short",
      "cta": "Schedule demo"
    }
  }
}
```

#### Expected Copywriter Result (in `copy:results`)

```json
{
  "metadata": {
    "task_id": "copy-1",
    "correlation_id": "<same correlation_id>",
    "status": "SUCCESS"
  },
  "payload": {
    "content": {
      "subject": "Quick follow-up - Step 3",
      "body": "Hi John,\n\nFollowing up...\n\nBest regards,\n[Your Name]",
      "metadata": {
        "model": "placeholder",
        "tokens": 0,
        "tone": "professional",
        "step": 3
      }
    },
    "lead_id": 1,
    "campaign_id": "camp-001"
  }
}
```

### Step 5: Trace Full Pipeline

Use correlation ID to trace all related messages across streams:

```python
from agent.tools.redis.client import RedisPubSub
from agent.utils.typed_envelope import from_redis_message
import redis as redis_lib

redis = RedisPubSub()
correlation_id = "<your-correlation-id>"

streams = [
    "agentic:orchestrator:commands",
    "agentic:rag:tasks",
    "agentic:rag:results",
    "agentic:copy:tasks",
    "agentic:copy:results"
]

print(f"Tracing correlation_id: {correlation_id}\n")

for stream in streams:
    print(f"=== {stream} ===")
    try:
        entries = redis.client.xrange(stream, "-", "+", count=100)
        for msg_id, fields in entries:
            try:
                env = from_redis_message(fields)
                if env.metadata.correlation_id == correlation_id:
                    print(f"  [{msg_id.decode()}]")
                    print(f"    Task ID: {env.metadata.task_id}")
                    print(f"    Status: {env.status}")
                    print(f"    Tags: {env.metadata.tags}")
                    print(f"    Payload keys: {list(env.payload.keys())}")
                    print()
            except Exception:
                pass
    except Exception as e:
        print(f"  Error reading stream: {e}")
    print()
```

## Verification Checklist

- [ ] Orchestrator consumes command and creates RAG tasks
- [ ] RAG tasks include `forward_to` with `agent="copywriter"`
- [ ] RAG worker fetches lead data successfully
- [ ] RAG worker enqueues copywriter tasks with `lead_data + campaign_context + instructions`
- [ ] Copywriter worker receives all three context components
- [ ] Copywriter generates email with correct tone, subject hint, and campaign context
- [ ] All tasks share same `correlation_id`
- [ ] Tags properly track parent tasks (`parent_task_id`)
- [ ] Results emitted with `status=SUCCESS` and `mark_processed()` applied
- [ ] No errors in DLQ streams

## Health Monitoring

Use `streams_health.py` to check stream activity:

```bash
python agent/tools/redis/streams_health.py
```

Expected output showing activity across:
- `orchestrator:commands` (1 message)
- `rag:tasks` (N messages, one per lead_id)
- `copy:tasks` (N messages forwarded from RAG)
- `rag:results` (N messages)
- `copy:results` (N messages)

## Troubleshooting

### No RAG tasks created
- Check orchestrator logs for `campaign_followup_batch` handler
- Verify command payload includes `type: "campaign_followup_batch"`
- Check `orchestrator:commands` stream has your message

### RAG doesn't forward to copywriter
- Verify `forward_to.agent == "copywriter"` in RAG task payload
- Check RAG worker logs for `_forward_to_copywriter()` calls
- Inspect `copy:tasks` stream for forwarded messages

### Copywriter receives incomplete context
- Check copywriter task payload has all three: `lead_data`, `campaign_context`, `instructions`
- Verify RAG forwarding logic preserves all fields from `forward_to`

### Correlation ID not consistent
- Ensure orchestrator sets correlation_id on initial command
- Verify RAG worker passes `task_envelope.metadata.correlation_id` when creating copywriter tasks
- Check all envelopes use same correlation_id in trace script

### Messages in DLQ
- Check DLQ streams: `agentic:dlq:rag`, `agentic:dlq:copy`, `agentic:dlq:write`
- Inspect error_code and error_msg in DLQ envelope
- Review worker logs for exception details

## Next Steps

After successful E2E test:

1. **LLM Integration**: Replace copywriter's placeholder `_generate()` with OpenAI/Anthropic API calls
2. **Batch Testing**: Test with larger `lead_ids` arrays (10+, 100+)
3. **Error Scenarios**: Test with invalid lead IDs, DB connection failures to verify DLQ
4. **Performance**: Measure latency across full pipeline
5. **Automated Tests**: Convert manual test into pytest fixture with mock Redis
