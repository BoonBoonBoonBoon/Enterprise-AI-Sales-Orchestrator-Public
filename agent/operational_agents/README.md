# Operational Agents — Overview

This folder contains small, focused "operational agents" that perform discrete operations (DB queries, writes, copy generation, sequencing, etc.).

Contract
- Inputs: free-text prompts or small structured filters.
- Outputs: human-readable summaries by default; use `--json` for machine-readable envelopes when available.
- Errors: agents should validate inputs and warn or raise when required env vars (SUPABASE_*, OPENAI_API_KEY) are missing.

How to run (examples)

Human-readable:

```powershell
python .\run_agent.py --prompt "check if we have any data under the email bill.mock@example-test.com"
```

JSON envelope:

```powershell
python .\run_agent.py --prompt "check if we have any data under the email bill.mock@example-test.com" --json
```

Discovery / Registry
- Use `agent.operational_agents.registry.discover_local_agents()` to list available agents.
- Each agent subpackage should expose `AGENT_CLASS` or `create_agent()` for discovery. The registry is PEP-420-safe and will attempt a nested import when needed.

Notes
- Keep per-agent READMEs in their subfolders to document behavior and examples.
- Shared helpers live under `agent/tools/` (see `agent.tools.persistence` adapters/facade and `agent.tools.redis` for Streams utilities).
- Prefer using factory helpers in `agent.operational_agents.factory` to construct agents with correct dependency injection (e.g. persistence == least privilege, RAG == read-only facade).

Factory Helpers (New)
---------------------
`agent.operational_agents.factory` now exposes:

| Function | Purpose |
|----------|---------|
| `create_persistence_agent(kind='supabase')` | Full read/write persistence agent (allow-listed tables only). |
| `create_readonly_rag_facade(kind='supabase')` | Read-only facade wrapping the shared `PersistenceService` for safe RAG retrieval. |
| `create_rag_agent(kind='supabase')` | Builds a `RAGAgent` already wired to the read-only facade (no legacy direct Supabase usage). |

RAG Integration (DI Pattern)
---------------------------
`RAGAgent` accepts an injected `ReadOnlyPersistenceFacade`. If provided, it will not create a direct Supabase client, ensuring strict no-write guarantees for retrieval flows. Use the factory:

```python
from agent.operational_agents.factory import create_rag_agent

rag = create_rag_agent()
envelope = rag.run("find leads at acme")  # internally uses read-only persistence
```

Backward Compatibility
----------------------
As of 2025-10, `RAGAgent` requires a `ReadOnlyPersistenceFacade` (provided by `create_rag_agent`). The legacy direct Supabase fallback has been removed. Use the factory to avoid breaking changes and enforce least-privilege.

Deprecations & Cleanup Roadmap
------------------------------
- `DBWriteAgent` (legacy) slated for removal in Phase 2.
- Direct Supabase access inside `RAGAgent` will be deleted once all callers migrate to the injected facade.
- See `docs/cleanup/README.md` for the authoritative task list.
