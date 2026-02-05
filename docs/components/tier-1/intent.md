# Intent Classification

Intent classification determines what action the Manager should take for incoming events.

## Overview

| Component    | Description                             |
| ------------ | --------------------------------------- |
| **Location** | `tiers/tier_1/manager/policy/intent.py` |
| **Purpose**  | Classify events into actionable intents |
| **Used By**  | Manager Agent                           |

## Classification Methods

### Rule-Based

```python
def classify_intent_rules(event: dict) -> str:
    """Simple rule-based classification."""
    event_type = event.get("type")

    if event_type == "inbound_email":
        return "inbound"
    elif event_type == "campaign_trigger":
        return "start_campaign"
    elif event_type == "lead_qualified":
        return "outbound"
    else:
        return "unknown"
```

### LLM-Based

For complex events, use LLM classification:

```python
async def classify_intent_llm(event: dict, llm) -> str:
    """LLM-based classification for ambiguous events."""
    prompt = f"""
    Classify the following event into one of these intents:
    - inbound: Inbound email / inbound lead event
    - start_campaign: Request to start outreach campaign
    - lead_enrichment: Request for lead enrichment
    - outbound: Outbound messaging / drafting / follow-up
    - qualify_lead: Score a staging lead and promote if qualified

    Event: {json.dumps(event)}

    Intent:"""

    response = await llm.complete(prompt)
    return response.strip().lower()
```

## Supported Intents

| Intent            | Description                                   | Typical Target         |
| ----------------- | --------------------------------------------- | ---------------------- |
| `inbound`         | Inbound email / inbound lead event            | Leads                  |
| `lead_enrichment` | Enrich a lead profile                         | Leads                  |
| `qualify_lead`    | Score a staging lead and promote if qualified | Leads                  |
| `start_campaign`  | Begin outreach campaign                       | Control/Leads/Outbound |
| `outbound`        | Draft/send outbound messaging                 | Outbound               |
| `audit`           | Audit / diagnostics                           | Audit                  |
| `control`         | Control-plane commands                        | Control                |

## Classification Pipeline

```
Event → Rule Check → Match? → Return Intent
                  ↓
                  No Match
                  ↓
            LLM Classification → Return Intent
                  ↓
            LLM Uncertain
                  ↓
            Return "unknown"
```

## Handling Unknown Intents

```python
def handle_unknown_intent(event: dict) -> dict:
    """Fallback for unclassified events."""
    return {
        "status": "error",
        "error": {
            "code": "UNKNOWN_INTENT",
            "message": "Could not classify event",
            "event": event
        }
    }
```

## Adding New Intents

1. Define intent in `intent.py`:

   ```python
   INTENTS = [
       "inbound",
       "new_intent_here",  # Add new
       ...
   ]
   ```

2. Add classification rule:

   ```python
   if event_type == "new_event_type":
       return "new_intent_here"
   ```

3. Add routing in `router.py`:
   ```python
    "new_intent_here": f"{tenant_id}:orchestrators:target:tasks"
   ```

## Related

- [Manager Agent](manager.md)
- [Policy Router](router.md)
- [LLM Integration](../../guides/dev/llm-integration.md)
