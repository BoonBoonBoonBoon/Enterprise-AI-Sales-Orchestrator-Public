# Agentic System - AI Coding Instructions

# Notes From Developer

Always read the Env and other important textual doccuments.
There is alot of time being spent and wasted developing things and systems that are already built but just need updating/refactoring.
Always check doccumentation in the docs folder, furthermore docs in the folder of the files you intend to work with for greater contextual grasp.

## 1. Architecture & Communication

This is a **3-Tier Agent Orchestration System** using **Redis Streams** for asynchronous communication.

- **Tier 1 (Strategic):** `ManagerAgent` - Routes high-level goals to orchestrators.
- **Tier 2 (Business Logic):** `LeadsOrchestrator`, `OutreachOrchestrator` - Decomposes workflows.
- **Tier 3 (Execution):** `RAGAgent`, `PersistenceAgent`, `CopywriterAgent` - Performs atomic tasks.

### Communication Rules (CRITICAL)

**VERTICAL ONLY - NO HORIZONTAL COMMUNICATION:**

- **Tier 2 orchestrators CANNOT communicate with each other directly**
- **Orchestrators can ONLY communicate:**
  - **UPWARD:** To Tier 1 Manager (via result streams)
  - **DOWNWARD:** To Tier 3 agents (via agent task streams)
- **All cross-orchestrator coordination MUST go through Manager (Tier 1)**
- **Example:** LeadsOrchestrator CANNOT send tasks to OutreachOrchestrator directly
  - ❌ FORBIDDEN: `{tenant}:orchestrators:outbound:tasks` from LeadsOrchestrator
  - ✅ CORRECT: Return result to Manager, Manager delegates to OutreachOrchestrator

### Enforcement

- **Code guardrails:** Tier 2 orchestration code calls a guard `assert_agents_stream()` before publishing; attempts to publish to any stream that is not an `:agents:` stream raise an error.
- **Result path:** Orchestrators read from `{tenant}:orchestrators:{name}:tasks` and publish results to `{tenant}:orchestrators:{name}:results`. They never publish to other orchestrators’ task streams.
- **Routing:** Manager constructs orchestrator task streams via the router (see `tiers/tier_1/manager/policy/router.py`) and is the only component allowed to coordinate between orchestrators.

### Redis Stream Naming (CRITICAL)

Strictly follow this naming convention. Do NOT invent new patterns.

- **Manager:** `{tenant}:manager:tasks` → `{tenant}:manager:results`
- **Orchestrators:** `{tenant}:orchestrators:{orchestrator_name}:tasks` (e.g., `agentic-dev:orchestrators:leads:tasks`)
  - _Note: Always use `orchestrators` prefix to create hierarchical Redis structure._
- **Agents:** `{tenant}:agents:{agent_name}:tasks` (e.g., `agentic-dev:agents:rag:tasks`)

### Deep Reply Chaining (Leads → Manager → Outreach)

- Manager may chain deep reply flows: it waits on `{tenant}:orchestrators:leads:results` for a `reply_packet`, then enqueues `{tenant}:orchestrators:outbound:tasks` with that packet.
- Leads must include `reply_packet` in its result payload when handling inbound email/reply contexts; Outreach consumes `reply_packet` and forwards to Copywriter.
- Do NOT send tasks directly between orchestrators; Manager owns the chaining hop.

## 2. Project Structure & Imports

- **Root:** `c:\Users\Elliot\Desktop\Agency Files\Important\Technicals\Agentic System`
- **Tiers:** `tiers/tier_{1,2,3}/<component_name>/`
- **Core:** `core/` (Harness, Envelope, DeepAgents, Intent, DLQ, Shutdown, Tokens)
- **Services:** `services/` (Redis, Persistence, Email)

**Import Convention:**
Always use absolute imports from the project root.

```python
# CORRECT
from tiers.tier_1.manager.manager_agent import ManagerAgent
from core.harness.agent_harness import AgentHarness

# INCORRECT
from ..manager_agent import ManagerAgent
```

## 3. Development Workflow (Windows/PowerShell)

The environment is **Windows PowerShell**.

- **Virtual Env:** `.venv` (Activate: `\.venv\Scripts\Activate.ps1`)
- **Running Consumers:** Always use the venv python to avoid system-site packages.
  ```powershell
  & "\.venv\Scripts\python.exe" -m tiers.tier_2.leads_orchestrator.consumer
  & "\.venv\Scripts\python.exe" -m tiers.tier_3.rag_agent.consumer
  & "\.venv\Scripts\python.exe" -m tiers.tier_3.persistence_agent.consumer
  ```
- **Running Tests:**
  ```powershell
  pytest tests/integration/ -v
  python test_e2e_flow.py  # For full flow verification
  ```
- **Encoding:** Set `$env:PYTHONIOENCODING='utf-8'` if dealing with emoji/unicode output to avoid `UnicodeEncodeError`.

## 4. Coding Patterns

### Agent Harness

All agents are wrapped in a `Harness` to handle Redis communication, retries, and state.

- **Sync Agents:** Inherit from `AgentHarness`.
- **Async/Deep Agents:** Use `DeepAgentHarness` or `LangGraph` integration.

### Message Envelopes

Inter-agent communication uses a standardized JSON envelope.

```json
{
  "task_id": "uuid",
  "tenant_id": "agentic-dev",
  "payload": { ... },
  "metadata": { "source": "manager", "target": "leads" }
}
```

### Delegation

- **Manager (Tier 1):** Decision + routing ONLY. The Manager never generates outreach copy, replies, subject lines, or email bodies.
  - The Manager receives events/goals (e.g., "incoming email", "start campaign") and decides which actions to take: **store**, **enrich**, **reply**, or **all three**.
  - The Manager then delegates those actions to Tier 2 orchestrators and/or Tier 3 agents via the approved routing patterns.
  - ❌ FORBIDDEN: Manager returning an email body/subject as its own output (Manager outputs must be decisions + delegation metadata only).
  - ❌ FORBIDDEN: Manager acting as a copywriter (no drafting/reply composition in Tier 1).
  - ✅ CORRECT: Manager delegates reply drafting to the copywriting pathway (Tier 2 Outreach → Tier 3 Copywriter).
- **Orchestrators (Tier 2):** Use `DeepAgent` tools to delegate to Tier 3 agents.

### RAG Testing Requirement

- End-to-end tests must include at least one realistic RAG flow (task → retrieval → enrichment result) against the configured backend.
- If there is no real corpus, create minimal synthetic data for the test tenant and assert non-empty retrieval/enrichment output.

## 5. Tier 3 Agents (Execution Layer)

Tier 3 agents perform atomic, specialized tasks. They are the workhorses of the system.

### Agent Overview

| Agent              | Purpose                                       | Database Role                | Key Files                                        |
| ------------------ | --------------------------------------------- | ---------------------------- | ------------------------------------------------ |
| `RAGAgent`         | Retrieval-Augmented Generation, vector search | `agent_reader` (SELECT only) | `rag_agent.py`, `rag_agent_harness.py`           |
| `PersistenceAgent` | CRUD operations on all tables                 | `agent_writer` (full CRUD)   | `persistence_agent.py`, `persistence_harness.py` |
| `CopywriterAgent`  | AI-powered content generation                 | None (no DB access)          | `copywriter_agent.py`, `copywriter_harness.py`   |

### Agent Folder Structure

Each Tier 3 agent follows this standard structure:

```
tiers/tier_3/<agent_name>/
├── <agent_name>.py          # Core logic (LangGraph StateGraph)
├── <agent_name>_harness.py  # Redis wrapper (AgentHarness subclass)
├── consumer.py              # Entry point for Redis stream consumer
├── validators.py            # Pydantic models for input/output
├── worker.py                # Synchronous execution wrapper
├── __init__.py
└── README.md
```

### Agent Harness Pattern

```python
from core.harness.agent_harness import AgentHarness

class MyAgentHarness(AgentHarness):
    def __init__(self, tenant_id: str):
        super().__init__(
            tenant_id=tenant_id,
            agent_name="my_agent",  # Stream: {tenant}:agents:my_agent:tasks
            result_stream_suffix="results"
        )

    def process_task(self, task: dict) -> dict:
        # Extract from envelope
        payload = task.get("payload", {})
        # Call core agent logic
        result = my_agent_function(payload)
        return {"status": "success", "data": result}
```

### Consumer Entry Point

```python
# consumer.py - Run with: python -m tiers.tier_3.my_agent.consumer
if __name__ == "__main__":
    harness = MyAgentHarness(tenant_id="agentic-dev")
    harness.run()  # Blocks, listens on Redis stream
```

## 6. Supabase Integration

### 3-Layer Authentication Stack

All database access uses a 3-layer security model:

1. **API Gateway:** Supabase anon_key + custom JWT in Authorization header
2. **PostgreSQL GRANT:** Role-based permissions (`agent_reader`, `agent_writer`)
3. **RLS Policies:** Row-level security with `current_setting('request.jwt.claims')::json->>'role'`

### SupabaseAdapter Usage

```python
from services.persistence.supabase_adapter import SupabaseAdapter

# Initialize (uses env vars: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_JWT_SECRET)
adapter = SupabaseAdapter(role="agent_writer")  # or "agent_reader"

# CRUD Operations
adapter.write("leads", {"name": "John", "email": "john@example.com"})
adapter.read("leads", "uuid-here")
adapter.query("leads", {"status": "new"}, limit=10)
adapter.update("leads", "uuid-here", {"status": "contacted"})
adapter.delete("leads", "uuid-here")
adapter.batch_write("leads", [{"name": "A"}, {"name": "B"}])
```

### Database Roles

- **`agent_reader`:** SELECT only. Used by RAGAgent for retrieval.
- **`agent_writer`:** SELECT, INSERT, UPDATE, DELETE. Used by PersistenceAgent.

### Core Tables

| Table           | FK Dependencies    | Notes                         |
| --------------- | ------------------ | ----------------------------- |
| `clients`       | None               | Top-level tenant              |
| `staging_leads` | None               | Pre-processed leads           |
| `leads`         | `clients.id`       | Qualified leads               |
| `conversations` | `leads.id`         | Lead conversations            |
| `messages`      | `conversations.id` | Requires `metadata: {}` field |

### Environment Variables

```powershell
$env:SUPABASE_URL = "https://your-project.supabase.co"
$env:SUPABASE_ANON_KEY = "your-anon-key"
$env:SUPABASE_JWT_SECRET = "your-jwt-secret"
$env:CAMPAIGN_ID_PLACEHOLDER = "9646f98a-e987-4a8c-b786-9b82ea985d38"  # optional override for temporary campaign assignment
```

### Temporary campaign placeholder (replace soon)

- PersistenceAgent injects `campaign_id` with `CAMPAIGN_ID_PLACEHOLDER` when none is provided (default: 9646f98a-e987-4a8c-b786-9b82ea985d38).
- This is a stopgap for inbound/unsolicited leads without campaign context; replace with a real campaign ASAP or set `CAMPAIGN_ID_PLACEHOLDER` to a real campaign UUID present in `campaigns`.
- If the placeholder is not present in `campaigns`, Supabase FK may still fail; create a stub campaign with that UUID when using the placeholder.

## 7. Common Pitfalls

- **Stream Names:** Double-check `router.py` and `delegation_tools.py` to ensure they match the consumer's expected stream.
- **Windows Paths:** Use `os.path.join` or `pathlib` for file paths.
- **Blocking Code:** Consumers must handle `SIGINT` (Ctrl+C) gracefully.
- **Supabase RLS:** Always use the correct role. `agent_reader` cannot INSERT/UPDATE/DELETE.
- **Messages Table:** The `metadata` field is NOT NULL - always include `"metadata": {}` minimum.
- **FK Order:** When inserting, respect FK chain: clients → leads → conversations → messages.

## 8. Debugging & Tracing (Jan 2026)

- `Metadata.debug` (typed envelope) can carry a brief `llm_summary` from Manager when LLM fallback is used; keep it short, no chain-of-thought.
- RAG `get_lead_context` now uses a cascading lookup (leads → staging_leads → conversations → messages) and returns `query_trace` with per-table steps and `error_count`.
- Leads Orchestrator forwards `lead_source` and `query_trace` into `ReplyPacket` so Outreach/Copywriter can see exactly which tables were queried.

## 9. Staging Leads (Jan 2026)

- Store pre-qualification threads in `staging_conversations` (FK → `staging_leads`) and `staging_messages` (FK → `staging_conversations`) so RAG can surface early replies.
- On promotion: create the lead in `leads`, replay staging conversations/messages into `conversations`/`messages`, then soft-delete staging rows via `archived_at` (keep audit history; no hard deletes).
- Promotion is manual today; later automation can live in Manager policy or a dedicated promotion/audit agent, but keep orchestration vertical (Manager mediates any cross-orchestrator coordination).

## 10. Core Utilities (Jan 2026)

### Intent Enum (`core/intent.py`)

- Use `Intent` enum instead of hardcoded strings: `Intent.INBOUND`, `Intent.REPLY_EMAIL`, etc.
- Parse strings with `Intent.from_string("inbound")` (case-insensitive, returns `Intent.UNKNOWN` for invalid values).
- Check categories with `ROUTING_INTENTS` and `ACTION_INTENTS` frozensets.

### Dead Letter Queue (`core/dlq.py`)

- `DeadLetterQueue` class routes failed messages to `{stream}:dlq` after max retries.
- Configurable via `DLQ_ENABLED`, `DLQ_MAX_RETRIES`, `DLQ_STREAM_SUFFIX` env vars.
- Use `dlq.should_dlq(failure_count)` to check, `dlq.send_to_dlq(msg, msg_id, error=e)` to route.
- Supports `peek_dlq()`, `requeue_message()` for manual inspection and retry.

### Graceful Shutdown (`core/shutdown.py`)

- `ShutdownHandler` catches SIGTERM/SIGINT and waits for in-flight tasks.
- Use `handler.register_signals()` from main thread, `handler.processing_context()` around task processing.
- Configurable timeout (default 30s) before forcing shutdown.

### Token Management (`core/tokens.py`)

- `estimate_tokens(text)` for fast token estimation (~4 chars/token).
- `truncate_messages_by_tokens(messages, max_tokens)` preserves recent messages within budget.
- `TokenBudget` class tracks cumulative token usage while building prompts.
- RAG `build_reply_context()` now supports `max_tokens` parameter.

### Email Dry-Run (`EMAIL_DRY_RUN=1`)

- Set `EMAIL_DRY_RUN=1` to log emails instead of sending (for dev/test).

### Inbox Backpressure (`INBOX_BACKPRESSURE_ENABLED=1`)

- Skips poll if Manager stream has > `INBOX_MAX_PENDING` (default 100) messages.
- Prevents overwhelming downstream during high load or outages.
