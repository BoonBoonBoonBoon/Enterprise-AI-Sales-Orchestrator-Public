# Tier 3 - Agents

The execution layer of the Agentic System. Tier 3 contains specialized **Agents** that perform atomic, stateless tasks. Each agent has a single responsibility and well-defined inputs/outputs.

## Role in the Architecture

```
                    TIER 2 - Orchestrators
                            │
    ┌───────────────────────┼───────────────────────┐
    ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TIER 3 - AGENTS                            │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │    RAG Agent    │  │   Persistence   │  │   Copywriter    │ │
│  │                 │  │      Agent      │  │      Agent      │ │
│  │  • Retrieve     │  │                 │  │                 │ │
│  │    context      │  │  • Create       │  │  • Generate     │ │
│  │  • Vector       │  │  • Read         │  │    emails       │ │
│  │    search       │  │  • Update       │  │  • Personalize  │ │
│  │  • Enrich       │  │  • Delete       │  │    content      │ │
│  │    leads        │  │  • Batch ops    │  │  • Draft        │ │
│  │                 │  │                 │  │    replies      │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘ │
│           │                    │                    │          │
│     agent_reader         agent_writer              None        │
│      (SELECT)         (CRUD operations)        (No DB access)  │
└───────────┴────────────────────┴────────────────────┴──────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                         SERVICES                                │
│        Supabase  •  Redis  •  Vector DB  •  LLM APIs           │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Inventory

### Active Agents

| Agent                               | Status    | DB Role        | Path                              | Purpose                                           |
| ----------------------------------- | --------- | -------------- | --------------------------------- | ------------------------------------------------- |
| [RAG Agent](rag.md)                 | ✅ Active | `agent_reader` | `tiers/tier_3/rag_agent/`         | Context retrieval, vector search, lead enrichment |
| [Persistence Agent](persistence.md) | ✅ Active | `agent_writer` | `tiers/tier_3/persistence_agent/` | CRUD operations on all tables                     |
| [Copywriter Agent](copywriter.md)   | ✅ Active | None           | `tiers/tier_3/copywriter_agent/`  | AI-powered content generation                     |
| [Classifier Agent](classifier.md)   | ✅ Active | None           | `tiers/tier_3/classifier_agent/`  | Email triage/classification for inbound workflows |

### In Development

| Agent                                     | Status         | Path                                    | Planned Purpose                            |
| ----------------------------------------- | -------------- | --------------------------------------- | ------------------------------------------ |
| Scheduler Agent                           | 🚧 Skeleton    | `tiers/tier_3/scheduler_agent/`         | Task scheduling, delay management          |
| [Channel Sequencer](channel-sequencer.md) | 🚧 In Progress | `tiers/tier_3/channel_sequencer_agent/` | MVP-safe outbound sequencing + persistence |

See [Roadmap → In Progress](../../roadmap/in-progress.md) for development status.

## Database Roles

Agents have strict database access controls enforced at the PostgreSQL GRANT level:

| Role           | Permissions                            | Used By           |
| -------------- | -------------------------------------- | ----------------- |
| `agent_reader` | `SELECT` only                          | RAG Agent         |
| `agent_writer` | `SELECT`, `INSERT`, `UPDATE`, `DELETE` | Persistence Agent |
| None           | No database access                     | Copywriter Agent  |

This separation ensures:

- **RAG Agent** can never accidentally modify data
- **Copywriter Agent** has no database access at all
- Only **Persistence Agent** can write to the database

See [Database → RLS Policies](../../reference/database/rls.md) for row-level security details.

## Standard Agent Structure

Every Tier 3 agent follows this folder structure:

```
tiers/tier_3/{agent_name}/
├── {agent_name}.py          # Core logic (LangGraph StateGraph)
├── {agent_name}_harness.py  # Redis wrapper (AgentHarness subclass)
├── consumer.py              # Entry point for Redis stream consumer
├── validators.py            # Pydantic models for input/output
├── worker.py                # Synchronous execution wrapper
├── __init__.py
└── README.md
```

## Agent Harness Pattern

All agents are wrapped in a `Harness` that provides:

- **Redis communication** — Automatic stream reading/writing
- **Retry logic** — Configurable retry with exponential backoff
- **Circuit breaker** — Fail-fast when downstream services are unhealthy
- **Observability** — Automatic tracing and metrics
- **Checkpointing** — State persistence for resumable workflows

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

See [Concepts → Agent Harness](../../concepts/agent-harness.md) for details.

## Stream Interface

Each agent follows this stream naming pattern:

**Input:**

```
{tenant}:agents:{agent_name}:tasks
```

**Output:**

```
{tenant}:agents:{agent_name}:results
```

### Example: RAG Agent

```
Input:   agentic-dev:agents:rag:tasks
Output:  agentic-dev:agents:rag:results
```

## Adding a New Agent

See [Adding a New Agent](../../guides/dev/new-agent.md) for a complete tutorial covering:

1. Folder structure setup
2. Core logic implementation
3. Harness wrapper
4. Consumer entry point
5. Validators and tests
6. Registration and deployment

## Quick Start

```powershell
# Start RAG Agent
& ".venv/Scripts/python.exe" -m tiers.tier_3.rag_agent.consumer

# Start Persistence Agent
& ".venv/Scripts/python.exe" -m tiers.tier_3.persistence_agent.consumer

# Start Copywriter Agent
& ".venv/Scripts/python.exe" -m tiers.tier_3.copywriter_agent.consumer
```
