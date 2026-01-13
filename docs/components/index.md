# Components

The Agentic System is composed of modular, independently deployable components organized into three tiers plus a shared services layer. Each component has a specific responsibility and communicates through well-defined interfaces.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        TIER 1 - STRATEGIC                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Manager Agent                         │   │
│  │         Routes goals • Classifies intent • Delegates     │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     TIER 2 - BUSINESS LOGIC                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │    Leads    │  │  Outreach   │  │   Inbound   │  + more     │
│  │ Orchestrator│  │ Orchestrator│  │ Orchestrator│             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TIER 3 - EXECUTION                         │
│  ┌───────────┐  ┌─────────────┐  ┌────────────┐                │
│  │    RAG    │  │ Persistence │  │ Copywriter │   + more       │
│  │   Agent   │  │    Agent    │  │   Agent    │                │
│  └───────────┘  └─────────────┘  └────────────┘                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         SERVICES                                │
│  ┌───────┐  ┌─────────────┐  ┌───────────┐  ┌───────┐         │
│  │ Redis │  │ Persistence │  │ Vector DB │  │ Email │         │
│  └───────┘  └─────────────┘  └───────────┘  └───────┘         │
└─────────────────────────────────────────────────────────────────┘
```

## Component Categories

### [Tier 1 - Manager](tier-1/index.md)

The strategic layer containing the Manager Agent — the single entry point that receives all external goals and routes them to appropriate orchestrators.

| Component                          | Status    | Purpose                                           |
| ---------------------------------- | --------- | ------------------------------------------------- |
| [Manager Agent](tier-1/manager.md) | ✅ Active | Intent classification, policy routing, delegation |

### [Tier 2 - Orchestrators](tier-2/index.md)

The business logic layer containing domain-specific orchestrators that decompose complex workflows into atomic agent tasks.

| Component                                   | Status         | Purpose                                   |
| ------------------------------------------- | -------------- | ----------------------------------------- |
| [Leads Orchestrator](tier-2/leads.md)       | ✅ Active      | Lead qualification, enrichment, promotion |
| [Outreach Orchestrator](tier-2/outreach.md) | ✅ Active      | Campaign execution, reply handling        |
| [Inbound Orchestrator](tier-2/inbound.md)   | 🚧 In Progress | Inbound message processing                |

### [Tier 3 - Agents](tier-3/index.md)

The execution layer containing specialized agents that perform atomic, stateless tasks.

| Component                                  | Status    | DB Role        | Purpose                          |
| ------------------------------------------ | --------- | -------------- | -------------------------------- |
| [RAG Agent](tier-3/rag.md)                 | ✅ Active | `agent_reader` | Context retrieval, vector search |
| [Persistence Agent](tier-3/persistence.md) | ✅ Active | `agent_writer` | CRUD operations                  |
| [Copywriter Agent](tier-3/copywriter.md)   | ✅ Active | None           | AI content generation            |

### [Services](services/index.md)

Shared infrastructure services used by agents and orchestrators.

| Service                                        | Purpose                       |
| ---------------------------------------------- | ----------------------------- |
| [Redis Service](services/redis.md)             | Stream management, pub/sub    |
| [Persistence Service](services/persistence.md) | Supabase adapter, queries     |
| [Vector DB](services/vector-db.md)             | Embeddings, similarity search |
| [Email Service](services/email.md)             | Gmail integration             |

## Component Lifecycle

All components follow the same lifecycle pattern:

1. **Initialization** — Load config, connect to Redis
2. **Registration** — Register with consumer group
3. **Listen** — Block on `XREADGROUP` for tasks
4. **Process** — Execute task, produce result
5. **Acknowledge** — `XACK` the processed message
6. **Publish** — Send result to result stream

See [Running Consumers](../guides/ops/consumers.md) for operational details.

## Adding New Components

- [Adding a New Agent](../guides/dev/new-agent.md) — Step-by-step Tier 3 agent creation
- [Adding an Orchestrator](../guides/dev/new-orchestrator.md) — Step-by-step Tier 2 orchestrator creation
