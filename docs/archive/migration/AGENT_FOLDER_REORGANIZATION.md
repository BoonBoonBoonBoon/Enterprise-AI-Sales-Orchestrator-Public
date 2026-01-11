# Complete Agent Folder Reorganization Plan

## Current State Analysis

### 📁 What's in `agent/` That Needs Reorganization

```
agent/
├── tools/                          ← NEEDS REDISTRIBUTION
│   ├── data_coordinator.py         (DEPRECATED - RAG fallback)
│   ├── supabase_tools.py           (Data access - move to services/)
│   ├── db_write/                   (DB operations - move to services/)
│   ├── delivery/                   (Delivery service - move to services/)
│   ├── persistence/                (Persistence helpers - move to services/)
│   ├── redis/                      (Redis tools - already in services/!)
│   ├── registry.py                 (Tool discovery - consolidate)
│   └── README.md                   (Tool guidelines - keep reference)
│
├── manager/                        ← PARTIALLY DEPRECATED
│   ├── manager_agent.py            (Move to tiers/tier_1/manager/)
│   ├── manager_agent_harness.py    (Move to tiers/tier_1/manager/)
│   ├── consumer.py                 (Move to tiers/tier_1/manager/)
│   ├── tools/                      (Move to tiers/tier_1/manager/tools/)
│   │   └── delegation_tools.py     (Manager-specific tools)
│   ├── deep_agent_factory.py       (Keep or move to core/?)
│   └── shortcut_registry.py        (Consolidate registries)
│
├── config/                         ← SHOULD BE IN config/profiles/
│   └── persistence_config.py       (Database config)
│
├── Flow_of_sys.md                  ← DOCUMENTATION (archive or delete)
├── Improvements.md                 ← DOCUMENTATION (archive or delete)
└── Infastructure/                  ← LEGACY (archive)
    ├── dispatcher/
    ├── orchestration_engine/
    ├── queue/
    └── worker/
```

### ✅ Already Correct (Don't Touch)
- `harness/` → Deprecated (points to core/harness)
- `schemas/` → Deprecated (points to core/schemas)
- `utils/` → Deprecated (points to core/utils)
- `orchestrators/` → Mostly deprecated (most moved to tiers/tier_2/)
- `operational_agents/` → Mostly deprecated (most moved to tiers/tier_3/)

---

## 🎯 Reorganization Strategy

### TIER 1: DISTRIBUTE `agent/tools/`

The tools fall into different categories:

#### **Category A: Database/Persistence Tools** → `services/persistence/tools/`
```
Current Location:
agent/tools/
├── db_write/
├── persistence/
└── supabase_tools.py

New Location:
services/persistence/tools/
├── __init__.py
├── db_write/
├── supabase_tools.py
└── README.md (updated)
```

**Files to move:**
- [ ] `agent/tools/db_write/` → `services/persistence/tools/db_write/`
- [ ] `agent/tools/persistence/` → `services/persistence/tools/persistence/`
- [ ] `agent/tools/supabase_tools.py` → `services/persistence/tools/supabase_tools.py`

**Action:**
```bash
cp -r agent/tools/db_write services/persistence/tools/
cp -r agent/tools/persistence services/persistence/tools/
cp agent/tools/supabase_tools.py services/persistence/tools/
```

---

#### **Category B: Delivery/External Service Tools** → `services/external_apis/tools/`
```
Current Location:
agent/tools/delivery/

New Location:
services/external_apis/tools/
├── delivery/
└── __init__.py
```

**Files to move:**
- [ ] `agent/tools/delivery/` → `services/external_apis/tools/delivery/`

---

#### **Category C: Data Coordination (DEPRECATED)** → `archive/`
```
Current:
agent/tools/data_coordinator.py (marked as DEPRECATED in file)

Action: Move to archive for reference
archive/legacy-tools/
└── data_coordinator.py
```

**Files to move:**
- [ ] `agent/tools/data_coordinator.py` → `archive/legacy-tools/data_coordinator.py`

---

#### **Category D: Redis Tools** → Already in correct place!
```
Note: agent/tools/redis/ might exist but redis/ is already in services/redis/
- Check if duplicate
- If yes, keep services/redis/ version, remove agent/tools/redis/
- If no, this category doesn't apply
```

---

#### **Category E: Tool Registry/Discovery** → `core/registry/`
```
Current:
agent/tools/registry.py

New Location:
core/registry/
├── tool_registry.py          (consolidated tool discovery)
└── orchestrator_registry.py
└── agent_registry.py
```

**Files to move:**
- [ ] `agent/tools/registry.py` → `core/registry/tool_registry.py` (or consolidate)

---

#### **Category F: Tool Documentation** → `docs/`
```
Current:
agent/tools/README.md

New Location:
docs/guides/tools.md (or docs/reference/tools.md)
```

---

### TIER 2: MOVE MANAGER TO TIER 1

Manager-specific code that's still in `agent/manager/` needs to move to `tiers/tier_1/manager/`:

```
Current:
agent/manager/
├── manager_agent.py
├── manager_agent_harness.py
├── manager_agent_backup.py
├── consumer.py
├── tools/
│   └── delegation_tools.py
├── deep_agent_factory.py
└── shortcut_registry.py

New Location (already partially exists):
tiers/tier_1/manager/
├── __init__.py
├── manager_agent.py              ← MOVE (already there?)
├── manager_agent_harness.py      ← MOVE (already there?)
├── consumer.py                   ← MOVE (already there?)
├── tools/
│   └── delegation_tools.py       ← MOVE
├── deep_agent_factory.py         ← MOVE or consolidate
└── shortcut_registry.py          ← CONSOLIDATE with core/registry/
```

**Files to move:**
- [ ] `agent/manager/tools/` → `tiers/tier_1/manager/tools/` (copy + verify)
- [ ] `agent/manager/deep_agent_factory.py` → `tiers/tier_1/manager/` (if not already there)
- [ ] `agent/manager/manager_agent_backup.py` → `archive/backup-files/` (backup - not needed in active code)

---

### TIER 3: CONSOLIDATE CONFIG

Configuration files scattered around should go to `config/profiles/`:

```
Current Locations:
agent/config/persistence_config.py

New Location:
config/profiles/
├── dev/
│   └── persistence_config.py
├── staging/
│   └── persistence_config.py
└── prod/
    └── persistence_config.py
```

**Files to move:**
- [ ] `agent/config/persistence_config.py` → `config/profiles/dev/persistence_config.py`
- [ ] Create staging and prod variants

---

### TIER 4: ARCHIVE DOCUMENTATION & LEGACY

Clean up orphaned documentation:

```
Stray documentation:
agent/Flow_of_sys.md             → archive/docs/ or docs/reference/
agent/Improvements.md            → archive/docs/ or docs/roadmap/

Legacy Infrastructure:
agent/Infastructure/             → archive/legacy-infrastructure/
├── dispatcher/
├── orchestration_engine/
├── queue/
└── worker/
```

---

## 📋 Complete Action Plan

### PHASE 1: Distribute `agent/tools/` (1.5 hours)

**Step 1.1: Move persistence tools to services/**
```bash
# Copy to new location
mkdir -p services/persistence/tools
cp -r agent/tools/db_write services/persistence/tools/
cp -r agent/tools/persistence services/persistence/tools/
cp agent/tools/supabase_tools.py services/persistence/tools/

# Add deprecation wrapper to old location
cat > agent/tools/supabase_tools.py << 'EOF'
"""DEPRECATED: This module has moved to services.persistence.tools.supabase_tools

Use: from services.persistence.tools import SupabaseClient
"""
import warnings
warnings.warn(
    "Importing from agent.tools.supabase_tools is deprecated. "
    "Use services.persistence.tools instead.",
    DeprecationWarning,
    stacklevel=2
)

try:
    from services.persistence.tools.supabase_tools import *
except ImportError:
    pass
EOF

# Remove old copies after verification
rm -r agent/tools/db_write agent/tools/persistence agent/tools/supabase_tools.py
```

**Step 1.2: Move delivery tools to services/**
```bash
mkdir -p services/external_apis/tools
cp -r agent/tools/delivery services/external_apis/tools/

# Add deprecation wrapper
cat > agent/tools/delivery/__init__.py << 'EOF'
"""DEPRECATED: This module has moved to services.external_apis.tools.delivery"""
import warnings
warnings.warn(
    "Importing from agent.tools.delivery is deprecated. "
    "Use services.external_apis.tools instead.",
    DeprecationWarning,
    stacklevel=2
)

try:
    from services.external_apis.tools.delivery import *
except ImportError:
    pass
EOF

rm -r agent/tools/delivery
```

**Step 1.3: Archive data_coordinator**
```bash
mkdir -p archive/legacy-tools
cp agent/tools/data_coordinator.py archive/legacy-tools/
rm agent/tools/data_coordinator.py
```

**Step 1.4: Clean up agent/tools/**
```bash
# After moves above, agent/tools/ should only have:
# - __init__.py (with re-exports)
# - registry.py (to be consolidated)
# - README.md (reference)
# - __pycache__/

# Remove duplicates (if agent/tools/redis/ exists and services/redis/ is authoritative):
rm -rf agent/tools/redis
```

---

### PHASE 2: Move Manager to Tier 1 (1 hour)

**Step 2.1: Verify tier_1/manager exists and has core files**
```bash
# Check what's already there
ls -la tiers/tier_1/manager/
```

**Step 2.2: Copy manager/tools to tier_1**
```bash
cp -r agent/manager/tools tiers/tier_1/manager/

# Add deprecation wrapper
cat > agent/manager/tools/__init__.py << 'EOF'
"""DEPRECATED: This module has moved to tiers.tier_1.manager.tools"""
import warnings
warnings.warn(
    "Importing from agent.manager.tools is deprecated. "
    "Use tiers.tier_1.manager.tools instead.",
    DeprecationWarning,
    stacklevel=2
)

try:
    from tiers.tier_1.manager.tools import *
except ImportError:
    pass
EOF
```

**Step 2.3: Copy deep_agent_factory.py if not already in tier_1**
```bash
if [ ! -f tiers/tier_1/manager/deep_agent_factory.py ]; then
    cp agent/manager/deep_agent_factory.py tiers/tier_1/manager/
fi
```

**Step 2.4: Archive backup files**
```bash
mkdir -p archive/backup-files
cp agent/manager/manager_agent_backup.py archive/backup-files/
rm agent/manager/manager_agent_backup.py
```

---

### PHASE 3: Consolidate Config (30 minutes)

**Step 3.1: Migrate persistence_config.py**
```bash
# Create dev, staging, prod profile dirs
mkdir -p config/profiles/{dev,staging,prod}

# Copy to dev (primary)
cp agent/config/persistence_config.py config/profiles/dev/

# Create staging and prod variants (copy with environment-specific tweaks)
cp config/profiles/dev/persistence_config.py config/profiles/staging/
cp config/profiles/dev/persistence_config.py config/profiles/prod/

# Add deprecation wrapper to agent/config/
cat > agent/config/persistence_config.py << 'EOF'
"""DEPRECATED: This module has moved to config/profiles/dev/persistence_config.py"""
import warnings
warnings.warn(
    "Importing from agent.config is deprecated. "
    "Use config.profiles instead.",
    DeprecationWarning,
    stacklevel=2
)

try:
    from config.profiles.dev.persistence_config import *
except ImportError:
    pass
EOF
```

---

### PHASE 4: Archive Legacy Docs & Infrastructure (1 hour)

**Step 4.1: Archive legacy documentation**
```bash
mkdir -p archive/legacy-docs
mv agent/Flow_of_sys.md archive/legacy-docs/
mv agent/Improvements.md archive/legacy-docs/

# Or if useful, move to docs/:
# mv agent/Flow_of_sys.md docs/reference/system-flow-legacy.md
# mv agent/Improvements.md docs/roadmap/improvements-tracking.md
```

**Step 4.2: Archive legacy infrastructure**
```bash
mkdir -p archive/legacy-infrastructure
mv agent/Infastructure/* archive/legacy-infrastructure/
rmdir agent/Infastructure
```

---

### PHASE 5: Clean Up Registry Files (30 minutes)

**Step 5.1: Consolidate registries to core/registry/**
```bash
# Create if not exists
mkdir -p core/registry

# Copy and consolidate
cp agent/tools/registry.py core/registry/tool_registry.py
cp agent/manager/shortcut_registry.py core/registry/orchestrator_shortcuts.py
cp agent/operational_agents/registry.py core/registry/agent_registry.py

# Create consolidated __init__.py
cat > core/registry/__init__.py << 'EOF'
"""
Central registry for all framework components

Provides discovery and registration for:
- Tools (database, delivery, external APIs)
- Orchestrators (tier 2 components)
- Agents (tier 3 components)
- Shortcuts (manager delegations)
"""

from .tool_registry import discover_local_tools
from .orchestrator_registry import get_orchestrator
from .agent_registry import get_agent
from .orchestrator_shortcuts import ShortcutRegistry

__all__ = [
    "discover_local_tools",
    "get_orchestrator",
    "get_agent",
    "ShortcutRegistry",
]
EOF

# Add deprecation wrappers to old locations
cat > agent/tools/registry.py << 'EOF'
"""DEPRECATED: Use core.registry.tool_registry"""
import warnings
warnings.warn(
    "Importing from agent.tools.registry is deprecated. "
    "Use core.registry instead.",
    DeprecationWarning,
    stacklevel=2
)

try:
    from core.registry.tool_registry import *
except ImportError:
    pass
EOF

cat > agent/manager/shortcut_registry.py << 'EOF'
"""DEPRECATED: Use core.registry"""
import warnings
warnings.warn(
    "Importing from agent.manager.shortcut_registry is deprecated. "
    "Use core.registry instead.",
    DeprecationWarning,
    stacklevel=2
)

try:
    from core.registry import ShortcutRegistry
except ImportError:
    pass
EOF
```

---

## 📊 Final Structure After Cleanup

```
✅ CLEAN agent/ (LEGACY CONTAINER - mostly empty or deprecated)
agent/
├── __init__.py (deprecation warning header)
├── config/
│   └── persistence_config.py (deprecation wrapper only)
├── manager/
│   └── tools/ (deprecation wrapper only)
├── orchestrators/ (deprecation wrapper only)
├── operational_agents/ (deprecation wrapper only)
├── tools/ (mostly empty)
│   ├── __init__.py (re-exports from services/)
│   ├── registry.py (deprecation wrapper only)
│   └── README.md (reference)
├── utils/ (deprecation wrapper only)
├── schemas/ (deprecation wrapper only)
├── harness/ (deprecation wrapper only)
└── __pycache__/

✅ CLEAN services/ (TOOLS & ADAPTERS)
services/
├── persistence/
│   ├── tools/                          ← NEW (from agent/tools/)
│   │   ├── db_write/
│   │   ├── persistence/
│   │   ├── supabase_tools.py
│   │   └── __init__.py
│   └── ...
├── external_apis/
│   ├── tools/                          ← NEW (from agent/tools/)
│   │   ├── delivery/
│   │   └── __init__.py
│   └── ...
├── redis/
├── vector_db/
└── __init__.py

✅ CLEAN config/ (CONFIGURATION)
config/
├── profiles/
│   ├── dev/
│   │   └── persistence_config.py      ← NEW (from agent/config/)
│   ├── staging/
│   │   └── persistence_config.py
│   └── prod/
│       └── persistence_config.py
└── ...

✅ CLEAN core/ (FRAMEWORK)
core/
├── registry/                           ← CONSOLIDATED REGISTRIES
│   ├── __init__.py
│   ├── tool_registry.py                (from agent/tools/)
│   ├── orchestrator_registry.py
│   ├── agent_registry.py
│   └── orchestrator_shortcuts.py       (from agent/manager/)
├── harness/
├── envelope/
├── schemas/
├── utils/
└── ...

✅ CLEAN tiers/ (BUSINESS LOGIC)
tiers/
├── tier_1/manager/
│   ├── tools/                          ← NEW (from agent/manager/tools/)
│   │   └── delegation_tools.py
│   └── ...
├── tier_2/...
└── tier_3/...

✅ ARCHIVE (REFERENCE & BACKUP)
archive/
├── legacy-tools/
│   └── data_coordinator.py
├── legacy-docs/
│   ├── Flow_of_sys.md
│   └── Improvements.md
├── legacy-infrastructure/
│   ├── dispatcher/
│   ├── orchestration_engine/
│   ├── queue/
│   └── worker/
├── backup-files/
│   └── manager_agent_backup.py
└── ...
```

---

## 🚀 Execution Plan

| Phase | Task | Time | Priority |
|-------|------|------|----------|
| 1 | Distribute agent/tools/ | 1.5h | 🔴 CRITICAL |
| 2 | Move manager/tools to tier_1 | 1h | 🔴 CRITICAL |
| 3 | Migrate config files | 0.5h | 🟡 HIGH |
| 4 | Archive legacy docs & infra | 1h | 🟢 MEDIUM |
| 5 | Consolidate registries | 0.5h | 🟢 MEDIUM |
| - | Testing & import verification | 1.5h | 🔴 CRITICAL |
| **TOTAL** | | **6 hours** | |

---

## Risk Assessment

**Low Risk (Safe):**
- Moving deprecated data_coordinator to archive
- Moving Flow_of_sys.md, Improvements.md to archive
- Moving legacy Infrastructure/ to archive
- Archiving backup files

**Medium Risk (Verify First):**
- Moving agent/tools/* to services/* (need to verify imports work)
- Moving agent/config/ to config/profiles/ (need env-specific handling)
- Consolidating registries (multiple import paths may exist)

**Higher Risk (Test Heavily):**
- Moving agent/manager/tools/ to tier_1/manager/tools/ (core manager functionality)
- Registry consolidation (used by framework)

---

## Questions Before Implementation

1. **Should we keep agent/tools/README.md?** (reference for tool guidelines)
   - [ ] Yes, keep in agent/tools/ for reference
   - [ ] Move to docs/guides/tools.md
   - [ ] Archive it

2. **For config files, do we need multi-environment variants?**
   - [ ] Yes, create dev/staging/prod/ copies with env tweaks
   - [ ] Just dev, others inherit
   - [ ] Single config, environment selection via env var

3. **Backup files - keep or discard?**
   - [ ] Archive manager_agent_backup.py for reference
   - [ ] Delete - not needed, have git history
   - [ ] Keep in agent/manager/ (don't archive)

4. **Should we update imports in running code immediately or gradually?**
   - [ ] Update all at once (riskier, cleaner)
   - [ ] Gradual with deprecation wrappers (safer, longer transition)

**Your preferences?**
