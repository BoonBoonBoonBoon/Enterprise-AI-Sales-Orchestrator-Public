# Your First Task

This guide walks you through sending your first task through the Agentic System.

## Prerequisites

Complete these first:

- [x] [Installation](installation.md)
- [x] [Environment Setup](environment.md)
- [x] [Quick Start](quickstart.md) (all services running)

## Overview

You'll learn to:

1. Publish a task to an agent stream
2. Watch the consumer process it
3. Read the result

## Step 1: Start the RAG Agent

In a terminal:

```powershell
& ".venv/Scripts/python.exe" -m tiers.tier_3.rag_agent.consumer
```

You should see:

```
INFO: RAG Agent consumer started
INFO: Listening on agentic-dev:agents:rag:tasks
```

## Step 2: Publish a Task

In a new Python terminal:

```python
import json
import uuid
from services.redis.client import get_redis_client

redis = get_redis_client()

# Create task envelope
task = {
    "task_id": str(uuid.uuid4()),
    "tenant_id": "agentic-dev",
    "payload": {
        "action": "get_lead_context",
        "lead_id": "test-lead-001"  # May not exist
    },
    "metadata": {
        "source": "manual_test"
    }
}

# Publish to stream
message_id = redis.xadd(
    "agentic-dev:agents:rag:tasks",
    {"data": json.dumps(task)}
)

print(f"Published task: {task['task_id']}")
print(f"Message ID: {message_id}")
```

## Step 3: Check the Consumer

In the consumer terminal, you should see:

```
INFO: Received task: <task_id>
INFO: Action: get_lead_context
INFO: Processing...
INFO: Result: {"status": "error", "error": {"code": "LEAD_NOT_FOUND", ...}}
```

(Error is expected since `test-lead-001` doesn't exist)

## Step 4: Read the Result

Back in Python:

```python
# Read from results stream
results = redis.xread(
    {"agentic-dev:agents:rag:results": "0"},
    count=10
)

for stream, messages in results:
    for msg_id, data in messages:
        result = json.loads(data[b"data"])
        if result["task_id"] == task["task_id"]:
            print(f"Status: {result['status']}")
            if result["status"] == "success":
                print(f"Result: {result['result']}")
            else:
                print(f"Error: {result['error']}")
```

## Step 5: Create Test Data

To see a successful response, create a test lead:

```python
from services.persistence.supabase_adapter import SupabaseAdapter

adapter = SupabaseAdapter(role="agent_writer")

# Create client first (FK requirement)
client = adapter.write("clients", {
    "name": "Test Client",
    "email": "test@example.com"
})

# Create campaign
campaign = adapter.write("campaigns", {
    "client_id": client["id"],
    "name": "Test Campaign"
})

# Create lead
lead = adapter.write("leads", {
    "client_id": client["id"],
    "campaign_id": campaign["id"],
    "name": "John Doe",
    "email": "john@example.com",
    "status": "new"
})

print(f"Created lead: {lead['id']}")
```

Now publish a task with the real lead ID:

```python
task = {
    "task_id": str(uuid.uuid4()),
    "tenant_id": "agentic-dev",
    "payload": {
        "action": "get_lead_context",
        "lead_id": lead["id"]  # Real ID
    },
    "metadata": {"source": "manual_test"}
}

redis.xadd("agentic-dev:agents:rag:tasks", {"data": json.dumps(task)})
```

## What's Next?

- [Adding a New Agent](../guides/dev/new-agent.md) — Build your own agent
- [Concepts](../concepts/index.md) — Understand the architecture
- [Troubleshooting](../guides/ops/troubleshooting.md) — Common issues
