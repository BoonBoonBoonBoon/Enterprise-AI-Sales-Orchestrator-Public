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
        return "inbound_inquiry"
    elif event_type == "campaign_trigger":
        return "campaign_start"
    elif event_type == "lead_qualified":
        return "draft_reply"
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
    - inbound_inquiry: New lead or customer inquiry
    - campaign_start: Request to start outreach campaign
    - enrich_lead: Request for lead enrichment
    - draft_reply: Need to respond to a lead
    - qualify_lead: Need to score/qualify a lead

    Event: {json.dumps(event)}

    Intent:"""

    response = await llm.complete(prompt)
    return response.strip().lower()
```

## Supported Intents

| Intent            | Description               | Trigger Events                |
| ----------------- | ------------------------- | ----------------------------- |
| `inbound_inquiry` | New lead/customer contact | Email, form submission        |
| `campaign_start`  | Begin outreach campaign   | Manual trigger, schedule      |
| `enrich_lead`     | Add data to lead          | Lead created, manual          |
| `qualify_lead`    | Score lead                | Enrichment complete           |
| `draft_reply`     | Create response           | Lead qualified, inbound reply |
| `send_followup`   | Send follow-up            | Time trigger, no response     |
| `process_inbound` | Handle inbound message    | Email received                |

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
       "inbound_inquiry",
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
