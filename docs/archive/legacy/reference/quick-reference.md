# Three-Tier Architecture - Quick Reference

**Last Updated:** November 8, 2025  
**Architecture Version:** 3-Tier v2.0  
**Status:** Production Ready ✅

---

## 📁 Directory Quick Reference

```bash
# New Structure (Use These)
tiers/tier_1/manager/              # Strategic layer
tiers/tier_2/leads_orchestrator/   # Business logic - Leads
tiers/tier_2/outreach_orchestrator/ # Business logic - Outreach
tiers/tier_3/rag_agent/            # Execution - Research
tiers/tier_3/persistence_agent/    # Execution - Database
tiers/tier_3/copywriter/           # Execution - Content

services/persistence/              # Shared database service
services/redis/                    # Shared Redis service
services/vector_db/                # Shared vector DB
services/external_apis/            # External integrations

core/harness/                      # Agent framework
core/envelope/                     # Messaging system

# Legacy Structure (Still Works)
agent/manager/                     # Old manager location
agent/orchestrators/               # Old orchestrators
agent/operational_agents/          # Old agents
agent/tools/                       # Old shared tools
agent/harness/                     # Old harness
```

---

## 🔄 Import Cheat Sheet

### Manager (Tier 1)

```python
# NEW (Recommended)
try:
    from tiers.tier_1.manager.manager_agent import ManagerAgent
    from tiers.tier_1.manager.consumer import ManagerConsumer
    from tiers.tier_1.manager.tools.delegation_tools import DelegationTools
except ImportError:
    from agent.manager.manager_agent import ManagerAgent
    from agent.manager.consumer import ManagerConsumer
    from agent.manager.tools.delegation_tools import DelegationTools
```

### Orchestrators (Tier 2)

```python
# NEW (Recommended)
try:
    from tiers.tier_2.leads_orchestrator import LeadsOrchestrator
    from tiers.tier_2.outreach_orchestrator import OutreachOrchestrator
except ImportError:
    from agent.orchestrators.leads_orchestrator import LeadsOrchestrator
    from agent.orchestrators.outreach_orchestrator import OutreachOrchestrator
```

### Agents (Tier 3)

```python
# NEW (Recommended)
try:
    from tiers.tier_3.rag_agent.rag_agent import RAGAgent
    from tiers.tier_3.persistence_agent.persistence_agent import PersistenceAgent
    from tiers.tier_3.copywriter.copywriter_agent import CopywriterAgent
except ImportError:
    from agent.operational_agents.rag_agent.rag_agent import RAGAgent
    from agent.operational_agents.persistence_agent.persistence_agent import PersistenceAgent
    from agent.operational_agents.copywriter.copywriter_agent import CopywriterAgent
```

### Core Framework

```python
# NEW (Recommended)
try:
    from core.harness import AgentHarness, HarnessConfig
    from core.envelope import Envelope, Priority, Status
except ImportError:
    from agent.harness.agent_harness import AgentHarness
    from agent.harness.config import HarnessConfig
    from agent.utils.typed_envelope import Envelope, Priority, Status
```

### Services

```python
# NEW (Recommended)
try:
    from services.redis import RedisPubSub
    from services.persistence import PersistenceService
    from services.vector_db import VectorDBClient
except ImportError:
    from agent.tools.redis.client import RedisPubSub
    from agent.tools.persistence.service import PersistenceService
    from agent.tools.vector_db.client import VectorDBClient
```

---

## 🏗️ Redis Stream Naming

### New Hierarchical Format

```python
# Format: {tenant}:tier_{n}:{agent_name}:tasks

# Tier 1 (Manager)
{tenant}:tier_1:manager:tasks

# Tier 2 (Orchestrators)
{tenant}:tier_2:leads:tasks
{tenant}:tier_2:outreach:tasks

# Tier 3 (Agents)
{tenant}:tier_3:rag:tasks
{tenant}:tier_3:persistence:tasks
{tenant}:tier_3:copywriter:tasks
```

### Legacy Format (Still Works)

```python
# Old Format: {tenant}:{agent}:tasks

{tenant}:manager:tasks
{tenant}:orchestrate:tasks
{tenant}:rag:tasks
{tenant}:persistence:tasks
```

---

## 🧪 Testing Commands

### Run Integration Tests
```bash
# All integration tests
pytest tests/integration/

# Tier integration tests specifically
pytest tests/integration/test_tier_integration.py -v

# Expected: 11/11 tests pass
```

### Run Smoke Test
```bash
# End-to-end system validation
python scripts/smoke_test_three_tier.py

# Expected: 7/7 tests pass
```

### Validate Imports
```bash
# Check specific tier
python -m pytest tests/integration/test_tier_integration.py::test_tier1_manager_imports

# Check backward compatibility
python -m pytest tests/integration/test_tier_integration.py::test_backward_compatibility_imports
```

---

## 🐳 Docker Commands

### Build Worker Image
```bash
# Build with tag
docker build -f deployment/docker/Dockerfile.worker -t agentic/worker:dev .

# Verify image
docker images | grep agentic/worker
```

### Run Services
```bash
# Start Redis
docker compose up -d redis

# Start all services
docker compose up -d

# Check status
docker compose ps
```

### Deploy Workers
```bash
# Scale specific workers
docker compose up -d --scale rag_worker=3 --scale persistence_worker=2
```

---

## 📊 Health Checks

### Redis Health
```bash
# Check Redis streams
python scripts/redis_health.py --topic orchestrate

# Monitor stream health
python scripts/streams_health.py

# Overall system health
python scripts/health_check.py
```

### Smoke Test
```bash
# Quick validation
python scripts/smoke_test_three_tier.py

# Specific tenant
python scripts/smoke_test_three_tier.py my_tenant_id
```

---

## 📝 Documentation Locations

| Document | Location | Purpose |
|----------|----------|---------|
| **README.md** | `/README.md` | Project overview, quick start |
| **Architecture** | `/docs/ARCHITECTURE.md` | Three-tier design details |
| **Migration** | `/docs/MIGRATION.md` | Import path mappings, migration guide |
| **Scripts** | `/docs/SCRIPT_COMPATIBILITY.md` | Script validation report |
| **Completion** | `/docs/PROJECT_COMPLETION_REPORT.md` | Full project completion details |
| **Quick Ref** | `/docs/QUICK_REFERENCE.md` | This document |

---

## 🚀 Quick Start

### Development Setup

```bash
# 1. Clone repository
git clone <repository-url>
cd agentic_system

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your settings

# 5. Start services
docker compose up -d redis

# 6. Run tests
pytest tests/integration/

# 7. Run smoke test
python scripts/smoke_test_three_tier.py
```

### Docker Deployment

```bash
# 1. Build images
docker compose build

# 2. Start all services
docker compose up -d

# 3. Check logs
docker compose logs -f manager_worker

# 4. Scale workers
docker compose up -d --scale rag_worker=3

# 5. Run health check
docker compose exec manager_worker python scripts/health_check.py
```

---

## ⚠️ Common Issues

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'tiers'`

**Solution:**
```python
# Ensure project root is in Python path
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
```

### Redis Connection Failed

**Problem:** `redis.exceptions.ConnectionError`

**Solution:**
```bash
# Check Redis is running
docker compose ps redis

# Start Redis
docker compose up -d redis

# Verify connection
python -c "import redis; r = redis.Redis(host='localhost', port=6379); print(r.ping())"
```

### Docker Build Fails

**Problem:** Build fails with missing dependencies

**Solution:**
```bash
# Clean build
docker compose build --no-cache

# Check Dockerfile paths
cat deployment/docker/Dockerfile.worker

# Verify requirements files exist
ls requirements*.txt
```

---

## 🔧 Environment Variables

### Required Variables

```bash
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=  # Optional

# Database Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key

# Tenant Configuration
TENANT_ID=default

# Agent Configuration
LOG_LEVEL=INFO
ENABLE_TRACING=false
```

### Optional Variables

```bash
# Performance Tuning
WORKER_CONCURRENCY=1
MAX_RETRIES=3
RETRY_DELAY=1.0

# External APIs
CRUNCHBASE_API_KEY=your-key
LINKEDIN_API_KEY=your-key

# Vector DB
VECTOR_DB_URL=http://localhost:8000
EMBEDDING_MODEL=text-embedding-ada-002
```

---

## 📈 Scaling Guide

### Horizontal Scaling

```bash
# Scale agents independently
docker compose up -d \
  --scale manager_worker=1 \
  --scale leads_orchestrator_worker=2 \
  --scale outreach_orchestrator_worker=2 \
  --scale rag_worker=3 \
  --scale persistence_worker=2 \
  --scale copywriter_worker=2
```

### Kubernetes Deployment

```bash
# Apply manifests
kubectl apply -f deployment/kubernetes/

# Scale deployment
kubectl scale deployment rag-worker --replicas=5

# Check status
kubectl get pods -l app=agentic-system
```

---

## 🔄 Deprecation Timeline

### Phase 1: Current (Nov 2025 - Mar 2026)
- ✅ Both old and new imports work
- ✅ No warnings
- **Action:** None required

### Phase 2: Q1 2026 (Apr - Jun 2026)
- ⚠️ Deprecation warnings added
- ✅ Old imports still work
- **Action:** Plan migration for scripts/code

### Phase 3: Q2 2026 (Jul - Sep 2026)
- ❌ Legacy structure removed
- **Action:** Complete migration required

---

## 📞 Support

### Issues & Questions

1. Check documentation: `/docs/`
2. Review migration guide: `/docs/MIGRATION.md`
3. Run smoke test: `python scripts/smoke_test_three_tier.py`
4. Check logs: `docker compose logs -f`

### Useful Scripts

```bash
# System health
python scripts/health_check.py

# Redis streams status
python scripts/streams_health.py

# Smoke test
python scripts/smoke_test_three_tier.py

# Check specific stream
python scripts/redis_health.py --topic orchestrate
```

---

## ✅ Validation Checklist

Before deployment, verify:

- [ ] All integration tests pass: `pytest tests/integration/`
- [ ] Smoke test passes: `python scripts/smoke_test_three_tier.py`
- [ ] Docker image builds: `docker compose build`
- [ ] Redis connection works: `docker compose up -d redis`
- [ ] Environment variables configured: Check `.env`
- [ ] Health checks pass: `python scripts/health_check.py`

---

**Quick Reference Version:** 1.0  
**Architecture Version:** 3-Tier v2.0  
**Last Updated:** November 8, 2025  
**Status:** ✅ Production Ready
