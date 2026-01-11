# Tests Overview

This directory contains the automated test suites for the Agentic System. The focus is on
verifying the Retrieval Augmented Generation (RAG) agent, persistence layer governance, and
integration behaviors with both mock (in‑memory) and real Supabase backends.

## Quick Run
```bash
# Run fast deterministic tests only
pytest -k "rag and not integration" -q

# Run full suite including integration tests (requires .env with SUPABASE_URL + key)
pytest -q
```

Environment auto-loading: `tests/conftest.py` loads a root `.env` without overriding existing
process environment variables.

## Directory Structure (Updated Task 16)

With the new three-tier + services architecture, tests are now organized as:

```
tests/
├── conftest.py                    # Shared pytest configuration and fixtures
├── unit/                          # Unit tests (isolated components)
│   ├── __init__.py
│   ├── tier_1/                    # Manager agent tests
│   ├── tier_2/                    # Orchestrators tests
│   ├── tier_3/                    # Agents tests (RAG, Persistence, Copywriter)
│   ├── services/                  # Services layer tests
│   ├── core/                      # Core framework tests (harness, envelope)
│   ├── test_rate_limiter.py       # Utility tests (legacy - to migrate)
│   └── test_typed_envelope.py     # Envelope tests (legacy - to migrate)
├── integration/                   # Integration tests (multi-component)
│   ├── __init__.py
│   ├── test_redis_streams.py      # Redis streams integration
│   └── test_worker_lifecycle.py   # Full worker lifecycle
├── smoke/                         # Quick health checks
│   ├── __init__.py
│   └── test_health.py             # Basic health/import validation
├── fixtures/                      # Shared test fixtures and mock data
│   ├── __init__.py
│   ├── agents.py                  # Mock agent fixtures
│   ├── messages.py                # Sample envelopes and messages
│   └── data_generators.py         # Test data generators
└── README.md                      # This file
```

## File Summaries

### `test_rag_agent.py`
End-to-end core RAG agent fast-path tests using an in-memory persistence facade.
- Seeds multiple tables (`leads`, `conversations`, `messages`, etc.) to simulate a small dataset.
- Verifies email/company/wildcard filter parsing via `run()`.
- Exercises the generic `query_table` tool across the read allowlist.
- Ensures invalid table queries return error metadata instead of raising.
- Confirms LLM fallback path (`fallback_on_empty=True`) augments the envelope with a synthetic response record when no rows.
- Asserts the agent exposes no write capabilities when using `ReadOnlyPersistenceFacade`.

### `test_rag_agent_nlp.py`
Deterministic NLP-style parsing tests (rule-based only) for `id`, `email`, and `company`.
- Uses shared in-memory adapter and a read-only facade.
- Validates envelope structure and provenance presence implicitly.
- Ensures the agent remains read-only (no accidental write surface).

### `test_rag_tool_guard.py`
Legacy guard regression test for `rag_tool` passthrough behavior.
- Supplies a pre-built envelope (dict + JSON string) to `rag_tool` and expects records to be returned unchanged.
- Verifies that the legacy coordinator path is not invoked when an envelope is already provided.

### `test_rag_pagination_and_cache.py`
Pagination and caching behavior validation.
- Seeds 120 leads to exercise page slicing.
- Verifies default limit enforcement, explicit `limit/offset`, and max limit capping.
- Confirms in-run cache hit after initial query via `query_leads` tool metadata (`cache: hit`).

### `test_rag_public_leads_integration.py`
Hybrid mock + real integration scenarios for the public `leads` table.
- Real tests (guarded by Supabase env vars) perform basic limited queries, wildcard filtering, and fallback invocation.
- Mock tests cover: correct filters, intentionally wrong/no data cases, reformulation attempts, pagination sanity, and fallback logic.
- Provides debug `print` statements for visibility during CI or manual runs.

### `conftest.py`
Global test configuration and utilities.
- Auto-loads root `.env` file (non-destructive to existing env vars).
- Implements autouse fixture to wrap `RAGAgent.run` and capture every JSON envelope (intermediate + final) with timing.
- Generates colorized per-test session summary plus optional JSON artifact (`rag_summary.json`).
- Supports suppression of live integration tests via `DISABLE_LIVE_INTEGRATION=1`.

## Key Concepts Validated
- Deterministic filter parsing vs. LLM fallback behavior.
- Read-only governance (no writes via RAG agent facade).
- Tool shape resilience to malformed input.
- Pagination (limit/offset) and cache effectiveness.
- Reformulation loop (broadening strategies) before agent reasoning fallback.
- Integration with real Supabase (if credentials present).

## Adding New Tests
1. Prefer in-memory adapter for deterministic logic.
2. Use `return_json=True` to automatically include the run in session summary.
3. For new performance assertions, mark tests (e.g. `@pytest.mark.perf`) and optionally add latency guards.
4. To test new fallback strategies, force zero-result initial filters and assert presence + shape of `reformulation_attempts`.

## Environment Flags
| Variable | Purpose |
|----------|---------|
| SUPABASE_URL / SUPABASE_SERVICE_KEY | Enable real integration tests |
| DISABLE_LIVE_INTEGRATION=1 | Skip tests marked by keyword (currently live Supabase classes) |
| RAG_DEBUG=1 | Verbose internal debug prints from RAG agent |
| RAG_SUMMARY_COLOR=0 | Disable colored summary output |
| RAG_SUMMARY_JSON=path | Change JSON summary output filename |
| RAG_SUMMARY_DISABLE_FILE=1 | Disable writing summary JSON artifact |
| RAG_SUMMARY_INTERMEDIATE=0 | Suppress intermediate per-run log lines |

## Coverage & Badges

You can generate a coverage report (terminal %, HTML, XML) and produce a badge that can be published
via GitHub Pages or an external service (Codecov, Coveralls).

### 1. Local Coverage Run
Install the plugin (if not already available):
```bash
pip install pytest-cov
```
Run tests with coverage:
```bash
pytest --cov=agent --cov=tests --cov-report=term-missing --cov-report=xml --cov-report=html -q
```
Artifacts:
- `coverage.xml` (XML report; used by Codecov / Shields endpoint)
- `htmlcov/` (open `htmlcov/index.html` in a browser)

### 2. Simple Local Badge (Static)
After running coverage you can extract the total percent and write a JSON endpoint
consumable by Shields.io. Example helper script (`scripts/make_coverage_badge.py`):
```python
import json, re, pathlib
xml = pathlib.Path('coverage.xml').read_text()
m = re.search(r'lines-rate="([0-9.]+)"', xml)
pct = 0 if not m else round(float(m.group(1))*100, 1)
badge = {
	"schemaVersion": 1,
	"label": "coverage",
	"message": f"{pct}%",
	"color": "brightgreen" if pct >= 90 else "green" if pct >= 80 else "yellow" if pct >= 65 else "orange"
}
pathlib.Path('coverage-badge.json').write_text(json.dumps(badge))
print('Wrote coverage-badge.json with', pct)
```
Commit `coverage-badge.json` to a branch (or publish via GitHub Pages) and then reference it:
```markdown
![coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/BoonBoonBoonBoon/Agentic-System/hazard/coverage-badge.json)
```

### 3. Codecov Badge (Recommended for Automation)
1. Sign in to https://codecov.io and add the repository.
2. In CI, after tests, upload coverage:
```bash
curl -Os https://uploader.codecov.io/latest/linux/codecov
chmod +x codecov
./codecov -t <CODECOV_TOKEN>
```
3. Add badge to main README:
```markdown
[![codecov](https://codecov.io/gh/BoonBoonBoonBoon/Agentic-System/branch/hazard/graph/badge.svg)](https://codecov.io/gh/BoonBoonBoonBoon/Agentic-System)
```

### 4. GitHub Actions Example Snippet
Add a workflow (e.g. `.github/workflows/ci.yml`):
```yaml
name: CI
on: [push, pull_request]
jobs:
	tests:
		runs-on: ubuntu-latest
		steps:
			- uses: actions/checkout@v4
			- uses: actions/setup-python@v5
				with:
					python-version: '3.11'
			- name: Install deps
				run: |
					pip install -U pip
					pip install -e .[dev] pytest-cov
			- name: Run tests with coverage
				run: pytest --cov=agent --cov=tests --cov-report=xml --cov-report=term-missing -q
			- name: Upload coverage artifact
				uses: actions/upload-artifact@v4
				with:
					name: coverage-xml
					path: coverage.xml
			- name: Generate badge JSON
				run: python scripts/make_coverage_badge.py
			- name: Commit badge (optional)
				if: github.ref == 'refs/heads/hazard'
				run: |
					git config user.name github-actions
					git config user.email actions@github.com
					git add coverage-badge.json
					git commit -m "chore: update coverage badge" || echo "No changes"
					git push
```

### 5. Adding the Badge to Main README
Insert near the top of `README.md`:
```markdown
![coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/BoonBoonBoonBoon/Agentic-System/hazard/coverage-badge.json)
```

### 6. Notes
- Keep badge JSON lightweight (<1KB).
- If using GitHub Pages, place `coverage-badge.json` in the `docs/` folder and point Shields to the raw URL.
- For monorepos, produce separate badges per package (e.g. `coverage-agent.json`).

## Future Enhancement Ideas
- Add stress tests for high-volume pagination.
- Introduce property-based tests for filter parsing.
- Add performance budget tests (p95 latency assertions).
- Expand real integration to multi-table contexts once implemented.

---

## CI/CD Test Suite (Added October 29, 2025)

### New Test Structure

In addition to the RAG-specific tests above, we now have a comprehensive CI/CD test suite:

```
tests/
├── test_imports.py          # Import smoke tests for all modules
├── unit/                    # Fast unit tests (<1ms)
│   ├── test_rate_limiter.py      # Rate limiting algorithms
│   └── test_typed_envelope.py    # Envelope schema validation
├── integration/             # Integration tests (requires Redis)
│   ├── test_redis_streams.py     # Redis stream operations
│   └── test_worker_lifecycle.py  # Worker startup/shutdown
└── smoke/                   # Quick health checks
    └── test_health.py             # System health validation
```

### Running CI/CD Tests

```bash
# All tests
pytest -v

# By category
pytest -m unit -v              # Fast unit tests
pytest -m integration -v       # Integration tests (requires Redis)
pytest -m smoke -v             # Quick health checks

# With coverage
pytest --cov=agent --cov-report=html -v
```

### Test Markers

Use pytest markers to categorize tests:

- `@pytest.mark.unit` - Fast tests, no external dependencies
- `@pytest.mark.integration` - Tests with Redis, databases
- `@pytest.mark.smoke` - Quick health checks
- `@pytest.mark.slow` - Tests taking >1 second
- `@pytest.mark.llm` - Tests calling LLM APIs

### Configuration Files

- **pytest.ini** - Test discovery, coverage, markers
- **.flake8** - Linting rules
- **mypy.ini** - Type checking configuration

### GitHub Actions Integration

Tests run automatically on:
- **preprod branch:** Linting, type checking, unit tests
- **hazard branch:** All tests + integration + Docker builds

See: [.github/workflows/](../.github/workflows/)

### Writing New Tests

#### Unit Test Template
```python
import pytest

@pytest.mark.unit
def test_feature():
    """Test specific feature behavior."""
    # Arrange
    input_data = "test"
    
    # Act
    result = function(input_data)
    
    # Assert
    assert result == expected
```

#### Integration Test Template
```python
import pytest
import redis
import os

@pytest.fixture
def redis_client():
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    client = redis.from_url(redis_url, decode_responses=True)
    yield client
    # Cleanup
    for key in client.scan_iter("test:*"):
        client.delete(key)

@pytest.mark.integration
def test_redis_operation(redis_client):
    """Test Redis stream operation."""
    message_id = redis_client.xadd("test:stream", {"data": "value"})
    assert message_id is not None
```

### Coverage Targets

| Category | Target | Current |
|----------|--------|---------|
| Critical code | 100% | ~95% |
| Business logic | 80% | ~70% |
| Utils/helpers | 70% | ~65% |
| Overall | 60% | ~65% |

### Environment Variables for Tests

```bash
# Required for integration tests
export REDIS_URL=redis://localhost:6379

# Optional for LLM tests
export OPENAI_API_KEY=sk-proj-...
export ANTHROPIC_API_KEY=sk-ant-...

# Optional for database tests
export DATABASE_URL=postgresql://...
```

### Documentation

Full CI/CD documentation: **[docs/CI_CD_SETUP.md](../docs/CI_CD_SETUP.md)**

---
Maintainers: Agent Infrastructure / Data Platform.
