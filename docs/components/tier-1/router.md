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
        "inbound": f"{tenant_id}:orchestrators:leads:tasks",
        "lead_enrichment": f"{tenant_id}:orchestrators:leads:tasks",
        "qualify_lead": f"{tenant_id}:orchestrators:leads:tasks",

        # Campaign bootstrap can involve multiple orchestrators
        "start_campaign": f"{tenant_id}:orchestrators:control:tasks",

        # Outbound intent → Outreach Orchestrator
        "outbound": f"{tenant_id}:orchestrators:outbound:tasks",
    }

    return routes.get(intent)
```

## Intent → Orchestrator Mapping

| Intent            | Typical Target Orchestrator | Stream Suffix                  |
| ----------------- | --------------------------- | ------------------------------ |
| `inbound`         | Leads                       | `orchestrators:leads:tasks`    |
| `lead_enrichment` | Leads                       | `orchestrators:leads:tasks`    |
| `qualify_lead`    | Leads                       | `orchestrators:leads:tasks`    |
| `start_campaign`  | Control                     | `orchestrators:control:tasks`  |
| `outbound`        | Outreach                    | `orchestrators:outbound:tasks` |

## Usage

```python
from tiers.tier_1.manager.policy.router import stream_for, get_routing_map

# In Manager
intent = self.classify_intent(event)
routes = get_routing_map(self.tenant_id)
target_orchestrators = routes.get(intent, [])
target_stream = stream_for(self.tenant_id, target_orchestrators[0]) if target_orchestrators else None

if target_stream:
    self.redis.xadd(target_stream, {"data": json.dumps(task)})
else:
    logger.warning(f"No route for intent: {intent}")
```

## Adding New Routes

Routes are configured via YAML (with safe defaults):

1. Add/update mapping in `config/manager/routing.yaml` (or `config/tenants/{tenant_id}/manager_routing.yaml`)
2. Ensure orchestrator exists and is running

```python
# Add to routes dict
"new_intent": f"{tenant_id}:orchestrators:new_orch:tasks",
```

## Related

- [Manager Agent](manager.md)
- [Intent Classification](intent.md)
- [Stream Keys Reference](../../reference/api/streams.md)
