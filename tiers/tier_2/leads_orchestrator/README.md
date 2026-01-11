# Leads Orchestrator

**Tier:** 2 (Business Logic) | **Type:** Deep Agent Orchestrator

## Purpose

The Leads Orchestrator is a Tier 2 autonomous agent responsible for **all lead database operations**. It uses Deep Agents for strategic planning and delegates complex operations to Tier 3 specialist agents (RAG, Persistence, Deduplication).

### Key Responsibilities

1. **Lead CRUD Operations** — Create, read, update, query leads
2. **Pipeline Management** — Move leads through sales stages
3. **Inbound Email Processing** — Store and link inbound emails to leads
4. **Lead Enrichment** — Delegate to RAG agent for external data enrichment
5. **Deduplication** — Identify and merge duplicate leads
6. **Compound Persistence** — Multi-step FK-safe database writes

## Architecture

```
Manager Agent (Tier 1)
    │
    ▼ {tenant}:orchestrators:leads:tasks
┌──────────────────────────────────────┐
│       LEADS ORCHESTRATOR (Tier 2)    │
│                                      │
│  Deep Agent with Middleware:         │
│  - TodoListMiddleware                │
│  - FilesystemMiddleware              │
│  - SubAgentMiddleware                │
└───────────────┬──────────────────────┘
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
┌─────────┐ ┌─────────┐ ┌─────────────┐
│ RAG     │ │Persist- │ │Deduplication│
│ Agent   │ │ence     │ │Agent        │
│         │ │Agent    │ │             │
└─────────┘ └─────────┘ └─────────────┘
  (Tier 3)    (Tier 3)    (Tier 3)
```

### Communication Pattern

- **Input:** Redis stream `{tenant}:orchestrators:leads:tasks`
- **Output:** Results to `{tenant}:orchestrators:leads:results`
- **Downward:** Delegates to `{tenant}:agents:rag:tasks`, `{tenant}:agents:persistence:tasks`

**CRITICAL:** Leads Orchestrator **CANNOT** communicate horizontally with other orchestrators (Outreach, Audit, etc.). All cross-orchestrator coordination goes through Manager (Tier 1).

## Key Components

| File                            | Purpose                                           |
| ------------------------------- | ------------------------------------------------- |
| `leads_orchestrator.py`         | Core Deep Agent logic: tools, planning, execution |
| `leads_orchestrator_harness.py` | Redis wrapper: stream consumption, retries        |
| `consumer.py`                   | Entry point: runs the harness loop                |

## Tools

### Deterministic Tools (Direct Execution)

| Tool                       | Purpose                                                    |
| -------------------------- | ---------------------------------------------------------- |
| `validate_lead_tool`       | Validate lead data quality (email format, required fields) |
| `write_lead_tool`          | Create a new lead record                                   |
| `read_lead_tool`           | Fetch a single lead by ID                                  |
| `update_lead_tool`         | Modify lead fields                                         |
| `query_leads_tool`         | Search leads by any field (email, stage, industry)         |
| `query_conversations_tool` | Get conversations for a lead                               |
| `query_messages_tool`      | Get messages in a conversation                             |
| `move_lead_stage_tool`     | Update pipeline stage                                      |

### Delegation Tools (Tier 3 Agents)

| Tool                                   | Target Agent        | Purpose                                          |
| -------------------------------------- | ------------------- | ------------------------------------------------ |
| `delegate_to_rag_agent_tool`           | RAG Agent           | Enrich leads with external data, semantic search |
| `delegate_to_rag_context_tool`         | RAG Agent           | Retrieve lead + conversation context             |
| `delegate_to_persistence_agent_tool`   | Persistence Agent   | Bulk writes, complex queries                     |
| `compound_persistence_tool`            | Persistence Agent   | Multi-step FK-safe writes with `$ref` chaining   |
| `store_inbound_email_tool`             | Persistence Agent   | Standard inbound email compound flow             |
| `delegate_to_deduplication_agent_tool` | Deduplication Agent | Find and merge duplicate leads                   |

## Quick Start

```bash
# Run the Leads Orchestrator consumer
python -m tiers.tier_2.leads_orchestrator.consumer
```

## Execution Pattern

The orchestrator follows this autonomous execution pattern:

1. **Analyze** — Parse the goal and context. What data do you have?
2. **Plan** — Determine minimal steps. For simple tasks, skip planning.
3. **Execute** — Call tools immediately. No confirmation needed.
4. **Iterate** — If query returns no results, try broader filters.
5. **Complete** — Return structured JSON result.

## Example Workflows

### Simple Lead Query

**Input:**

```json
{
  "goal": "Find all leads in tech industry with stage=qualified"
}
```

**Execution:**

1. Call `query_leads_tool(filters={"industry": "tech", "stage": "qualified"})`
2. Return results

### Inbound Email Processing

**Input:**

```json
{
  "goal": "Store inbound email and create/link lead",
  "payload": {
    "email_event": {
      "from": "john@acme.com",
      "subject": "Re: Your proposal",
      "body": "Thanks for sending..."
    }
  }
}
```

**Execution:**

1. Call `store_inbound_email_tool(email_event, lead_data, cleanup_staging=true)`
2. Compound tool creates: conversation → message → lead link
3. Return created record IDs

### Lead Enrichment

**Input:**

```json
{
  "goal": "Enrich lead-123 with company data"
}
```

**Execution:**

1. Call `read_lead_tool(lead_id="lead-123")` — Get current data
2. Call `delegate_to_rag_agent_tool(query="company info for Acme Corp")`
3. Call `update_lead_tool(lead_id="lead-123", updates={...})` — Apply enrichment
4. Return updated lead

## Configuration

Environment variables:

- `TENANT_ID` — Tenant context for multi-tenant isolation
- `REDIS_URL` — Redis connection string
- `OPENAI_MODEL` — Model for Deep Agent reasoning (default: `gpt-4o-mini`)

## ReplyPacket Schema

When handling inbound emails/replies, the orchestrator builds a `ReplyPacket` for downstream processing:

```python
@dataclass
class ReplyPacket:
    lead: LeadResolution        # Lead identification
    conversation: ConversationSummary  # Thread context
    facts: Facts                # Extracted data points
    actions_taken: ActionsTaken # What was done
    next_step: NextStep         # Recommended action
```

## Harness Integration

The orchestrator is wrapped by `AgentHarness`:

```python
from tiers.tier_2.leads_orchestrator.leads_orchestrator_harness import LeadsOrchestratorHarness

harness = LeadsOrchestratorHarness(
    redis_client=redis_client,
    tenant_id="agentic-dev",
)
harness.run()  # Blocks, listens on Redis stream
```

## Testing

```bash
# Unit tests
pytest tests/unit/tier_2/test_leads_orchestrator.py -v

# Integration test with Redis
python scripts/testing/test_compound_staging.py
```

## See Also

- [Three-Tier Architecture](../../../docs/architecture/three-tier-system.md)
- [RAG Agent](../../tier_3/rag_agent/README.md)
- [Persistence Agent](../../tier_3/persistence_agent/README.md)
- [Orchestrator Isolation](../../../docs/ORCHESTRATOR_ISOLATION_VERIFICATION.md)
