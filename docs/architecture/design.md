# System Design

This document describes the high-level design of the Agentic System.

## Design Goals

1. **Scalability** - Handle thousands of concurrent leads and messages
2. **Reliability** - Never lose a task; graceful failure handling
3. **Extensibility** - Easy to add new agents and orchestrators
4. **Observability** - Full visibility into system behavior
5. **Multi-tenancy** - Complete tenant isolation

## Architecture Pattern

The system follows a **Tiered Agent Orchestration** pattern:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         External World                               │
│    (Email, Webhooks, API calls, Scheduled triggers)                 │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      TIER 1: Strategic                              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                        Manager                               │   │
│  │  • Intent classification                                     │   │
│  │  • Goal decomposition                                        │   │
│  │  • Orchestrator routing                                      │   │
│  │  • Cross-workflow coordination                               │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     TIER 2: Business Logic                          │
│  ┌───────────────────────┐   ┌───────────────────────┐             │
│  │   LeadsOrchestrator   │   │  OutreachOrchestrator │             │
│  │   • Inbound handling  │   │   • Campaign exec     │             │
│  │   • Lead enrichment   │   │   • Reply handling    │             │
│  │   • Qualification     │   │   • Email sending     │             │
│  └───────────────────────┘   └───────────────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
                                  │
           ┌──────────────────────┼──────────────────────┐
           ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      TIER 3: Execution                              │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐           │
│  │   RAG Agent   │  │  Persistence  │  │  Copywriter   │           │
│  │   • Retrieval │  │   • CRUD ops  │  │   • LLM calls │           │
│  │   • Embedding │  │   • Supabase  │  │   • Drafting  │           │
│  └───────────────┘  └───────────────┘  └───────────────┘           │
└─────────────────────────────────────────────────────────────────────┘
```

## Core Principles

### Vertical Communication Only

Orchestrators (Tier 2) cannot communicate directly with each other. All cross-orchestrator coordination must go through the Manager (Tier 1).

```
✅ CORRECT:
Manager → LeadsOrchestrator → RAGAgent
Manager → OutreachOrchestrator → CopywriterAgent

❌ FORBIDDEN:
LeadsOrchestrator → OutreachOrchestrator (direct)
```

### Single Responsibility

Each component has one job:

- **Manager**: Routing decisions only (never generates content)
- **Orchestrators**: Workflow coordination (decompose into agent calls)
- **Agents**: Atomic tasks (one function, one purpose)

### Async-First

All inter-component communication is asynchronous via Redis Streams. No synchronous RPC calls between tiers.

---

## Component Interactions

### Message Flow

```
1. External event (email, API call)
      │
      ▼
2. Event Router → Manager task stream
      │
      ▼
3. Manager classifies intent, routes to orchestrator
      │
      ▼
4. Orchestrator decomposes into agent tasks
      │
      ▼
5. Agents execute, return results
      │
      ▼
6. Orchestrator aggregates, returns to Manager
      │
      ▼
7. Manager may chain to another orchestrator
      │
      ▼
8. Final result returned or action taken
```

### Consumer Pattern

Each component runs as a Redis Streams consumer:

```python
while running:
    messages = redis.xreadgroup(
        group=consumer_group,
        consumer=consumer_name,
        streams={task_stream: ">"},
        block=5000
    )

    for message in messages:
        result = process_task(message)
        redis.xadd(result_stream, result)
        redis.xack(task_stream, consumer_group, message.id)
```

---

## Key Design Decisions

### Why Redis Streams?

1. **Durability** - Messages persist until acknowledged
2. **Consumer Groups** - Built-in load balancing
3. **Ordering** - Guaranteed message order per stream
4. **Simplicity** - No separate message broker needed

### Why Tiered Architecture?

1. **Separation of Concerns** - Each tier has distinct responsibility
2. **Scalability** - Scale each tier independently
3. **Testability** - Mock any tier for testing
4. **Flexibility** - Replace implementations without affecting others

### Why Supabase?

1. **PostgreSQL** - Full SQL capabilities
2. **RLS** - Built-in row-level security
3. **Realtime** - Future capability for live updates
4. **Hosted** - Reduced operational burden

---

## State Management

### Stateless Agents

All agents are stateless. State is:

- Passed in via task payload
- Retrieved from database on demand
- Never cached locally

### Database as Source of Truth

```
Transient State (Redis):
├── Current tasks in flight
├── Consumer group positions
└── Task results (TTL)

Persistent State (Supabase):
├── Leads, conversations, messages
├── Campaign configurations
└── Client settings
```

---

## Error Handling Strategy

### Retry Policy

1. Transient errors → Automatic retry (3 attempts)
2. Permanent errors → Return error result, move to DLQ
3. Timeout → Task redelivered to another consumer

### Dead Letter Queue

Failed tasks after max retries:

```
{tenant_id}:agents:{agent_name}:dlq
```

### Circuit Breaker

For external service calls (LLM APIs, email):

```python
if failure_count > threshold:
    circuit_open = True
    # Return cached response or degraded result
```

---

## Security Model

### Multi-Tenancy

- All stream keys prefixed with `{tenant_id}:`
- RLS policies filter by tenant claim in JWT
- No cross-tenant data access possible

### Role-Based Access

| Role           | Permissions  |
| -------------- | ------------ |
| `agent_reader` | SELECT only  |
| `agent_writer` | Full CRUD    |
| `service_role` | Admin access |

### API Security

- All Supabase calls use signed JWT
- JWT includes role and tenant claims
- Policies verify claims on every query

---

## Performance Considerations

### Batching

- Batch writes to database when possible
- Batch reads for lead context retrieval
- Batch LLM calls where feasible

### Caching

- Lead context cached for workflow duration
- Configuration cached at startup
- No cross-request state caching

### Scaling

| Component | Scaling Strategy                |
| --------- | ------------------------------- |
| Agents    | Horizontal (multiple consumers) |
| Redis     | Vertical (larger instance)      |
| Supabase  | Vertical (plan upgrade)         |

## Related

- [Data Flow](data-flow.md)
- [Communication Rules](communication.md)
- [Security Model](security.md)
