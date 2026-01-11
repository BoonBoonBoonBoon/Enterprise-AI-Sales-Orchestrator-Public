# Scripts Migration Mapping

Organization of existing scripts into the new categorized structure.

## Migration Status: Task 18

**Status:** Directory structure created, scripts to be migrated

## Script Organization Map

### Startup Scripts (`scripts/startup/`)

**Purpose:** System initialization and setup

- [x] `generate_mock_leads.py` - Generate test lead data
- [x] `ingest_cli.py` - CLI task enqueuing
- [x] `mock_ingest.py` - Mock ingestion helper
- [ ] `workflow_lead_upsert_example.py` - Workflow example (archive or demo?)

**Notes:**
- These run during system startup or manual initialization
- Can be one-time or repeated
- Generate test data or configure initial state

---

### Monitoring Scripts (`scripts/monitoring/`)

**Purpose:** Health checks, observability, diagnostics

- [x] `health_check.py` - Service health verification
- [x] `health_server.py` - HTTP health endpoint (port 8080)
- [x] `redis_health.py` - Redis connectivity checks
- [x] `streams_health.py` - Stream status monitoring
- [x] `redis_stream_smoke.py` - Stream smoke tests
- [x] `redis_smoke_test.py` - Redis smoke test
- [x] `test_redis_cloud.py` - Redis Cloud connectivity test

**Diagnostic Scripts (also monitoring):**
- [x] `diagnose_supabase.py` - Supabase diagnostics
- [x] `check_rag_tasks.py` - RAG stream diagnostics
- [x] `check_copy_tasks.py` - Copywriter stream diagnostics
- [x] `check_audit.py` - Audit diagnostics
- [x] `decode_supabase_jwt.py` - JWT decoding utility

**Demo Scripts (monitoring/education):**
- [x] `rag_demo.py` - RAG agent demonstration
- [x] `orchestrator_demo.py` - Orchestrator demonstration
- [x] `orchestrator_redis_demo.py` - Orchestrator Redis demo
- [x] `orchestrator_write_demo.py` - Orchestrator write demo

**Notes:**
- Provide operational visibility
- Used for debugging and troubleshooting
- Can be run continuously or periodically

---

### Maintenance Scripts (`scripts/maintenance/`)

**Purpose:** Operations, cleanup, recovery

- [x] `streams_group_reset.py` - Reset consumer groups
- [x] `dlq_requeue.py` - Reprocess DLQ messages
- [x] `dlq_automation.py` - Automated DLQ handling
- [x] `check_namespace.py` - Stream namespace validation

**Data Management:**
- [x] `migrate_db_write.py` - Database migration
- [x] `migrate_redis_streams.py` - Redis Streams migration
- [x] `workflow_state.py` - Workflow state utilities
- [x] `test_workflow_state.py` - Workflow state tests

**Query/Report Scripts:**
- [x] `get_lead_by_email.py` - Query utility
- [x] `run_live_queries.py` - Live query execution
- [x] `persistence_write_smoke.py` - Persistence write test
- [x] `supabase_smoke.py` - Supabase smoke test

**Performance/Testing:**
- [x] `streams_write_benchmark.py` - Benchmark streams write performance
- [x] `test_complete_flow.py` - End-to-end flow test

**CI/Guard:**
- [x] `ci_guard_persistence.py` - CI persistence checks
- [x] `ops.py` - Operations utilities

**Debug/Troubleshooting:**
- [x] `debug_orchestrator.py` - Orchestrator debugging
- [x] `enqueue_copy_task.py` - Manual task enqueuing

**Notes:**
- Run on-demand for maintenance
- Handle special cases and recovery
- Fix system state issues

---

## Migration Strategy

### Phase 1: Create Structure (✅ DONE - Task 18)
- [x] Create `scripts/startup/`, `monitoring/`, `maintenance/` directories
- [x] Create `__init__.py` files for each directory
- [x] Create comprehensive `README.md`
- [x] Create this mapping document

### Phase 2: Organize Scripts (Next)
- [ ] Move startup scripts:
  - `generate_mock_leads.py` → `scripts/startup/`
  - `ingest_cli.py` → `scripts/startup/`
  - `mock_ingest.py` → `scripts/startup/`

- [ ] Move monitoring scripts:
  - `health_check.py` → `scripts/monitoring/`
  - `health_server.py` → `scripts/monitoring/`
  - `redis_health.py` → `scripts/monitoring/`
  - `streams_health.py` → `scripts/monitoring/`
  - `*_demo.py` → `scripts/monitoring/demos/` (optional subdirectory)
  - `*_smoke*.py` → `scripts/monitoring/`
  - `diagnose_*.py` → `scripts/monitoring/`
  - `check_*.py` → `scripts/monitoring/`

- [ ] Move maintenance scripts:
  - `streams_group_reset.py` → `scripts/maintenance/`
  - `dlq_*.py` → `scripts/maintenance/`
  - `migrate_*.py` → `scripts/maintenance/`
  - `workflow_*.py` → `scripts/maintenance/`
  - `*_benchmark.py` → `scripts/maintenance/`
  - `test_complete_flow.py` → `scripts/maintenance/`

### Phase 3: Clean Symlinks/Forwards (If needed)
- [ ] Update imports in scripts that reference each other
- [ ] Create forward-compatible imports in root `scripts/` if needed
- [ ] Ensure Docker and CI/CD find scripts in new locations

### Phase 4: Update References
- [ ] Update `docker-compose.yml` to reference new script paths
- [ ] Update CI/CD workflows if they reference scripts
- [ ] Update any hardcoded script references in code

## Demoing vs. Monitoring

Some scripts are both demos and monitoring tools:

### Demo Scripts (Educational)
- Show how system works
- Often interactive
- Examples: `rag_demo.py`, `orchestrator_demo.py`

**Suggested Location:** `scripts/monitoring/demos/` (optional subdirectory for clarity)

### Monitor Scripts (Operational)
- Check system health
- Provide diagnostics
- Examples: `health_check.py`, `redis_health.py`

**Location:** `scripts/monitoring/`

---

## Script Dependencies

Scripts in each category may depend on:

### Common Dependencies
- `services/redis/` - Redis client/streams
- `services/persistence/` - Database client
- `core/envelope/` - Message format
- `tiers/` - Agent/orchestrator modules

### Import Updates Needed

When scripts are moved, verify imports work:

```python
# Old paths (will still work via fallback)
from agent.utils.envelope import Envelope
from agent.tools.persistence import PersistenceService

# New paths (preferred)
from core.envelope import Envelope
from services.persistence import PersistenceService
```

---

## Testing After Migration

### Verify Imports

```bash
python -m py_compile scripts/startup/generate_mock_leads.py
python -m py_compile scripts/monitoring/health_check.py
python -m py_compile scripts/maintenance/streams_group_reset.py
```

### Test Execution

```bash
# Startup
python scripts/startup/generate_mock_leads.py --help

# Monitoring
python scripts/monitoring/health_check.py --help
docker compose exec manager python scripts/monitoring/health_server.py --help

# Maintenance
python scripts/maintenance/streams_group_reset.py --help
```

### Docker References

```bash
# In docker-compose.yml, ensure paths work
docker compose exec manager python scripts/monitoring/health_check.py

# If scripts directory is volume-mounted
docker run -v $(pwd):/app agentic/worker python /app/scripts/monitoring/health_check.py
```

---

## Optional: Demo Subdirectory

Consider creating `scripts/monitoring/demos/` for educational scripts:

```
scripts/monitoring/
├── health_check.py
├── health_server.py
├── redis_health.py
├── streams_health.py
├── demos/                    # Educational
│   ├── rag_demo.py
│   ├── orchestrator_demo.py
│   ├── orchestrator_redis_demo.py
│   └── orchestrator_write_demo.py
└── __init__.py
```

**Pros:**
- Clear separation between operations and learning
- Easier to exclude demos from production

**Cons:**
- Additional level of nesting
- Less common usage pattern

**Recommendation:** Keep demos in `monitoring/` for now, organize later if needed

---

## Notes on Legacy Scripts

Some scripts may be:
- **Deprecated:** No longer used (mark for archival)
- **LLM-specific:** Only for certain agent types
- **Testing:** Only for CI/CD workflows

Review these before migration:
- `encode_supabase_jwt.py` (if it exists)
- Version-specific migration scripts
- One-off troubleshooting scripts

---

## See Also

- `scripts/README.md` - User-facing documentation
- `tests/README.md` - Testing structure
- `deployment/README.md` - Deployment procedures

---

**Created:** Task 18 - Scripts organization mapping  
**Status:** Migration ready, execution pending  
**Total Scripts:** ~40 scripts across 3 categories
