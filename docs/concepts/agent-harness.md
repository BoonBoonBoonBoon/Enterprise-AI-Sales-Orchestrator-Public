# Agent Harness

The Agent Harness is a wrapper pattern that abstracts Redis communication, error handling, and lifecycle management for all Tier 3 agents.

## Why Use a Harness?

Without harness, every agent needs to:

- Connect to Redis
- Subscribe to the right stream
- Parse message envelopes
- Handle acknowledgments
- Publish results
- Log consistently
- Handle shutdown gracefully

The harness handles all of this, so agents only implement business logic.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Harness                           │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Redis Stream Consumer                   │   │
│  │  • Connects to Redis                                │   │
│  │  • Subscribes to {tenant}:agents:{name}:tasks       │   │
│  │  • Consumer group management                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                                │
│                            ▼                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Message Handler                         │   │
│  │  • Parses TaskEnvelope                              │   │
│  │  • Validates payload                                │   │
│  │  • Calls process_task()  ◄──── YOU IMPLEMENT THIS   │   │
│  │  • Wraps result in ResultEnvelope                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                                │
│                            ▼                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Result Publisher                        │   │
│  │  • Publishes to {tenant}:agents:{name}:results      │   │
│  │  • Acknowledges original message                    │   │
│  │  • Logs outcome                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Basic Usage

### Creating an Agent

```python
from core.harness.agent_harness import AgentHarness

class MyAgentHarness(AgentHarness):
    """My custom agent."""

    def __init__(self, tenant_id: str):
        super().__init__(
            tenant_id=tenant_id,
            agent_name="my_agent",
            consumer_group="my_agent_workers"
        )

    def process_task(self, task: dict) -> dict:
        """Process a single task. Called by harness for each message."""
        payload = task.get("payload", {})
        action = payload.get("action")

        if action == "do_something":
            result = self._do_something(payload)
            return {"status": "success", "result": result}
        else:
            return {
                "status": "error",
                "error": {"code": "UNKNOWN_ACTION", "message": f"Unknown: {action}"}
            }

    def _do_something(self, payload: dict) -> dict:
        # Your business logic here
        return {"processed": True}
```

### Running the Consumer

```python
# consumer.py
if __name__ == "__main__":
    from my_agent_harness import MyAgentHarness

    harness = MyAgentHarness(tenant_id="agentic-dev")
    harness.run()  # Blocks forever, processing messages
```

Run:

```powershell
& ".venv/Scripts/python.exe" -m tiers.tier_3.my_agent.consumer
```

## AgentHarness API

### Constructor Parameters

| Parameter        | Type | Required | Description                                           |
| ---------------- | ---- | -------- | ----------------------------------------------------- |
| `tenant_id`      | str  | ✅       | Tenant identifier                                     |
| `agent_name`     | str  | ✅       | Agent name (used in stream keys)                      |
| `consumer_group` | str  | ⚠️       | Consumer group name (default: `{agent_name}_workers`) |
| `redis_url`      | str  | ⚠️       | Redis URL (default: from env)                         |

### Methods to Override

#### `process_task(self, task: dict) -> dict`

**Required.** Process a single task envelope.

```python
def process_task(self, task: dict) -> dict:
    """
    Args:
        task: Full TaskEnvelope dict with keys:
            - task_id: str
            - tenant_id: str
            - payload: dict (your data)
            - metadata: dict

    Returns:
        Result dict with keys:
            - status: "success" | "error"
            - result: dict (if success)
            - error: dict (if error) with code, message
    """
```

#### `on_startup(self) -> None`

**Optional.** Called once when consumer starts.

```python
def on_startup(self) -> None:
    self.db_connection = create_connection()
    self.logger.info("Agent ready")
```

#### `on_shutdown(self) -> None`

**Optional.** Called on graceful shutdown.

```python
def on_shutdown(self) -> None:
    self.db_connection.close()
    self.logger.info("Agent shutdown complete")
```

### Built-in Methods

| Method                   | Description                    |
| ------------------------ | ------------------------------ |
| `run()`                  | Start blocking consumer loop   |
| `stop()`                 | Request graceful shutdown      |
| `publish_result(result)` | Manually publish a result      |
| `logger`                 | Pre-configured logger instance |

## DeepAgentHarness

For agents that need to call LLMs with tools (LangGraph):

```python
from core.harness.deep_agent_harness import DeepAgentHarness
from langchain_core.tools import tool

class SmartAgentHarness(DeepAgentHarness):
    def __init__(self, tenant_id: str):
        super().__init__(
            tenant_id=tenant_id,
            agent_name="smart_agent",
            tools=self._get_tools()
        )

    def _get_tools(self):
        @tool
        def search_database(query: str) -> str:
            """Search the database for information."""
            return f"Results for: {query}"

        return [search_database]

    def process_task(self, task: dict) -> dict:
        # DeepAgentHarness provides self.agent (LangGraph)
        result = self.agent.invoke({
            "messages": [{"role": "user", "content": task["payload"]["query"]}]
        })
        return {"status": "success", "result": result}
```

## Error Handling

### Task Errors

Return error status for recoverable errors:

```python
def process_task(self, task: dict) -> dict:
    try:
        result = risky_operation()
        return {"status": "success", "result": result}
    except NotFoundError as e:
        return {
            "status": "error",
            "error": {
                "code": "NOT_FOUND",
                "message": str(e),
                "retryable": False
            }
        }
    except TemporaryError as e:
        return {
            "status": "error",
            "error": {
                "code": "TEMPORARY_FAILURE",
                "message": str(e),
                "retryable": True
            }
        }
```

### Unhandled Exceptions

The harness catches unhandled exceptions and:

1. Logs the full traceback
2. Returns error result
3. Does NOT acknowledge message (allows retry)

```python
def process_task(self, task: dict) -> dict:
    # If this raises, harness handles it
    raise ValueError("Something went wrong")
    # Message will be reclaimed by another worker after timeout
```

## Validation

Use Pydantic for payload validation:

```python
from pydantic import BaseModel, Field

class MyTaskPayload(BaseModel):
    action: str
    lead_id: str
    options: dict = Field(default_factory=dict)

class MyAgentHarness(AgentHarness):
    def process_task(self, task: dict) -> dict:
        try:
            payload = MyTaskPayload(**task.get("payload", {}))
        except ValidationError as e:
            return {
                "status": "error",
                "error": {"code": "INVALID_PAYLOAD", "message": str(e)}
            }

        # Now payload is validated and typed
        return self._handle_action(payload)
```

## Testing

### Unit Testing

```python
import pytest
from my_agent_harness import MyAgentHarness

def test_process_task():
    harness = MyAgentHarness(tenant_id="test")

    result = harness.process_task({
        "task_id": "test-1",
        "tenant_id": "test",
        "payload": {"action": "do_something"},
        "metadata": {}
    })

    assert result["status"] == "success"
```

### Integration Testing

```python
import pytest
from services.redis.client import get_redis_client
import json

@pytest.fixture
def redis():
    return get_redis_client()

def test_agent_via_stream(redis):
    # Publish task
    task = {
        "task_id": "test-1",
        "tenant_id": "test",
        "payload": {"action": "do_something"},
        "metadata": {}
    }
    redis.xadd("test:agents:my_agent:tasks", {"data": json.dumps(task)})

    # Wait for result (with running consumer)
    result = redis.xread(
        {"test:agents:my_agent:results": "0"},
        count=1,
        block=5000
    )

    assert result is not None
```

## Best Practices

1. **Keep `process_task` focused** — Single responsibility
2. **Validate early** — Use Pydantic at the start
3. **Return structured errors** — Include code and message
4. **Log important events** — Use `self.logger`
5. **Test in isolation** — Mock Redis for unit tests
6. **Handle cleanup** — Implement `on_shutdown`

## Related

- [ADR-005: Agent Harness Pattern](../architecture/decisions/005-agent-harness-pattern.md)
- [Creating New Agents](../guides/dev/new-agent.md)
- [Redis Streams](redis-streams.md)
- [Envelope Schema](../reference/api/envelope.md)
