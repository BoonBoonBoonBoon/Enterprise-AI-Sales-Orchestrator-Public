# Tier 3 - Execution Layer

**Role:** Atomic Task Execution

## Purpose

Tier 3 contains **agents** that:

- Perform specialized, atomic tasks
- Are wrapped in Agent Harness for reliability (retries, observability, checkpointing)
- Report results back to Tier 2 orchestrators
- Have no knowledge of the broader workflow

## Agents

| Agent                                                | Responsibility                                | Database Role                | Status      |
| ---------------------------------------------------- | --------------------------------------------- | ---------------------------- | ----------- |
| [rag_agent/](rag_agent/)                             | Retrieval-Augmented Generation, vector search | `agent_reader` (SELECT only) | ✅ Active   |
| [persistence_agent/](persistence_agent/)             | CRUD operations on all tables                 | `agent_writer` (full CRUD)   | ✅ Active   |
| [copywriter_agent/](copywriter_agent/)               | AI-powered content generation                 | None                         | ✅ Active   |
| [scheduler_agent/](scheduler_agent/)                 | Meeting scheduling                            | None                         | 🚧 Skeleton |
| [channel_sequencer_agent/](channel_sequencer_agent/) | Channel sequence optimization                 | None                         | 🚧 Skeleton |

## Shared Components

| File         | Purpose                                 |
| ------------ | --------------------------------------- |
| `factory.py` | Agent factory for dynamic instantiation |

## Communication

```
Orchestrator (Tier 2)
    │
    ▼ {tenant}:agents:{name}:tasks
┌──────────────────────┐
│    AGENT (Tier 3)    │  ← You are here
│                      │
│  Performs atomic     │
│  specialized task    │
└──────────┬───────────┘
           │
           ▼ {tenant}:agents:{name}:results
    Orchestrator (Tier 2)
```

### Stream Naming

```
Input:  {tenant}:agents:{name}:tasks
Output: {tenant}:agents:{name}:results
```

## Agent Harness Pattern

All agents are wrapped in `AgentHarness` from `core/harness/`:

```python
from core.harness.agent_harness import AgentHarness

class MyAgentHarness(AgentHarness):
    def __init__(self, tenant_id: str):
        super().__init__(
            tenant_id=tenant_id,
            agent_name="my_agent",  # Stream: {tenant}:agents:my_agent:tasks
            result_stream_suffix="results"
        )

    def process_task(self, task: dict) -> dict:
        payload = task.get("payload", {})
        result = my_agent_function(payload)
        return {"status": "success", "data": result}
```

## Standard Folder Structure

Each agent follows this structure:

```
tiers/tier_3/{name}_agent/
├── README.md                # Documentation
├── {name}_agent.py          # Core logic (LangGraph StateGraph)
├── {name}_agent_harness.py  # Redis wrapper (AgentHarness subclass)
├── consumer.py              # Entry point for Redis stream consumer
├── validators.py            # Pydantic models for input/output
├── worker.py                # Synchronous execution wrapper (optional)
├── schemas/                 # Additional Pydantic models
└── tests/                   # Unit tests
```

## Quick Start

```bash
# Run individual agents
python -m tiers.tier_3.rag_agent.consumer
python -m tiers.tier_3.persistence_agent.consumer
python -m tiers.tier_3.copywriter_agent.consumer
```

## Database Roles

Agents use role-based database access:

| Role           | Permissions                    | Used By           |
| -------------- | ------------------------------ | ----------------- |
| `agent_reader` | SELECT only                    | RAG Agent         |
| `agent_writer` | SELECT, INSERT, UPDATE, DELETE | Persistence Agent |

## See Also

- [Tier Architecture Overview](../README.md)
- [Agent Harness](../../core/harness/README.md)
- [Persistence Agent README](persistence_agent/README.md)
- [RAG Agent README](rag_agent/README.md)
