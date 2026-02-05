# Enterprise AI Sales Orchestrator (Agentic System)

The Agentic System is an **enterprise-style, multi-agent orchestration platform** built to coordinate end-to-end B2B sales workflows — from lead discovery and qualification to drafting replies and sequencing outreach.

This repository is best read as a **systems + architecture showcase**:

- A three-tier, event-driven design using **Redis Streams** for async communication.
- A standardized **message envelope** for provenance and traceability.
- Tiered separation between **policy (Manager)**, **business workflows (Orchestrators)**, and **execution (Agents)**.

## Read the Docs (primary)

The main documentation lives on GitHub Pages:

- https://boonboonboonboon.github.io/Enterprise-AI-Sales-Orchestrator-Public/

If you only read one thing, start here:

- System overview: https://boonboonboonboon.github.io/Enterprise-AI-Sales-Orchestrator-Public/concepts/system-overview/
- Three-tier architecture: https://boonboonboonboon.github.io/Enterprise-AI-Sales-Orchestrator-Public/concepts/three-tier-architecture/
- Redis Streams model: https://boonboonboonboon.github.io/Enterprise-AI-Sales-Orchestrator-Public/concepts/redis-streams/

## What this is

At a high level, the system behaves like a distributed “assembly line” for sales operations:

- **Tier 1 — Manager (strategic):** decides what to do next and routes work.
- **Tier 2 — Orchestrators (business logic):** run workflows (lead qualification, inbound triage, outreach sequencing).
- **Tier 3 — Agents (execution):** do atomic work (RAG retrieval, persistence CRUD, copywriting, classification).

All coordination is **vertical-only** (Manager ↔ Orchestrators ↔ Agents). This prevents cross-workflow coupling and keeps the system debuggable.

### Architecture (at a glance)

```
┌──────────────────────────────────────────────────────────────┐
│ TIER 1: Strategic Layer (Manager)                            │
│ {tenant}:manager:tasks → {tenant}:manager:results            │
│ - High-level campaign decisions                              │
│ - Workflow orchestration                                     │
│ - Routes to appropriate Tier 2 orchestrators                 │
└──────────────┬───────────────────────────────────────────────┘
               │ Delegates via Redis Streams
               ▼
┌──────────────────────────────────────────────────────────────┐
│ TIER 2: Business Logic Layer (Orchestrators)                 │
│                                                              │
│ ┌─ Leads Orchestrator ──────────────────────────────────┐   │
│ │ {tenant}:orchestrators:leads:tasks                    │   │
│ │ → Discovery → Qualification → Enrichment              │   │
│ └──────────────┬──────────────────────────────────────┘   │
│                │                                           │
│ ┌──────────────┤                                           │
│ │ Outreach Orchestrator ────────────────────────────────┐   │
│ │ {tenant}:orchestrators:outbound:tasks                 │   │
│ │ → Personalization → Sequencing → Delivery             │   │
│ └──────────────┬──────────────────────────────────────┘   │
│                │                                           │
└────────────────┼───────────────────────────────────────────┘
                 │ Delegates to specialized agents
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ TIER 3: Execution Layer (Specialized Agents)                 │
│                                                              │
│ ┌─ RAG Agent ──────────────┐  ┌─ Copywriter Agent ──────┐  │
│ │ agents:rag:tasks         │  │ agents:copywriter:tasks │  │
│ │ Research & enrichment    │  │ Content generation      │  │
│ └──────────────────────────┘  └─────────────────────────┘  │
│                                                              │
│ ┌─ Persistence Agent ──┐  ┌─ Booking Agent ────────────┐   │
│ │ agents:persistence  │  │ agents:booking:tasks       │   │
│ │ Database operations │  │ Meeting scheduling         │   │
│ └─────────────────────┘  └────────────────────────────┘   │
│                                                              │
│ ┌─ Sequencing Agent ──┐  ┌─ Deduplication Agent ──────┐   │
│ │ agents:sequencing:  │  │ agents:deduplication:tasks │   │
│ │ ML optimization     │  │ Duplicate detection        │   │
│ └─────────────────────┘  └────────────────────────────┘   │
└──────────────┬───────────────────────────────────────────────┘
               │ Uses shared services
               ▼
┌──────────────────────────────────────────────────────────────┐
│ SERVICES: Shared Infrastructure                              │
│ - Persistence: Database adapters & service                  │
│ - Redis: Pub/Sub & Streams                                  │
│ - Vector DB: Embeddings & similarity search                 │
│ - External APIs: Crunchbase, LinkedIn integration           │
└──────────────────────────────────────────────────────────────┘
```

## Key capabilities

- **Three-tier architecture** (policy → workflows → execution)
- **Event-driven concurrency** via Redis Streams + consumer groups
- **Typed/standardized envelopes** for provenance and debugging
- **Pluggable services** (persistence adapters, vector DB pipeline, email providers)
- **Operational guardrails** (retries, DLQ, graceful shutdown, health endpoints)
- **Deployment patterns** (Docker Compose / K8s manifests / Helm chart)

## Repository status / scope

- This is a **public demonstration** of a private product.
- Secrets have been removed/redacted; docs use placeholders.
- Some components may be mocked, partially implemented, or non-functional without your own credentials and infrastructure.

## Where to look in the code

- Tier 1 Manager: `tiers/tier_1/manager/`
- Tier 2 Orchestrators: `tiers/tier_2/`
- Tier 3 Agents: `tiers/tier_3/`
- Shared framework: `core/` (envelope, harness, DLQ, shutdown, intent)
- Services: `services/` (Redis, persistence, email, vector pipeline)
- API gateway: `api/gateway/`
- Portals (Next.js): `apps/`

## Project Structure

```
agentic-system/
├── tiers/                      # Three-tier architecture
│   ├── tier_1/                 # Strategic layer
│   │   └── manager/            # Campaign orchestration
│   ├── tier_2/                 # Business logic layer
│   │   ├── leads_orchestrator/ # Leads workflows
│   │   └── outreach_orchestrator/ # Outreach workflows
│   └── tier_3/                 # Execution layer
│       ├── rag_agent/          # Research & enrichment
│       ├── persistence_agent/  # Database operations
│       └── copywriter_agent/   # Content generation
├── core/                       # Framework components
│   ├── harness/                # Agent harness & config
│   ├── envelope/               # Message envelope
│   └── deep_agents/            # Deep agent utilities
├── services/                   # Shared services
│   ├── persistence/            # Database service
│   ├── redis/                  # Redis client & streams
│   ├── vector_db/              # Vector database
│   └── external_apis/          # API integrations
├── deployment/                 # Docker & infrastructure
│   ├── docker/                 # Dockerfiles
│   └── docker-compose.yml      # Service orchestration
├── docs/                       # Documentation
│   ├── ARCHITECTURE.md         # System architecture
│   ├── MIGRATION.md            # Migration guide
│   ├── REDIS_STREAMS.md        # Redis patterns
│   └── API.md                  # API reference
├── tests/                      # Test suites
│   ├── integration/            # Integration tests
│   ├── unit/                   # Unit tests
│   └── fixtures/               # Test fixtures
├── scripts/                    # Operational scripts
│   ├── startup/                # Initialization
│   ├── monitoring/             # Health checks
│   └── maintenance/            # Maintenance tasks
├── utils/                      # Shared utilities
└── config/                     # Configuration files
```

## Setup (quick, detailed guide in docs)

For full instructions, use the docs:

- Installation: https://boonboonboonboon.github.io/Enterprise-AI-Sales-Orchestrator-Public/getting-started/installation/
- Quick start: https://boonboonboonboon.github.io/Enterprise-AI-Sales-Orchestrator-Public/getting-started/quickstart/
- Environment variables: https://boonboonboonboon.github.io/Enterprise-AI-Sales-Orchestrator-Public/getting-started/environment/

### Minimal local workflow

1. Clone and enter the repo

```powershell
git clone https://github.com/BoonBoonBoonBoon/Enterprise-AI-Sales-Orchestrator-Public.git
cd "Enterprise-AI-Sales-Orchestrator-Public"
```

2. Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Configure environment

```powershell
Copy-Item .env.example .env
# Edit .env with your configuration
```

4. Run tests

```powershell
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires Redis)
pytest tests/integration/ -v

# All tests
pytest -v
```

### Docker (optional)

1. **Build images**

```powershell
cd deployment
docker compose build
```

2. **Start services**

```powershell
# Start Redis and Postgres
docker compose --profile local up -d redis postgres

# Start all workers
docker compose up -d
```

3. **Scale workers**

```powershell
# Scale tier_3 agents for parallel processing
docker compose up -d --scale persistence_agent=3
docker compose up -d --scale rag_agent=2
docker compose up -d --scale copywriter_agent=2
```

4. **Monitor workers**

```powershell
docker compose ps
docker compose logs -f manager
```

### Validate reply pipeline (optional)

The quickest end-to-end validation for reply context + sequencing is:

```powershell
cd deployment
docker compose exec -T outreach_orchestrator python scripts/testing/validate_rag_to_copywriter_flow.py --auto-send
```

This confirms:

- RAG returns reply-ready context
- Leads builds `reply_packet`
- Outreach enqueues Copywriter and registers auto-send context
- Sequencer receives a task and emits a `sent` result

## Next steps

- Read the docs: https://boonboonboonboon.github.io/Enterprise-AI-Sales-Orchestrator-Public/
- Start here for architecture: https://boonboonboonboon.github.io/Enterprise-AI-Sales-Orchestrator-Public/concepts/three-tier-architecture/

```python
from tiers.tier_1.manager import ManagerAgent, ManagerAgentHarness
from core.harness import HarnessConfig

# Create manager for campaign orchestration
config = HarnessConfig()
harness = ManagerAgentHarness(redis_client, tenant_id="my-tenant", config=config)
result = harness.execute(campaign_envelope)
```

### Tier 2: Business Logic

```python
from tiers.tier_2.leads_orchestrator import LeadsOrchestrator, LeadsConsumer

# Process leads workflow
consumer = LeadsConsumer(redis_client, tenant_id="my-tenant")
consumer.start()  # Begins processing from Redis stream
```

### Tier 3: Specialized Execution

```python
from tiers.tier_3.rag_agent import RAGAgent
from tiers.tier_3.persistence_agent import PersistenceAgent
from tiers.tier_3.copywriter_agent import CopywriterAgent

# Research enrichment
rag = RAGAgent()
citations = await rag.search_company("Acme Inc")

# Database operations
persistence = PersistenceAgent()
await persistence.save_lead(lead_data)

# Content generation
copywriter = CopywriterAgent()
email = await copywriter.generate_email(context)
```

### Services Layer

```python
from services.persistence import PersistenceService
from services.redis import RedisPubSub
from services.vector_db import VectorDBClient

# Database operations
persistence = PersistenceService()
leads = await persistence.query_leads(filters={"company": "Acme"})

# Redis pub/sub
redis = RedisPubSub()
await redis.publish("tier_2:leads:tasks", envelope)

# Vector similarity search
vector_db = VectorDBClient()
similar = await vector_db.similarity_search(query, top_k=5)
```

## Documentation

### Core Documentation

- **[QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)** - Quick reference guide (START HERE)
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Three-tier architecture design
- **[MIGRATION.md](docs/MIGRATION.md)** - Migration guide with import path mappings

### Implementation Guides

- **[REDIS_STREAMS.md](docs/REDIS_STREAMS.md)** - Redis Streams patterns
- **[API.md](docs/API.md)** - API reference and endpoints
- **[DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Deployment guide

### Project Reports

- **[PROJECT_COMPLETION_REPORT.md](docs/PROJECT_COMPLETION_REPORT.md)** - Complete reorganization report
- **[SCRIPT_COMPATIBILITY.md](docs/SCRIPT_COMPATIBILITY.md)** - Script validation results

## Testing

### Unit Tests

```powershell
pytest tests/unit/ -v --cov=tiers --cov=core --cov=services
```

### Integration Tests

```powershell
# Requires Redis running
docker compose --profile local up -d redis
pytest tests/integration/ -v
```

### Smoke Tests

```powershell
# End-to-end system test
pytest tests/smoke/ -v
```

## Monitoring

### Health Checks

```powershell
# Redis connectivity
python scripts/monitoring/check_redis_status.py

# Stream monitoring
python scripts/monitoring/stream_monitor.py

# Worker health
docker compose ps
```

### Metrics

- Prometheus metrics exposed on workers
- Grafana dashboards in `deployment/monitoring/`
- Stream lag monitoring via Redis

## Development

### Adding a New Agent

1. Create agent directory in appropriate tier:

```
tiers/tier_3/my_agent/
├── my_agent.py
├── my_agent_harness.py
├── consumer.py
├── tools/
└── __init__.py
```

2. Implement agent class:

```python
from core.harness import AgentHarness

class MyAgent:
    def execute(self, envelope):
        # Agent logic here
        pass
```

3. Create consumer for Redis Streams:

```python
from services.redis import RedisPubSub

class MyAgentConsumer:
    def __init__(self, redis_client, tenant_id):
        self.task_stream = f"{tenant_id}:agents:myagent:tasks"
        self.result_stream = f"{tenant_id}:agents:myagent:results"
```

4. Add to docker-compose.yml:

```yaml
my_agent:
  image: agentic/worker:dev
  command: ["python", "-m", "tiers.tier_3.my_agent.consumer"]
```

### Running Locally

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run specific consumer
python -m tiers.tier_3.rag_agent.consumer

# Run with debugging
$env:RAG_DEBUG_IO="1"
python -m tiers.tier_3.rag_agent.consumer
```

## Environment Variables

```bash
# Required
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
OPENAI_API_KEY=your-openai-api-key
REDIS_URL=rediss://your-redis-cloud-url:port

# Optional
TENANT_ID=agentic-dev                    # Default: agentic-dev
REDIS_NAMESPACE=agentic                  # Stream prefix
OPS_HB_ENABLED=1                         # Heartbeat monitoring
RAG_DEBUG_IO=0                           # RAG debug logging

# External APIs (for enrichment)
CRUNCHBASE_API_KEY=your-api-key         # Company research
LINKEDIN_ACCESS_TOKEN=your-token        # Professional data
```

## Redis Stream Architecture

The system uses a hierarchical Redis Streams structure for clear separation of concerns:

### Tier 1: Manager (Strategic)

```
{tenant}:manager:tasks      # External requests enter here
{tenant}:manager:results    # Final responses exit here
```

### Tier 2: Orchestrators (Business Logic) ⭐ NEW HIERARCHICAL STRUCTURE

```
{tenant}:orchestrators:leads:tasks
{tenant}:orchestrators:leads:results
{tenant}:orchestrators:outreach:tasks
{tenant}:orchestrators:outreach:results
```

### Tier 3: Agents (Execution)

```
{tenant}:agents:rag:tasks
{tenant}:agents:rag:results
{tenant}:agents:persistence:tasks
{tenant}:agents:persistence:results
{tenant}:agents:copywriter:tasks
{tenant}:agents:copywriter:results
...and more
```

**Key Design**: The `orchestrators/` parent folder provides clear hierarchy in Redis browsers, matching the `agents/` structure for consistency.

## Troubleshooting

### Import Errors

If you see import errors, ensure you're using the new tier paths:

```python
# OLD (deprecated)
from agent.manager.manager_agent import ManagerAgent

# NEW (correct)
from tiers.tier_1.manager import ManagerAgent
```

See [MIGRATION.md](docs/MIGRATION.md) for complete path mappings.

### Docker Build Issues

```powershell
# Clean rebuild
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Redis Connection Issues

```powershell
# Check Redis is running
docker compose ps redis

# Test connection
python scripts/monitoring/check_redis_status.py
```

## Contributing

This is a demonstration project and not open source. However, you're welcome to:

- Study the architecture
- Use patterns in your own projects
- Provide feedback via issues (for educational purposes)

## License

Proprietary - Demonstration purposes only. Not for production use.

---

**Last Updated:** November 8, 2025  
**Architecture Version:** 3-Tier (v2.0)  
**Status:** Production Ready ✅
