# Inbound Orchestrator

The Inbound Orchestrator handles incoming messages and routes them appropriately.

!!! info "Status: Skeleton"
This orchestrator is in early development. See [Roadmap](../../roadmap/in-progress.md).

## Overview

| Property   | Value                                  |
| ---------- | -------------------------------------- |
| **Tier**   | 2 (Orchestration)                      |
| **Stream** | `{tenant}:orchestrators:inbound:tasks` |
| **Status** | 🚧 Skeleton                            |

## Planned Responsibilities

- Process incoming emails
- Detect lead vs existing customer
- Route to appropriate workflow
- Handle spam/unsubscribe requests

## Planned Actions

### `process_email`

```json
{
  "action": "process_email",
  "email": {
    "from": "sender@example.com",
    "subject": "Re: Your product",
    "body": "...",
    "headers": {...}
  }
}
```

### `classify_sender`

Determine if sender is:

- New lead
- Existing lead
- Existing customer
- Spam/bot

## Current Implementation

The Leads Orchestrator currently handles most inbound logic. This orchestrator will be separated as complexity grows.

## Related

- [Leads Orchestrator](leads.md)
- [Outreach Orchestrator](outreach.md)
- [Roadmap](../../roadmap/in-progress.md)
