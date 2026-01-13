# Outreach Orchestrator

The Outreach Orchestrator manages all outbound communication workflows including reply drafting and campaign execution.

## Overview

| Property        | Value                                                         |
| --------------- | ------------------------------------------------------------- |
| **Tier**        | 2 (Orchestration)                                             |
| **Stream**      | `{tenant}:orchestrators:outbound:tasks`                       |
| **Uses Agents** | CopywriterAgent, PersistenceAgent                             |
| **Core File**   | `tiers/tier_2/outreach_orchestrator/outreach_orchestrator.py` |

## Responsibilities

- Draft and send email replies
- Execute outreach campaigns
- Coordinate content generation
- Store sent messages
- Track delivery status

## Actions

### `draft_reply`

Generate and send a reply using a reply_packet.

**Request:**

```json
{
  "action": "draft_reply",
  "reply_packet": {
    "lead_id": "uuid-lead",
    "lead_source": "leads",
    "context": {
      "name": "John Doe",
      "company": "Acme Inc",
      "recent_messages": [...]
    },
    "thread_id": "uuid-conv"
  }
}
```

**Response:**

```json
{
  "status": "success",
  "result": {
    "message_id": "uuid-msg",
    "subject": "Re: Your inquiry",
    "sent_at": "2026-01-13T10:00:00Z"
  }
}
```

### `execute_campaign`

Send outreach to a list of leads.

**Request:**

```json
{
  "action": "execute_campaign",
  "campaign_id": "uuid-campaign",
  "leads": ["uuid-lead-1", "uuid-lead-2"],
  "template": "cold_outreach_v2"
}
```

**Response:**

```json
{
  "status": "success",
  "result": {
    "sent": 2,
    "failed": 0,
    "message_ids": ["uuid-msg-1", "uuid-msg-2"]
  }
}
```

### `schedule_followup`

Queue a follow-up email.

**Request:**

```json
{
  "action": "schedule_followup",
  "lead_id": "uuid-lead",
  "delay_days": 3,
  "template": "followup_1"
}
```

## Workflow Example

Drafting a reply:

```
1. Receive task: draft_reply with reply_packet
   ↓
2. Extract context from reply_packet
   ↓
3. Generate reply
   → CopywriterAgent: draft_reply
   ↓
4. Send email
   → EmailService: send
   ↓
5. Store sent message
   → PersistenceAgent: create message
   ↓
6. Return result to Manager
```

## DeepAgent Tools

```python
class OutreachOrchestrator(DeepAgentHarness):
    def _get_tools(self):
        @tool
        async def generate_reply(context: dict) -> dict:
            """Generate reply via Copywriter."""
            return await self._call_copywriter({
                "action": "draft_reply",
                "reply_packet": context
            })

        @tool
        async def send_email(to: str, subject: str, body: str) -> dict:
            """Send email via Email Service."""
            return await self.email_service.send(to, subject, body)

        @tool
        async def store_message(conversation_id: str, content: str) -> dict:
            """Store message via Persistence."""
            return await self._call_persistence({
                "action": "store_message",
                "conversation_id": conversation_id,
                "content": content,
                "direction": "outbound"
            })

        return [generate_reply, send_email, store_message]
```

## Reply Packet Consumption

The orchestrator receives `reply_packet` from Manager (chained from Leads):

```python
def process_task(self, task: dict) -> dict:
    payload = task["payload"]

    if payload["action"] == "draft_reply":
        reply_packet = payload["reply_packet"]

        # Context already populated by Leads Orchestrator
        lead_context = reply_packet["context"]
        thread_id = reply_packet["thread_id"]

        # Generate and send reply...
```

## File Structure

```
tiers/tier_2/outreach_orchestrator/
├── outreach_orchestrator.py  # LangGraph agent
├── outreach_harness.py       # Redis wrapper
├── consumer.py               # Entry point
├── tools/
│   ├── copywriter_tools.py
│   ├── email_tools.py
│   └── persistence_tools.py
└── README.md
```

## Communication

!!! warning "Vertical Only"
OutreachOrchestrator can **only** communicate:

    - **Up:** Results to Manager
    - **Down:** Tasks to Tier 3 agents

    It **cannot** receive tasks from LeadsOrchestrator directly.

### Streams Used

| Direction      | Stream                                    |
| -------------- | ----------------------------------------- |
| Input          | `{tenant}:orchestrators:outbound:tasks`   |
| Output         | `{tenant}:orchestrators:outbound:results` |
| To Copywriter  | `{tenant}:agents:copywriter:tasks`        |
| To Persistence | `{tenant}:agents:persistence:tasks`       |

## Email Service Integration

```python
from services.email.gmail_service import GmailService

class OutreachOrchestrator:
    def __init__(self):
        self.email_service = GmailService()

    async def send_email(self, to: str, subject: str, body: str):
        return await self.email_service.send(
            to=to,
            subject=subject,
            body=body,
            thread_id=self.current_thread_id  # For threading
        )
```

## Error Codes

| Code                     | Description             |
| ------------------------ | ----------------------- |
| `COPY_GENERATION_FAILED` | Copywriter error        |
| `EMAIL_SEND_FAILED`      | Email service error     |
| `INVALID_REPLY_PACKET`   | Missing required fields |
| `LEAD_NOT_FOUND`         | Lead context missing    |

## Configuration

| Variable              | Default   | Description         |
| --------------------- | --------- | ------------------- |
| `GMAIL_CLIENT_ID`     | —         | Gmail OAuth client  |
| `GMAIL_CLIENT_SECRET` | —         | Gmail OAuth secret  |
| `GMAIL_REFRESH_TOKEN` | —         | OAuth refresh token |
| `EMAIL_RATE_LIMIT`    | `50/hour` | Sending rate limit  |

## Running

```powershell
& ".venv/Scripts/python.exe" -m tiers.tier_2.outreach_orchestrator.consumer
```

## Related

- [Manager Agent](../tier-1/manager.md) — Routes tasks here
- [Leads Orchestrator](leads.md) — Provides reply_packet
- [Copywriter Agent](../tier-3/copywriter.md) — Generates content
- [Email Service](../services/email.md) — Sends emails
