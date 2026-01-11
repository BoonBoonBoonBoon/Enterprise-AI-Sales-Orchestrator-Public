RAGAgent — Retrieval Augmented Generation (Read-Only Persistence + Adaptive Retrieval)
=====================================================================================

Purpose
-------
Provide deterministic, least‑privilege retrieval over business tables (currently `leads` focused) combined with a LangChain tool interface and standardized JSON envelope output. The agent supports dependency injection of a `ReadOnlyPersistenceFacade` (enforcing read-only access) plus adaptive behaviors: multi‑attempt filter reformulation, optional agent reasoning fallback (rate‑limited), pagination, caching, and large result summarization.

Key Characteristics
-------------------
- Deterministic filter parsing (rule-based + optional LLM JSON extraction) for `id`, `email`, `company`, `client_id`.
- Read-only DB access when constructed via factory (`create_rag_agent`) — avoids legacy direct Supabase client.
- Emits provenance per record (hash + retrieval timestamp) when returning JSON envelopes.
- Pagination + limit enforcement (`limit`, `offset`, env defaults) and manual slicing for adapters without native offset.
- In-run query caching (filter+pagination key) to avoid duplicate adapter hits.
- Multi-attempt deterministic reformulation (drop email, shorten company suffix, drop company) before LLM fallback.
- Rate-limited agent fallback (sliding 60s window) with metadata `fallback: agent|reformulation|suppressed`.
- Large result summarization with lightweight statistical sample when count exceeds threshold.
- Tool exposure: `query_leads`, `rag_agent`, `query_table`, disabled `deliver_data`.
- Graceful handling of malformed tool input (stringified dicts, JSON-ish payloads).

Construction Patterns
---------------------
Preferred (Facade Injected):
```python
from agent.operational_agents.factory import create_rag_agent

rag = create_rag_agent(kind='supabase')  # or 'memory' for tests
result = rag.run("find leads at acme")
```

Legacy
------
The legacy direct Supabase boot path inside `RAGAgent` has been removed. Always construct via the factory so a `ReadOnlyPersistenceFacade` is injected.

JSON Envelope Shape (Fast Path / Fallback)
-----------------------------------------
```
{
  "metadata": {
    "source": "persistence.leads" | "agent",
    "query_filters": { ... } | null,
    "retrieved_at": ISO8601,
    "total_count": int,
  "error": optional str,
  "fallback": optional "agent" | "reformulation" | "suppressed",
  "truncated": optional bool,
  "summary": optional { ... },
  "cache": optional "hit" | "miss",
  "limit": optional int,
  "offset": optional int,
  "reformulation_attempts": optional [ {"reason": str, "filters": {...}, "result_count": int } ]
  },
  "records": [
    {
      ...row fields...,
      "provenance": {
  "source": "persistence.leads",
        "row_id": <id>,
        "row_hash": <sha256 of sorted items>,
        "retrieved_at": ISO8601,
        "raw_row": {...}  // only when include_raw=True
      }
    }
  ]
}
```

Filter & Fallback Pipeline
--------------------------
1. Rule-based extractor (`parse_filters_from_text`).
2. If empty & OpenAI key present: LLM JSON extraction (`parse_filters_with_llm`).
3. If filters non-empty: fast direct query via persistence facade.
4. If zero results: deterministic reformulation attempts (ordered strategies) until rows found or exhausted.
5. If still zero and rate limit allows: agent reasoning fallback (tool-enabled LangChain plan).
6. If fallback suppressed (rate limit exceeded): metadata marks `fallback: suppressed` with zero records.

Tools
-----
- `query_leads`: Deterministic table query with pagination + caching + reformulation context.
- `query_table`: Generic table read (facade-driven, respects allowlist).
- `rag_agent`: Wraps free-text or partial envelope input; ensures canonical output shape.
- `deliver_data`: Disabled placeholder (returns status=DISABLED) to avoid accidental loops.
- `data_coordinator`: (Legacy) Provided only when direct Supabase path is active.

Security & Least Privilege
--------------------------
When constructed through the factory, all read operations route through `ReadOnlyPersistenceFacade`, which:
- Enforces table allow-list.
- Forbids write/upsert/batch operations (raises `PersistencePermissionError`).

Current policy (dual allowlists):
* Reads: all business tables (`campaigns`, `clients`, `conversations`, `leads`, `messages`, `sequences`, `staging_leads`, `inquiries`).
* Writes: restricted; governance/reference tables (`clients`, `campaigns`) are always read-only.
The facade is provisioned with an *empty* write list to harden against accidental mutation even if the underlying service changes.

Testing Guidance
----------------
Use the memory backend for fast, deterministic tests:
```python
from agent.operational_agents.factory import create_rag_agent, create_persistence_agent

p = create_persistence_agent(kind='memory')
p.write('leads', {'email': 'a@x.io', 'company_name': 'Acme'})
rag = create_rag_agent(kind='memory')
assert rag.run('find leads at acme', return_json=True)['metadata']['total_count'] == 1
```

Config & Environment
--------------------
| Variable | Purpose | Default |
|----------|---------|---------|
| RAG_DEFAULT_LIMIT | Default page size when limit omitted | 50 |
| RAG_MAX_LIMIT | Hard ceiling on requested limit | 500 |
| RAG_SUMMARY_THRESHOLD | Row count above which summary/truncation metadata added | 200 |
| RAG_MAX_FALLBACKS_PER_MIN | Fallback (LLM) invocations allowed / 60s | 30 |
| RAG_REFORMULATION_MAX_ATTEMPTS | Max deterministic reformulation attempts | 3 |
| RAG_CACHE_DISABLED | Set to 1/true to disable in-run cache | enabled when not set |

Planned Enhancements (Next)
---------------------------
- Multi-table composite query (batch leads + conversations) with unified envelope.
- Vector / hybrid retrieval adapter integration.
- Optional PII redaction + redaction-aware provenance.
- Projection & column whitelist for security hardening.
- Extended operators (range, in) with capability negotiation.
- Structured logging of agent fallback error chain (debug flag).

Deprecation Timeline
--------------------
- Phase 2: Remove legacy direct Supabase client; require injected facade.
- Phase 3: Introduce capability flags (filter ops) negotiated with persistence layer.

Troubleshooting
---------------
| Symptom | Cause | Action |
|---------|-------|--------|
| Empty results | Filters over-constrained | Re-run with fewer explicit filters. |
| Missing `OPENAI_API_KEY` warning | Dev env missing key | Set env var or ignore (LLM fallback disabled). |
| PersistencePermissionError | Attempted write via facade | Use full `PersistenceAgent` for writes. |

Ownership
---------
Agent Infrastructure / Data Platform.

Change Log
----------
- v0.1: Legacy direct Supabase RAG agent.
- v0.2: Deterministic filter parsing + envelope output.
- v0.3: Read-only facade injection + factory integration.
- v0.4: Robust agent invocation wrapper, fallback_on_empty logic.
- v0.5: Pagination, caching, reformulation loop, rate-limited fallback, large result summarization.

End.
