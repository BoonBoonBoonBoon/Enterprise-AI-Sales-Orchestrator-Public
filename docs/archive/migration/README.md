# Migration Documentation Index

This directory contains all documentation related to the agent folder reorganization and migration to the three-tier architecture.

## Quick Links

### Migration Guides
- **[CLEANUP_SUMMARY.md](./CLEANUP_SUMMARY.md)** - Complete summary of the cleanup work done on Nov 16, 2025
- **[AGENT_FOLDER_REORGANIZATION.md](./AGENT_FOLDER_REORGANIZATION.md)** - Detailed reorganization plan and rationale
- **[FOLDER_CLEANUP_PLAN.md](./FOLDER_CLEANUP_PLAN.md)** - Phase-by-phase cleanup execution plan
- **[MIGRATION_VERIFICATION_REPORT.md](./MIGRATION_VERIFICATION_REPORT.md)** - Verification and testing results

### Analysis & Design
- **[overview.md](./overview.md)** - High-level migration overview
- **[legacy-analysis.md](./legacy-analysis.md)** - Analysis of legacy code structure
- **[design-compliance.md](./design-compliance.md)** - Design compliance documentation
- **[file-system-migration.md](./file-system-migration.md)** - File system migration details
- **[deprecations.md](./deprecations.md)** - Deprecation paths and timelines

## Archive Reference

The complete original `agent/` folder is preserved at:
- **Location**: `../../archive/legacy-agent/`
- **Guide**: `../../archive/legacy-agent/MIGRATION_GUIDE.md`
- **Structure**: `../../archive/legacy-agent/README.md`

## What Happened

### November 16, 2025 - Complete Agent Folder Cleanup

**Status**: ✅ Complete

1. **Archived** entire `agent/` directory → `archive/legacy-agent/` (200+ files)
2. **Deleted** the `agent/` folder from active codebase
3. **Migrated** key components:
   - Harness → `core/harness/`
   - Schemas → `core/schemas/`
   - Utils → `core/utils/`
   - Tools → `services/persistence/tools/`, `services/external_apis/tools/`
   - Tiers → `tiers/tier_1/`, `tiers/tier_2/`, `tiers/tier_3/`

4. **Fixed** import paths in core/harness subdirectories
5. **Organized** documentation into proper structure

## New Architecture

```
tiers/
├── tier_1/manager/          # Strategic planning & delegation
├── tier_2/                  # Orchestrators (leads, outreach, audit, inbound, control)
└── tier_3/                  # Operational agents (rag, persistence, copywriter, sequencer)

core/
├── harness/                 # Execution framework
├── schemas/                 # Data models
├── utils/                   # Shared utilities
├── envelope/                # Message format
├── exceptions/              # Central exceptions
└── deep_agents/            # AI planning

services/
├── persistence/             # Database layer
├── redis/                   # Message broker
├── external_apis/           # Third-party integrations
└── vector_db/              # Embeddings & RAG

config/
├── profiles/                # Environment configs (dev, staging, prod)
└── settings.py             # Global settings
```

## Remaining Work

See `CLEANUP_SUMMARY.md` for details, but key items:

### High Priority
1. Migrate `control_orchestrator` to `tiers/tier_2/`
2. Migrate `multi_channel_sequencer` to `tiers/tier_3/`

### Medium Priority
3. Complete tool migrations to `services/`
4. Consolidate registries into `core/registry/`
5. Migrate manager tools to `tiers/tier_1/manager/tools/`
6. Move config to `config/profiles/`

## Import Changes

### Before (Deprecated)
```python
from agent.manager import ManagerAgent
from agent.orchestrators.leads_orchestrator import LeadsOrchestrator
from agent.operational_agents.rag_agent import RAGAgent
from agent.tools.supabase_tools import SupabaseClient
from agent.harness import AgentHarness
```

### After (Current)
```python
from tiers.tier_1.manager import ManagerAgent
from tiers.tier_2.leads_orchestrator import LeadsOrchestrator
from tiers.tier_3.rag_agent import RAGAgent
from services.persistence.tools.supabase_tools import SupabaseClient
from core.harness import AgentHarness
```

## Benefits

1. **Kubernetes-Ready**: Clear service boundaries for K8s Deployments
2. **Independent Scaling**: Each tier scales separately
3. **Better Testing**: Isolated component testing
4. **Clear Ownership**: No ambiguity about code location
5. **Maintainability**: Easier onboarding and navigation

## Related Documentation

- **Architecture**: `../architecture/`
- **Getting Started**: `../getting-started/`
- **Reference**: `../reference/`
- **Updates**: `../updates/`

---

**Last Updated**: November 16, 2025  
**Status**: Migration Complete, Testing Pending
