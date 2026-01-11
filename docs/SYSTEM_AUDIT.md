# 📊 Agentic System - Codebase Priority Audit

**Date:** December 12, 2025  
**Purpose:** Identify essential infrastructure, useful components, and deprecated items for cleanup.

---

## 🔴 HIGH PRIORITY (Core Infrastructure)

### `/core/` - Central Framework ⭐⭐⭐
| Path | Purpose | Status |
|------|---------|--------|
| `core/envelope/` | Message envelope system (typed_envelope.py, envelope.py) | **ESSENTIAL** |
| `core/harness/agent_harness.py` | Base harness for all agents | **ESSENTIAL** |
| `core/harness/circuit_breaker.py` | Fault tolerance | **ESSENTIAL** |
| `core/harness/checkpointing/` | State persistence (redis, postgres, s3) | **ESSENTIAL** |
| `core/harness/retry_strategies/` | Backoff strategies | **ESSENTIAL** |
| `core/observability/` | Logging, metrics, audit trails | **ESSENTIAL** |
| `core/schemas/` | Pydantic schemas for all agents | **ESSENTIAL** |
| `core/utils/graceful_shutdown.py` | Worker shutdown handling | **ESSENTIAL** |
| `core/utils/rate_limiter.py` | API rate limiting | **ESSENTIAL** |
| `core/utils/tracing.py` | Distributed tracing | **ESSENTIAL** |

### `/tiers/` - Agent Architecture ⭐⭐⭐
| Path | Purpose | Status |
|------|---------|--------|
| `tiers/tier_1/manager/manager_agent.py` | Strategic routing | **ESSENTIAL** |
| `tiers/tier_1/manager/manager_agent_harness.py` | Manager harness | **ESSENTIAL** |
| `tiers/tier_1/manager/consumer.py` | Redis consumer | **ESSENTIAL** |
| `tiers/tier_2/leads_orchestrator/` | Lead workflow orchestration | **ESSENTIAL** |
| `tiers/tier_2/base_orchestrator.py` | Base class for orchestrators | **ESSENTIAL** |
| `tiers/tier_3/rag_agent/` | RAG queries (consumer, harness, worker) | **ESSENTIAL** |
| `tiers/tier_3/persistence_agent/` | DB writes (consumer, harness, write_worker) | **ESSENTIAL** |
| `tiers/tier_3/copywriter_agent/` | Content generation | **ESSENTIAL** |
| `tiers/tier_3/factory.py` | Agent factory | **ESSENTIAL** |

### `/services/` - Service Layer ⭐⭐⭐
| Path | Purpose | Status |
|------|---------|--------|
| `services/redis/client.py` | RedisStreamsClient | **ESSENTIAL** |
| `services/redis/streams.py` | Stream configuration | **ESSENTIAL** |
| `services/redis/stream_registry.py` | Stream naming | **ESSENTIAL** |
| `services/persistence/service.py` | Persistence facade | **ESSENTIAL** |
| `services/persistence/adapters/supabase_adapter.py` | Supabase integration | **ESSENTIAL** |
| `services/persistence/adapters/in_memory_adapter.py` | Testing adapter | **ESSENTIAL** |

### Root Config Files ⭐⭐⭐
| File | Purpose | Status |
|------|---------|--------|
| `requirements.txt` | Dependencies | **ESSENTIAL** |
| `.env.example` | Environment template | **ESSENTIAL** |
| `docker-compose.yml` | Main compose file | **ESSENTIAL** |
| `pytest.ini` | Test configuration | **ESSENTIAL** |
| `.gitignore` | Git exclusions | **ESSENTIAL** |

---

## 🟡 LOW PRIORITY (Useful but Not Essential)

### `/deployment/` - Observability Stack
| Path | Purpose | Status |
|------|---------|--------|
| `deployment/docker/Dockerfile.worker` | Worker image | Useful |
| `deployment/grafana/` | Dashboards | Useful |
| `deployment/prometheus/` | Metrics config | Useful |
| `deployment/loki/` | Log aggregation | Useful |
| `deployment/promtail/` | Log shipping | Useful |
| `deployment/tempo/` | Tracing | Useful |
| `deployment/docker-compose.observability.yml` | Observability stack | Useful |

### `/scripts/` - Utility Scripts (Keep Selectively)
| Path | Purpose | Status |
|------|---------|--------|
| `scripts/startup/` | Consumer startup scripts | **KEEP** |
| `scripts/verify_production_ready.py` | Health checks | **KEEP** |
| `scripts/start_all_consumers.py` | Multi-consumer start | **KEEP** |
| `scripts/ops.py` | Operations CLI | **KEEP** |
| `scripts/health_check.py` | Basic health | **KEEP** |
| `scripts/redis/` | Redis utilities | Useful |
| `scripts/diagnostics/` | Stream diagnostics | Useful |

### `/docs/` - Documentation (Keep Core)
| Path | Purpose | Status |
|------|---------|--------|
| `docs/architecture/` | Architecture docs | **KEEP** |
| `docs/E2E_TESTING.md` | E2E guide | **KEEP** |
| `docs/guides/` | How-to guides | **KEEP** |
| `docs/README.md` | Doc index | **KEEP** |

### `/tests/` - Test Suite (Keep Core)
| Path | Purpose | Status |
|------|---------|--------|
| `tests/unit/` | Unit tests | **KEEP** |
| `tests/integration/` | Integration tests | **KEEP** |
| `tests/conftest.py` | Pytest fixtures | **KEEP** |
| `tests/smoke/` | Smoke tests | **KEEP** |

### `/config/` - Configuration
| Path | Purpose | Status |
|------|---------|--------|
| `config/settings.py` | App settings | Useful |
| `config/persistence_config.py` | DB config | Useful |

### Other Low Priority
| Path | Purpose | Status |
|------|---------|--------|
| `k8s/` | K8s manifests (future use) | Keep for later |
| `int-frontend/` | Streamlit admin UI | Useful for debugging |
| `examples/` | Demo scripts | Useful for onboarding |

---

## ⚫ ZERO PRIORITY (Delete Candidates)

### `/archive/` - Entire Folder 🗑️
| Path | Reason | Action |
|------|--------|--------|
| `archive/legacy-agent/` | Old agent structure, fully migrated | **DELETE** |
| `archive/legacy-tools/` | Single deprecated file | **DELETE** |
| `archive/debug/` | Old debug captures | **DELETE** |
| `archive/test-reports/` | Historical test results | **DELETE** |
| `archive/migration-logs/` | Completed migration logs | **DELETE** |
| `archive/task-tracking/` | Completed task docs | **DELETE** |
| `archive/analysis/` | Old analysis | **DELETE** |
| `archive/planning-docs/` | Old planning | **DELETE** |
| `archive/deployment-history/` | Old deployment logs | **DELETE** |
| `archive/scripts/` | Old startup script | **DELETE** |
| `archive/monitoring_legacy_2025-11-20/` | Old monitoring | **DELETE** |

### `/utils/` - Compatibility Shims 🗑️
| Path | Reason | Action |
|------|--------|--------|
| `utils/__init__.py` | Just re-exports `core/utils` | **DELETE** |
| `utils/redis.py` | Just re-exports `services/redis` | **DELETE** |

### `/core/deep_agents/` - Empty Module 🗑️
| Path | Reason | Action |
|------|--------|--------|
| `core/deep_agents/__init__.py` | Empty placeholder, `__all__ = []` | **DELETE** |

### `/platform_monitoring/` - Deprecated 🗑️
| Path | Reason | Action |
|------|--------|--------|
| `platform_monitoring/exporters.py` | Replaced by `core/observability` | **DELETE** |
| `platform_monitoring/README_DEPRECATED.md` | Self-declares deprecated | **DELETE** |

### Duplicate/Old Files in `/tiers/`
| Path | Reason | Action |
|------|--------|--------|
| `tiers/tier_1/manager/manager_agent_backup.py` | Backup file | **DELETE** |
| `tiers/tier_2/QuickRM.md` | Unclear purpose | **REVIEW/DELETE** |
| `tiers/tier_1/manager/QuickRM.md` | Unclear purpose | **REVIEW/DELETE** |

### Scripts to Delete (Outdated/One-off)
| Path | Reason | Action |
|------|--------|--------|
| `scripts/debugging/` | Debug one-offs | **DELETE** |
| `scripts/maintenance/fix_emojis*.py` | One-time fixes | **DELETE** |
| `scripts/testing/view_cloud*.py` | Old cloud testing | **DELETE** |
| `scripts/fresh_test.py` | One-off test | **DELETE** |
| `scripts/mock_ingest.py` | Old mock script | **DELETE** |
| `scripts/*.sql` | SQL scripts (move to migrations) | **REVIEW** |
| `scripts/supabase-edge-function-fixed.ts` | Orphan TypeScript | **DELETE** |

### Root-Level Cleanup
| File | Reason | Action |
|------|--------|--------|
| `Dockerfile` | Duplicate of `deployment/docker/Dockerfile.worker` | **DELETE** |
| `Dockerfile.worker` | Duplicate of `deployment/docker/Dockerfile.worker` | **DELETE** |
| `docker-compose.aws.yml` | Not used (k8s preferred) | **REVIEW** |
| `docker-compose.azure.yml` | Not used | **REVIEW** |
| `docker-compose.override.yml` | Local overrides only | Keep if used |
| `.coverage` | Generated file | **DELETE** |
| `htmlcov/` | Generated coverage HTML | **DELETE** |

### Docs Cleanup
| Path | Reason | Action |
|------|--------|--------|
| `docs/COMPLETE_TEST_REPORT.md` | Historical | **DELETE** |
| `docs/RAG_AGENT_TEST_EXECUTION.md` | Historical | **DELETE** |
| `docs/RAG_TEST_SUMMARY.md` | Historical | **DELETE** |
| `docs/ORCHESTRATOR_TEST_RESULTS.md` | Historical | **DELETE** |
| `docs/changelogs/` | Old changelogs | **REVIEW** |
| `docs/updates/` | Old updates | **REVIEW** |
| `docs/debugging/` | Debug docs | **REVIEW** |

### Tests Cleanup
| Path | Reason | Action |
|------|--------|--------|
| `tests/manual_e2e_test.py` | Duplicate of integration tests | **DELETE** |
| `tests/systemformat.md` | Orphan doc | **DELETE** |
| `tests/TEST_MIGRATION_MAP.md` | Completed migration | **DELETE** |
| `tests/validation/` | Check if empty/stale | **REVIEW** |
| `tests/end-to-end/` | Check if empty/stale | **REVIEW** |

---

## 📋 Summary

| Priority | Folder Count | Action |
|----------|-------------|--------|
| 🔴 HIGH | ~15 folders | **Protect & maintain** |
| 🟡 LOW | ~12 folders | **Keep, review periodically** |
| ⚫ ZERO | ~25+ items | **Delete or archive externally** |

---

## 🧹 Quick Delete Commands (PowerShell)

```powershell
# Remove archive folder entirely
Remove-Item -Recurse -Force "archive"

# Remove deprecated modules
Remove-Item -Recurse -Force "utils"
Remove-Item -Recurse -Force "platform_monitoring"
Remove-Item -Recurse -Force "core/deep_agents"

# Remove generated files
Remove-Item -Recurse -Force "htmlcov"
Remove-Item -Force ".coverage"

# Remove duplicate Dockerfiles at root
Remove-Item -Force "Dockerfile"
Remove-Item -Force "Dockerfile.worker"

# Remove backup files
Remove-Item -Force "tiers/tier_1/manager/manager_agent_backup.py"

# Remove orphan docs
Remove-Item -Force "tests/manual_e2e_test.py"
Remove-Item -Force "tests/systemformat.md"
Remove-Item -Force "tests/TEST_MIGRATION_MAP.md"
```

---

## ✅ Post-Cleanup Verification

After cleanup, run:
```powershell
# Verify imports still work
python -c "from core.envelope import task, result; print('✓ core.envelope')"
python -c "from services.redis import RedisStreamsClient; print('✓ services.redis')"
python -c "from tiers.tier_3.factory import create_rag_agent; print('✓ tiers.tier_3')"

# Run smoke tests
pytest tests/smoke/ -v

# Verify no broken imports
python -m py_compile tiers/tier_2/leads_orchestrator/consumer.py
python -m py_compile tiers/tier_3/rag_agent/consumer.py
```
