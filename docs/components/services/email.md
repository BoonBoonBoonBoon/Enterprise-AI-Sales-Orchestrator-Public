# Email Service

The Email Service supports **outbound sending** and **inbound ingestion**.

Inbound ingestion is handled by Tier-0 ingress processes (poller + webhook backup) which publish typed envelopes to Manager.

## Overview

| Component    | Description                           |
| ------------ | ------------------------------------- |
| **Location** | `services/email/`                     |
| **Purpose**  | Gmail/IMAP ingestion + SMTP sending   |
| **Used By**  | Tier-0 ingress, Outreach Orchestrator |

## Usage

### Send (SMTP)

```python
from services.email.gmail_sender import send_email_via_gmail

message_id = send_email_via_gmail(
    to_email="recipient@example.com",
    subject="Hello",
    body="This is the email body.",
    html_body=None,
    attachments=None,
)
print(message_id)
```

### Ingest inbound via poller (primary)

Polls Gmail API (OAuth) or IMAP and publishes to `{tenant}:manager:tasks`.

```powershell
& ".venv/Scripts/python.exe" -m services.email.inbox_poller --tenant agentic-dev --provider gmail --poll-interval 60
```

### Ingest inbound via webhook (backup)

FastAPI endpoint that accepts `inbound_email_event` JSON and publishes to `{tenant}:manager:tasks`.

We are **not relying on the webhook by default** in the current MVP flow. The poller is the primary ingress because it requires no additional inbound infrastructure and works reliably with a single inbox.

Use the webhook when:

- You have a push-capable provider (or a bridge service) that can POST inbound events
- You want lower latency than polling
- You want to avoid polling quotas

```powershell
& ".venv/Scripts/python.exe" -m services.email.webhook_receiver
```

### Containerized Tier-0 ingress

The repository’s `docker-compose.yml` includes profile-gated services for Tier-0 ingress:

- `inbox_poller` (primary)
- `inbox_webhook` (backup)

Run them with:

```powershell
docker compose --profile inbox --env-file .env up --build inbox_poller inbox_webhook
```

## Inbound Triage (Pre-Filter + Inbound Orchestrator)

Inbound ingestion includes a cheap **Tier-0 pre-filter** step that can skip obvious low-value mail (bounces, marketing/promotions, newsletters) before publishing to Manager.

When a message is published, Manager routes `intent=inbound` to the Tier-2 Inbound Orchestrator, which classifies the email (via the Tier-3 Classifier Agent) and decides whether to:

- Route into the lead/reply pipeline
- Store-only (no reply)
- Drop (bounce/spam)

## File Structure

## GmailService API

### Ingest inbound via webhook (backup)

### Constructor

```powershell
& ".venv/Scripts/python.exe" -m services.email.webhook_receiver
```

class GmailService:
POST `/webhook/email/{tenant_id}` with JSON body:
self,

```json
{
  "provider": "sendgrid",
  "message_id": "<unique-id>",
  "thread_id": null,
  "subject": "Re: Inquiry",
  "body": "Hello...",
  "from": "lead@example.com",
  "to": "inbox@agency.com",
  "received_at": "2026-01-18T10:00:00Z"
}
```

async def send(

## File Structure

    to: str,                        # Recipient email

```
services/email/
├── gmail_sender.py      # SMTP sender (App Password)
├── gmail_reader.py      # Gmail API reader (OAuth)
├── providers.py         # Provider abstraction (gmail/imap)
├── inbox_poller.py      # Tier-0 poller -> Manager stream
├── pre_filter.py         # Tier-0 cheap classification (skip obvious junk)
├── webhook_receiver.py  # FastAPI backup receiver -> Manager stream
└── README.md
```

## Related

- [Inbound Orchestrator](../tier-2/inbound.md)
- [Outreach Orchestrator](../tier-2/outreach.md)
- [Classifier Agent](../tier-3/classifier.md)
- [Environment Variables](../../reference/config/env-vars.md)
