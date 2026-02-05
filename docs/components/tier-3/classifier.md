# Classifier Agent

The Classifier Agent categorizes inbound emails into a deterministic taxonomy (newsletter, bounce, personal, etc.) so the system avoids wasting downstream work (LLM calls, outreach drafting) on low-value or automated messages.

## Overview

| Property    | Value                              |
| ----------- | ---------------------------------- |
| **Tier**    | 3 (Execution)                      |
| **Stream**  | `{tenant}:agents:classifier:tasks` |
| **Status**  | ✅ Active                          |
| **DB Role** | None                               |

## Responsibilities

- Assign an `EmailCategory` (e.g. `personal`, `newsletter`, `bounce`)
- Assign a `ClassificationAction` (e.g. `ROUTE_TO_LEADS`, `STORE_ONLY`, `DROP`, `REVIEW`)
- Provide a confidence score and a small set of rule-based signals

## Input / Output

### Input

The agent expects a payload derived from an inbound email event:

```json
{
  "email": {
    "message_id": "...",
    "thread_id": "...",
    "from_email": "lead@example.com",
    "subject": "Re: pricing",
    "body": "...",
    "headers": {
      "list_unsubscribe": "<mailto:...>",
      "precedence": "bulk",
      "auto_response_suppress": "All",
      "x_mailer": "...",
      "reply_to": "...",
      "pre_filter_category": "bounce"
    }
  }
}
```

### Output

```json
{
  "status": "success",
  "data": {
    "category": "business_inquiry",
    "priority": "high",
    "confidence": 0.91,
    "action": "ROUTE_TO_LEADS",
    "reasoning": "Subject indicates pricing inquiry; sender is not bulk/marketing.",
    "signals": ["has_question", "no_list_unsubscribe"]
  }
}
```

## Configuration

- `CLASSIFIER_LLM_ENABLED` — when enabled, uncertain classifications may fall back to an LLM. MVP defaults should keep this off unless needed.

## Run

```powershell
& ".venv/Scripts/python.exe" -m tiers.tier_3.classifier_agent.consumer
```

## Related

- [Inbound Orchestrator](../tier-2/inbound.md)
- [Email Service](../services/email.md)
- [Environment Variables](../../reference/config/env-vars.md)
