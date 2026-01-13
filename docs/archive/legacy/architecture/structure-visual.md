# Agentic System - Visual File Structure

## Overview: Current vs. Proposed

### Current Organization (Simplified)
```
agentic-system/
├── tiers/                          ✅ Three-tier architecture
│   ├── tier_1/manager/             ✅ Manager agent
│   ├── tier_2/leads_orchestrator/  ✅ Leads workflow
│   ├── tier_2/outreach_orchestrator/ ✅ Outreach workflow
│   └── tier_3/                     ✅ RAG, Persistence, Copywriter
├── services/                       ✅ Shared services
│   ├── redis/                      ✅ Redis pub/sub
│   ├── persistence/                ✅ Database
│   ├── vector_db/                  ✅ Vector DB
│   └── external_apis/              ✅ External APIs
├── core/                           ✅ Framework
│   ├── harness/                    ✅ Agent harness
│   ├── envelope/                   ✅ Messaging
│   └── deep_agents/                ✅ Utilities
├── agent/                          ⚠️  LEGACY (retained for compatibility)
├── config/                         ⚠️  Config files
├── deployment/                     ⚠️  Docker, K8s, Terraform
├── scripts/                        ✅ Operational scripts
├── tests/                          ✅ Test suite
├── docs/                           ✅ Documentation
└── README.md, pyproject.toml, etc.
```

---

## Detailed View: Tier Organization

### TIER 1: Manager (Strategic)
```
tiers/tier_1/manager/
├── __init__.py
├── manager_agent.py              # Core logic
├── manager_agent_harness.py       # Runner
├── consumer.py                    # Redis consumer
├── tools/
│   ├── __init__.py
│   ├── delegation_tools.py        # Send to tier 2
│   └── validation.py
├── schemas/
│   ├── __init__.py
│   └── manager_schemas.py
└── tests/
    ├── test_manager_agent.py
    ├── test_delegation.py
    └── fixtures.py
```

### TIER 2: Orchestrators (Business Logic)
```
tiers/tier_2/
├── leads_orchestrator/
│   ├── __init__.py
│   ├── leads_orchestrator.py      # Core workflow
│   ├── leads_orchestrator_harness.py
│   ├── consumer.py
│   ├── workflows/                 # Business logic
│   │   ├── lead_enrichment.py
│   │   ├── lead_qualification.py
│   │   └── base_workflow.py
│   ├── schemas/
│   │   └── leads_schemas.py
│   └── tests/
│       ├── test_leads_orchestrator.py
│       └── test_workflows.py
│
└── outreach_orchestrator/
    ├── __init__.py
    ├── outreach_orchestrator.py   # Core workflow
    ├── consumer.py
    ├── workflows/                 # Campaign logic
    │   ├── campaign_management.py
    │   ├── sequence_execution.py
    │   └── base_workflow.py
    ├── schemas/
    │   └── outreach_schemas.py
    └── tests/
        ├── test_outreach_orchestrator.py
        └── test_workflows.py
```

### TIER 3: Specialized Agents (Execution)
```
tiers/tier_3/
├── rag_agent/                     # Research & Retrieval
│   ├── __init__.py
│   ├── rag_agent.py               # Core logic
│   ├── consumer.py
│   ├── worker.py
│   ├── retrieval/                 # Document retrieval
│   │   ├── retriever.py
│   │   ├── ranking.py
│   │   └── filters.py
│   ├── generation/                # Response generation
│   │   ├── generator.py
│   │   └── prompts/               # Prompt templates
│   ├── schemas/
│   │   └── rag_schemas.py
│   └── tests/
│       ├── test_rag_agent.py
│       ├── test_retrieval.py
│       └── test_generation.py
│
├── persistence_agent/             # Database Operations
│   ├── __init__.py
│   ├── persistence_agent.py       # Core logic
│   ├── consumer.py
│   ├── write_worker.py            # Write process
│   ├── read_worker.py             # Read process
│   ├── operations/                # CRUD operations
│   │   ├── read_ops.py
│   │   ├── write_ops.py
│   │   └── batch_ops.py
│   ├── schemas/
│   │   └── persistence_schemas.py
│   └── tests/
│       ├── test_persistence_agent.py
│       ├── test_read_ops.py
│       └── test_write_ops.py
│
└── copywriter_agent/              # Content Generation
    ├── __init__.py
    ├── copywriter.py              # Core logic
    ├── consumer.py
    ├── worker.py
    ├── content/                   # Content generation
    │   ├── generator.py
    │   ├── templates/             # Email, LinkedIn, etc.
    │   │   ├── email_templates.py
    │   │   ├── linkedin_templates.py
    │   │   └── custom_templates.py
    │   └── variants.py            # A/B variants
    ├── quality/                   # Quality control
    │   ├── validator.py           # Validation
    │   └── scorer.py              # Quality scoring
    ├── schemas/
    │   └── copywriter_schemas.py
    └── tests/
        ├── test_copywriter.py
        ├── test_content_gen.py
        └── test_quality.py
```

---

## Services Layer (Shared Infrastructure)

```
services/
├── persistence/                   # Database Service
│   ├── service.py                 # Main API
│   ├── adapters/
│   │   ├── supabase_adapter.py    # Supabase impl
│   │   └── in_memory_adapter.py   # In-memory
│   ├── models/                    # Data models
│   │   ├── lead.py
│   │   ├── campaign.py
│   │   └── interaction.py
│   ├── queries/                   # Query builders
│   │   ├── lead_queries.py
│   │   └── campaign_queries.py
│   └── tests/
│       ├── test_service.py
│       └── test_adapters.py
│
├── redis/                         # Redis Service
│   ├── client.py                  # Wrapper
│   ├── pubsub.py                  # Pub/sub
│   ├── streams.py                 # Streams
│   ├── consumer_group.py          # Consumer groups
│   ├── health_checks.py           # Monitoring
│   └── tests/
│       ├── test_streams.py
│       └── test_pubsub.py
│
├── vector_db/                     # Vector Database
│   ├── client.py                  # Client
│   ├── embeddings.py              # Embedding gen
│   ├── search.py                  # Search impl
│   └── tests/
│       ├── test_embeddings.py
│       └── test_search.py
│
└── external_apis/                 # External APIs
    ├── crunchbase/
    │   ├── client.py
    │   ├── schema.py
    │   └── rate_limiter.py
    └── linkedin/
        ├── client.py
        ├── schema.py
        └── auth.py
```

---

## Core Framework

```
core/
├── harness/                       # Agent Harness
│   ├── agent_harness.py           # Base class
│   ├── config.py                  # Configuration
│   ├── interfaces.py              # Abstract interfaces
│   ├── retry_strategies/          # Retry logic
│   │   ├── exponential_backoff.py
│   │   ├── jitter.py
│   │   └── circuit_breaker.py
│   ├── checkpointing/             # State management
│   │   ├── checkpoint.py
│   │   └── recovery.py
│   ├── observability/             # Monitoring
│   │   ├── metrics.py             # Prometheus metrics
│   │   ├── logging.py             # Structured logs
│   │   └── tracing.py             # Distributed tracing
│   └── tests/
│       ├── test_harness.py
│       ├── test_retry.py
│       └── test_checkpointing.py
│
├── envelope/                      # Message System
│   ├── envelope.py                # Base envelope
│   ├── typed_envelope.py          # Typed version
│   ├── serialization.py           # Serialization
│   ├── validation.py              # Validation
│   └── tests/
│       ├── test_envelope.py
│       └── test_serialization.py
│
├── utils/                         # Shared Utilities
│   ├── ab_testing.py              # A/B testing
│   ├── rate_limiter.py            # Rate limiting
│   ├── secrets.py                 # Secrets mgmt
│   ├── workflow_progress.py       # Workflow tracking
│   ├── caching.py                 # Caching
│   └── mock_data.py               # Test data
│
├── schemas/                       # Shared Schemas
│   ├── base.py                    # Base classes
│   ├── config.py                  # Config schemas
│   ├── lead.py                    # Lead schemas
│   ├── campaign.py                # Campaign schemas
│   └── validation.py              # Validators
│
├── exceptions/                    # Exceptions
│   ├── agent_exceptions.py
│   ├── service_exceptions.py
│   └── validation_exceptions.py
│
└── deep_agents/                   # Deep Agent Utils
    ├── capabilities.py
    └── factories.py
```

---

## Configuration

```
config/
├── settings.py                    # Main settings
├── env.py                         # Environment vars
├── logging.py                     # Logging config
├── redis.yaml                     # Redis config
├── database.yaml                  # DB config
└── profiles/
    ├── development.yaml           # Dev settings
    ├── staging.yaml               # Staging settings
    ├── production.yaml            # Prod settings
    └── testing.yaml               # Test settings
```

**Example settings.py:**
```python
from enum import Enum
from pathlib import Path

class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"

class Settings:
    ENV: Environment = Environment.DEVELOPMENT
    DEBUG: bool = ENV == Environment.DEVELOPMENT
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    DATABASE_URL: str = "postgresql://localhost/agentic"
    LOG_LEVEL: str = "DEBUG"
```

---

## Deployment

```
deployment/
├── docker/
│   ├── Dockerfile.worker          # Worker image
│   ├── docker-compose.yml         # All services
│   ├── docker-compose.dev.yml     # Dev overrides
│   └── docker-compose.prod.yml    # Prod overrides
│
├── kubernetes/
│   ├── namespace.yaml             # K8s namespace
│   ├── manager-deployment.yaml    # Manager deployment
│   ├── orchestrator-deployment.yaml
│   ├── agent-deployment.yaml      # Agent deployments
│   ├── service.yaml               # K8s service
│   └── configmap.yaml             # Config mapping
│
├── helm/
│   ├── Chart.yaml
│   ├── values.yaml                # Default values
│   ├── values-dev.yaml            # Dev values
│   ├── values-prod.yaml           # Prod values
│   └── templates/
│       ├── deployment.yaml
│       └── service.yaml
│
└── terraform/
    ├── main.tf                    # Main infrastructure
    ├── variables.tf               # Variables
    ├── modules/
    │   ├── redis/                 # Redis module
    │   ├── database/              # DB module
    │   ├── kubernetes/            # K8s module
    │   └── networking/            # Network module
    └── environments/
        ├── dev.tfvars
        ├── staging.tfvars
        └── prod.tfvars
```

---

## Scripts Organization

```
scripts/
├── startup/
│   ├── initialize_db.py           # DB initialization
│   ├── initialize_redis.py        # Redis setup
│   └── seed_data.py               # Initial data
│
├── monitoring/
│   ├── health_check.py            # System health
│   ├── redis_health.py            # Redis health
│   ├── streams_health.py          # Stream monitoring
│   ├── performance_monitor.py     # Performance metrics
│   └── alert_system.py            # Alerting
│
├── maintenance/
│   ├── cleanup_old_streams.py     # Stream cleanup
│   ├── reset_consumer_groups.py   # Consumer reset
│   ├── rebuild_indexes.py         # Index rebuild
│   ├── backup_database.py         # Backups
│   └── migrate_data.py            # Data migration
│
├── development/
│   ├── setup_dev_env.py           # Dev setup
│   ├── generate_sample_data.py    # Sample data
│   ├── load_test.py               # Load testing
│   └── debug_flows.py             # Debug utilities
│
├── smoke_test_three_tier.py       # E2E smoke test
├── run_agent.py                   # Main entry point
└── utils.py                       # Script utilities
```

---

## Testing

```
tests/
├── conftest.py                    # Pytest configuration
├── fixtures/
│   ├── mock_data.py               # Mock data
│   ├── redis_fixtures.py          # Redis test fixtures
│   ├── database_fixtures.py       # DB fixtures
│   └── agent_fixtures.py          # Agent fixtures
│
├── integration/                   # Integration tests
│   ├── test_tier_integration.py   # Tier integration
│   ├── test_delegation_flow.py    # Delegation flow
│   ├── test_end_to_end.py         # E2E tests
│   └── test_error_handling.py     # Error handling
│
├── unit/                          # Unit tests
│   ├── tier_1/
│   │   ├── test_manager.py
│   │   └── test_delegation_tools.py
│   ├── tier_2/
│   │   ├── test_leads_orchestrator.py
│   │   └── test_outreach_orchestrator.py
│   ├── tier_3/
│   │   ├── test_rag_agent.py
│   │   ├── test_persistence_agent.py
│   │   └── test_copywriter_agent.py
│   ├── core/
│   │   ├── test_harness.py
│   │   └── test_envelope.py
│   └── services/
│       ├── test_persistence.py
│       ├── test_redis.py
│       └── test_vector_db.py
│
└── performance/                   # Performance tests
    ├── test_throughput.py         # Throughput
    ├── test_latency.py            # Latency
    └── test_resource_usage.py     # Resources
```

---

## Documentation

```
docs/
├── QUICK_REFERENCE.md             # Quick start
├── ARCHITECTURE.md                # Architecture
├── MIGRATION.md                   # Migration guide
│
├── guides/
│   ├── getting_started.md
│   ├── development.md
│   ├── deployment.md
│   ├── troubleshooting.md
│   └── faq.md
│
├── api/
│   ├── manager_api.md
│   ├── orchestrator_api.md
│   ├── agent_api.md
│   └── services_api.md
│
├── architecture/
│   ├── three_tier_model.md
│   ├── message_flow.md
│   ├── redis_streams.md
│   └── scalability.md
│
├── operations/
│   ├── monitoring.md
│   ├── logging.md
│   ├── metrics.md
│   └── maintenance.md
│
└── project/
    ├── completion_report.md
    ├── changelog.md
    └── roadmap.md
```

---

## Root Level Files

```
Project Root/
├── .env.example                   # Template
├── .env.test                      # Test env
├── .gitignore                     # Git ignore
├── .github/
│   ├── workflows/
│   │   ├── tests.yml
│   │   ├── build.yml
│   │   └── deploy.yml
│   └── ISSUE_TEMPLATE/
│
├── pyproject.toml                 # Project config
├── requirements.txt               # Production deps
├── requirements-dev.txt           # Dev deps
├── setup.py                       # Setup script
├── pytest.ini                     # Pytest config
├── mypy.ini                       # Type checking
├── .pylintrc                      # Linting
├── .black                         # Code formatting
├── Makefile                       # Common commands
├── README.md                      # Main README
├── LICENSE                        # License
└── CHANGELOG.md                   # Changes
```

---

## Import Examples by Location

### From Tier 1 (Manager)
```python
# Import from tier 2 (delegation)
from tiers.tier_2.leads_orchestrator import LeadsOrchestrator
from tiers.tier_2.outreach_orchestrator import OutreachOrchestrator

# Import from services
from services.redis import RedisPubSub
from services.persistence import PersistenceService

# Import from core
from core.harness import AgentHarness
from core.envelope import Envelope
from core.utils import rate_limiter
```

### From Tier 2 (Orchestrators)
```python
# Import from tier 3 (delegation)
from tiers.tier_3.rag_agent import RAGAgent
from tiers.tier_3.persistence_agent import PersistenceAgent
from tiers.tier_3.copywriter_agent import CopywriterAgent

# Import from services
from services.redis import RedisPubSub
from services.persistence import PersistenceService

# Import from core
from core.harness import AgentHarness
from core.schemas import LeadSchema
```

### From Tier 3 (Agents)
```python
# Import from services
from services.redis import RedisPubSub
from services.persistence import PersistenceService
from services.vector_db import VectorDBClient

# Import from core
from core.harness import AgentHarness
from core.utils import caching, rate_limiter
from core.exceptions import ServiceException
```

---

## Size Metrics

| Component | Files | Approx Size | Complexity |
|-----------|-------|-------------|-----------|
| Tier 1 Manager | 10 | Small | Low |
| Tier 2 Leads | 15 | Medium | Medium |
| Tier 2 Outreach | 15 | Medium | Medium |
| Tier 3 RAG | 18 | Medium | High |
| Tier 3 Persistence | 16 | Medium | Medium |
| Tier 3 Copywriter | 15 | Medium | Medium |
| Services Layer | 60 | Large | Medium |
| Core Framework | 40 | Large | High |
| Tests | 40 | Large | Medium |
| Docs | 25 | Large | Low |

**Total**: ~250 files, well-organized and maintainable

---

## Key Statistics

✅ **Well-Organized:**
- 3 tiers + 5 specialized agents
- 4 core services
- Comprehensive testing
- Clear separation of concerns

✅ **Scalable:**
- Easy to add new agents
- Services independent
- Clear dependency tree
- Horizontal scaling ready

✅ **Maintainable:**
- Logical file hierarchy
- Colocated tests
- Consistent patterns
- Clear documentation

✅ **DevOps-Friendly:**
- IaC (Terraform, Helm, K8s)
- Docker containerized
- Environment-specific configs
- Monitoring integrated

---

## Transition Timeline

**Today (Nov 2025):**
✅ Three-tier core + services implemented
✅ Backward compatibility maintained
✅ All tests passing

**Q1 2026:**
- Optional: Extract tier-specific schemas
- Optional: Move utilities to core/utils/
- Optional: Add domain-specific subdirectories

**Q2 2026:**
- Optional: Full cleanup (remove legacy paths)
- Enhanced observability
- Performance optimizations

**Status:** Production-ready now, optimization optional later! 🚀

---

**Last Updated:** November 8, 2025  
**Current Status:** ✅ Optimized and Production Ready  
**File Complexity:** Well-organized and maintainable
