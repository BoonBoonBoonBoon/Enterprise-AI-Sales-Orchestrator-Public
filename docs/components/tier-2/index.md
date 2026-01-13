# Tier 2 - Orchestrators

The business logic layer of the Agentic System. Tier 2 contains domain-specific **Orchestrators** that receive high-level goals from the Manager and decompose them into sequences of atomic agent tasks.

## Role in the Architecture

```
                    TIER 1 - Manager
                          │
    ┌─────────────────────┼─────────────────────┐
    ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                   TIER 2 - ORCHESTRATORS                        │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │      Leads      │  │    Outreach     │  │     Inbound     │ │
│  │   Orchestrator  │  │   Orchestrator  │  │   Orchestrator  │ │
│  │                 │  │                 │  │                 │ │
│  │  • Qualify      │  │  • Execute      │  │  • Route        │ │
│  │  • Enrich       │  │    campaigns    │  │    messages     │ │
│  │  • Promote      │  │  • Handle       │  │  • Classify     │ │
│  │    leads        │  │    replies      │  │    intent       │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘ │
│           │                    │                    │          │
└───────────┼────────────────────┼────────────────────┼──────────┘
            │                    │                    │
            ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│              TIER 3 - RAG, Persistence, Copywriter              │
└─────────────────────────────────────────────────────────────────┘
```

## Critical Communication Rule

!!! danger "Vertical Only — No Horizontal Communication"
Orchestrators can **ONLY** communicate:

    - **UPWARD:** To Tier 1 Manager (via result streams)
    - **DOWNWARD:** To Tier 3 Agents (via agent task streams)

    **Orchestrators CANNOT communicate with each other directly.**

    All cross-orchestrator coordination MUST go through the Manager.

    ```python
    # ❌ FORBIDDEN
    publish_to("agentic-dev:orchestrators:outreach:tasks")  # From Leads

    # ✅ CORRECT
    publish_to("agentic-dev:agents:rag:tasks")  # Downward to agent
    publish_to("agentic-dev:orchestrators:leads:results")  # Upward to Manager
    ```

## Orchestrator Inventory

### Active Orchestrators

| Orchestrator                         | Status    | Path                                  | Purpose                                   |
| ------------------------------------ | --------- | ------------------------------------- | ----------------------------------------- |
| [Leads Orchestrator](leads.md)       | ✅ Active | `tiers/tier_2/leads_orchestrator/`    | Lead qualification, enrichment, promotion |
| [Outreach Orchestrator](outreach.md) | ✅ Active | `tiers/tier_2/outreach_orchestrator/` | Campaign execution, reply generation      |

### In Development

| Orchestrator                       | Status      | Path                                 | Planned Purpose                            |
| ---------------------------------- | ----------- | ------------------------------------ | ------------------------------------------ |
| [Inbound Orchestrator](inbound.md) | 🚧 Skeleton | `tiers/tier_2/inbound_orchestrator/` | Inbound message classification and routing |
| Audit Orchestrator                 | 🚧 Skeleton | `tiers/tier_2/audit_orchestrator/`   | Compliance and quality auditing            |
| Control Orchestrator               | 🚧 Skeleton | `tiers/tier_2/control_orchestrator/` | System control and configuration           |

See [Roadmap → In Progress](../../roadmap/in-progress.md) for development status.

## Stream Interface

Each orchestrator follows this stream naming pattern:

**Input:**

```
{tenant}:orchestrators:{name}:tasks
```

**Output:**

```
{tenant}:orchestrators:{name}:results
```

**Delegates to Agents:**

```
{tenant}:agents:{agent_name}:tasks
```

### Example: Leads Orchestrator

```
Input:   agentic-dev:orchestrators:leads:tasks
Output:  agentic-dev:orchestrators:leads:results
Agents:  agentic-dev:agents:rag:tasks
         agentic-dev:agents:persistence:tasks
```

## Common Patterns

### 1. DeepAgent Delegation

Orchestrators use `DeepAgent` tools to delegate to Tier 3:

```python
from core.harness.deep_agent_harness import DeepAgentHarness

class LeadsOrchestrator(DeepAgentHarness):
    def __init__(self, tenant_id: str):
        super().__init__(
            tenant_id=tenant_id,
            orchestrator_name="leads"
        )

    async def process(self, task: dict) -> dict:
        # Delegate to RAG for context
        context = await self.delegate_to_agent("rag", {
            "action": "get_lead_context",
            "lead_id": task["lead_id"]
        })
        # Process and return
        return {"status": "success", "context": context}
```

### 2. Result Bubbling

Results flow upward with `reply_packet` for chained workflows:

```python
return {
    "status": "success",
    "reply_packet": {
        "lead_id": lead_id,
        "context": enriched_context,
        "thread_id": conversation_id
    }
}
```

## Adding a New Orchestrator

See [Adding an Orchestrator](../../guides/dev/new-orchestrator.md) for a complete tutorial.

## Quick Start

```powershell
# Start Leads Orchestrator
& ".venv/Scripts/python.exe" -m tiers.tier_2.leads_orchestrator.consumer

# Start Outreach Orchestrator
& ".venv/Scripts/python.exe" -m tiers.tier_2.outreach_orchestrator.consumer
```
