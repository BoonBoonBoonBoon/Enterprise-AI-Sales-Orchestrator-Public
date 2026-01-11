# Agent Package Migration Guide

> **Status:** In Progress  
> **Impact:** ~50 import statements across test and production code  
> **Priority:** Medium (system functions, but creates technical debt)

## Overview

The `agent/` package is a legacy compatibility shim that should be fully migrated to the canonical module structure. This document tracks the migration status and provides the mapping for all legacy imports.

## Import Mapping

### Core Harness (`agent.harness.*` → `core.harness.*`)

| Legacy Import                                                        | Canonical Import                                                    |
| -------------------------------------------------------------------- | ------------------------------------------------------------------- |
| `from agent.harness import AgentHarness, HarnessConfig`              | `from core.harness import AgentHarness, HarnessConfig`              |
| `from agent.harness.retry_strategies import ExponentialBackoffRetry` | `from core.harness.retry_strategies import ExponentialBackoffRetry` |
| `from agent.harness.observability import SimpleLoggingObservability` | `from core.observability import SimpleLoggingObservability`         |
| `from agent.harness.observability import OpenTelemetryObservability` | `from core.observability import OpenTelemetryObservability`         |
| `from agent.harness.observability import DatadogObservability`       | `from core.observability import DatadogObservability`               |
| `from agent.harness.quota_management import InMemoryQuota`           | `from core.harness.quota_management import InMemoryQuota`           |

### Redis Tools (`agent.tools.redis.*` → `services.redis.*`)

| Legacy Import                                             | Canonical Import                                       |
| --------------------------------------------------------- | ------------------------------------------------------ |
| `from agent.tools.redis.client import RedisPubSub`        | `from services.redis.pubsub import RedisPubSub`        |
| `from agent.tools.redis.client import RedisStreamsClient` | `from services.redis.client import RedisStreamsClient` |

### Persistence Tools (`agent.tools.persistence.*` → `services.persistence.*`)

| Legacy Import                                                                    | Canonical Import                                                         |
| -------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `from agent.tools.persistence.service import PersistenceService`                 | `from services.persistence.service import PersistenceService`            |
| `from agent.tools.persistence.service import ReadOnlyPersistenceFacade`          | `from services.persistence.service import ReadOnlyPersistenceFacade`     |
| `from agent.tools.persistence.service import InMemoryAdapter`                    | `from services.persistence.adapters import InMemoryAdapter`              |
| `from agent.tools.persistence.adapters.in_memory_adapter import InMemoryAdapter` | `from services.persistence.adapters import InMemoryAdapter`              |
| `from agent.tools.persistence.exceptions import PersistencePermissionError`      | `from services.persistence.exceptions import PersistencePermissionError` |
| `from agent.tools.persistence.exceptions import TableNotAllowedError`            | `from services.persistence.exceptions import TableNotAllowedError`       |

### Operational Agents (`agent.operational_agents.*` → `tiers.tier_3.*`)

| Legacy Import                                                                               | Canonical Import                                                                |
| ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `from agent.operational_agents.rag_agent.rag_agent import RAGAgent`                         | `from tiers.tier_3.rag_agent.rag_agent import RAGAgent`                         |
| `from agent.operational_agents.rag_agent.rag_agent_new import RAGAgent`                     | `from tiers.tier_3.rag_agent.rag_agent import RAGAgent`                         |
| `from agent.operational_agents.rag_agent.rag_agent_harness import RAGAgentHarness`          | `from tiers.tier_3.rag_agent.rag_agent_harness import RAGAgentHarness`          |
| `from agent.operational_agents.rag_agent.consumer_new import RAGConsumer`                   | `from tiers.tier_3.rag_agent.consumer import RAGConsumer`                       |
| `from agent.operational_agents.persistence_agent.persistence_agent import PersistenceAgent` | `from tiers.tier_3.persistence_agent.persistence_agent import PersistenceAgent` |
| `from agent.operational_agents.persistence_agent.facade import PersistenceFacade`           | `from tiers.tier_3.persistence_agent.facade import PersistenceFacade`           |
| `from agent.operational_agents.db_write_agent.db_write_agent import create_in_memory_agent` | `from tiers.tier_3.persistence_agent.factory import create_in_memory_agent`     |
| `from agent.operational_agents.factory import create_persistence_agent`                     | `from tiers.tier_3.persistence_agent.factory import create_persistence_agent`   |
| `from agent.operational_agents.factory import create_rag_agent`                             | `from tiers.tier_3.rag_agent.factory import create_rag_agent`                   |

### Manager (`agent.manager.*` → `tiers.tier_1.manager.*`)

| Legacy Import                                                            | Canonical Import                                                                |
| ------------------------------------------------------------------------ | ------------------------------------------------------------------------------- |
| `from agent.manager.manager_agent import ManagerAgent`                   | `from tiers.tier_1.manager.manager_agent import ManagerAgent`                   |
| `from agent.manager.deep_agent_factory import create_manager_deep_agent` | `from tiers.tier_1.manager.deep_agent_factory import create_manager_deep_agent` |

### Configuration (`agent.config.*` → `config.*`)

| Legacy Import                                                     | Canonical Import                                            |
| ----------------------------------------------------------------- | ----------------------------------------------------------- |
| `from agent.config.persistence_config import get_write_allowlist` | `from config.persistence_config import get_write_allowlist` |
| `from agent.config.persistence_config import get_read_allowlist`  | `from config.persistence_config import get_read_allowlist`  |

## Files Requiring Migration

### Production Code (Priority: High)

| File                                                    | Legacy Imports                     | Status                |
| ------------------------------------------------------- | ---------------------------------- | --------------------- |
| `tiers/tier_1/manager/consumer.py`                      | `agent.tools.redis.client`         | ⏳ Pending            |
| `tiers/tier_2/leads_orchestrator/leads_orchestrator.py` | Commented out                      | ✅ OK (comments only) |
| `tiers/tier_3/persistence_agent/persistence_agent.py`   | `agent.operational_agents.factory` | ⏳ Pending            |

### Test Code (Priority: Medium)

| File                                               | Count       | Status     |
| -------------------------------------------------- | ----------- | ---------- |
| `tests/validation/validate_harness.py`             | 9 imports   | ⏳ Pending |
| `tests/validation/validate_manager_deep_agents.py` | 2 imports   | ⏳ Pending |
| `tests/validation/verify_redis_streams.py`         | 1 import    | ⏳ Pending |
| `tests/unit/tier_3/test_rag_*.py`                  | 15+ imports | ⏳ Pending |
| `tests/unit/tier_3/test_persistence_agent.py`      | 4 imports   | ⏳ Pending |
| `tests/unit/tier_3/test_db_write_agent.py`         | 1 import    | ⏳ Pending |

## Migration Steps

1. **Verify canonical paths exist** - Ensure all target modules exist and export the required symbols
2. **Update production code first** - Fix `tiers/` imports (3 files)
3. **Update test files** - Fix `tests/` imports (~15 files)
4. **Run full test suite** - Verify no regressions
5. **Remove agent/ package** - Delete `agent/` folder entirely
6. **Update .gitignore** - Remove any agent-related entries

## Automated Migration Script

```python
# scripts/utils/migrate_agent_imports.py
import re
from pathlib import Path

MAPPINGS = {
    r'from agent\.harness import': 'from core.harness import',
    r'from agent\.harness\.': 'from core.harness.',
    r'from agent\.tools\.redis\.': 'from services.redis.',
    r'from agent\.tools\.persistence\.': 'from services.persistence.',
    r'from agent\.operational_agents\.rag_agent\.': 'from tiers.tier_3.rag_agent.',
    r'from agent\.operational_agents\.persistence_agent\.': 'from tiers.tier_3.persistence_agent.',
    r'from agent\.operational_agents\.factory': 'from tiers.tier_3.factory',
    r'from agent\.manager\.': 'from tiers.tier_1.manager.',
    r'from agent\.config\.': 'from config.',
}

def migrate_file(filepath: Path, dry_run: bool = True):
    content = filepath.read_text()
    new_content = content

    for pattern, replacement in MAPPINGS.items():
        new_content = re.sub(pattern, replacement, new_content)

    if new_content != content:
        if dry_run:
            print(f"Would update: {filepath}")
        else:
            filepath.write_text(new_content)
            print(f"Updated: {filepath}")

# Usage: python -c "from scripts.utils.migrate_agent_imports import migrate_file; ..."
```

## Notes

- The `agent/utils/typed_envelope.py` was already deleted (moved to `core/envelope/`)
- Some imports in commented-out code can be ignored or updated for documentation accuracy
- The `agent/__init__.py` now raises `DeprecationWarning` to surface legacy usage

---

_Last Updated: January 2026_
