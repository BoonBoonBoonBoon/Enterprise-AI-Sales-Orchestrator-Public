# File System Organization - Summary & Best Practices

**Quick Reference for the New Organized File System**

---

## TL;DR: The New File Organization

### What You Have Now ✅
```
tiers/              ← Three-tier agents (Manager, Orchestrators, Specialized Agents)
services/           ← Shared infrastructure (Redis, Database, Vector DB, APIs)
core/               ← Framework (Harness, Envelope, Utils, Schemas)
config/             ← Centralized configuration
deployment/         ← Docker, Kubernetes, Terraform configs
scripts/            ← Operational scripts (monitoring, maintenance, startup)
tests/              ← Test suite (unit, integration, performance)
docs/               ← Comprehensive documentation
agent/              ← LEGACY (kept for backward compatibility)
```

### Key Principles 🎯
1. **Organize by Domain** - Schemas, tests, and code live together
2. **Colocate Tests** - Tests in subdirectories next to code
3. **Clear Hierarchy** - Tiers → Services → Framework
4. **Single Responsibility** - Each directory has one clear purpose
5. **Easy Discovery** - New developers find code quickly

---

## The Three Layers

### 1️⃣ TIERS (Agent Layer)
```
Purpose: The actual agents that do work
Structure: 
  - tier_1: Manager (strategic decisions)
  - tier_2: Orchestrators (business workflows)
  - tier_3: Specialized agents (RAG, Database, Content)

Each has:
  - Core logic files
  - Schemas (domain-specific data models)
  - Tools/Operations (business logic)
  - Tests (validation)
```

**Example: RAG Agent**
```
tiers/tier_3/rag_agent/
├── rag_agent.py             # Main orchestrator
├── consumer.py              # Redis consumer
├── retrieval/               # Document retrieval module
│   ├── retriever.py
│   ├── ranking.py
│   └── tests/
├── generation/              # Response generation module
│   ├── generator.py
│   ├── prompts/
│   └── tests/
├── schemas/                 # RAG-specific data schemas
│   └── rag_schemas.py
└── tests/                   # Overall agent tests
    └── test_rag_agent.py
```

### 2️⃣ SERVICES (Infrastructure Layer)
```
Purpose: Shared, reusable services
Services:
  - redis/          → Message broker & streams
  - persistence/    → Database operations
  - vector_db/      → Vector storage & search
  - external_apis/  → Third-party integrations

Each has:
  - Main service implementation
  - Adapters (database implementations)
  - Configuration
  - Tests
```

**Example: Redis Service**
```
services/redis/
├── client.py                # Redis wrapper
├── streams.py               # Stream operations
├── pubsub.py                # Pub/sub operations
├── consumer_group.py        # Consumer management
├── health_checks.py         # Monitoring
├── config.py                # Configuration
└── tests/
    ├── test_streams.py
    ├── test_pubsub.py
    └── test_client.py
```

### 3️⃣ CORE (Framework Layer)
```
Purpose: Shared framework & utilities
Components:
  - harness/        → Agent base class & lifecycle
  - envelope/       → Message format & serialization
  - utils/          → General utilities
  - schemas/        → Shared data schemas
  - exceptions/     → Common exceptions

Each has:
  - Implementation
  - Configuration
  - Tests
  - Documentation
```

**Example: Harness (Agent Framework)**
```
core/harness/
├── agent_harness.py         # Base class
├── config.py                # Configuration
├── retry_strategies/        # Retry logic
│   ├── exponential_backoff.py
│   └── circuit_breaker.py
├── checkpointing/           # State management
│   └── recovery.py
├── observability/           # Monitoring
│   ├── metrics.py           # Prometheus metrics
│   ├── logging.py           # Structured logging
│   └── tracing.py           # Distributed tracing
└── tests/
    ├── test_harness.py
    ├── test_retry.py
    └── test_checkpointing.py
```

---

## Supporting Directories

### 📁 Configuration (`config/`)
**What goes here:** Settings, environment variables, profiles
```
config/
├── settings.py              # Main settings class
├── env.py                   # Environment variables
├── logging.py               # Logging setup
├── profiles/
│   ├── development.yaml     # Dev overrides
│   ├── staging.yaml         # Staging overrides
│   ├── production.yaml      # Prod overrides
│   └── testing.yaml         # Test overrides
└── services/
    ├── redis.yaml           # Redis config
    └── database.yaml        # Database config
```

**Why here:** Centralized, easy to manage, environment-aware

---

### 🚀 Deployment (`deployment/`)
**What goes here:** Docker, Kubernetes, Infrastructure as Code
```
deployment/
├── docker/                  # Docker configuration
│   ├── Dockerfile.worker    # Worker image
│   ├── docker-compose.yml   # Local dev
│   ├── docker-compose.prod.yml  # Production
│   └── .dockerignore
├── kubernetes/              # K8s manifests
│   ├── manager-deployment.yaml
│   ├── orchestrator-deployment.yaml
│   ├── agent-deployment.yaml
│   └── service.yaml
├── helm/                    # Helm charts
│   ├── Chart.yaml
│   └── values.yaml
└── terraform/               # Infrastructure as Code
    ├── main.tf
    ├── modules/
    └── environments/
```

**Why here:** All deployment configs in one place

---

### 📝 Scripts (`scripts/`)
**What goes here:** Operational scripts, utilities, tools
```
scripts/
├── startup/
│   ├── initialize_db.py     # DB setup
│   ├── initialize_redis.py  # Redis setup
│   └── seed_data.py         # Initial data
├── monitoring/
│   ├── health_check.py      # System health
│   ├── redis_health.py      # Redis monitoring
│   └── streams_health.py    # Streams monitoring
├── maintenance/
│   ├── cleanup_old_streams.py
│   ├── reset_consumer_groups.py
│   └── backup_database.py
└── development/
    ├── setup_dev_env.py     # Dev environment
    ├── load_test.py         # Load testing
    └── debug_flows.py       # Debugging
```

**Why here:** Separate from core code, easy to find

---

### 🧪 Tests (`tests/`)
**What goes here:** Test files (also colocated in source)
```
tests/
├── conftest.py              # Pytest configuration
├── fixtures/                # Test fixtures
│   ├── mock_data.py
│   ├── redis_fixtures.py
│   └── database_fixtures.py
├── integration/             # Integration tests
│   ├── test_tier_integration.py
│   ├── test_delegation_flow.py
│   └── test_end_to_end.py
├── unit/                    # Unit tests organized by component
│   ├── tier_1/
│   ├── tier_2/
│   ├── tier_3/
│   ├── core/
│   └── services/
└── performance/             # Performance tests
    ├── test_throughput.py
    └── test_latency.py
```

**Why here:** Main test location, but also colocated tests in source

---

### 📚 Documentation (`docs/`)
**What goes here:** All documentation
```
docs/
├── QUICK_REFERENCE.md       # Quick start (start here!)
├── ARCHITECTURE.md          # System architecture
├── MIGRATION.md             # Migration guide
├── guides/
│   ├── getting_started.md
│   ├── development.md
│   ├── deployment.md
│   └── troubleshooting.md
├── api/
│   ├── manager_api.md
│   ├── orchestrator_api.md
│   ├── agent_api.md
│   └── services_api.md
├── operations/
│   ├── monitoring.md
│   ├── logging.md
│   └── metrics.md
└── project/
    ├── completion_report.md
    └── roadmap.md
```

**Why here:** Centralized documentation, easy to find

---

## Best Practices for Organization

### ✅ DO's

1. **✅ Keep related code together**
   ```
   Good: tier_3/rag_agent/retrieval/ (all retrieval logic)
   Bad:  tier_3/rag_agent/retrieval.py (mixed with main)
   ```

2. **✅ Colocate tests with code**
   ```
   Good: tiers/tier_3/rag_agent/retrieval/tests/
   Bad:  tests/unit/tier_3/rag/test_retrieval.py
   ```

3. **✅ Use subdirectories for domain concepts**
   ```
   Good: tier_3/rag_agent/retrieval/, generation/, prompts/
   Bad:  tier_3/rag_agent/retrieval.py, generation.py, prompts.py
   ```

4. **✅ Keep configuration centralized**
   ```
   Good: config/profiles/production.yaml
   Bad:  tiers/tier_1/manager/config.yaml
   ```

5. **✅ Group similar services**
   ```
   Good: services/external_apis/crunchbase/, linkedin/
   Bad:  services/crunchbase/, services/linkedin/
   ```

---

### ❌ DON'Ts

1. **❌ Don't scatter related code**
   ```
   Bad:  rag_logic.py in tier_3, retrieval.py in services/
   Good: All RAG logic in tier_3/rag_agent/
   ```

2. **❌ Don't hide tests far from code**
   ```
   Bad:  tests/unit/tier_3/rag/subfolder/test_retrieval.py
   Good: tier_3/rag_agent/retrieval/tests/test_retrieval.py
   ```

3. **❌ Don't create one file per concept if related**
   ```
   Bad:  Many small files scattered
   Good: Related concepts in organized subdirectories
   ```

4. **❌ Don't mix configuration with code**
   ```
   Bad:  Config hardcoded in tiers/tier_3/
   Good: Config in config/ with environment overrides
   ```

5. **❌ Don't put everything at the root level**
   ```
   Bad:  tier1.py, tier2.py, tier3.py at root
   Good: Organized hierarchy in tiers/
   ```

---

## Import Patterns

### From a Tier (e.g., Manager importing Orchestrators)
```python
# ✅ Good: Tier → Tier via defined interface
from tiers.tier_2.leads_orchestrator import LeadsOrchestrator
from tiers.tier_2.outreach_orchestrator import OutreachOrchestrator

# ✅ Good: Use from services
from services.redis import RedisPubSub
from services.persistence import PersistenceService

# ✅ Good: Use from core
from core.harness import AgentHarness
from core.envelope import Envelope
from core.utils import rate_limiter

# ❌ Bad: Circular imports
# Don't import from tier_1 inside tier_3
```

### From a Service (e.g., Redis)
```python
# ✅ Good: Service is reusable
from services.redis import RedisPubSub
from services.redis.streams import StreamClient

# ✅ Good: Import from core utilities
from core.utils import caching

# ❌ Bad: Services shouldn't import from tiers
# Tiers use services, not the other way around
```

### From Core Framework
```python
# ✅ Good: Framework is widely imported
from core.harness import AgentHarness
from core.envelope import Envelope, Priority
from core.schemas import LeadSchema
from core.utils import rate_limiter

# ✅ Good: Everyone can use framework
# It's infrastructure, not business logic
```

---

## Directory Size Guidelines

| Directory | Typical Size | Purpose |
|-----------|--------------|---------|
| `tier_1/manager/` | 10-20 files | Single agent |
| `tier_2/leads_orchestrator/` | 20-30 files | Complex workflows |
| `tier_3/rag_agent/` | 25-35 files | Multi-module agent |
| `services/redis/` | 10-15 files | Single service |
| `core/harness/` | 15-25 files | Framework component |
| `config/` | 10-15 files | All configuration |
| `deployment/` | 15-30 files | IaC + containers |
| `scripts/` | 20-30 files | Utilities + tools |
| `tests/` | 30-50 files | Test coverage |
| `docs/` | 20-30 files | Documentation |

**Total: ~200-300 files, well-organized** ✅

---

## Adding a New Agent

### Template for New Tier 3 Agent
```
tiers/tier_3/new_agent/
├── __init__.py
├── new_agent.py               # Main logic
├── new_agent_harness.py       # Runner
├── consumer.py                # Redis consumer
├── worker.py                  # Worker process
│
├── core_module/               # Primary functionality
│   ├── __init__.py
│   ├── main_logic.py
│   └── tests/
│       └── test_main_logic.py
│
├── schemas/                   # Data schemas
│   ├── __init__.py
│   └── new_agent_schemas.py
│
└── tests/                     # Agent-level tests
    ├── test_new_agent.py
    └── fixtures.py
```

### Template for New Service
```
services/new_service/
├── __init__.py
├── service.py                 # Main service
├── config.py                  # Configuration
├── exceptions.py              # Service exceptions
│
├── adapters/                  # Implementations
│   ├── __init__.py
│   ├── adapter_1.py
│   └── adapter_2.py
│
└── tests/
    ├── test_service.py
    ├── test_adapter_1.py
    └── test_adapter_2.py
```

---

## File Naming Conventions

### Module Names (files)
```
✅ descriptor_action.py           (e.g., redis_health.py)
✅ descriptive_name.py            (e.g., rate_limiter.py)
✅ PascalCase_modules.py          (e.g., RAGAgent.py - rarely)

❌ file1.py, module.py            (too generic)
❌ mixedCaseFiles.py              (inconsistent)
```

### Class Names
```
✅ PascalCase                     (e.g., RedisPubSub, RAGAgent)
✅ Descriptive                    (e.g., StreamClient, QueryBuilder)

❌ lower_case_classes            (Python uses PascalCase for classes)
```

### Variable Names
```
✅ snake_case                     (e.g., redis_client, stream_name)
✅ descriptive                    (e.g., consumer_group, cache_ttl)

❌ camelCase                      (Python uses snake_case)
```

---

## Quick Reference: Where Things Go

| Type | Location | Example |
|------|----------|---------|
| Agent logic | `tiers/tier_X/agent/agent.py` | `tiers/tier_3/rag_agent/rag_agent.py` |
| Agent schemas | `tiers/tier_X/agent/schemas/` | `tiers/tier_3/rag_agent/schemas/rag_schemas.py` |
| Agent tests | `tiers/tier_X/agent/tests/` | `tiers/tier_3/rag_agent/tests/test_rag_agent.py` |
| Domain logic | `tiers/tier_X/agent/domain/` | `tiers/tier_3/rag_agent/retrieval/retriever.py` |
| Service logic | `services/service_name/` | `services/redis/client.py` |
| Service tests | `services/service_name/tests/` | `services/redis/tests/test_client.py` |
| Framework | `core/framework/` | `core/harness/agent_harness.py` |
| Config | `config/` | `config/settings.py` |
| Scripts | `scripts/category/` | `scripts/monitoring/health_check.py` |
| Tests | `tests/` + colocated | `tests/integration/test_flow.py` |
| Docs | `docs/` | `docs/guides/deployment.md` |

---

## Summary: Organization Principles

### 1. **Clear Hierarchy**
```
Tiers (agents) → Services (infrastructure) → Core (framework)
                        ↓
                  Config, Deployment, Scripts
```

### 2. **Logical Grouping**
- Related code lives together
- Easy to find and maintain
- Clear ownership

### 3. **Colocated Tests**
- Tests near code they test
- Easy to run specific tests
- Obvious coverage

### 4. **Domain-Driven**
- Organized by business concepts
- Not by technical type
- Easier for new developers

### 5. **Single Responsibility**
- Each directory has clear purpose
- Minimal cross-directory dependencies
- Easy to scale

---

## Current Status ✅

Your file system is **well-organized and production-ready**:
- ✅ Clear hierarchy (tiers → services → core)
- ✅ Logical organization (by domain)
- ✅ Comprehensive testing
- ✅ Centralized configuration
- ✅ Complete documentation
- ✅ Easy to extend
- ✅ DevOps-ready (Docker, K8s, Terraform)

**Next optional steps (Q1-Q2 2026):**
- Extract tier-specific schemas for even better organization
- Consolidate utilities in `core/utils/`
- Add domain-specific subdirectories
- Eventually remove legacy `agent/` directory

**Recommendation:** Current structure is optimal. Future improvements are optional and can be done incrementally. 🚀

---

**Last Updated:** November 8, 2025  
**Version:** 1.0  
**Status:** ✅ Production Ready & Well Organized
