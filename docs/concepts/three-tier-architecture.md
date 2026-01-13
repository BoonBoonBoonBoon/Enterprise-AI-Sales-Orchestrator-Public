# Three-Tier Architecture

The Agentic System uses a three-tier hierarchical architecture for agent orchestration. This design ensures clear separation of concerns, scalable workflows, and maintainable code.

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         TIER 1                                  │
│                    Strategic Layer                              │
│                                                                 │
│                     ┌──────────────┐                            │
│                     │   Manager    │                            │
│                     │    Agent     │                            │
│                     └──────┬───────┘                            │
│                            │                                    │
│             ┌──────────────┼──────────────┐                     │
│             │              │              │                     │
│             ▼              ▼              ▼                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                      TIER 2                               │   │
│  │                 Orchestration Layer                       │   │
│  │                                                           │   │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐              │   │
│  │  │  Leads   │   │ Outreach │   │ Inbound  │              │   │
│  │  │  Orch.   │   │  Orch.   │   │  Orch.   │              │   │
│  │  └────┬─────┘   └────┬─────┘   └────┬─────┘              │   │
│  │       │              │              │                     │   │
│  └───────┼──────────────┼──────────────┼────────────────────┘   │
│          │              │              │                        │
│          ▼              ▼              ▼                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                      TIER 3                               │   │
│  │                   Execution Layer                         │   │
│  │                                                           │   │
│  │  ┌─────────┐   ┌─────────────┐   ┌────────────┐          │   │
│  │  │   RAG   │   │ Persistence │   │ Copywriter │          │   │
│  │  │  Agent  │   │    Agent    │   │   Agent    │          │   │
│  │  └─────────┘   └─────────────┘   └────────────┘          │   │
│  │                                                           │   │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Tier Responsibilities

### Tier 1: Strategic Layer (Manager)

**One component:** ManagerAgent

**Responsibilities:**

- Receives high-level goals and events
- Makes strategic decisions (what needs to happen)
- Routes to appropriate orchestrators
- Coordinates cross-orchestrator workflows
- Does NOT perform any work itself

**Examples:**

- "New inbound email" → Decide: enrich? reply? store?
- "Start campaign X" → Delegate to Outreach Orchestrator
- "Lead qualified" → Chain: Leads result → Outreach task

### Tier 2: Orchestration Layer

**Components:** LeadsOrchestrator, OutreachOrchestrator, InboundOrchestrator

**Responsibilities:**

- Decompose workflows into atomic tasks
- Delegate tasks to Tier 3 agents
- Coordinate multi-step processes within their domain
- Report results back to Manager

**Examples:**

- LeadsOrchestrator: New lead → enrich → score → store
- OutreachOrchestrator: Reply request → get context → draft → send

### Tier 3: Execution Layer (Agents)

**Components:** RAGAgent, PersistenceAgent, CopywriterAgent

**Responsibilities:**

- Perform single, atomic operations
- No delegation (leaf nodes)
- Report results to calling orchestrator

**Examples:**

- RAGAgent: Retrieve lead context from database
- PersistenceAgent: Store lead record
- CopywriterAgent: Generate email copy

## Communication Rules

### Vertical-Only Communication

!!! warning "Critical Rule"
**Tier 2 orchestrators CANNOT communicate with each other directly.**

All cross-domain coordination must flow through the Manager.

```
CORRECT:
    Manager → LeadsOrchestrator → result → Manager → OutreachOrchestrator

FORBIDDEN:
    LeadsOrchestrator → OutreachOrchestrator  ❌
```

### Direction of Flow

| From   | To     | Allowed?   |
| ------ | ------ | ---------- |
| Tier 1 | Tier 2 | ✅ Tasks   |
| Tier 2 | Tier 1 | ✅ Results |
| Tier 2 | Tier 3 | ✅ Tasks   |
| Tier 3 | Tier 2 | ✅ Results |
| Tier 2 | Tier 2 | ❌ Never   |
| Tier 3 | Tier 3 | ❌ Never   |

## Why Three Tiers?

### Separation of Concerns

- **Strategy** is isolated in Tier 1
- **Business logic** lives in Tier 2
- **Execution** is handled by Tier 3

### Scalability

- Scale Tier 3 agents independently (add more RAG workers)
- Add new orchestrators without touching Manager
- Add new agents without touching orchestrators

### Testability

- Test agents in isolation
- Mock Redis for orchestrator tests
- Test Manager routing logic separately

### Maintainability

- Clear ownership of functionality
- Predictable code locations
- Easier onboarding

## Data Flow Example

**Scenario:** Inbound email triggers reply

```
1. Email webhook → Manager

2. Manager decides:
   - Action: REPLY
   - Route to: LeadsOrchestrator

3. Manager → LeadsOrchestrator (via Redis Stream)
   Task: {action: "process_inbound", email_data: {...}}

4. LeadsOrchestrator:
   a. → RAGAgent: Get lead context
   b. ← RAGAgent: Returns context + query_trace
   c. Creates reply_packet
   d. → Manager: Result with reply_packet

5. Manager chains to Outreach:
   → OutreachOrchestrator (via Redis Stream)
   Task: {action: "draft_reply", reply_packet: {...}}

6. OutreachOrchestrator:
   a. → CopywriterAgent: Generate reply
   b. ← CopywriterAgent: Returns email draft
   c. → EmailService: Send email
   d. → PersistenceAgent: Store sent message
   e. → Manager: Result (email sent)
```

## Implementation Details

### Stream Naming Convention

```
{tenant}:manager:tasks          # Manager input
{tenant}:manager:results        # Manager output

{tenant}:orchestrators:{name}:tasks    # Orchestrator input
{tenant}:orchestrators:{name}:results  # Orchestrator output

{tenant}:agents:{name}:tasks    # Agent input
{tenant}:agents:{name}:results  # Agent output
```

### Harness Pattern

Each tier uses a harness to handle common concerns:

```python
# Tier 3 Agent
class MyAgentHarness(AgentHarness):
    def process_task(self, task: dict) -> dict:
        # Your logic here
        return {"status": "success", "result": {...}}

# Tier 2 Orchestrator (with DeepAgent tools)
class MyOrchestrator(DeepAgentHarness):
    def __init__(self):
        super().__init__(tools=[
            self.call_rag_agent,
            self.call_persistence_agent,
        ])
```

## Related

- [ADR-001: Three-Tier Architecture](../architecture/decisions/001-three-tier-architecture.md)
- [ADR-002: Vertical-Only Communication](../architecture/decisions/002-vertical-only-communication.md)
- [Redis Streams](redis-streams.md)
- [Agent Harness](agent-harness.md)
