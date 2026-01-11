# GitHub Actions CI/CD Pipeline

## Overview

This folder contains automated testing and deployment workflows for the Agentic System.

## Workflows

### 1. Pre-Production Pipeline (`ci-preprod.yml`)

**Purpose:** Fast feedback loop for code quality

**Triggers:**
- Push to `preprod` branch
- Pull requests to `preprod`
- Manual dispatch

**Checks:**
- ✅ Code linting (flake8)
- ✅ Type checking (mypy)
- ✅ Import smoke tests
- ✅ Unit tests (fast, no external deps)
- ✅ Coverage reporting (60% threshold)

**Duration:** ~3-5 minutes

**Status Badge:**
```markdown
[![CI - Pre-Production](https://github.com/BoonBoonBoonBoon/Agentic-System/actions/workflows/ci-preprod.yml/badge.svg?branch=preprod)](https://github.com/BoonBoonBoonBoon/Agentic-System/actions/workflows/ci-preprod.yml)
```

---

### 2. Production Pipeline (`ci-hazard.yml`)

**Purpose:** Comprehensive validation before production

**Triggers:**
- Push to `hazard` branch
- Pull requests to `hazard`
- Manual dispatch

**Jobs:**
1. **Pre-production checks** - All preprod checks
2. **Integration tests** - Redis streams, worker lifecycle, E2E workflows
3. **Docker build** - Validate all worker images build successfully

**Checks:**
- ✅ All pre-production checks
- ✅ Integration tests with Redis
- ✅ Smoke tests (health checks)
- ✅ Redis Cloud validation (optional)
- ✅ Docker image builds

**Duration:** ~8-12 minutes

**Status Badge:**
```markdown
[![CI - Production](https://github.com/BoonBoonBoonBoon/Agentic-System/actions/workflows/ci-hazard.yml/badge.svg?branch=hazard)](https://github.com/BoonBoonBoonBoon/Agentic-System/actions/workflows/ci-hazard.yml)
```

---

## Required Secrets

Configure in: **Settings → Secrets and variables → Actions**

| Secret | Required For | Description |
|--------|--------------|-------------|
| `REDIS_CLOUD_URL` | ci-hazard.yml | Redis Cloud connection URL for integration tests |
| `OPENAI_API_KEY` | ci-hazard.yml (optional) | OpenAI API key for LLM tests |
| `ANTHROPIC_API_KEY` | ci-hazard.yml (optional) | Anthropic API key for LLM tests |
| `CODECOV_TOKEN` | ci-preprod.yml (optional) | Codecov.io integration token |

---

## Local Testing

Simulate CI pipeline locally before pushing:

### Pre-production checks
```bash
# Linting
flake8 .

# Type checking
mypy agent tests

# Import tests
pytest tests/test_imports.py -v

# Unit tests
pytest tests/unit/ -v -m unit
```

### Production checks
```bash
# All pre-production checks plus:

# Integration tests (requires Redis)
docker run -d -p 6379:6379 redis:7-alpine
pytest tests/integration/ -v -m integration

# Smoke tests
pytest tests/smoke/ -v -m smoke

# Docker builds
docker build -f agent/operational_agents/rag_agent/Dockerfile -t rag-worker:test .
```

---

## Configuration Files

Test and linting configuration:

- **pytest.ini** - Test discovery, coverage, markers
- **.flake8** - Linting rules, complexity threshold
- **mypy.ini** - Type checking strictness, module ignores

---

## Troubleshooting

### Workflow fails on linting
```bash
# Run locally to see errors
flake8 . --show-source --statistics

# Auto-fix most issues
autopep8 --in-place --aggressive --aggressive -r agent/
```

### Workflow fails on type checking
```bash
# Run locally
mypy agent tests

# Add type hints or use type: ignore
result = function()  # type: ignore[return-value]
```

### Workflow fails on integration tests
```bash
# Check Redis connectivity
docker ps | grep redis
python -c "import redis; redis.Redis(host='localhost').ping()"

# Run specific test
pytest tests/integration/test_redis_streams.py::test_xadd_creates_message -vv
```

### Workflow doesn't trigger
- Verify branch name matches trigger (preprod/hazard)
- Check if workflows are disabled in repository settings
- Verify .github/workflows/*.yml files are committed

---

## Documentation

Full documentation: **[docs/CI_CD_SETUP.md](../docs/CI_CD_SETUP.md)**

Covers:
- Architecture and pipeline design
- Test strategy (unit, integration, smoke)
- Branch protection rules
- Deployment environments
- Monitoring and alerts
- Best practices

---

## Quick Links

- [CI/CD Setup Guide](../docs/CI_CD_SETUP.md)
- [Test Documentation](../tests/README.md)
- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [Pytest Documentation](https://docs.pytest.org/)

---

**Status:** ✅ Production Ready (October 29, 2025)
