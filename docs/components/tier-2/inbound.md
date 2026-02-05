# Inbound Orchestrator

The Inbound Orchestrator handles **incoming email** and performs deterministic triage before any expensive downstream work.

It is designed to prevent automated / low-value messages (newsletters, bounces, bulk mail) from consuming LLM budget or triggering reply flows.

## Overview

| Property   | Value                                  |
| ---------- | -------------------------------------- |
| **Tier**   | 2 (Orchestration)                      |
| **Stream** | `{tenant}:orchestrators:inbound:tasks` |
| **Status** | ✅ Active                              |

## Responsibilities

- Classify inbound emails (rules-first) via the Tier-3 Classifier Agent
- Route actionable emails into the lead/reply pipeline
- Store-only for newsletters/marketing/transactional mail (no reply)
- Drop obvious bounces/spam

## Data Flow

1. Tier-0 inbox ingress publishes an `intent=inbound` task to `{tenant}:manager:tasks`
2. Manager routes `inbound` to this orchestrator via `config/manager/routing.yaml`
3. Inbound Orchestrator:
   - Uses Tier-0 pre-filter signals when present (e.g. bounce)
   - Delegates classification to the Tier-3 Classifier Agent
   - Executes an action (`ROUTE_TO_LEADS`, `STORE_ONLY`, `DROP`, `REVIEW`)

!!! danger "Vertical-only reminder"
Orchestrators should not directly publish to other orchestrators’ task streams. If cross-orchestrator coordination is needed, prefer returning a result payload that Manager can chain.

## Input

Inbound tasks should include an email event under `payload.context.email_event`.

```json
{
  "intent": "inbound",
  "payload": {
    "context": {
      "email_event": {
        "provider": "gmail",
        "message_id": "...",
        "thread_id": "...",
        "subject": "Re: Pricing",
        "body": "...",
        "from": "lead@example.com",
        "headers": {
          "list_unsubscribe": "...",
          "precedence": "bulk",
          "auto_response_suppress": "...",
          "x_mailer": "...",
          "reply_to": "...",
          "pre_filter_category": "bounce"
        }
      },
      "pre_filter": {
        "category": "marketing",
        "confidence": 0.9,
        "reason": "List-Unsubscribe present; marketing keywords"
      }
    }
  }
}
```

## Output

The orchestrator publishes results to `{tenant}:orchestrators:inbound:results`.

```json
{
  "status": "success",
  "data": {
    "classification": {
      "category": "newsletter",
      "priority": "low",
      "confidence": 0.95,
      "action": "STORE_ONLY"
    }
  }
}
```

## Run

```powershell
& ".venv/Scripts/python.exe" -m tiers.tier_2.inbound_orchestrator.consumer
```

## Related

- [Leads Orchestrator](leads.md)
- [Outreach Orchestrator](outreach.md)
- [Classifier Agent](../tier-3/classifier.md)
- [Email Service](../services/email.md)
