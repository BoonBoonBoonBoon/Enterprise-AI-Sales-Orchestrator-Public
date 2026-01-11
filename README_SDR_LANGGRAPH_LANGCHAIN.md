## AI SDR System — LangGraph (orchestration) vs LangChain (tools + LLM logic)

Purpose
- Help engineers and PMs understand which responsibilities belong in the orchestration layer (`LangGraph`) and which belong in the tools/LLM layer (`LangChain`).
- Provide concrete node/tool examples, minimal contracts, and testing guidance so implementation is consistent and testable.

## Quick summary
- **LangGraph**: orchestration, control flow, branching, retries, auditability. Think assembly line / air-traffic control.
- **LangChain**: atomic workers (tools) and LLM-driven logic. Think pilots, planes, and ground crew.

## Example: Reply Module (SDR workflow)

High-level flow (LangGraph blueprint)
1. Inbound Email Node — receives payload (email text, sender, thread id).
2. Parse Node — extracts structured intent (reply / unsubscribe / forward).
3. Fetch Data Node — call the DataCoordinator (Supabase + Qdrant) for contextual data.
4. Generate Reply Node — call CopyAgent (LLM) to draft a personalized reply.
5. Postprocess Node — enforce formatting, length, remove PII.
6. Delivery Node — send via email API (Instantly) or a queued sender.
7. Logging Node — persist envelope to Supabase for audit/history.

LangGraph responsibilities
- Define nodes, edges, and typed data schemas passed between nodes.
- Decide branching, retries, timeouts, and failure handling.
- Manage replayability and deterministic auditing (store workflow_run_id + node inputs/outputs).

## LangChain: tools and LLM logic

Implement these as small, testable tools or agents that LangGraph nodes invoke:

- `SupabaseTool` — deterministic queries to `leads` (returns provenance envelopes).
- `QdrantTool` — vector memory retrieval by id or text query.
- `CopyAgent` — prompt template + LLM call to draft personalized reply.
- `ReplyClassifier` — classify inbound email intent (reply / unsubscribe / spam / escalate).
- `FormatterTool` — enforce tone, remove PII, shorten long outputs.

LangChain responsibilities
- Encapsulate prompt templates, LLM params (temperature, max tokens), and retry logic.
- Provide deterministic wrappers for data calls (Supabase / Qdrant) and return structured envelopes.

## Minimal contracts (examples)

CopyAgent contract
- Input: `{ profile, context_snippets, tone, constraints }`
- Output: `{ subject, body, tokens_used, provenance }

SupabaseTool contract
- Input: `{ filters: {col: {op: val}}, select }`
- Output: `envelope: { metadata, records: [{..., provenance}] }`

DataCoordinator (recommended)
- Single entrypoint unifying DB + vector lookups.
- Input: allowed filter keys (id, client_id, email, company).
- Output: canonical envelope (metadata + records + provenance).

## Testing, observability & safety

Testing
- Unit tests for LangChain tools only (mock LLMs and DB clients) — deterministic and fast.
- Integration tests for LangGraph flows gated by a flag (e.g. `USE_REAL_TESTS=1`) for live runs.
- Contract tests: assert tool input shape -> normalized filter shape and envelope keys.

Observability & Audit
- Every tool returns an envelope with `metadata.source`, `query_filters`, `retrieved_at`, and `total_count`.
- Persist a `workflow_run_id` and node-level logs; store final envelopes in an audit table.

Safety
- Keep delivery disabled in dev and require manual enabling with a feature flag.
- Redact or separate PII in logs and audits unless explicitly allowed.

## Migration / evolution notes
- Your current LangChain `initialize_agent`/AgentExecutor-based code will continue to work, but LangChain recommends LangGraph for orchestration going forward.
- Strategy: keep LangChain tools as-is, migrate orchestration to LangGraph nodes that call those tools.

## Implementation checklist (practical)
- [ ] Implement `DataCoordinator` as canonical tool returning envelopes.
- [ ] Implement `SupabaseTool` returning canonical envelope with provenance.
- [ ] Create `CopyAgent` with prompt templates and unit tests.
- [ ] Model LangGraph workflow for the Reply Module and wire node inputs/outputs.
- [ ] Add Logging/Audit node that writes envelopes to Supabase.
- [ ] Add a gated Delivery node (disabled by default).

## Next steps I can help with
- Draft a LangGraph YAML/JSON graph for the Reply Module.
- Convert one LangChain agent (e.g. `CopyAgent`) into a LangGraph node as a demo.
- Produce prompt templates and unit tests for `CopyAgent` and `SupabaseTool`.

Keep the system provenance-first, testable, and deterministic: LangGraph for flow; LangChain for workers.
