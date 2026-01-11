jobs:
# Tests (what reviewers should know)

This folder holds the automated tests that prove the system’s core behaviors without relying on live services. They’re fast, deterministic, and written to showcase engineering discipline for a portfolio review.

## How to run

```powershell
# From the repo root
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run the fast, offline suite
pytest -q

# (Optional) Run only RAG-focused fast tests
pytest -k "rag and not integration" -q

# (Optional) Enable live integration tests locally (requires credentials)
$env:USE_REAL_TESTS = "1"
pytest -q
```

Notes:
- We auto-load a root `.env` (see `tests/conftest.py`) but never override existing environment variables.
- CI runs the offline suite and a secret scan. Coverage is published as a badge; details in `docs/CI.md`.

## What’s covered (at a glance)

- RAG behavior and tool path (`test_rag_agent.py`, `test_rag_agent_nlp.py`)
  - Parse simple filters (id/email/company), paginate safely, and return deterministic “envelopes” (metadata + records + provenance).
  - Read-only governance is enforced via a `ReadOnlyPersistenceFacade`.

- Pagination and caching (`test_rag_pagination_and_cache.py`)
  - Verifies default/explicit limits, offset paging, and caching hints.

- Public leads scenarios (`test_rag_public_leads_integration.py`)
  - Runs with a mock dataset by default; can exercise real reads if env vars are set.

- Persistence policy (`test_persistence_agent.py`)
  - Validates allowlists and read-only behavior; prevents writes to governance tables.

- Orchestrator and worker paths (`test_reply_orchestrator*.py`, `test_worker_audit.py`)
  - Prove envelope shaping and audit persistence with a no‑op delivery adapter.

## Helpful flags

- `-k "expr"` filter tests by keyword.
- `-q` quiet mode, `-s` show stdout.
- Debug envs for deeper visibility (optional):
  - `RAG_DEBUG_IO=1` to print I/O envelopes.
  - `DISABLE_LIVE_INTEGRATION=1` to skip any accidental live tests.

## Artifacts

The test harness can emit a colorized run summary and, optionally, `rag_summary.json` for quick inspection of prompts/filters and results. See hooks in `tests/conftest.py`.

---

If you’re reviewing this repo as a portfolio: skim the tests above (especially the RAG and persistence suites) to see how we keep behavior deterministic, safe, and auditable.
