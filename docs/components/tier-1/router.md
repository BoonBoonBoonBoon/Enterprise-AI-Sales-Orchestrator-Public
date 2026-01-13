# Policy Router

The Policy Router determines which orchestrator should handle a given intent.

## Overview

| Component    | Description                             |
| ------------ | --------------------------------------- |
| **Location** | `tiers/tier_1/manager/policy/router.py` |
| **Purpose**  | Map intents to orchestrator streams     |
| **Used By**  | Manager Agent                           |

## Routing Logic

```python
def route_intent(intent: str, tenant_id: str) -> str:
    """
    Return the target stream for a given intent.

    Args:
        intent: Classified intent string
        tenant_id: Tenant identifier for stream prefix

    Returns:
        Full stream key for the target orchestrator
    """
    routes = {
        # Lead-related intents → Leads Orchestrator
        "inbound_inquiry": f"{tenant_id}:orchestrators:leads:tasks",
        "enrich_lead": f"{tenant_id}:orchestrators:leads:tasks",
        "qualify_lead": f"{tenant_id}:orchestrators:leads:tasks",

        # Outreach intents → Outreach Orchestrator
        "campaign_start": f"{tenant_id}:orchestrators:outbound:tasks",
        "draft_reply": f"{tenant_id}:orchestrators:outbound:tasks",
        "send_followup": f"{tenant_id}:orchestrators:outbound:tasks",

        # Inbound handling
        "process_inbound": f"{tenant_id}:orchestrators:inbound:tasks",
    }

    return routes.get(intent)
```

## Intent → Orchestrator Mapping

| Intent            | Target Orchestrator | Stream Suffix                  |
| ----------------- | ------------------- | ------------------------------ |
| `inbound_inquiry` | Leads               | `orchestrators:leads:tasks`    |
| `enrich_lead`     | Leads               | `orchestrators:leads:tasks`    |
| `qualify_lead`    | Leads               | `orchestrators:leads:tasks`    |
| `campaign_start`  | Outreach            | `orchestrators:outbound:tasks` |
| `draft_reply`     | Outreach            | `orchestrators:outbound:tasks` |
| `send_followup`   | Outreach            | `orchestrators:outbound:tasks` |
| `process_inbound` | Inbound             | `orchestrators:inbound:tasks`  |

## Usage

```python
from tiers.tier_1.manager.policy.router import route_intent

# In Manager
intent = self.classify_intent(event)
target_stream = route_intent(intent, self.tenant_id)

if target_stream:
    self.redis.xadd(target_stream, {"data": json.dumps(task)})
else:
    logger.warning(f"No route for intent: {intent}")
```

## Adding New Routes

1. Define the intent in `intent.py`
2. Add mapping in `router.py`
3. Ensure orchestrator exists and is running

```python
# Add to routes dict
"new_intent": f"{tenant_id}:orchestrators:new_orch:tasks",
```

## Related

- [Manager Agent](manager.md)
- [Intent Classification](intent.md)
- [Stream Keys Reference](../../reference/api/streams.md)
