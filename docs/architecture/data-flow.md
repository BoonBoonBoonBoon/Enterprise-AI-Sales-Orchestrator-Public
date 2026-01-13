# Data Flow

This document describes how data flows through the Agentic System.

## Overview

Data flows vertically through tiers, never horizontally between components of the same tier.

## Primary Flows

### 1. Inbound Email Flow

```
┌──────────────┐
│ Gmail/IMAP   │
│   Inbox      │
└──────┬───────┘
       │
       ▼
┌──────────────┐     ┌──────────────────────────────────────────┐
│ Email Poller │────▶│ Manager:tasks                            │
│              │     │ {action: "goal", goal: "process inbound"}│
└──────────────┘     └──────────────────────────────────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────────────────┐
                     │ Orchestrators:leads:tasks                │
                     │ {action: "process_inbound", email: {...}}│
                     └──────────────────────────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│ agents:rag:tasks  │ │agents:persist:task│ │ agents:copy:tasks │
│ {get_lead_context}│ │{store_message}    │ │ {draft_reply}     │
└───────────────────┘ └───────────────────┘ └───────────────────┘
              │                     │                     │
              ▼                     ▼                     ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│ agents:rag:results│ │agents:persist:res │ │ agents:copy:result│
│ {lead_context}    │ │{stored: true}     │ │ {draft_email}     │
└───────────────────┘ └───────────────────┘ └───────────────────┘
              │                     │                     │
              └─────────────────────┼─────────────────────┘
                                    ▼
                     ┌──────────────────────────────────────────┐
                     │ Orchestrators:leads:results              │
                     │ {status: "success", reply_packet: {...}} │
                     └──────────────────────────────────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────────────────┐
                     │ Manager:results                          │
                     │ {chains_to: "outreach", reply_packet}    │
                     └──────────────────────────────────────────┘
```

### 2. Outbound Campaign Flow

```
┌──────────────┐
│  Dashboard   │
│ "Start Camp" │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────┐
│ Manager:tasks                            │
│ {action: "goal", goal: "send campaign"}  │
└──────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│ Orchestrators:outreach:tasks             │
│ {action: "send_campaign", campaign_id}   │
└──────────────────────────────────────────┘
       │
       ├─────────────────────┐
       ▼                     ▼
┌───────────────────┐ ┌───────────────────┐
│ agents:rag:tasks  │ │ agents:copy:tasks │
│ {get batch leads} │ │ {draft_emails}    │
└───────────────────┘ └───────────────────┘
       │                     │
       ▼                     ▼
┌───────────────────┐ ┌───────────────────┐
│   Lead Context    │ │  Drafted Emails   │
└───────────────────┘ └───────────────────┘
       │                     │
       └──────────┬──────────┘
                  ▼
       ┌───────────────────┐
       │  Email Service    │
       │  (send via SMTP)  │
       └───────────────────┘
                  │
                  ▼
       ┌───────────────────┐
       │ agents:persist    │
       │ {log sent emails} │
       └───────────────────┘
```

### 3. Reply Chain Flow

When Manager receives a result from Leads with `reply_packet`:

```
┌────────────────────────────────────────────────────────────────┐
│                         Manager                                 │
│                                                                 │
│  Receives:                      Chains to:                     │
│  ┌────────────────────┐        ┌────────────────────┐         │
│  │ Leads:results      │        │ Outreach:tasks     │         │
│  │ {reply_packet}     │ ──────▶│ {handle_reply,     │         │
│  └────────────────────┘        │  reply_packet}     │         │
│                                └────────────────────┘         │
└────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
                          ┌────────────────────────┐
                          │ Copywriter:tasks       │
                          │ {draft_reply}          │
                          └────────────────────────┘
                                         │
                                         ▼
                          ┌────────────────────────┐
                          │ Email:send             │
                          │ (via Gmail API)        │
                          └────────────────────────┘
```

---

## Data Transformations

### Task Envelope

Every message wrapped in envelope:

```json
{
  "task_id": "uuid",
  "tenant_id": "agentic-dev",
  "payload": { ... },
  "metadata": {
    "source": "leads",
    "target": "rag",
    "timestamp": "2025-01-15T10:00:00Z"
  }
}
```

### Result Envelope

```json
{
  "task_id": "uuid",
  "tenant_id": "agentic-dev",
  "status": "success",
  "data": { ... },
  "metadata": {
    "duration_ms": 1234,
    "source": "rag"
  }
}
```

### Reply Packet

Special payload for reply chaining:

```json
{
  "inbound_message": "Original email body...",
  "lead_context": {
    "name": "John",
    "company": "Acme",
    "history": [...]
  },
  "conversation_history": [...],
  "reply_type": "interested",
  "lead_source": "leads",
  "query_trace": { ... }
}
```

---

## Database Data Flow

### Write Path

```
Agent/Orchestrator
       │
       ▼
┌───────────────────┐
│ Persistence Agent │
│ (agent_writer)    │
└───────────────────┘
       │
       ▼
┌───────────────────┐
│   Supabase API    │
│   (with RLS)      │
└───────────────────┘
       │
       ▼
┌───────────────────┐
│   PostgreSQL      │
│                   │
└───────────────────┘
```

### Read Path

```
Agent/Orchestrator
       │
       ▼
┌───────────────────┐
│    RAG Agent      │
│  (agent_reader)   │
└───────────────────┘
       │
       ├──────────────────┐
       ▼                  ▼
┌───────────────┐  ┌───────────────┐
│  Supabase     │  │  Vector DB    │
│  (SQL query)  │  │  (embedding)  │
└───────────────┘  └───────────────┘
       │                  │
       └────────┬─────────┘
                ▼
         Combined Context
```

---

## Stream Data Lifetime

```
Message Published
       │
       ▼ (immediate)
Consumer reads with XREADGROUP
       │
       ▼ (processing)
Task processed
       │
       ▼ (immediate)
XADD to result stream
XACK to task stream
       │
       ▼ (7 days default)
Stream XTRIM (length limit)
       │
       ▼
Message deleted
```

---

## Error Flow

```
Task Processing
       │
       ├── Success ────────▶ Result Stream
       │
       ├── Transient Error ─▶ Retry (up to 3x)
       │                            │
       │                            ├── Success ──▶ Result Stream
       │                            │
       │                            └── Max Retries ──▶ DLQ
       │
       └── Permanent Error ─────────────────────────▶ Error Result
                                                            │
                                                            ▼
                                                      Result Stream
                                                      (status: error)
```

## Related

- [System Design](design.md)
- [Communication Rules](communication.md)
- [Redis Streams Concept](../concepts/redis-streams.md)
