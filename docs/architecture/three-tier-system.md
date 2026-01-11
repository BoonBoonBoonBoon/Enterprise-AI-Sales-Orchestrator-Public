# Optimized File System Architecture

**Date:** November 8, 2025  
**Current Status:** Three-tier architecture implemented with legacy backward compatibility  
**Goal:** Maximize organization and developer experience

---

## Current State vs. Proposed Organization

### Current State Summary
```
✅ Three-tier core implemented (tiers/, services/, core/)
⚠️  Some utilities still scattered (agent/utils/)
⚠️  Schemas in legacy location (agent/schemas/)
⚠️  Infrastructure duplicated (agent/Infastructure/)
⚠️  Tools partially organized (agent/tools/)
```

---

## Proposed Optimized Structure

```
agentic-system/
│
├── 📁 tiers/                          # Three-tier agent hierarchy
│   ├── tier_1/                        # Strategic layer
│   │   └── manager/
│   │       ├── __init__.py
│   │       ├── manager_agent.py       # Core manager logic
│   │       ├── manager_agent_harness.py
│   │       ├── consumer.py            # Redis stream consumer
│   │       ├── tools/
│   │       │   ├── __init__.py
│   │       │   ├── delegation_tools.py  # Tier delegation
│   │       │   └── validation.py      # Input validation
│   │       ├── schemas/
│   │       │   ├── __init__.py
│   │       │   └── manager_schemas.py # Manager-specific schemas
│   │       └── tests/
│   │           ├── __init__.py
│   │           ├── test_manager_agent.py
│   │           ├── test_delegation.py
│   │           └── fixtures.py
│   │
│   ├── tier_2/                        # Business logic layer
│   │   ├── leads_orchestrator/
│   │   │   ├── __init__.py
│   │   │   ├── leads_orchestrator.py
│   │   │   ├── leads_orchestrator_harness.py
│   │   │   ├── consumer.py
│   │   │   ├── workflows/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── lead_enrichment.py
│   │   │   │   ├── lead_qualification.py
│   │   │   │   └── base_workflow.py
│   │   │   ├── schemas/
│   │   │   │   ├── __init__.py
│   │   │   │   └── leads_schemas.py
│   │   │   └── tests/
│   │   │       ├── test_leads_orchestrator.py
│   │   │       └── test_workflows.py
│   │   │
│   │   └── outreach_orchestrator/
│   │       ├── __init__.py
│   │       ├── outreach_orchestrator.py
│   │       ├── outreach_orchestrator_harness.py
│   │       ├── consumer.py
│   │       ├── workflows/
│   │       │   ├── __init__.py
│   │       │   ├── campaign_management.py
│   │       │   ├── sequence_execution.py
│   │       │   └── base_workflow.py
│   │       ├── schemas/
│   │       │   ├── __init__.py
│   │       │   └── outreach_schemas.py
│   │       └── tests/
│   │           ├── test_outreach_orchestrator.py
│   │           └── test_workflows.py
│   │
│   ├── tier_3/                        # Execution layer
│   │   ├── rag_agent/
│   │   │   ├── __init__.py
│   │   │   ├── rag_agent.py           # Core RAG logic
│   │   │   ├── rag_agent_harness.py
│   │   │   ├── consumer.py
│   │   │   ├── worker.py              # Worker process
│   │   │   ├── retrieval/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── retriever.py       # Document retrieval
│   │   │   │   ├── ranking.py         # Result ranking
│   │   │   │   └── filters.py         # Query filters
│   │   │   ├── generation/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── generator.py       # Response generation
│   │   │   │   └── prompts/
│   │   │   │       ├── __init__.py
│   │   │   │       ├── base_prompt.py
│   │   │   │       └── templates.md
│   │   │   ├── schemas/
│   │   │   │   ├── __init__.py
│   │   │   │   └── rag_schemas.py
│   │   │   └── tests/
│   │   │       ├── test_rag_agent.py
│   │   │       ├── test_retrieval.py
│   │   │       └── test_generation.py
│   │   │
│   │   ├── persistence_agent/
│   │   │   ├── __init__.py
│   │   │   ├── persistence_agent.py   # Core persistence logic
│   │   │   ├── persistence_agent_harness.py
│   │   │   ├── consumer.py
│   │   │   ├── write_worker.py        # Write worker process
│   │   │   ├── read_worker.py         # Read worker process
│   │   │   ├── operations/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── read_ops.py        # Read operations
│   │   │   │   ├── write_ops.py       # Write operations
│   │   │   │   └── batch_ops.py       # Batch operations
│   │   │   ├── schemas/
│   │   │   │   ├── __init__.py
│   │   │   │   └── persistence_schemas.py
│   │   │   └── tests/
│   │   │       ├── test_persistence_agent.py
│   │   │       ├── test_read_ops.py
│   │   │       └── test_write_ops.py
│   │   │
│   │   └── copywriter_agent/
│   │       ├── __init__.py
│   │       ├── copywriter.py          # Core copywriter logic
│   │       ├── copywriter_agent_harness.py
│   │       ├── consumer.py
│   │       ├── worker.py
│   │       ├── content/
│   │       │   ├── __init__.py
│   │       │   ├── generator.py       # Content generation
│   │       │   ├── templates/
│   │       │   │   ├── __init__.py
│   │       │   │   ├── email_templates.py
│   │       │   │   ├── linkedin_templates.py
│   │       │   │   └── custom_templates.py
│   │       │   └── variants.py        # A/B variants
│   │       ├── quality/
│   │       │   ├── __init__.py
│   │       │   ├── validator.py       # Content validation
│   │       │   └── scorer.py          # Quality scoring
│   │       ├── schemas/
│   │       │   ├── __init__.py
│   │       │   └── copywriter_schemas.py
│   │       └── tests/
│   │           ├── test_copywriter.py
│   │           ├── test_content_gen.py
│   │           └── test_quality.py
│   │
│   └── __init__.py
│
├── 📁 core/                           # Core framework
│   ├── __init__.py
│   ├── harness/                       # Agent harness base classes
│   │   ├── __init__.py
│   │   ├── agent_harness.py           # Base harness
│   │   ├── config.py                  # Harness config
│   │   ├── interfaces.py              # Abstract interfaces
│   │   ├── retry_strategies/
│   │   │   ├── __init__.py
│   │   │   ├── exponential_backoff.py
│   │   │   ├── jitter.py
│   │   │   └── circuit_breaker.py
│   │   ├── checkpointing/
│   │   │   ├── __init__.py
│   │   │   ├── checkpoint.py          # Checkpoint management
│   │   │   └── recovery.py            # Recovery logic
│   │   ├── observability/
│   │   │   ├── __init__.py
│   │   │   ├── metrics.py             # Prometheus metrics
│   │   │   ├── logging.py             # Structured logging
│   │   │   └── tracing.py             # Distributed tracing
│   │   └── tests/
│   │       ├── test_harness.py
│   │       ├── test_retry.py
│   │       └── test_checkpointing.py
│   │
│   ├── envelope/                      # Message envelope system
│   │   ├── __init__.py
│   │   ├── envelope.py                # Base envelope
│   │   ├── typed_envelope.py          # Typed envelope
│   │   ├── serialization.py           # Serialization
│   │   ├── validation.py              # Envelope validation
│   │   └── tests/
│   │       ├── test_envelope.py
│   │       └── test_serialization.py
│   │
│   ├── utils/                         # Shared utilities
│   │   ├── __init__.py
│   │   ├── ab_testing.py              # A/B testing utils
│   │   ├── rate_limiter.py            # Rate limiting
│   │   ├── secrets.py                 # Secrets management
│   │   ├── workflow_progress.py       # Workflow tracking
│   │   ├── graceful_shutdown.py       # Shutdown handling
│   │   ├── mock_data.py               # Test data generation
│   │   ├── caching.py                 # Caching utilities
│   │   └── tests/
│   │       └── test_utils.py
│   │
│   ├── schemas/                       # Shared data schemas
│   │   ├── __init__.py
│   │   ├── base.py                    # Base schema classes
│   │   ├── config.py                  # Config schemas
│   │   ├── validation.py              # Validation utilities
│   │   ├── lead.py                    # Lead schemas
│   │   ├── campaign.py                # Campaign schemas
│   │   ├── content.py                 # Content schemas
│   │   └── tests/
│   │       └── test_schemas.py
│   │
│   ├── deep_agents/                   # Deep agent utilities
│   │   ├── __init__.py
│   │   ├── capabilities.py            # Agent capabilities
│   │   └── factories.py               # Agent factories
│   │
│   └── exceptions/                    # Shared exceptions
│       ├── __init__.py
│       ├── agent_exceptions.py
│       ├── service_exceptions.py
│       └── validation_exceptions.py
│
├── 📁 services/                       # Shared infrastructure services
│   ├── __init__.py
│   │
│   ├── persistence/                   # Database service
│   │   ├── __init__.py
│   │   ├── service.py                 # Main service
│   │   ├── config.py                  # Configuration
│   │   ├── exceptions.py              # Exceptions
│   │   ├── adapters/
│   │   │   ├── __init__.py
│   │   │   ├── base_adapter.py        # Abstract adapter
│   │   │   ├── supabase_adapter.py    # Supabase implementation
│   │   │   └── in_memory_adapter.py   # In-memory implementation
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── lead.py
│   │   │   ├── campaign.py
│   │   │   ├── interaction.py
│   │   │   └── metadata.py
│   │   ├── queries/
│   │   │   ├── __init__.py
│   │   │   ├── lead_queries.py        # Lead queries
│   │   │   ├── campaign_queries.py    # Campaign queries
│   │   │   └── analytics_queries.py   # Analytics
│   │   ├── migrations/
│   │   │   ├── __init__.py
│   │   │   └── versions/              # Migration versions
│   │   ├── metrics.py                 # Performance metrics
│   │   ├── caching.py                 # Query caching
│   │   └── tests/
│   │       ├── test_service.py
│   │       ├── test_adapters.py
│   │       └── test_queries.py
│   │
│   ├── redis/                         # Redis pub/sub and streams
│   │   ├── __init__.py
│   │   ├── client.py                  # Redis client wrapper
│   │   ├── config.py                  # Configuration
│   │   ├── pubsub.py                  # Pub/sub implementation
│   │   ├── streams.py                 # Streams implementation
│   │   ├── messages.py                # Message definitions
│   │   ├── consumer_group.py          # Consumer group management
│   │   ├── health_checks.py           # Health monitoring
│   │   ├── metrics.py                 # Performance metrics
│   │   └── tests/
│   │       ├── test_client.py
│   │       ├── test_streams.py
│   │       └── test_pubsub.py
│   │
│   ├── vector_db/                     # Vector database service
│   │   ├── __init__.py
│   │   ├── client.py                  # Vector DB client
│   │   ├── config.py                  # Configuration
│   │   ├── embeddings.py              # Embedding generation
│   │   ├── indexing.py                # Index management
│   │   ├── search.py                  # Search implementation
│   │   ├── metrics.py                 # Performance metrics
│   │   └── tests/
│   │       ├── test_client.py
│   │       ├── test_embeddings.py
│   │       └── test_search.py
│   │
│   └── external_apis/                 # Third-party integrations
│       ├── __init__.py
│       ├── config.py                  # API configuration
│       ├── base_client.py             # Base client class
│       ├── crunchbase/
│       │   ├── __init__.py
│       │   ├── client.py              # Crunchbase client
│       │   ├── schema.py              # Data schema
│       │   └── rate_limiter.py        # Rate limiting
│       ├── linkedin/
│       │   ├── __init__.py
│       │   ├── client.py              # LinkedIn client
│       │   ├── schema.py              # Data schema
│       │   └── auth.py                # Authentication
│       ├── other_apis/
│       │   ├── __init__.py
│       │   └── # Additional APIs
│       └── tests/
│           ├── test_crunchbase.py
│           ├── test_linkedin.py
│           └── test_base_client.py
│
├── 📁 config/                         # Configuration management
│   ├── __init__.py
│   ├── settings.py                    # Main settings
│   ├── env.py                         # Environment variables
│   ├── logging.py                     # Logging configuration
│   ├── redis.yaml                     # Redis config
│   ├── database.yaml                  # Database config
│   ├── secrets_example.yaml           # Secrets template
│   └── profiles/
│       ├── __init__.py
│       ├── development.yaml           # Dev config
│       ├── staging.yaml               # Staging config
│       ├── production.yaml            # Production config
│       └── testing.yaml               # Test config
│
├── 📁 deployment/                     # Deployment configuration
│   ├── __init__.py
│   ├── README.md                      # Deployment guide
│   ├── docker/
│   │   ├── Dockerfile.worker          # Worker image
│   │   ├── Dockerfile.base            # Base image
│   │   ├── docker-compose.yml         # Compose file
│   │   ├── docker-compose.dev.yml     # Dev overrides
│   │   ├── docker-compose.prod.yml    # Prod overrides
│   │   └── .dockerignore
│   │
│   ├── kubernetes/
│   │   ├── namespace.yaml
│   │   ├── manager-deployment.yaml
│   │   ├── orchestrator-deployment.yaml
│   │   ├── agent-deployment.yaml
│   │   ├── service.yaml
│   │   ├── ingress.yaml
│   │   ├── configmap.yaml
│   │   └── secrets-template.yaml
│   │
│   ├── helm/
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   ├── values-dev.yaml
│   │   ├── values-prod.yaml
│   │   └── templates/
│   │       ├── deployment.yaml
│   │       ├── service.yaml
│   │       └── configmap.yaml
│   │
│   └── terraform/
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       ├── modules/
│       │   ├── redis/
│       │   ├── database/
│       │   ├── kubernetes/
│       │   └── networking/
│       ├── environments/
│       │   ├── dev.tfvars
│       │   ├── staging.tfvars
│       │   └── prod.tfvars
│       └── .gitignore
│
├── 📁 scripts/                        # Operational scripts
│   ├── __init__.py
│   ├── README.md
│   │
│   ├── startup/                       # Startup scripts
│   │   ├── __init__.py
│   │   ├── initialize_db.py           # Database initialization
│   │   ├── initialize_redis.py        # Redis setup
│   │   └── seed_data.py               # Data seeding
│   │
│   ├── monitoring/                    # Monitoring scripts
│   │   ├── __init__.py
│   │   ├── health_check.py            # Health monitoring
│   │   ├── redis_health.py            # Redis health
│   │   ├── streams_health.py          # Streams monitoring
│   │   ├── performance_monitor.py     # Performance metrics
│   │   └── alert_system.py            # Alerting
│   │
│   ├── maintenance/                   # Maintenance scripts
│   │   ├── __init__.py
│   │   ├── cleanup_old_streams.py     # Stream cleanup
│   │   ├── reset_consumer_groups.py   # Consumer reset
│   │   ├── rebuild_indexes.py         # Index rebuild
│   │   ├── backup_database.py         # Database backups
│   │   └── migrate_data.py            # Data migration
│   │
│   ├── development/                   # Development utilities
│   │   ├── __init__.py
│   │   ├── setup_dev_env.py           # Dev environment setup
│   │   ├── generate_sample_data.py    # Sample data
│   │   ├── load_test.py               # Load testing
│   │   └── debug_flows.py             # Debugging utilities
│   │
│   ├── smoke_test_three_tier.py       # End-to-end smoke test
│   ├── run_agent.py                   # Main entry point
│   └── utils.py                       # Script utilities
│
├── 📁 tests/                          # Test suite
│   ├── __init__.py
│   ├── conftest.py                    # Pytest configuration
│   ├── fixtures/                      # Test fixtures
│   │   ├── __init__.py
│   │   ├── mock_data.py               # Mock data
│   │   ├── redis_fixtures.py          # Redis fixtures
│   │   ├── database_fixtures.py       # Database fixtures
│   │   └── agent_fixtures.py          # Agent fixtures
│   │
│   ├── integration/                   # Integration tests
│   │   ├── __init__.py
│   │   ├── test_tier_integration.py   # Tier integration
│   │   ├── test_delegation_flow.py    # Delegation flow
│   │   ├── test_end_to_end.py         # E2E tests
│   │   ├── test_worker_lifecycle.py   # Worker lifecycle
│   │   └── test_error_handling.py     # Error handling
│   │
│   ├── unit/                          # Unit tests
│   │   ├── tier_1/
│   │   │   ├── test_manager.py
│   │   │   └── test_delegation_tools.py
│   │   ├── tier_2/
│   │   │   ├── test_leads_orchestrator.py
│   │   │   └── test_outreach_orchestrator.py
│   │   ├── tier_3/
│   │   │   ├── test_rag_agent.py
│   │   │   ├── test_persistence_agent.py
│   │   │   └── test_copywriter_agent.py
│   │   ├── core/
│   │   │   ├── test_harness.py
│   │   │   ├── test_envelope.py
│   │   │   └── test_utils.py
│   │   └── services/
│   │       ├── test_persistence.py
│   │       ├── test_redis.py
│   │       └── test_vector_db.py
│   │
│   ├── performance/                   # Performance tests
│   │   ├── __init__.py
│   │   ├── test_throughput.py         # Throughput tests
│   │   ├── test_latency.py            # Latency tests
│   │   └── test_resource_usage.py     # Resource usage
│   │
│   ├── load/                          # Load tests
│   │   ├── __init__.py
│   │   └── locustfile.py              # Locust load tests
│   │
│   └── README.md                      # Testing guide
│
├── 📁 docs/                           # Documentation
│   ├── README.md                      # Main doc index
│   ├── QUICK_REFERENCE.md             # Quick start
│   ├── ARCHITECTURE.md                # Architecture overview
│   ├── MIGRATION.md                   # Migration guide
│   │
│   ├── guides/
│   │   ├── getting_started.md         # Getting started
│   │   ├── development.md             # Development guide
│   │   ├── deployment.md              # Deployment guide
│   │   ├── troubleshooting.md         # Troubleshooting
│   │   ├── faq.md                     # FAQ
│   │   └── glossary.md                # Glossary
│   │
│   ├── api/
│   │   ├── manager_api.md             # Manager API
│   │   ├── orchestrator_api.md        # Orchestrator API
│   │   ├── agent_api.md               # Agent API
│   │   └── services_api.md            # Services API
│   │
│   ├── architecture/
│   │   ├── three_tier_model.md        # Three-tier model
│   │   ├── message_flow.md            # Message flow
│   │   ├── redis_streams.md           # Redis streams
│   │   ├── error_handling.md          # Error handling
│   │   └── scalability.md             # Scalability
│   │
│   ├── operations/
│   │   ├── monitoring.md              # Monitoring
│   │   ├── logging.md                 # Logging
│   │   ├── metrics.md                 # Metrics
│   │   ├── alerting.md                # Alerting
│   │   └── maintenance.md             # Maintenance
│   │
│   ├── examples/
│   │   ├── basic_workflow.md          # Basic workflow
│   │   ├── custom_agent.md            # Custom agent
│   │   ├── error_scenarios.md         # Error handling
│   │   └── performance_tuning.md      # Performance
│   │
│   ├── legacy/
│   │   ├── legacy_structure_analysis.md
│   │   ├── script_compatibility.md
│   │   └── deprecation_timeline.md
│   │
│   └── project/
│       ├── completion_report.md       # Project completion
│       ├── changelog.md               # Changelog
│       └── roadmap.md                 # Future roadmap
│
├── 📁 agent/                          # LEGACY STRUCTURE (Retained)
│   ├── __init__.py
│   ├── manager/
│   ├── orchestrators/
│   ├── operational_agents/
│   ├── harness/
│   ├── tools/
│   ├── utils/
│   ├── schemas/
│   ├── Infastructure/
│   ├── config/
│   └── # ... (all original files for backward compatibility)
│
├── 📁 platform_monitoring/            # Platform monitoring
│   ├── __init__.py
│   ├── metrics_exporter.py
│   ├── dashboards/
│   │   ├── grafana_dashboards.json
│   │   └── prometheus_alerts.yaml
│   └── # ... monitoring infrastructure
│
├── 📄 Project Root Files
│   ├── .env.example                   # Environment template
│   ├── .env.test                      # Test environment
│   ├── .gitignore                     # Git ignore rules
│   ├── .github/
│   │   ├── workflows/
│   │   │   ├── tests.yml              # Run tests
│   │   │   ├── build.yml              # Build Docker
│   │   │   ├── deploy.yml             # Deploy to prod
│   │   │   └── lint.yml               # Code quality
│   │   └── ISSUE_TEMPLATE/
│   │
│   ├── pyproject.toml                 # Python project config
│   ├── requirements.txt               # Production deps
│   ├── requirements-dev.txt           # Dev deps
│   ├── setup.py                       # Setup script
│   ├── pytest.ini                     # Pytest config
│   ├── mypy.ini                       # Type checking
│   ├── .pylintrc                      # Linting
│   ├── .black                         # Code formatting
│   ├── Makefile                       # Common commands
│   ├── README.md                      # Project README
│   ├── LICENSE                        # License file
│   └── CHANGELOG.md                   # Change history
│
```

---

## Key Organizational Principles

### 1. **Clear Hierarchy** 🏗️
```
Tiers (agents) → Core (framework) → Services (infrastructure)
                ↓
              Schemas & Utils (shared)
```

### 2. **Colocated Tests** 🧪
- Each module has its own `tests/` subdirectory
- Tests live close to code they test
- Easy to run tests at any level

### 3. **Domain-Driven Structure** 📦
- Each tier contains its own:
  - Core logic
  - Schemas (specific to that tier)
  - Workflows/Operations (domain-specific)
  - Tests (isolated validation)

### 4. **Shared Utilities** 🔧
```
core/utils/           # General utilities
core/schemas/         # General data schemas
core/exceptions/      # Shared exceptions
```

### 5. **Configuration Separation** ⚙️
```
config/              # All configuration
├── settings.py      # Main settings
├── profiles/        # Environment-specific
└── *.yaml          # Service configs
```

### 6. **Deployment Flexibility** 🚀
```
deployment/
├── docker/          # Docker files
├── kubernetes/      # K8s manifests
├── helm/            # Helm charts
└── terraform/       # IaC
```

### 7. **Scripts Organization** 📝
```
scripts/
├── startup/         # Init scripts
├── monitoring/      # Health checks
├── maintenance/     # Cleanup/maintenance
└── development/     # Dev tools
```

---

## Migration Path to This Structure

### Phase 1: Current (✅ DONE)
- Three-tier core implemented
- Services extracted
- Core framework in place
- Backward compatibility maintained

### Phase 2: Optional Cleanup (Q1 2026)
```bash
# Move tier-specific schemas
agent/schemas/rag_schemas.py 
  → tiers/tier_3/rag_agent/schemas/rag_schemas.py

# Move tier-specific utilities
agent/utils/ab_testing.py 
  → core/utils/ab_testing.py

# Consolidate configurations
agent/config/*.py 
  → config/
```

### Phase 3: Full Optimization (Q2 2026)
```bash
# Add domain-specific subdirectories
tiers/tier_3/rag_agent/
├── retrieval/        # NEW: Retrieval logic
├── generation/       # NEW: Generation logic
├── prompts/          # NEW: Prompt templates
└── workflows/        # NEW: Workflow definitions

# Add schemas at each tier
tiers/tier_2/leads_orchestrator/schemas/
tiers/tier_2/outreach_orchestrator/schemas/
tiers/tier_3/rag_agent/schemas/
```

---

## File Organization Best Practices

### ✅ DO: Organize by Domain
```
✅ Good: tiers/tier_3/rag_agent/retrieval/
✅ Good: tiers/tier_2/leads_orchestrator/workflows/
✅ Good: core/harness/observability/
```

### ❌ DON'T: Spread related code
```
❌ Bad: rag_retrieval.py in tier_3 + retrieval.py in services
❌ Bad: Schemas in agent/schemas/ AND tier_3/rag_agent/
```

### ✅ DO: Colocate tests
```
✅ Good: tiers/tier_3/rag_agent/tests/test_retrieval.py
✅ Good: services/redis/tests/test_streams.py
```

### ❌ DON'T: Separate tests far from code
```
❌ Bad: Code in tiers/, tests in tests/unit/tier_3/
```

---

## Configuration & Secrets

### Environment-Specific Config
```yaml
# config/profiles/development.yaml
debug: true
log_level: DEBUG
redis:
  host: localhost
  port: 6379

# config/profiles/production.yaml
debug: false
log_level: INFO
redis:
  host: redis.prod.internal
  port: 6379
  ssl: true
```

### Secrets Management
```bash
# Never commit secrets!
.env.example          # Template (commit this)
.env                  # Actual secrets (in .gitignore)
```

---

## Module Import Patterns

### Tier → Tier Communication
```python
# Bad: Direct import
from tiers.tier_3.rag_agent import RAGAgent  # ❌ Tight coupling

# Good: Via services/interfaces
from tiers.tier_3.rag_agent.interfaces import RAGAgentInterface  # ✅
```

### Core → Everyone
```python
# OK: Framework is widely imported
from core.harness import AgentHarness  # ✅
from core.envelope import Envelope     # ✅
from core.utils import rate_limiter    # ✅
```

### Services → Everyone
```python
# OK: Services are dependencies
from services.redis import RedisPubSub     # ✅
from services.persistence import Persistence  # ✅
```

---

## Directory Sizing Guidelines

| Directory | Files | Size | Purpose |
|-----------|-------|------|---------|
| `tiers/tier_1/manager/` | 10-15 | Small | Single agent |
| `tiers/tier_2/leads_orchestrator/` | 15-20 | Medium | Complex workflows |
| `services/redis/` | 8-12 | Small | Single service |
| `core/harness/` | 15-20 | Medium | Framework |
| `docs/` | 20-30 | Large | Documentation |
| `tests/` | 30-50 | Large | Test coverage |

---

## Benefits of This Organization

### ✅ For Developers
- Find code quickly (clear hierarchy)
- Understand relationships easily
- Run tests at any level
- Add new features systematically

### ✅ For Operations
- Deploy specific components
- Monitor by tier/service
- Scale independently
- Debug efficiently

### ✅ For DevOps
- Infrastructure as code organization
- Environment-specific configs
- Clear deployment procedures
- Automated workflows

### ✅ For Architects
- System decomposition visible
- Dependencies clear
- Scalability demonstrated
- Evolution path obvious

---

## Implementation Checklist

### Immediate (Already Done ✅)
- [x] Three-tier core
- [x] Services layer
- [x] Core framework
- [x] Basic tests

### Phase 2 (Q1 2026)
- [ ] Move tier-specific schemas
- [ ] Extract utilities to core/
- [ ] Add domain-specific subdirectories
- [ ] Consolidate configuration

### Phase 3 (Q2 2026)
- [ ] Remove legacy agent/ paths
- [ ] Complete schema migration
- [ ] Full IaC setup
- [ ] Advanced observability

---

## Summary

This optimized structure provides:

1. **📊 Clear Organization**: Everything in logical places
2. **🧪 Colocated Tests**: Tests near code
3. **⚙️ Modular Design**: Independent deployment
4. **📦 Scalability**: Easy to add new tiers/agents
5. **🔧 Maintainability**: Simple to understand
6. **🚀 DevOps Ready**: IaC, monitoring, deployment

**Current Status**: Core structure is optimized and ready ✅  
**Next Steps**: Phase 2 cleanup (optional, Q1 2026)  
**Status**: Production-ready and well-organized

---

**Last Updated:** November 8, 2025  
**Version:** 1.0 - Optimized Architecture  
**Status:** ✅ Recommended for adoption
