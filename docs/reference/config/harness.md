# Harness Configuration

This reference documents the AgentHarness and DeepAgentHarness configuration options.

## AgentHarness

Base class for all Tier 3 agents.

### Constructor

```python
from core.harness.agent_harness import AgentHarness

class MyAgentHarness(AgentHarness):
    def __init__(self, tenant_id: str):
        super().__init__(
            tenant_id=tenant_id,
            agent_name="my_agent",
            result_stream_suffix="results",
            consumer_group="my_agent_group",
            consumer_name="consumer_1",
            block_ms=5000,
            batch_size=1
        )
```

### Parameters

| Parameter              | Type  | Default                | Description                         |
| ---------------------- | ----- | ---------------------- | ----------------------------------- |
| `tenant_id`            | `str` | **required**           | Tenant identifier for stream prefix |
| `agent_name`           | `str` | **required**           | Agent name for stream naming        |
| `result_stream_suffix` | `str` | `"results"`            | Suffix for result stream            |
| `consumer_group`       | `str` | `"{agent_name}_group"` | Redis consumer group name           |
| `consumer_name`        | `str` | `"consumer_1"`         | Unique consumer identifier          |
| `block_ms`             | `int` | `5000`                 | XREAD block timeout (ms)            |
| `batch_size`           | `int` | `1`                    | Messages per XREAD call             |

### Stream Names

Generated automatically:

```python
# Task stream (reads from)
f"{tenant_id}:agents:{agent_name}:tasks"
# Example: agentic-dev:agents:rag:tasks

# Result stream (writes to)
f"{tenant_id}:agents:{agent_name}:{result_stream_suffix}"
# Example: agentic-dev:agents:rag:results
```

### Methods

#### `process_task(task: dict) -> dict`

**Override required.** Implement agent logic.

```python
def process_task(self, task: dict) -> dict:
    payload = task.get("payload", {})
    # Process...
    return {"status": "success", "data": result}
```

#### `run()`

Start the consumer loop. Blocks indefinitely.

```python
harness = MyAgentHarness(tenant_id="agentic-dev")
harness.run()  # Blocking
```

#### `stop()`

Graceful shutdown.

```python
harness.stop()
```

---

## DeepAgentHarness

Extended harness for LangGraph-based orchestrators with tool delegation.

### Constructor

```python
from core.harness.deep_agent_harness import DeepAgentHarness

class LeadsOrchestratorHarness(DeepAgentHarness):
    def __init__(self, tenant_id: str):
        super().__init__(
            tenant_id=tenant_id,
            agent_name="leads",
            stream_prefix="orchestrators",
            tools=self._build_tools(),
            llm=self._build_llm()
        )
```

### Parameters

| Parameter         | Type         | Default           | Description                    |
| ----------------- | ------------ | ----------------- | ------------------------------ |
| `tenant_id`       | `str`        | **required**      | Tenant identifier              |
| `agent_name`      | `str`        | **required**      | Orchestrator name              |
| `stream_prefix`   | `str`        | `"orchestrators"` | Stream prefix (not `agents`)   |
| `tools`           | `list[Tool]` | `[]`              | LangGraph tools for delegation |
| `llm`             | `BaseLLM`    | `None`            | Language model instance        |
| `max_iterations`  | `int`        | `10`              | Max LangGraph iterations       |
| `timeout_seconds` | `int`        | `120`             | Per-task timeout               |

### Stream Names

```python
# Task stream
f"{tenant_id}:{stream_prefix}:{agent_name}:tasks"
# Example: agentic-dev:orchestrators:leads:tasks

# Result stream
f"{tenant_id}:{stream_prefix}:{agent_name}:results"
# Example: agentic-dev:orchestrators:leads:results
```

### Tool Building

```python
def _build_tools(self):
    from tiers.tier_2.leads_orchestrator.tools import (
        delegate_to_rag,
        delegate_to_persistence
    )
    return [delegate_to_rag, delegate_to_persistence]
```

### LLM Configuration

```python
def _build_llm(self):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model="gpt-4o",
        temperature=0.1
    )
```

---

## OrchestratorHarness

For non-LangGraph orchestrators using simple delegation.

### Constructor

```python
from core.harness.orchestrator_harness import OrchestratorHarness

class SimpleOrchestratorHarness(OrchestratorHarness):
    def __init__(self, tenant_id: str):
        super().__init__(
            tenant_id=tenant_id,
            orchestrator_name="simple",
            delegate_targets=["rag", "persistence"]
        )
```

### Delegation Methods

```python
async def delegate_to_agent(
    self,
    agent_name: str,
    payload: dict,
    timeout: int = 60
) -> dict:
    """Delegate task to Tier 3 agent and await response."""
    pass
```

---

## Environment Variables

Harness behavior can be configured via environment:

| Variable                 | Default | Description            |
| ------------------------ | ------- | ---------------------- |
| `HARNESS_BLOCK_MS`       | `5000`  | XREAD block timeout    |
| `HARNESS_BATCH_SIZE`     | `1`     | Messages per batch     |
| `HARNESS_MAX_RETRIES`    | `3`     | Retry count on failure |
| `HARNESS_RETRY_DELAY_MS` | `1000`  | Delay between retries  |
| `HARNESS_LOG_LEVEL`      | `INFO`  | Logging verbosity      |

---

## Lifecycle

```
┌─────────────────────────────────────────┐
│              Harness.run()              │
│                                         │
│  ┌─────────┐    ┌───────────────────┐  │
│  │  XREAD  │───▶│  process_task()   │  │
│  │ (block) │    │                   │  │
│  └─────────┘    └───────────────────┘  │
│       │                   │             │
│       │                   ▼             │
│       │         ┌───────────────────┐  │
│       │         │   XADD result     │  │
│       │         │   XACK task       │  │
│       │         └───────────────────┘  │
│       │                   │             │
│       └───────────────────┘             │
│                 (loop)                  │
└─────────────────────────────────────────┘
```

---

## Error Handling

### Automatic Retry

```python
# Harness automatically retries on transient errors
# After max_retries, task is moved to DLQ

# Custom retry logic
def process_task(self, task: dict) -> dict:
    try:
        return self._do_work(task)
    except TransientError:
        raise  # Harness will retry
    except PermanentError as e:
        return {"status": "error", "error": str(e)}
```

### Dead Letter Queue

Failed tasks after max retries:

```
{tenant_id}:agents:{agent_name}:dlq
```

---

## Graceful Shutdown

```python
import signal

def main():
    harness = MyAgentHarness(tenant_id="agentic-dev")

    def shutdown(sig, frame):
        harness.stop()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    harness.run()
```

## Related

- [Agent Harness Concept](../../concepts/agent-harness.md)
- [Creating Agents Guide](../../guides/dev/new-agent.md)
- [Settings Reference](settings.md)
