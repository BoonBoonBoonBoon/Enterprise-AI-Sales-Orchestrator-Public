# Manager Agent

The Manager Agent is the strategic decision-maker at Tier 1, routing high-level goals to appropriate orchestrators.

## Overview

| Property          | Value                                   |
| ----------------- | --------------------------------------- |
| **Tier**          | 1 (Strategic)                           |
| **Stream**        | `{tenant}:manager:tasks`                |
| **Database Role** | None (decision-only)                    |
| **Core File**     | `tiers/tier_1/manager/manager_agent.py` |

## Responsibilities

- Receive high-level events and goals
- Decide what actions are needed (classify intent)
- Route tasks to Tier 2 orchestrators
- Chain workflows across orchestrators
- **Never** perform work itself

## Critical Rules

!!! danger "Manager Does NOT Generate Content"
The Manager **never** creates:

    - Email bodies or subject lines
    - Outreach copy
    - Reply drafts
    - Any customer-facing content

    Content generation is **always** delegated to the Copywriter Agent via orchestrators.

!!! info "Decision + Delegation Only"
Manager outputs are always:

    - Intent classification
    - Routing decisions
    - Delegation metadata
    - Workflow chaining instructions

## Actions

### `process_goal`

Handle a high-level business goal.

**Request:**

```json
{
  "action": "process_goal",
  "goal": "new_inbound_email",
  "data": {
    "from": "john@example.com",
    "subject": "Interested in your product",
    "body": "Hi, I saw your demo..."
  }
}
```

**Response:**

```json
{
  "status": "success",
  "result": {
    "intent": "inbound_inquiry",
    "actions": ["store", "enrich", "reply"],
    "delegations": [
      {
        "target": "leads_orchestrator",
        "action": "process_inbound",
        "priority": 1
      }
    ]
  }
}
```

### `chain_workflow`

Continue a multi-step workflow.

**Request:**

```json
{
  "action": "chain_workflow",
  "source_result": {
    "orchestrator": "leads",
    "reply_packet": {...}
  }
}
```

**Response:**

```json
{
  "status": "success",
  "result": {
    "next_step": "outreach_orchestrator",
    "task": {
      "action": "draft_reply",
      "reply_packet": {...}
    }
  }
}
```

## Intent Classification

The Manager classifies incoming events:

| Event             | Intent            | Routed To               |
| ----------------- | ----------------- | ----------------------- |
| New inbound email | `inbound_inquiry` | LeadsOrchestrator       |
| Start campaign    | `campaign_start`  | OutreachOrchestrator    |
| Lead qualified    | `lead_qualified`  | OutreachOrchestrator    |
| Reply needed      | `reply_request`   | Chain: Leads → Outreach |
| Data enrichment   | `enrich_lead`     | LeadsOrchestrator       |

## Routing

### Router Module

```python
# tiers/tier_1/manager/policy/router.py

def route_intent(intent: str, tenant_id: str) -> str:
    """Return target stream for intent."""
    routes = {
        "inbound_inquiry": f"{tenant_id}:orchestrators:leads:tasks",
        "campaign_start": f"{tenant_id}:orchestrators:outbound:tasks",
        "lead_qualified": f"{tenant_id}:orchestrators:outbound:tasks",
        "enrich_lead": f"{tenant_id}:orchestrators:leads:tasks",
    }
    return routes.get(intent)
```

### Stream Names

```
Manager reads:   {tenant}:manager:tasks
Manager writes:  {tenant}:orchestrators:{name}:tasks
Manager writes:  {tenant}:manager:results
```

## Workflow Chaining

When Leads Orchestrator returns a `reply_packet`, Manager chains to Outreach:

```
1. Event: Inbound email
   ↓
2. Manager → LeadsOrchestrator
   Task: process_inbound
   ↓
3. LeadsOrchestrator returns result with reply_packet
   ↓
4. Manager receives result, sees reply_packet
   ↓
5. Manager → OutreachOrchestrator
   Task: draft_reply with reply_packet
   ↓
6. OutreachOrchestrator → Copywriter → Email sent
   ↓
7. Manager receives final result
```

## File Structure

```
tiers/tier_1/manager/
├── manager_agent.py         # Main agent
├── manager_harness.py       # Redis wrapper
├── consumer.py              # Entry point
├── policy/
│   ├── router.py            # Intent → Stream routing
│   └── intent.py            # Intent classification
└── README.md
```

## Configuration

### Environment Variables

| Variable    | Default                  | Description               |
| ----------- | ------------------------ | ------------------------- |
| `TENANT_ID` | `agentic-dev`            | Default tenant            |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection          |
| `LLM_MODEL` | `gpt-4o`                 | For intent classification |

## Error Handling

| Code             | Description                |
| ---------------- | -------------------------- |
| `UNKNOWN_INTENT` | Could not classify event   |
| `NO_ROUTE`       | No orchestrator for intent |
| `CHAIN_FAILED`   | Workflow chaining failed   |

## Usage Example

### Sending a Goal

```python
import json
from services.redis.client import get_redis_client

redis = get_redis_client()

task = {
    "task_id": "goal-001",
    "tenant_id": "agentic-dev",
    "payload": {
        "action": "process_goal",
        "goal": "new_inbound_email",
        "data": {
            "from": "lead@example.com",
            "subject": "Inquiry",
            "body": "..."
        }
    },
    "metadata": {"source": "email_webhook"}
}

redis.xadd("agentic-dev:manager:tasks", {"data": json.dumps(task)})
```

### Running Consumer

```powershell
& ".venv/Scripts/python.exe" -m tiers.tier_1.manager.consumer
```

## Demo

```powershell
& ".venv/Scripts/python.exe" examples/manager_demo.py
```

## Related

- [Leads Orchestrator](../tier-2/leads.md)
- [Outreach Orchestrator](../tier-2/outreach.md)
- [Three-Tier Architecture](../../concepts/three-tier-architecture.md)
- [ADR-002: Vertical Communication](../../architecture/decisions/002-vertical-only-communication.md)
