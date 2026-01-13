# Leads Orchestrator

The Leads Orchestrator manages lead-related workflows including ingestion, enrichment, qualification, and context retrieval.

## Overview

| Property        | Value                                                   |
| --------------- | ------------------------------------------------------- |
| **Tier**        | 2 (Orchestration)                                       |
| **Stream**      | `{tenant}:orchestrators:leads:tasks`                    |
| **Uses Agents** | RAGAgent, PersistenceAgent                              |
| **Core File**   | `tiers/tier_2/leads_orchestrator/leads_orchestrator.py` |

## Responsibilities

- Process inbound leads and emails
- Coordinate lead enrichment
- Retrieve lead context for replies
- Create `reply_packet` for downstream use
- Store lead and conversation data

## Actions

### `process_inbound`

Handle new inbound email or lead.

**Request:**

```json
{
  "action": "process_inbound",
  "email_data": {
    "from": "john@example.com",
    "subject": "Interested in your product",
    "body": "Hi, I saw your demo and...",
    "message_id": "msg-123"
  }
}
```

**Response:**

```json
{
  "status": "success",
  "result": {
    "lead_id": "uuid-lead",
    "reply_packet": {
      "lead_id": "uuid-lead",
      "lead_source": "staging_leads",
      "context": {...},
      "thread_id": "uuid-conv",
      "query_trace": {...}
    }
  }
}
```

### `enrich_lead`

Enrich lead with additional data.

**Request:**

```json
{
  "action": "enrich_lead",
  "lead_id": "uuid-lead",
  "sources": ["crunchbase", "linkedin"]
}
```

**Response:**

```json
{
  "status": "success",
  "result": {
    "lead_id": "uuid-lead",
    "enrichment": {
      "company_size": "50-100",
      "industry": "SaaS",
      "funding": "$10M Series A"
    }
  }
}
```

### `get_context`

Retrieve lead context without processing.

**Request:**

```json
{
  "action": "get_context",
  "lead_id": "uuid-lead",
  "include_messages": true
}
```

## Workflow Example

Processing an inbound email:

```
1. Receive task: process_inbound
   ↓
2. Check if lead exists
   → RAGAgent: get_lead_context (cascade lookup)
   ↓
3. If new lead:
   → PersistenceAgent: create staging_lead
   → PersistenceAgent: create staging_conversation
   ↓
4. Store message
   → PersistenceAgent: create staging_message
   ↓
5. Build reply_packet with context
   ↓
6. Return result to Manager
```

## DeepAgent Tools

The orchestrator uses LangGraph tools to delegate:

```python
from langchain_core.tools import tool

class LeadsOrchestrator(DeepAgentHarness):
    def _get_tools(self):
        @tool
        async def get_lead_context(lead_id: str) -> dict:
            """Get context for a lead from RAG agent."""
            return await self._call_rag_agent({
                "action": "get_lead_context",
                "lead_id": lead_id
            })

        @tool
        async def store_lead(data: dict) -> dict:
            """Store lead via Persistence agent."""
            return await self._call_persistence_agent({
                "action": "create",
                "table": "staging_leads",
                "data": data
            })

        return [get_lead_context, store_lead]
```

## Reply Packet

The `reply_packet` enables chained workflows:

```python
class ReplyPacket(BaseModel):
    lead_id: str
    lead_source: str  # "leads" or "staging_leads"
    context: dict     # Lead data + enrichment
    thread_id: str    # Conversation ID
    query_trace: dict # RAG debugging info
```

This is passed to Outreach Orchestrator for reply drafting.

## File Structure

```
tiers/tier_2/leads_orchestrator/
├── leads_orchestrator.py    # LangGraph agent
├── leads_harness.py         # Redis wrapper
├── consumer.py              # Entry point
├── tools/                   # DeepAgent tools
│   ├── rag_tools.py
│   └── persistence_tools.py
└── README.md
```

## Communication

!!! warning "Vertical Only"
LeadsOrchestrator can **only** communicate:

    - **Up:** Results to Manager
    - **Down:** Tasks to Tier 3 agents

    It **cannot** send tasks to OutreachOrchestrator directly.

### Streams Used

| Direction      | Stream                                 |
| -------------- | -------------------------------------- |
| Input          | `{tenant}:orchestrators:leads:tasks`   |
| Output         | `{tenant}:orchestrators:leads:results` |
| To RAG         | `{tenant}:agents:rag:tasks`            |
| To Persistence | `{tenant}:agents:persistence:tasks`    |

## Error Codes

| Code                | Description             |
| ------------------- | ----------------------- |
| `LEAD_NOT_FOUND`    | Lead doesn't exist      |
| `ENRICHMENT_FAILED` | External API error      |
| `STORAGE_FAILED`    | Persistence agent error |

## Configuration

| Variable             | Default       | Description             |
| -------------------- | ------------- | ----------------------- |
| `TENANT_ID`          | `agentic-dev` | Tenant identifier       |
| `RAG_TIMEOUT`        | `30s`         | RAG agent timeout       |
| `ENRICHMENT_SOURCES` | `[]`          | Enabled enrichment APIs |

## Running

```powershell
& ".venv/Scripts/python.exe" -m tiers.tier_2.leads_orchestrator.consumer
```

## Related

- [Manager Agent](../tier-1/manager.md) — Routes to this orchestrator
- [Outreach Orchestrator](outreach.md) — Receives reply_packet
- [RAG Agent](../tier-3/rag.md) — Retrieves context
- [Persistence Agent](../tier-3/persistence.md) — Stores data
