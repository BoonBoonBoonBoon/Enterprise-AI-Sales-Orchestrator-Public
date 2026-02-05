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
- Qualify and promote staging leads to `leads`
- Retrieve lead context for replies
- Create `reply_packet` for downstream use
- Store lead and conversation data

## Key Flows

### Staging vs `leads` routing

Inbound events are stored in either:

- **`staging_*` tables** (`staging_leads`, `staging_conversations`, `staging_messages`) for pre-qualification intake, or
- **live tables** (`leads`, `conversations`, `messages`) when a lead is already qualified or is **fast-tracked**.

The qualification thresholds and fast-track rules live in `config/manager/qualification.yaml`:

- `thresholds.auto_promote`: score ≥ 70 → promote staging → leads
- `thresholds.fast_track`: score ≥ 85 → skip staging and write directly to leads
- `thresholds.disqualify`: score ≤ 20 → disqualify (archive staging lead)

### Qualification lifecycle (decision → persisted state)

LeadsOrchestrator persists the scorer decision consistently via:

- `tiers/tier_2/leads_orchestrator/qualification/lifecycle.py`

This prevents hardcoding `qualification_status="qualified"` in multiple flows.

**Persisted `qualification_status` values** are normalized to one of:

- `pending` (default for unknown/empty)
- `qualified`
- `nurture`
- `disqualified`
- `fast_track`

**Where this matters:**

- Inbound auto-promotion: updates `staging_leads` with the normalized decision and `promotion_ready`.
- Manual `intent: qualify_lead`: promotion tasks carry the normalized `qualification_status`.
- Fast-track writes: when skipping staging and writing directly to `leads`, the lead row stores the normalized decision.

### Stale staging lead sweeper (maintenance)

To prevent staging leads from silently stalling in `pending/pending/not-ready`, a small maintenance script exists:

- `scripts/maintenance/sweep_stale_staging_leads.py`

It is dry-run by default and only writes with `--apply`.

### `intent: inbound` (persist inbound email)

Handle an inbound email event and persist it deterministically.

This path exists to ensure inbound emails are stored even when a payload contains conversation-like words ("thread", "history", etc.).

**Request (typical Manager → Leads payload):**

```json
{
  "intent": "inbound",
  "payload": {
    "context": {
      "email_event": {
        "from": "john@example.com",
        "subject": "Interested in your product",
        "body": "Hi, I saw your demo and...",
        "message_id": "msg-123",
        "direction": "inbound"
      }
    }
  }
}
```

**Response (summary):**

```json
{
  "success": true,
  "orchestrator": "leads",
  "path": "inbound_persist",
  "store_inbound": { "status": "enqueued" }
}
```

**Auto-promotion behavior:**

- Inbound persistence always stores the email first (typically into `staging_*` unless an existing lead is found).
- If the qualification pipeline marks the lead as `promote=True`, LeadsOrchestrator also enqueues a second Persistence operation:
  - `operation: promote_staging_lead`
  - `staging_lead_id: <uuid>`
- Staging data is preserved for audit: promotion uses soft-archiving (`archived_at`) and does not hard-delete threads/messages.

### `intent: qualify_lead` (promote staging lead)

Evaluate a staging lead (and its messages) and promote it to `leads` when qualified.

High-level behavior:

1. Fetch staging lead context via RAG (`context_depth="deep"`)
2. Score using hybrid rules (and optional LLM fallback)
3. If `promote=True` (typically score ≥ `thresholds.auto_promote`), enqueue `operation: promote_staging_lead` to Persistence

**Request:**

```json
{
  "intent": "qualify_lead",
  "staging_lead_id": "uuid-staging-lead",
  "campaign_id": "uuid-campaign-optional"
}
```

**Response (summary):**

```json
{
  "success": true,
  "orchestrator": "leads",
  "path": "qualify_lead",
  "staging_lead_id": "uuid-staging-lead",
  "qualification": {
    "score": 92,
    "decision": "fast_track",
    "promote": true
  },
  "promoted": true
}
```

### Deep reply flow (`context_depth: deep` + `email_event`)

When `context_depth` is `deep` and an `email_event` is present, LeadsOrchestrator can build a `reply_packet` containing:

- lead resolution (`leads` vs `staging_leads`)
- conversation context (recent messages)
- extracted facts + query trace

This `reply_packet` is returned to Manager so Manager can vertically chain to Outreach (Tier 2) for drafting.

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
  → RAGAgent: build_reply_context (thread_id → subject → recency)
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

When a lead becomes qualified:

```
1. Receive task: intent=qualify_lead (staging_lead_id)
   ↓
2. RAGAgent: get_lead_context (deep)
   ↓
3. Compute qualification score (rules + optional LLM fallback)
   ↓
4. If score >= auto_promote (default 70):
   → PersistenceAgent: operation=promote_staging_lead

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
  # High-level lead match and provenance
  lead_resolution: dict  # status, lead_id, source, lead_data

  # Conversation summary used for reply drafting
  conversation: dict     # includes recent_messages

  # Extracted facts for personalization
  facts: dict            # first_name, last_name, company, role, email, intent

  # What the system did + what to do next
  actions_taken: dict
  inbound_email_event: dict
  recommended_strategy: str
  next: dict

  # Deep query trace for debugging
  query_trace: dict
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

| Variable                      | Default       | Description                         |
| ----------------------------- | ------------- | ----------------------------------- |
| `TENANT_ID`                   | `agentic-dev` | Tenant identifier                   |
| `LEADS_WAIT_FOR_RAG_CONTEXT`  | `1`           | Whether Leads waits for RAG context |
| `LEADS_RAG_CONTEXT_TIMEOUT_S` | `20`          | RAG wait timeout (seconds)          |
| `ENRICHMENT_SOURCES`          | `[]`          | Enabled enrichment APIs             |

## Running

```powershell
& ".venv/Scripts/python.exe" -m tiers.tier_2.leads_orchestrator.consumer
```

## Related

- [Manager Agent](../tier-1/manager.md) — Routes to this orchestrator
- [Outreach Orchestrator](outreach.md) — Receives reply_packet
- [RAG Agent](../tier-3/rag.md) — Retrieves context
- [Persistence Agent](../tier-3/persistence.md) — Stores data
