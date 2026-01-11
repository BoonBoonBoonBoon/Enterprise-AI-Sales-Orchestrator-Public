# Core - Framework Components

The `core/` directory contains the foundational framework components that power all agents and orchestrators in the system.

## Directory Structure

```
core/
├── README.md           ← You are here
├── __init__.py
├── streams.py          # Redis stream naming utilities & guards
│
├── envelope/           # Message envelope format
│   ├── envelope.py     # Envelope creation helpers
│   └── typed_envelope.py  # Strongly-typed envelope class
│
├── harness/            # Agent execution wrapper
│   ├── agent_harness.py    # Base harness class
│   ├── circuit_breaker.py  # Circuit breaker pattern
│   ├── config.py           # HarnessConfig
│   ├── interfaces.py       # Abstract interfaces
│   ├── checkpointing/      # State persistence
│   ├── observability/      # Metrics & tracing
│   ├── quota_management/   # Rate limiting
│   └── retry_strategies/   # Retry policies
│
├── exceptions/         # Custom exception classes
│
├── observability/      # Observability infrastructure
│   └── backends/       # Datadog, OpenTelemetry, etc.
│
├── schemas/            # Shared Pydantic models
│
└── utils/              # Utility functions
```

## Key Components

### Envelope (`envelope/`)

The message envelope is the standardized format for all inter-agent communication:

```python
from core.envelope import task, to_redis_fields

envelope = task(
    tenant_id="agentic-dev",
    payload={"action": "query_leads", "filters": {"stage": "qualified"}},
    source="manager",
    target="leads"
)
```

### Agent Harness (`harness/`)

The harness wraps all agents with production-grade reliability:

```python
from core.harness import AgentHarness, HarnessConfig

class MyAgentHarness(AgentHarness):
    def process_task(self, task: dict) -> dict:
        # Your agent logic here
        return {"status": "success"}
```

Features:

- **Retries** — Exponential backoff, jitter, configurable strategies
- **Circuit Breaker** — Prevent cascade failures
- **Observability** — OpenTelemetry spans, Datadog metrics
- **Checkpointing** — Redis/PostgreSQL state persistence
- **Quota Management** — Per-tenant rate limiting

### Streams (`streams.py`)

Utilities for Redis stream naming and communication guards:

```python
from core.streams import assert_agents_stream

# Raises error if orchestrators try to publish to non-agent streams
assert_agents_stream("agentic-dev:agents:rag:tasks")  # ✓ OK
assert_agents_stream("agentic-dev:orchestrators:outreach:tasks")  # ✗ Error
```

### Schemas (`schemas/`)

Shared Pydantic models used across tiers:

- `ReplyPacket` — Structured reply data from leads to outreach
- `LeadResolution` — Lead identification result
- `ConversationSummary` — Thread context summary

## Usage in Agents

Every Tier 3 agent inherits from `AgentHarness`:

```python
from core.harness.agent_harness import AgentHarness

class RAGAgentHarness(AgentHarness):
    def __init__(self, tenant_id: str):
        super().__init__(
            tenant_id=tenant_id,
            agent_name="rag",
        )

    def process_task(self, task: dict) -> dict:
        # RAG-specific logic
        pass
```

## See Also

- [Agent Harness Documentation](harness/README.md)
- [Tier Architecture](../tiers/README.md)
- [Redis Stream Patterns](../docs/architecture/redis/)
