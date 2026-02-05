# Payload Schemas

This reference documents the JSON payload schemas for each agent and orchestrator.

## TaskEnvelope

All payloads are wrapped in a TaskEnvelope:

```json
{
  "task_id": "uuid",
  "tenant_id": "agentic-dev",
  "payload": { ... },
  "metadata": {
    "source": "manager",
    "target": "leads",
    "priority": "normal",
    "timestamp": "2025-01-15T10:00:00Z"
  }
}
```

---

## Tier 3: Agent Payloads

### RAGAgent

#### Task: `get_lead_context`

Retrieve context for a lead from vector DB and database.

```json
{
  "action": "get_lead_context",
  "lead_id": "uuid",
  "query": "optional search query",
  "top_k": 5
}
```

#### Response

```json
{
  "status": "success",
  "data": {
    "lead": { "name": "...", "email": "...", ... },
    "conversations": [...],
    "messages": [...],
    "similar_leads": [...],
    "query_trace": {
      "leads": { "found": true },
      "staging_leads": { "found": false },
      "conversations": { "found": true, "count": 3 }
    }
  },
  "error_count": 0
}
```

#### Task: `search`

Vector similarity search.

```json
{
  "action": "search",
  "query": "interested in SaaS solutions",
  "top_k": 10,
  "filters": {
    "status": "qualified"
  }
}
```

---

### PersistenceAgent

#### Task: `create`

Insert a new record.

```json
{
  "action": "create",
  "table": "leads",
  "data": {
    "name": "John Doe",
    "email": "john@example.com",
    "client_id": "uuid",
    "status": "new"
  }
}
```

#### Response

```json
{
  "status": "success",
  "data": {
    "id": "uuid",
    "name": "John Doe",
    ...
  }
}
```

#### Task: `read`

Fetch by ID.

```json
{
  "action": "read",
  "table": "leads",
  "id": "uuid"
}
```

#### Task: `update`

Update existing record.

```json
{
  "action": "update",
  "table": "leads",
  "id": "uuid",
  "data": {
    "status": "contacted"
  }
}
```

#### Task: `delete`

Soft delete (sets `archived_at`).

```json
{
  "action": "delete",
  "table": "leads",
  "id": "uuid"
}
```

#### Task: `query`

Search with filters.

```json
{
  "action": "query",
  "table": "leads",
  "filters": {
    "status": "new",
    "client_id": "uuid"
  },
  "limit": 50,
  "order_by": "created_at",
  "order_dir": "desc"
}
```

#### Task: `batch_create`

Insert multiple records.

```json
{
  "action": "batch_create",
  "table": "messages",
  "records": [
    { "conversation_id": "uuid", "body": "...", "metadata": {} },
    { "conversation_id": "uuid", "body": "...", "metadata": {} }
  ]
}
```

---

### CopywriterAgent

#### Task: `draft_email`

Generate outbound email.

```json
{
  "action": "draft_email",
  "lead_context": {
    "name": "John Doe",
    "company": "Acme Inc",
    "industry": "SaaS",
    "pain_points": ["scaling", "customer acquisition"]
  },
  "campaign": {
    "name": "Q1 Outreach",
    "tone": "professional",
    "offer": "Free demo"
  },
  "template_id": "optional-template-uuid"
}
```

#### Response

```json
{
  "status": "success",
  "data": {
    "subject": "Quick question about Acme's growth",
    "body": "Hi John,\n\n...",
    "tokens_used": 245
  }
}
```

#### Task: `draft_reply`

Generate reply to inbound message.

```json
{
  "action": "draft_reply",
  "reply_packet": {
    "lead_resolution": { "status": "found", "lead_id": "uuid" },
    "facts": {
      "first_name": "Jane",
      "company": "Acme",
      "email": "jane@acme.com"
    },
    "conversation": {
      "recent_messages": [{ "role": "lead", "content": "..." }]
    },
    "inbound_email_event": {
      "from": "jane@acme.com",
      "to": "inbox@agency.com",
      "subject": "Re: ...",
      "body": "...",
      "thread_id": "...",
      "message_id": "...",
      "received_at": "2026-01-18T10:00:00Z"
    },
    "query_trace": { "operation": "build_reply_context" }
  }
}
```

#### Task: `rewrite`

Rewrite content with different tone/style.

```json
{
  "action": "rewrite",
  "content": "Original email text...",
  "instructions": "Make it more casual and shorter"
}
```

---

## Tier 2: Orchestrator Payloads

### LeadsOrchestrator

#### Task: `process_inbound`

Handle inbound email/reply.

```json
{
  "action": "process_inbound",
  "email": {
    "from": "john@example.com",
    "to": "inbox@agency.com",
    "subject": "Re: Your proposal",
    "body": "I'm interested in learning more...",
    "message_id": "...",
    "received_at": "2025-01-15T10:00:00Z"
  },
  "lead_id": "uuid or null"
}
```

#### Response

```json
{
  "status": "success",
  "lead_id": "uuid",
  "lead_source": "leads",
  "reply_packet": {
    "lead_resolution": { "status": "found", "lead_id": "uuid" },
    "facts": { "email": "john@example.com" },
    "conversation": { "recent_messages": [] },
    "inbound_email_event": {
      "from": "john@example.com",
      "to": "inbox@agency.com",
      "subject": "Re: ...",
      "body": "...",
      "thread_id": "...",
      "message_id": "...",
      "received_at": "2026-01-18T10:00:00Z"
    }
  },
  "query_trace": { ... }
}
```

#### Task: `enrich_lead`

Enrich lead with external data.

```json
{
  "action": "enrich_lead",
  "lead_id": "uuid",
  "sources": ["linkedin", "clearbit"]
}
```

---

### OutreachOrchestrator

#### Task: `send_campaign`

Execute campaign for leads.

```json
{
  "action": "send_campaign",
  "campaign_id": "uuid",
  "lead_ids": ["uuid1", "uuid2"],
  "schedule": {
    "start_time": "2025-01-15T09:00:00Z",
    "batch_size": 50,
    "delay_minutes": 5
  }
}
```

#### Task: `handle_reply`

Process reply packet from Leads.

```json
{
  "action": "handle_reply",
  "reply_packet": {
    "lead_resolution": { "status": "found", "lead_id": "uuid" },
    "facts": { "first_name": "John", "company": "Acme" },
    "conversation": {
      "recent_messages": [{ "role": "lead", "content": "..." }]
    },
    "inbound_email_event": { "thread_id": "..." }
  }
}
```

---

## Tier 1: Manager Payloads

### Manager

#### Task: `goal`

High-level goal processing.

```json
{
  "action": "goal",
  "goal": "Process inbound email from john@example.com",
  "context": {
    "email": { ... }
  }
}
```

#### Response

```json
{
  "status": "success",
  "decision": {
    "actions": ["store", "enrich", "reply"],
    "delegations": [
      { "target": "leads", "action": "process_inbound" },
      { "target": "outreach", "action": "handle_reply" }
    ]
  },
  "metadata": {
    "intent": "inbound_reply",
    "confidence": 0.95
  }
}
```

---

## Common Response Patterns

### Success

```json
{
  "status": "success",
  "data": { ... }
}
```

### Error

```json
{
  "status": "error",
  "error": {
    "code": "NOT_FOUND",
    "message": "Lead not found",
    "details": { "lead_id": "uuid" }
  }
}
```

### Partial Success

```json
{
  "status": "partial",
  "data": { ... },
  "warnings": [
    "Some records failed to process"
  ],
  "failed_ids": ["uuid1", "uuid2"]
}
```

## Related

- [Envelope Reference](envelope.md)
- [Stream Keys Reference](streams.md)
- [Message Envelope Concept](../../concepts/envelope.md)
