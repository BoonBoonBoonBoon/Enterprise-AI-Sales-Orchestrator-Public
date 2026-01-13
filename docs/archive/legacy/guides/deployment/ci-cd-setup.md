# CI/CD Pipeline Setup

## Overview

This document describes the continuous integration and deployment pipeline for the Agentic System. The CI/CD setup ensures code quality, prevents regressions, and enables safe automated deployments across environments.

**Last Updated:** October 29, 2025  
**Status:** âœ… Production Ready

---

## Table of Contents

1. [Architecture](#architecture)
2. [GitHub Actions Workflows](#github-actions-workflows)
3. [Branch Strategy](#branch-strategy)
4. [Test Strategy](#test-strategy)
5. [Configuration Files](#configuration-files)
6. [Secrets Management](#secrets-management)
7. [Deployment Environments](#deployment-environments)
8. [Monitoring & Alerts](#monitoring--alerts)
9. [Troubleshooting](#troubleshooting)
10. [Best Practices](#best-practices)

---

## Architecture

### Pipeline Overview

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                         Developer Push                          â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                             â”‚
                   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                   â”‚  GitHub Actions   â”‚
                   â”‚    Triggered      â”‚
                   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                             â”‚
              â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
              â”‚                             â”‚
    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”      â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
    â”‚   Pre-Production   â”‚      â”‚    Production      â”‚
    â”‚   Workflow (preprod)â”‚      â”‚  Workflow (hazard) â”‚
    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜      â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
              â”‚                            â”‚
    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”      â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
    â”‚  1. Linting        â”‚      â”‚  1. All Preprod    â”‚
    â”‚  2. Type Checking  â”‚      â”‚     Checks         â”‚
    â”‚  3. Import Tests   â”‚      â”‚  2. Integration    â”‚
    â”‚  4. Unit Tests     â”‚      â”‚     Tests          â”‚
    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜      â”‚  3. Redis Cloud    â”‚
              â”‚                 â”‚     Validation     â”‚
              â”‚                 â”‚  4. Docker Build   â”‚
              â”‚                 â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
              â”‚                           â”‚
              â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                         â”‚
                    â”Œâ”€â”€â”€â”€â–¼â”€â”€â”€â”€â”
                    â”‚ Success â”‚ â”€â”€â–º Ready for Deployment
                    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Two-Stage Validation

1. **Pre-Production (preprod branch)**

   - Fast feedback loop (~3-5 minutes)
   - Code quality checks (linting, type checking)
   - Import smoke tests
   - Unit tests
   - **Purpose:** Catch syntax errors, import issues, basic logic bugs early

2. **Production (hazard branch)**
   - Comprehensive validation (~8-12 minutes)
   - All pre-production checks PLUS:
   - Integration tests with live Redis Cloud
   - Worker health checks
   - End-to-end workflow validation
   - Docker image builds
   - **Purpose:** Ensure production readiness with realistic integration

---

## GitHub Actions Workflows

### 1. Pre-Production Workflow

**File:** `.github/workflows/ci-preprod.yml`

**Triggers:**

- Push to `preprod` branch
- Pull requests targeting `preprod`

**Jobs:**

```yaml
jobs:
  quality-checks:
    - Setup Python 3.11
    - Install dependencies
    - Run flake8 (linting)
    - Run mypy (type checking)
    - Run import tests
    - Run unit tests with pytest
    - Upload coverage reports
```

**Checks Performed:**

| Check             | Tool       | Purpose                           | Fail Threshold       |
| ----------------- | ---------- | --------------------------------- | -------------------- |
| **Linting**       | flake8     | Code style, PEP 8 compliance      | Any error            |
| **Type Checking** | mypy       | Static type validation            | Any error            |
| **Import Tests**  | pytest     | Verify all modules importable     | Any import failure   |
| **Unit Tests**    | pytest     | Test individual functions/classes | Any test failure     |
| **Coverage**      | pytest-cov | Code coverage reporting           | < 60% (warning only) |

**Example Output:**

```
âœ“ Linting passed (0 errors, 3 warnings)
âœ“ Type checking passed (0 errors)
âœ“ Import tests passed (47 modules imported successfully)
âœ“ Unit tests passed (124 tests, 0 failures)
âœ“ Coverage: 73.5% (target: 60%)
```

**Duration:** ~3-5 minutes

---

### 2. Production Workflow

**File:** `.github/workflows/ci-hazard.yml`

**Triggers:**

- Push to `hazard` branch
- Pull requests targeting `hazard`
- Manual workflow dispatch

**Jobs:**

```yaml
jobs:
  preprod-checks:
    - Run all pre-production checks

  integration-tests:
    needs: preprod-checks
    - Setup Python 3.11
    - Install dependencies
    - Start Redis container (for local tests)
    - Run integration tests
    - Validate Redis Cloud connectivity
    - Test worker startup/shutdown
    - Verify stream operations

  docker-build:
    needs: integration-tests
    - Build Docker images (workers, orchestrator)
    - Tag images with commit SHA
    - Push to registry (optional)
```

**Checks Performed:**

| Check                 | Tool              | Purpose                 | Fail Threshold       |
| --------------------- | ----------------- | ----------------------- | -------------------- |
| **All Preprod**       | See above         | Baseline quality        | Any preprod failure  |
| **Integration Tests** | pytest            | End-to-end workflows    | Any test failure     |
| **Redis Streams**     | pytest + redis-py | Stream operations       | Connection failure   |
| **Worker Health**     | pytest            | Worker startup/shutdown | Health check failure |
| **Docker Build**      | docker build      | Container creation      | Build failure        |

**Example Output:**

```
âœ“ Pre-production checks passed (3m 42s)
âœ“ Integration tests passed (28 tests, 0 failures)
  - Redis stream operations: PASS (12 tests)
  - Worker lifecycle: PASS (8 tests)
  - End-to-end workflows: PASS (8 tests)
âœ“ Redis Cloud validation passed
âœ“ Docker builds successful (3 images)
```

**Duration:** ~8-12 minutes

---

## Branch Strategy

### Branch Hierarchy

```
main (stable, deployable)
  â””â”€â”€ hazard (production candidate)
       â””â”€â”€ preprod (development integration)
            â””â”€â”€ feature/* (developer branches)
```

### Branch Protection Rules

**`preprod` branch:**

- âœ… Require status checks to pass before merging
  - `quality-checks` job must succeed
- âœ… Require pull request reviews (1 approval)
- âœ… Require branches to be up to date before merging
- âŒ Do not allow force pushes
- âŒ Do not allow deletions

**`hazard` branch:**

- âœ… Require status checks to pass before merging
  - `preprod-checks` job must succeed
  - `integration-tests` job must succeed
  - `docker-build` job must succeed
- âœ… Require pull request reviews (2 approvals)
- âœ… Require linear history
- âœ… Require branches to be up to date before merging
- âŒ Do not allow force pushes
- âŒ Do not allow deletions

**`main` branch:**

- âœ… Require pull request from `hazard` only
- âœ… Require 2 approvals from code owners
- âœ… Require all status checks from `hazard` branch
- âŒ Do not allow direct pushes
- âŒ Do not allow force pushes

### Workflow

```bash
# 1. Create feature branch from preprod
git checkout preprod
git pull origin preprod
git checkout -b feature/add-new-functionality

# 2. Develop and commit
git add .
git commit -m "feat: Add new functionality"

# 3. Push and create PR to preprod
git push origin feature/add-new-functionality
# Create PR on GitHub: feature/add-new-functionality â†’ preprod

# 4. CI runs pre-production checks
# Wait for: âœ“ quality-checks

# 5. After review and merge to preprod, create PR to hazard
git checkout hazard
git pull origin hazard
# Create PR on GitHub: preprod â†’ hazard

# 6. CI runs integration tests
# Wait for: âœ“ preprod-checks, âœ“ integration-tests, âœ“ docker-build

# 7. After review and merge to hazard, create PR to main
# Create PR on GitHub: hazard â†’ main

# 8. Deploy from main
```

---

## Test Strategy

### Test Pyramid

```
                    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                    â”‚   E2E Tests â”‚ (Few, Slow, High Value)
                    â”‚  ~10 tests  â”‚
                    â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”˜
                  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”
                  â”‚ Integration Testsâ”‚ (Some, Medium, High Value)
                  â”‚   ~30 tests      â”‚
                  â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
              â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
              â”‚     Unit Tests        â”‚ (Many, Fast, Essential)
              â”‚    ~150+ tests        â”‚
              â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Test Categories

#### 1. Unit Tests (`tests/unit/`)

**Scope:** Individual functions, classes, methods

**Examples:**

- `test_typed_envelope_creation()`
- `test_rate_limiter_token_bucket()`
- `test_secrets_provider_env()`
- `test_prompt_builder_validation()`

**Run Command:**

```bash
pytest tests/unit/ -v
```

**Characteristics:**

- Fast (<1ms per test)
- No external dependencies (mock Redis, LLMs, etc.)
- High coverage (aim for 80%+)

#### 2. Integration Tests (`tests/integration/`)

**Scope:** Multiple components working together

**Examples:**

- `test_redis_stream_operations()` - XADD, XREADGROUP, XACK
- `test_rag_worker_lifecycle()` - Start, process, shutdown
- `test_copywriter_end_to_end()` - Task â†’ LLM â†’ Result
- `test_persistence_write_flow()` - Task â†’ DB â†’ Verification

**Run Command:**

```bash
pytest tests/integration/ -v
```

**Characteristics:**

- Medium speed (100ms-1s per test)
- Requires Redis (local or Cloud)
- Tests real integrations (no mocks for Redis/DB)

#### 3. Import Tests (`tests/test_imports.py`)

**Scope:** Verify all modules are importable

**Purpose:**

- Catch circular import issues
- Validate dependency availability
- Ensure **init**.py correctness

**Run Command:**

```bash
pytest tests/test_imports.py -v
```

**Example:**

```python
def test_import_workers():
    """Verify all workers can be imported."""
    from agent.operational_agents.rag_agent.worker import RAGWorker
    from agent.operational_agents.copywriter.worker import CopywriterWorker
    from agent.operational_agents.persistence_agent.write_worker import PersistenceWriteWorker
    assert RAGWorker is not None
    assert CopywriterWorker is not None
    assert PersistenceWriteWorker is not None
```

#### 4. Smoke Tests (`tests/smoke/`)

**Scope:** Basic system health checks

**Examples:**

- `test_redis_connectivity()` - Can connect to Redis?
- `test_database_connectivity()` - Can connect to PostgreSQL?
- `test_llm_api_keys()` - Are API keys configured?
- `test_worker_health_endpoints()` - Are workers responding?

**Run Command:**

```bash
pytest tests/smoke/ -v
```

**Characteristics:**

- Very fast (<100ms per test)
- Run on every deploy
- Early failure detection

---

## Configuration Files

### pytest.ini

**Location:** `pytest.ini` (repository root)

```ini
[pytest]
# Test discovery
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Output
addopts =
    -v
    --tb=short
    --strict-markers
    --cov=agent
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=60

# Markers
markers =
    unit: Unit tests (fast, no external dependencies)
    integration: Integration tests (requires Redis)
    smoke: Smoke tests (basic health checks)
    slow: Slow tests (>1 second)
    llm: Tests that call LLM APIs (requires API keys)

# Coverage
[coverage:run]
omit =
    tests/*
    .venv/*
    */migrations/*
    */site-packages/*

[coverage:report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
```

### .flake8

**Location:** `.flake8` (repository root)

```ini
[flake8]
# Maximum line length
max-line-length = 120

# Exclude patterns
exclude =
    .git,
    __pycache__,
    .venv,
    venv,
    build,
    dist,
    *.egg-info,
    .pytest_cache,
    .mypy_cache

# Ignore specific rules
ignore =
    E203,  # Whitespace before ':'
    E266,  # Too many leading '#' for block comment
    E501,  # Line too long (handled by max-line-length)
    W503,  # Line break before binary operator
    W504,  # Line break after binary operator

# Error codes to always check
select =
    E,    # pycodestyle errors
    W,    # pycodestyle warnings
    F,    # pyflakes
    C,    # mccabe complexity

# Complexity threshold
max-complexity = 15

# Per-file ignores
per-file-ignores =
    __init__.py:F401,F403
    tests/*:F401,F811
```

### mypy.ini

**Location:** `mypy.ini` (repository root)

```ini
[mypy]
# Python version
python_version = 3.11

# Import discovery
mypy_path = agent
files = agent, tests

# Type checking strictness
strict = False
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = False
disallow_incomplete_defs = False
check_untyped_defs = True
disallow_untyped_decorators = False

# Error output
show_error_codes = True
show_column_numbers = True
show_error_context = True
pretty = True

# Warnings
warn_redundant_casts = True
warn_unused_ignores = True
warn_no_return = True
warn_unreachable = True

# Untyped definitions
disallow_any_unimported = False
disallow_any_expr = False
disallow_any_decorated = False
disallow_any_explicit = False

# Strict optional
no_implicit_optional = True
strict_optional = True

# Module-specific settings
[mypy-redis.*]
ignore_missing_imports = True

[mypy-sqlalchemy.*]
ignore_missing_imports = True

[mypy-pydantic.*]
ignore_missing_imports = True

[mypy-openai.*]
ignore_missing_imports = True

[mypy-anthropic.*]
ignore_missing_imports = True

[mypy-pytest.*]
ignore_missing_imports = True
```

### .gitignore Updates

Add CI/CD artifacts:

```gitignore
# CI/CD
.pytest_cache/
.mypy_cache/
htmlcov/
.coverage
coverage.xml
*.cover
.hypothesis/

# Test outputs
test-results/
test-output/
*.log
```

---

## Secrets Management

### GitHub Secrets

Configure in: **Settings â†’ Secrets and variables â†’ Actions**

#### Required Secrets

| Secret Name         | Description                     | Used In       | Example Value                    |
| ------------------- | ------------------------------- | ------------- | -------------------------------- |
| `REDIS_CLOUD_URL`   | Redis Cloud connection URL      | ci-hazard.yml | `redis://<REDACTED_REDIS_URL>    |
| `OPENAI_API_KEY`    | OpenAI API key for LLM tests    | ci-hazard.yml | `sk-proj-...`                    |
| `ANTHROPIC_API_KEY` | Anthropic API key for LLM tests | ci-hazard.yml | `sk-ant-...`                     |
| `DATABASE_URL`      | PostgreSQL connection URL       | ci-hazard.yml | `postgresql://user:pass@host/db` |
| `DOCKER_USERNAME`   | Docker Hub username (optional)  | ci-hazard.yml | `yourorg`                        |
| `DOCKER_PASSWORD`   | Docker Hub token (optional)     | ci-hazard.yml | `dckr_pat_...`                   |

#### Optional Secrets

| Secret Name         | Description                      | Used In        |
| ------------------- | -------------------------------- | -------------- |
| `SLACK_WEBHOOK_URL` | Slack notifications for failures | Both workflows |
| `SENTRY_DSN`        | Sentry error tracking            | Both workflows |
| `CODECOV_TOKEN`     | Codecov.io integration           | ci-preprod.yml |

### Using Secrets in Workflows

```yaml
- name: Run integration tests
  env:
    REDIS_URL: ${{ secrets.REDIS_CLOUD_URL }}
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  run: |
    pytest tests/integration/ -v
```

### Local Testing

Create `.env.test` (gitignored):

```bash
# .env.test (DO NOT COMMIT)
REDIS_URL=redis://localhost:6379
OPENAI_API_KEY=sk-proj-test-key
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql://localhost/agentic_test
```

Load before running tests:

```bash
# Windows PowerShell
Get-Content .env.test | ForEach-Object {
    $name, $value = $_.split('=')
    Set-Content env:\$name $value
}

# Linux/Mac
export $(cat .env.test | xargs)
```

---

## Deployment Environments

### Environment Configuration

| Environment     | Branch    | CI Workflow    | Deploy Target | Redis       | Database         |
| --------------- | --------- | -------------- | ------------- | ----------- | ---------------- |
| **Development** | `preprod` | ci-preprod.yml | Local Docker  | Local Redis | Local PostgreSQL |
| **Staging**     | `hazard`  | ci-hazard.yml  | Cloud VMs     | Redis Cloud | RDS/Azure SQL    |
| **Production**  | `main`    | (Manual)       | Kubernetes    | Redis Cloud | RDS/Azure SQL    |

### Environment Variables

**Development (preprod):**

```bash
ENV=development
DEBUG=true
LOG_LEVEL=DEBUG
REDIS_URL=redis://localhost:6379
RATE_LIMIT_ENABLED=false
```

**Staging (hazard):**

```bash
ENV=staging
DEBUG=false
LOG_LEVEL=INFO
REDIS_URL=redis://<REDACTED_REDIS_URL>
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_SECOND=100
```

**Production (main):**

```bash
ENV=production
DEBUG=false
LOG_LEVEL=WARNING
REDIS_URL=redis://<REDACTED_REDIS_URL>
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_SECOND=50
SECRETS_PROVIDER=azure-keyvault
```

---

## Monitoring & Alerts

### GitHub Actions Monitoring

**Status Badge:**

Add to README.md:

```markdown
[![CI - Pre-Production](https://github.com/BoonBoonBoonBoon/Agentic-System/actions/workflows/ci-preprod.yml/badge.svg?branch=preprod)](https://github.com/BoonBoonBoonBoon/Agentic-System/actions/workflows/ci-preprod.yml)

[![CI - Production](https://github.com/BoonBoonBoonBoon/Agentic-System/actions/workflows/ci-hazard.yml/badge.svg?branch=hazard)](https://github.com/BoonBoonBoonBoon/Agentic-System/actions/workflows/ci-hazard.yml)
```

### Failure Notifications

**Slack Integration:**

```yaml
# In workflow file
- name: Notify Slack on Failure
  if: failure()
  uses: slackapi/slack-github-action@v1.24.0
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
    payload: |
      {
        "text": "âŒ CI Pipeline Failed",
        "blocks": [
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": "*Workflow:* ${{ github.workflow }}\n*Branch:* ${{ github.ref_name }}\n*Commit:* ${{ github.sha }}\n*Author:* ${{ github.actor }}"
            }
          }
        ]
      }
```

### Metrics to Track

| Metric                   | Description             | Target  | Alert Threshold |
| ------------------------ | ----------------------- | ------- | --------------- |
| **Build Success Rate**   | % of successful builds  | >95%    | <90%            |
| **Build Duration**       | Time to complete CI     | <10 min | >15 min         |
| **Test Pass Rate**       | % of tests passing      | 100%    | <100%           |
| **Code Coverage**        | % code covered by tests | >70%    | <60%            |
| **Deployment Frequency** | Deploys per week        | >5      | <2              |

---

## Troubleshooting

### Common Issues

#### 1. Linting Failures

**Symptom:**

```
./agent/operational_agents/rag_agent/worker.py:45:80: E501 line too long (121 > 120 characters)
```

**Solution:**

```bash
# Auto-fix most issues
flake8 . --extend-ignore=E501 --max-line-length=120

# Manual fix for complex cases
# Break long lines:
result = self.process_long_function_call(
    param1="value1",
    param2="value2",
    param3="value3"
)
```

#### 2. Type Checking Failures

**Symptom:**

```
agent/utils/rate_limiter.py:123: error: Incompatible return value type (got "int", expected "float")
```

**Solution:**

```python
# Add type hints
def calculate_rate(self) -> float:
    return float(self.count / self.window)

# Or use type: ignore for complex cases
result = complex_function()  # type: ignore[return-value]
```

#### 3. Import Failures

**Symptom:**

```
ImportError: cannot import name 'TypedEnvelope' from 'agent.schemas.typed_envelope'
```

**Solution:**

```bash
# Check for circular imports
python -c "from agent.schemas.typed_envelope import TypedEnvelope"

# Verify __init__.py exports
cat agent/schemas/__init__.py

# Fix import order (import TypedEnvelope last if circular)
```

#### 4. Integration Test Failures

**Symptom:**

```
redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379. Connection refused.
```

**Solution:**

**Option 1: Start Redis locally**

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

**Option 2: Use Redis Cloud**

```bash
export REDIS_URL="redis://<REDACTED_REDIS_URL>"
pytest tests/integration/ -v
```

**Option 3: Skip integration tests**

```bash
pytest -m "not integration" -v
```

#### 5. Docker Build Failures

**Symptom:**

```
ERROR: failed to solve: failed to compute cache key: failed to calculate checksum of ref
```

**Solution:**

```bash
# Clean Docker build cache
docker builder prune -a

# Rebuild without cache
docker build --no-cache -t agentic-worker:latest .

# Check Dockerfile syntax
docker build --check -f Dockerfile .
```

#### 6. Secrets Not Available

**Symptom:**

```
Error: Secret REDIS_CLOUD_URL not found
```

**Solution:**

1. Verify secret exists in GitHub:

   - Go to: Settings â†’ Secrets and variables â†’ Actions
   - Check secret name matches exactly (case-sensitive)

2. Check workflow references correct secret:

   ```yaml
   env:
     REDIS_URL: ${{ secrets.REDIS_CLOUD_URL }} # Must match exactly
   ```

3. Verify secret scope:
   - Repository secrets: Available to all workflows
   - Environment secrets: Only available to specific environment

---

## Best Practices

### 1. Write Tests First (TDD)

```python
# 1. Write failing test
def test_rate_limiter_blocks_after_limit():
    limiter = TokenBucket(rate=10, capacity=10)
    # Exhaust capacity
    for _ in range(10):
        assert limiter.acquire() == True
    # Next should block
    assert limiter.acquire(timeout=0) == False

# 2. Implement feature
class TokenBucket:
    def acquire(self, timeout=30):
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False

# 3. Run test - should pass
pytest tests/unit/test_rate_limiter.py::test_rate_limiter_blocks_after_limit -v
```

### 2. Keep Tests Fast

```python
# âŒ Bad: Slow test with sleeps
def test_worker_processes_task():
    worker.start()
    time.sleep(5)  # Wait for worker
    result = redis.xread("results:stream")
    assert result is not None

# âœ… Good: Fast test with mocks
def test_worker_processes_task():
    with patch('redis.Redis') as mock_redis:
        mock_redis.xreadgroup.return_value = [mock_task]
        worker.process()
        assert mock_redis.xadd.called
```

### 3. Use Descriptive Test Names

```python
# âŒ Bad: Unclear what's being tested
def test_worker():
    assert worker.process() == True

# âœ… Good: Clear intent and expected outcome
def test_rag_worker_successfully_processes_search_query_and_returns_citations():
    task = create_rag_task(query="test query")
    result = worker.process(task)
    assert result.status == "success"
    assert len(result.citations) > 0
```

### 4. Test Edge Cases

```python
def test_rate_limiter_handles_edge_cases():
    limiter = TokenBucket(rate=10, capacity=10)

    # Test zero rate
    limiter.rate = 0
    assert limiter.acquire(timeout=0) == False

    # Test negative capacity
    with pytest.raises(ValueError):
        TokenBucket(rate=10, capacity=-1)

    # Test concurrent access
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(limiter.acquire) for _ in range(100)]
        results = [f.result() for f in futures]
        assert sum(results) <= 10  # Should not exceed capacity
```

### 5. Clean Up After Tests

```python
import pytest

@pytest.fixture
def redis_client():
    """Provide clean Redis client for each test."""
    client = redis.Redis(host='localhost', port=6379, decode_responses=True)
    yield client
    # Cleanup
    client.flushdb()

def test_stream_operations(redis_client):
    redis_client.xadd("test:stream", {"data": "value"})
    assert redis_client.xlen("test:stream") == 1
    # redis_client.flushdb() called automatically after test
```

### 6. Mock External Services

```python
# âŒ Bad: Calls real OpenAI API (slow, costs money, flaky)
def test_copywriter_generates_copy():
    worker = CopywriterWorker()
    result = worker.generate_copy(task)
    assert result is not None

# âœ… Good: Mocks OpenAI response
@patch('openai.ChatCompletion.create')
def test_copywriter_generates_copy(mock_openai):
    mock_openai.return_value = {"choices": [{"message": {"content": "Generated copy"}}]}
    worker = CopywriterWorker()
    result = worker.generate_copy(task)
    assert result.content == "Generated copy"
    assert mock_openai.called
```

### 7. Use Markers for Test Categories

```python
import pytest

@pytest.mark.unit
def test_token_bucket_creation():
    """Fast unit test - no external dependencies."""
    bucket = TokenBucket(rate=10, capacity=10)
    assert bucket.rate == 10

@pytest.mark.integration
def test_redis_stream_operations():
    """Integration test - requires Redis."""
    redis.xadd("stream", {"data": "value"})
    assert redis.xlen("stream") == 1

@pytest.mark.slow
@pytest.mark.llm
def test_end_to_end_copywriter_flow():
    """Slow E2E test - calls real LLM API."""
    result = run_copywriter_workflow(task)
    assert result.status == "success"
```

Run specific categories:

```bash
# Fast feedback: unit tests only (10-30 seconds)
pytest -m unit -v

# Medium feedback: unit + integration (1-2 minutes)
pytest -m "unit or integration" -v

# Full validation: all tests (5-10 minutes)
pytest -v

# Skip slow tests during development
pytest -m "not slow" -v
```

### 8. Maintain High Coverage

```bash
# Generate coverage report
pytest --cov=agent --cov-report=html

# Open in browser
start htmlcov/index.html  # Windows
open htmlcov/index.html   # Mac
xdg-open htmlcov/index.html  # Linux

# Focus on untested code
pytest --cov=agent --cov-report=term-missing

# Example output:
Name                              Stmts   Miss  Cover   Missing
---------------------------------------------------------------
agent/utils/rate_limiter.py          45      5    89%   78-82
agent/utils/secrets.py               89      0   100%
```

**Coverage Targets:**

- **Critical code:** 100% (secrets, rate limiting, envelope handling)
- **Business logic:** 80%+ (workers, orchestrators)
- **Utils/helpers:** 70%+ (logging, formatting)
- **Overall target:** 70%+

---

## Quick Reference

### Local Development Commands

```bash
# Run all tests
pytest -v

# Run specific test file
pytest tests/unit/test_rate_limiter.py -v

# Run specific test function
pytest tests/unit/test_rate_limiter.py::test_token_bucket_creation -v

# Run with coverage
pytest --cov=agent --cov-report=html -v

# Run only fast tests
pytest -m "unit" -v

# Run integration tests (requires Redis)
pytest -m "integration" -v

# Skip slow tests
pytest -m "not slow" -v

# Run linting
flake8 .

# Run type checking
mypy agent tests

# Auto-fix linting issues
autopep8 --in-place --aggressive --aggressive -r agent/
```

### CI/CD Commands

```bash
# Simulate preprod CI locally
flake8 .
mypy agent tests
pytest tests/test_imports.py -v
pytest tests/unit/ -v

# Simulate hazard CI locally
flake8 .
mypy agent tests
pytest tests/test_imports.py -v
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/smoke/ -v
docker build -t agentic-worker:test .

# Check if ready to push
git status
flake8 .
pytest -v
```

### Debugging Failed CI

```bash
# 1. Pull latest CI logs from GitHub
gh run view <run-id> --log

# 2. Reproduce locally
git checkout <failed-commit-sha>
pytest -v

# 3. Check specific failure
pytest tests/integration/test_redis_streams.py::test_xadd_operation -vv

# 4. Fix and verify
# ... make changes ...
pytest -v
git add .
git commit --amend
git push --force-with-lease
```

---

## Related Documentation

- [Monitoring Setup](./monitoring-setup.md) - Grafana dashboards and alerts
- [Rate Limiting](../../api/rate-limiting.md) - Rate limiter configuration
- [Secrets](./secrets.md) - Secrets provider setup
- [Architecture Overview](../../architecture/overview.md) - System architecture overview
- [API Reference](../../api/reference.md) - API documentation

---

## Support

**Issues:** Create a GitHub issue with:

- CI run URL
- Error message
- Steps to reproduce
- Expected vs actual behavior

**Questions:** Reach out to:

- Engineering team lead
- DevOps team
- #engineering-support Slack channel

---

**Version:** 1.0.0  
**Last Updated:** October 29, 2025  
**Maintained by:** Engineering Team


