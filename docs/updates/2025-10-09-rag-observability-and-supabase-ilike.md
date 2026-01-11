# RAG observability and Supabase ilike enhancements (2025-10-09)

This update focuses on making RAG test runs transparent end-to-end and improving Supabase retrieval fidelity. It also adds targeted real-data tests to experiment with success/fail filters on the `leads` table.

## Highlights

- Deep trace mode for RAG
  - Enable with `--rag-deep-debug` or env `RAG_DEEP_DEBUG=1`.
  - Shows: parsing (rule/LLM), normalized filters, persistence queries, pagination, reformulations, fallback attempts, and agent call outcomes.
- Rich test-time I/O prints
  - `--rag-verbose` prints live run/tool lines.
  - `--rag-capture-tools` shows tool SEND/RECV and final tool snapshots.
  - `--rag-print-records` previews rows; `--rag-print-records-full` prints full JSON rows.
  - Red "failed identification" line on zero results, e.g. `[IDENT FAIL] failed identification (email=...)`.
  - A summary is written to `rag_summary.json` after test session.
- Deterministic default on empty filters
  - When no filters are parsed and `return_json=True`, run a small, safe list of `leads` before LLM fallback. Controlled by `RAG_DEFAULT_LIST_ON_EMPTY=1` (default).
- Supabase `ilike` support in adapter
  - SDK path uses `q.ilike()` when `%` is present.
  - REST fallback translates to `ilike.*pattern*`.
  - Adapter capabilities now expose `ilike=True`.
- New real Supabase tests (success/fail experiments)
  - `test_real_email_exact_success_and_fail`
  - `test_real_company_success_and_fail`
  - `test_real_id_success_and_fail`
  - A `one_valid_lead` fixture samples a real row to avoid hard-coding test data.

## How to run

- Single test with full visibility:

```powershell
# Email success+fail with deep traces and full records printed
.\.venv\Scripts\python.exe -m pytest tests/test_rag_public_leads_integration.py::TestPublicLeadsReal::test_real_email_exact_success_and_fail -s --rag-verbose --rag-capture-tools --rag-print-records --rag-print-records-full --rag-deep-debug -q
```

- Run all real tests in the class:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_rag_public_leads_integration.py::TestPublicLeadsReal -s --rag-verbose --rag-capture-tools --rag-print-records --rag-deep-debug -q
```

- Environment toggles (instead of flags):

```powershell
$env:RAG_DEEP_DEBUG = "1"
$env:RAG_PRINT_RECORDS = "1"; $env:RAG_PRINT_RECORDS_FULL = "1"
$env:RAG_CAPTURE_TOOLS = "1"; $env:RAG_DEBUG_IO = "1"
```

## What changed (code)

- `agent/operational_agents/rag_agent/rag_agent.py`
  - Added deep trace helper (`_deep`) and instrumentation across parse, query, pagination, reformulation, and fallbacks.
  - Deterministic default list on empty filters before LLM fallback (env: `RAG_DEFAULT_LIST_ON_EMPTY`).
- `agent/tools/persistence/adapters/supabase_adapter.py`
  - `capabilities["ilike"]=True`; SDK uses `ilike`, REST uses `ilike.*pattern*`.
  - Added trace prints for SDK and REST query paths when `RAG_DEEP_DEBUG=1`.
- `agent/tools/persistence/adapters/in_memory_adapter.py`
  - Added `[MEM TRACE]` for queries when `RAG_DEEP_DEBUG=1`.
- `agent/tools/persistence/service.py`
  - Added `[PERSIST TRACE] begin/end` around adapter calls when `RAG_DEEP_DEBUG=1`.
- `tests/conftest.py`
  - Autoload `.env`.
  - Added CLI flags: `--rag-verbose`, `--rag-capture-tools`, `--rag-print-records`, `--rag-print-records-full`, `--rag-records-n`, `--rag-record-fields`, `--rag-deep-debug`.
  - Session-early tool patch; per-run and per-tool record previews; red `[IDENT FAIL]` marker on zero results.
  - Summary printing + `rag_summary.json` artifact.
- `tests/test_rag_public_leads_integration.py`
  - New tests to validate success/fail with real data for email/company/id.

## Notes & next steps

- The pure agent path can still report planner validation messages when no structured args are provided; this is intentionally captured in the envelope to avoid exceptions.
- Optional: add a green `[IDENT OK]` line for successful identifications.
- Optional: introduce a small data catalog/router to normalize filters and route table selection declaratively.
- Optional: limit default-list to N rows and add ordering per table via a manifest.
