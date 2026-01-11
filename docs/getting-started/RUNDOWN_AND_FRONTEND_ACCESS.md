````markdown
# Rundown + Frontend Access

## What We Accomplished

### Frontend improvements (Streamlit)
- Added file-backed JSON templates under `int-frontend/templates/`.
- Added an example template: `int-frontend/templates/inbound_email.json`.
- Updated the Streamlit app to:
  - Load templates from disk and optionally save edits back to disk.
  - Submit templated JSON into the system.
  - Add a **Task Flow Trace** tab that correlates events across multiple Redis streams by `task_id`.

### Manager / routing guardrails
- Enforced **Manager = delegation-only** behavior:
  - Manager no longer returns generated copy from deep-agent fallback (output is suppressed).
  - Manager “email generation” delegation routes via the outbound/outreach orchestrator pathway.
  - Manager envelopes now set `destination` to the orchestrator segment correctly.
- Aligned manager delegation stream naming to the orchestrator namespace (canonical form):
  - `{tenant}:orchestrators:{orchestrator_name}:tasks`
- Deprecated direct copywriter delegation from Manager (now errors) to preserve **vertical-only** comms.

### Vertical-only comms enforcement
- Tier 2 → Tier 3 publishes are guarded by `core/streams.py::assert_agents_stream()`.
- Leads orchestrator’s persistence delegation now asserts the agent stream pattern consistently.

### Tests added/updated
- Added a regression test ensuring Manager stays delegation-only (no copy content in responses, no `:agents:` streams):
  - `tiers/tier_1/manager/tests/test_manager_agent.py`
- Added a synthetic RAG retrieval integration test (no external services):
  - `tests/integration/test_rag_synthetic_e2e.py`
- Fixed the synthetic RAG test to call LangChain `StructuredTool` via `.invoke(...)`.

### Targeted tests run
- `pytest tiers/tier_1/manager/tests/test_manager_agent.py tests/integration/test_rag_synthetic_e2e.py`


## How to Access the New Frontend

### Start the Streamlit app (Windows PowerShell)
From the repo root:

```powershell
Set-Location "C:\Users\Elliot\Desktop\Agency Files\Important\Technicals\Agentic System"
& ".\.venv\Scripts\Activate.ps1"
streamlit run int-frontend/app.py
```

Streamlit will print a local URL (commonly `http://localhost:8501`). Open that in your browser.

### Using templates
- Templates live in `int-frontend/templates/`.
- Start with: `int-frontend/templates/inbound_email.json`.
- In the frontend:
  - Pick a template, edit the JSON, optionally save back to file.
  - Submit it.

### Tracing a task end-to-end
- After submitting, copy the `task_id` returned.
- Open the **Task Flow Trace** tab.
- Paste the `task_id` to see correlated events across manager/orchestrators/agents streams.

## Staging leads (manual promotion for now)
- Early replies for unqualified leads should land in `staging_conversations`/`staging_messages` (FK → `staging_leads`) so they remain visible to RAG.
- Ensure the DB migration is applied first:
  - `docs/architecture/supabase/migrations/20260102_staging_conversations.sql`
  - See: `docs/architecture/supabase/SUPABASE_MANUAL_STEPS.md`
- When a staging lead is ready: create the lead in `leads`, recreate its staging conversations/messages into `conversations`/`messages`, then soft-delete the staging lead by setting `staging_leads.archived_at` (keep for audit).
- Until a UI action exists, promotion is a manual step (e.g., invoke Persistence to write the lead and replay the messages). Track the same `task_id` in Task Flow Trace to confirm copy + soft-delete happened.

````
