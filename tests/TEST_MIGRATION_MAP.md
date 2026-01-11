# Test Migration Mapping

This document maps old test files to their new locations in the reorganized structure.

## Migration Status: Task 16

**Status:** Directory structure created, files staged for migration

## Test File Migration Map

### Tier 1 (Manager / Strategic Layer)
- [ ] `test_manager_agent.py` → `tests/unit/tier_1/test_manager.py`
- [ ] `test_manager_deep_agents_validation.py` → `tests/unit/tier_1/test_deep_agents.py`

### Tier 2 (Orchestrators / Business Logic)
- [ ] `test_reply_orchestrator.py` → `tests/unit/tier_2/test_reply_orchestrator.py`
- [ ] `test_reply_orchestrator_delivery.py` → `tests/unit/tier_2/test_delivery.py`
- [ ] `test_campaign_manager_queue.py` → `tests/unit/tier_2/test_campaign_queue.py`

### Tier 3 (Agents / Operational Layer)
- [ ] `test_rag_agent.py` → `tests/unit/tier_3/test_rag_agent.py`
- [ ] `test_rag_agent_new.py` → `tests/unit/tier_3/test_rag_agent_new.py`
- [ ] `test_rag_agent_nlp.py` → `tests/unit/tier_3/test_rag_nlp.py`
- [ ] `test_rag_agent_no_redis.py` → `tests/unit/tier_3/test_rag_no_redis.py`
- [ ] `test_rag_pagination_and_cache.py` → `tests/unit/tier_3/test_rag_pagination.py`
- [ ] `test_rag_tool_guard.py` → `tests/unit/tier_3/test_rag_tool_guard.py`
- [ ] `test_rag_real_data_randomized.py` → `tests/unit/tier_3/test_rag_randomized.py`
- [ ] `test_db_write_agent.py` → `tests/unit/tier_3/test_persistence_agent.py`
- [ ] `test_persistence_agent.py` → `tests/unit/tier_3/test_persistence_advanced.py`
- [ ] `test_copywriter_agent.py` → `tests/unit/tier_3/test_copywriter_agent.py`

### Services Layer
- [ ] `test_rag_public_leads_integration.py` → `tests/unit/services/test_persistence_service.py`

### Core Framework
- [ ] `test_envelope.py` → `tests/unit/core/test_envelope.py`
- [ ] `test_envelope_parsing.py` → `tests/unit/core/test_envelope_parsing.py`
- [ ] `test_typed_envelope.py` → `tests/unit/core/test_typed_envelope.py` (already exists)
- [ ] `test_rate_limiter.py` → `tests/unit/core/test_rate_limiter.py` (already exists)
- [ ] `test_imports.py` → `tests/unit/core/test_imports.py`
- [ ] `test_registry.py` → `tests/unit/core/test_registry.py`

### Integration & System Tests
- [ ] `test_context_forwarding.py` → `tests/integration/test_context_forwarding.py`
- [ ] `test_delegation_flow.py` → `tests/integration/test_delegation_flow.py`
- [ ] `test_agent.py` → `tests/integration/test_agent_flow.py`
- [ ] `test_worker.py` → `tests/integration/test_worker_base.py`
- [ ] `test_worker_audit.py` → `tests/integration/test_worker_audit.py`

### Smoke/Health Tests
- [ ] `test_health.py` → `tests/smoke/test_health.py` (already exists)

### Legacy/Archived
- [ ] `test_queue_in_memory.py` → Archive (deprecated in-memory queue)

## Import Path Updates Required

When migrating tests, update imports from old to new paths:

### Old → New Import Mappings

```python
# Old paths
from agent.manager import ManagerAgent
from agent.orchestrators.leads_orchestrator import LeadsOrchestrator
from agent.operational_agents.rag_agent import RAGAgent
from agent.operational_agents.persistence_agent import PersistenceAgent
from agent.operational_agents.copywriter import CopywriterAgent
from agent.tools.persistence import PersistenceService
from agent.utils.typed_envelope import Envelope

# New paths
from tiers.tier_1.manager.manager_agent import ManagerAgent
from tiers.tier_2.leads_orchestrator.leads_orchestrator import LeadsOrchestrator
from tiers.tier_3.rag_agent.rag_agent import RAGAgent
from tiers.tier_3.persistence_agent.persistence_agent import PersistenceAgent
from tiers.tier_3.copywriter_agent.copywriter_agent import CopywriterAgent
from services.persistence.service import PersistenceService
from core.envelope import Envelope  # or core.envelope.typed_envelope

# Fallback imports (still work for compatibility)
from agent.utils.typed_envelope import Envelope  # forwards to core.envelope
```

## Migration Strategy

### Phase 1: Directory Structure (✅ DONE - Task 16)
- [x] Create `tests/unit/tier_1/`, `tier_2/`, `tier_3/`, `services/`, `core/`
- [x] Create `tests/fixtures/` for shared mock data
- [x] Create `tests/integration/` (already existed)
- [x] Create `tests/smoke/` (already existed)
- [x] Add `__init__.py` to all new directories

### Phase 2: Copy & Update Tests (Tasks 19-21)
- [ ] Copy old test files to new locations
- [ ] Update import paths to use new module locations
- [ ] Update any hardcoded paths in test fixtures
- [ ] Validate syntax and run tests

### Phase 3: Consolidate Fixtures (Task 25)
- [ ] Identify common test fixtures and move to `tests/fixtures/`
- [ ] Create `agents.py` with mock agent fixtures
- [ ] Create `messages.py` with sample envelopes
- [ ] Create `data_generators.py` with test data builders

### Phase 4: Delete Old Files (Task 33)
- [ ] Once all tests are migrated and passing
- [ ] Delete old test files from root `tests/` directory
- [ ] Verify no orphaned imports remain

## Test Organization by Category

### By Tier
- **Tier 1:** Manager initialization, delegation logic, system state
- **Tier 2:** Orchestrator workflows, agent coordination
- **Tier 3:** Agent execution, service interactions, business logic

### By Service
- **Persistence:** Database operations, adapter patterns, transactions
- **Redis:** Streams, consumer groups, message passing
- **Vector DB:** Embeddings, similarity search, caching
- **External APIs:** API client patterns, rate limiting, retries

### By Type
- **Unit:** Fast, isolated, no external dependencies (<100ms each)
- **Integration:** Multi-component, requires Redis/DB (1-5s each)
- **Smoke:** Health checks, import validation (<1s each)

## Running Tests by New Structure

```bash
# All tests
pytest tests/ -v

# By tier
pytest tests/unit/tier_1/ -v        # Tier 1 only
pytest tests/unit/tier_2/ -v        # Tier 2 only
pytest tests/unit/tier_3/ -v        # Tier 3 only

# By service
pytest tests/unit/services/ -v      # All services
pytest tests/unit/core/ -v          # Core framework

# By type
pytest tests/unit/ -v               # Unit tests
pytest tests/integration/ -v        # Integration tests
pytest tests/smoke/ -v              # Smoke tests

# Specific test
pytest tests/unit/tier_3/test_rag_agent.py -v
pytest tests/unit/tier_3/test_rag_agent.py::test_search_returns_results -v

# With coverage
pytest tests/ --cov=tiers --cov=services --cov=core --cov-report=html
```

## Test Naming Conventions

After migration, follow these naming patterns:

```python
# File naming
test_<component>.py              # Single component
test_<component>_<feature>.py    # Component with feature
test_<tier>_<flow>.py           # Multi-tier flow

# Test function naming
test_<method>_<scenario>_<expected>

# Examples
test_search_returns_results
test_search_with_empty_query_returns_empty
test_manager_delegates_to_orchestrator_successfully
test_persistence_agent_writes_and_reads_correctly
```

## Fixture Organization

New fixture structure under `tests/fixtures/`:

```python
# fixtures/agents.py
@pytest.fixture
def manager_agent(redis_client):
    return MockManagerAgent(redis_client)

@pytest.fixture
def rag_agent(redis_client):
    return MockRAGAgent(redis_client)

# fixtures/messages.py
@pytest.fixture
def task_envelope(envelope_factory):
    return envelope_factory(
        source="manager",
        task_id="t1",
        payload={"goal": "discover_leads"}
    )

# fixtures/data_generators.py
def generate_company_data(count=10):
    return [{"id": i, "name": f"Co {i}"} for i in range(count)]
```

## Notes

- **No tests deleted:** Old test files remain during migration for rollback capability
- **Gradual rollout:** Tests migrate incrementally alongside code changes
- **Import compatibility:** Old imports still work via fallback mechanisms
- **CI/CD ready:** New structure compatible with GitHub Actions workflows

## See Also

- `ARCHITECTURE.md` - System architecture overview
- `deployment/README.md` - Docker and deployment setup
- `pytest.ini` - Pytest configuration (root of workspace)

---

**Created:** Task 16 - Test Directory Reorganization  
**Status:** Directory structure complete, migration mapping ready  
**Next:** Tasks 19-21 will update tier imports and facilitate test migration
