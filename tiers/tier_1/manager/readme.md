# Manager Agent

**Tier:** 1 (Strategic) | **Type:** Decision-Making & Routing Agent

## Purpose

The Manager Agent is the **strategic brain** of the multi-agent system. It receives high-level goals, analyzes intent, and delegates work to the appropriate Tier 2 orchestrators. The Manager **never performs heavy execution work**—it only decides _what_ to run and _when_.

### Key Responsibilities

1. **Analyze goals** — Takes user requests and understands what needs to be done
2. **Take shortcuts** — For simple tasks (<50ms), answers directly without delegating
3. **Delegate complex work** — Routes complicated tasks to specialist orchestrators
4. **Track progress** — Can check on delegated task status
5. **Aggregate results** — Assembles final answers from multiple sources

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    USER REQUEST                              │
│            "Find tech leads and email them"                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │   MANAGER AGENT      │
            │   (Tier 1)           │
            │                      │
            │ 1. Check Shortcuts   │
            │ 2. Analyze Intent    │
            │ 3. Delegate to T2    │
            └──────────┬───────────┘
                       │
       ┌───────────────┴───────────────┐
       ▼                               ▼
┌──────────────────────┐    ┌──────────────────────┐
│ Leads Orchestrator   │    │ Outreach Orchestrator│
│ (Tier 2)             │    │ (Tier 2)             │
└──────────────────────┘    └──────────────────────┘
```

### Communication Pattern

- **Input:** Redis stream `{tenant}:manager:tasks`
- **Output:** Writes to orchestrator streams `{tenant}:orchestrators:{name}:tasks`
- **Results:** Reads from `{tenant}:orchestrators:{name}:results`

**CRITICAL:** Manager communicates **ONLY** with Tier 2 orchestrators. It never directly talks to Tier 3 agents.

## Key Components

| File                       | Purpose                                                   |
| -------------------------- | --------------------------------------------------------- |
| `manager_agent.py`         | Core logic: goal analysis, routing, delegation            |
| `manager_agent_harness.py` | Redis wrapper: stream consumption, retries, observability |
| `consumer.py`              | Entry point: runs the harness loop                        |
| `deep_agent_factory.py`    | Creates LangGraph deep agents for complex reasoning       |
| `shortcut_registry.py`     | Fast paths for simple operations (math, dates, status)    |

### Subdirectories

| Directory  | Purpose                                         |
| ---------- | ----------------------------------------------- |
| `intake/`  | Message intake and validation                   |
| `intent/`  | Intent classification and analysis              |
| `policy/`  | Routing policies and decision rules             |
| `tools/`   | Delegation tools for orchestrator communication |
| `schemas/` | Pydantic models for input/output validation     |
| `tests/`   | Unit and integration tests                      |

## Quick Start

```bash
# Run the Manager consumer
python -m tiers.tier_1.manager.consumer
```

```python
from tiers.tier_1.manager.manager_agent import ManagerAgent

manager = ManagerAgent(redis_client, tenant_id="agentic-dev")

# Simple shortcut (no delegation)
result = manager.execute("What is 25 * 4?")
# Returns: {"path": "shortcut", "result": 100, "latency_ms": 2}

# Complex delegation
result = manager.execute("Find leads and email them")
# Returns: {"path": "deep_agent_delegation",
#           "result": "Delegated to Leads & Outreach orchestrators"}
```

## Delegation Tools

The Manager uses 5 delegation tools to communicate with orchestrators:

```python
1. delegate_coding_task()     → Scripts, automation, data processing
2. delegate_data_query()      → Database queries, analytics, searches
3. delegate_api_request()     → CRM sync (HubSpot, Salesforce), webhooks
4. delegate_email_generation()→ Email generation, personalization
5. check_task_status()        → Check if delegated task is done
```

All tools write to Redis streams for async orchestrator pickup.

## Harness Integration

The Manager is wrapped by `AgentHarness` from `core/harness/`:

```python
from core.harness import AgentHarness, HarnessConfig

config = HarnessConfig.for_production(
    service_name="manager",
    retry_strategy="exponential",
    max_retries=3,
    observability_backend="opentelemetry",
)

harness = AgentHarness.from_config(agent=manager, config=config)
```

The harness provides:

- **Retries** — Exponential backoff on failures
- **Tracing** — OpenTelemetry spans for every execution
- **Checkpointing** — State persistence for crash recovery
- **Quota** — Rate limiting per tenant

## Performance

| Operation               | Latency    | Cost    | Use Case                       |
| ----------------------- | ---------- | ------- | ------------------------------ |
| **Shortcut**            | <10ms      | $0      | Math, date/time, status checks |
| **Single delegation**   | 500-1000ms | ~$0.007 | One task type                  |
| **Multi-step planning** | 2-5s       | ~$0.02  | Complex workflows              |

## Scaling

### In Docker

```yaml
services:
  manager:
    image: manager-worker
    deploy:
      replicas: 3 # Scale horizontally
```

### In Kubernetes

- All manager Pods read from the same Redis consumer group
- HPA can autoscale based on pending tasks in `manager:tasks`
- Stateless design enables clean horizontal scaling

## Configuration

Environment variables:

- `TENANT_ID` — Default tenant for stream naming
- `REDIS_URL` — Redis connection string
- `MANAGER_SHORTCUT_ENABLED` — Enable/disable shortcut paths (default: true)

See `config/manager/routing.yaml` for routing policy configuration.

## Testing

```bash
# Unit tests
pytest tiers/tier_1/manager/tests/ -v

# Integration test with Redis
python scripts/testing/send_manager_test.py
```

## See Also

- [Three-Tier Architecture](../../../docs/architecture/three-tier-system.md)
- [Redis Stream Patterns](../../../docs/architecture/redis/)
- [Harness Quick Reference](../../../docs/reference/harness-quick-reference.md)
