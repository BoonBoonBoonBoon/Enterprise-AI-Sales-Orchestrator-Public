# ADR-005: Agent Harness Pattern

**Status:** ✅ Accepted  
**Date:** November 2025

## Context

Every agent in the system needs common infrastructure:

1. **Redis communication** — Read from stream, write results
2. **Retry logic** — Handle transient failures
3. **Circuit breaker** — Fail fast when downstream is unhealthy
4. **Observability** — Tracing, metrics, logging
5. **Checkpointing** — State persistence for resumable workflows
6. **Error handling** — Consistent error responses

Implementing these in every agent creates duplication and inconsistency.

## Decision

We wrap all agents in an **AgentHarness** class that provides common infrastructure:

```python
from core.harness.agent_harness import AgentHarness

class MyAgentHarness(AgentHarness):
    def __init__(self, tenant_id: str):
        super().__init__(
            tenant_id=tenant_id,
            agent_name="my_agent",
            result_stream_suffix="results"
        )

    def process_task(self, task: dict) -> dict:
        # Agent-specific logic only
        payload = task.get("payload", {})
        result = do_work(payload)
        return {"status": "success", "data": result}
```

### Harness Responsibilities

```
┌─────────────────────────────────────────────────────────────────┐
│                      AgentHarness                               │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Stream I/O: XREADGROUP → process → XACK → XADD result    │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Retry: Exponential backoff, configurable attempts        │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Circuit Breaker: Fail-fast on repeated failures          │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Observability: Tracing spans, metrics, structured logs   │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Checkpointing: State persistence for long workflows      │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                  │
│                              ▼                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │              Agent Logic (process_task)                   │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Harness Variants

| Class               | Use Case                                  |
| ------------------- | ----------------------------------------- |
| `AgentHarness`      | Synchronous agents (most Tier 3)          |
| `DeepAgentHarness`  | LangGraph-based agents with complex state |
| `AsyncAgentHarness` | Async agents using asyncio                |

## Consequences

### Positive

- **DRY** — Common code in one place
- **Consistency** — All agents behave the same way
- **Reliability** — Proven retry/circuit breaker logic
- **Observability** — Automatic tracing without agent code
- **Testability** — Mock harness to test agent logic in isolation
- **Onboarding** — New agents just implement `process_task`

### Negative

- **Abstraction overhead** — Must understand harness to debug
- **Coupling** — Agents tied to harness interface
- **Configuration complexity** — Many options to tune

### Neutral

- **Inheritance vs. composition** — We chose inheritance for simplicity
- **Python-specific** — Pattern would differ in other languages

## Configuration Options

```python
from core.harness.config import HarnessConfig

config = HarnessConfig(
    max_retries=3,
    retry_delay_seconds=1.0,
    retry_backoff_multiplier=2.0,
    circuit_breaker_threshold=5,
    circuit_breaker_timeout=60,
    checkpoint_enabled=True,
    checkpoint_interval=10,
    tracing_enabled=True,
    metrics_enabled=True,
)

harness = MyAgentHarness(tenant_id="dev", config=config)
```

## Alternatives Considered

### Option A: No Wrapper (Inline Everything)

Each agent implements its own stream handling, retries, etc.

- **Pros:** No abstraction to learn, full control
- **Cons:** Massive duplication, inconsistent behavior, bugs in each
- **Why rejected:** Doesn't scale, maintenance nightmare

### Option B: Decorator Pattern

Wrap agent functions with decorators for each feature.

```python
@retry(attempts=3)
@circuit_breaker(threshold=5)
@trace
def process(task):
    pass
```

- **Pros:** Composable, explicit
- **Cons:** Many decorators, ordering matters, complex
- **Why rejected:** Too many decorators, harness is cleaner

### Option C: Middleware Pipeline

Chain of handlers that process before/after agent.

- **Pros:** Very flexible, each concern separate
- **Cons:** Complex to configure, ordering non-obvious
- **Why rejected:** Over-engineered for our needs

## Usage Example

```python
# tiers/tier_3/my_agent/my_agent_harness.py
from core.harness.agent_harness import AgentHarness

class MyAgentHarness(AgentHarness):
    def __init__(self, tenant_id: str):
        super().__init__(
            tenant_id=tenant_id,
            agent_name="my_agent",
        )

    def process_task(self, task: dict) -> dict:
        action = task["payload"]["action"]
        if action == "do_thing":
            result = self._do_thing(task["payload"])
            return {"status": "success", "result": result}
        return {"status": "error", "message": f"Unknown action: {action}"}

    def _do_thing(self, payload: dict) -> dict:
        # Actual agent logic
        pass
```

```python
# tiers/tier_3/my_agent/consumer.py
from .my_agent_harness import MyAgentHarness

if __name__ == "__main__":
    harness = MyAgentHarness(tenant_id="agentic-dev")
    harness.run()  # Blocks, listens on stream
```

## References

- [Agent Harness Concept](../../concepts/agent-harness.md)
- [Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html)
- [Retry Pattern](https://docs.microsoft.com/en-us/azure/architecture/patterns/retry)
