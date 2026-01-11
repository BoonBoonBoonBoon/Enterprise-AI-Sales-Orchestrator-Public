# Folder Structure Cleanup - Remaining Work

## Current State Analysis

### ✅ **CORRECTLY ORGANIZED (No Action Needed)**

```
✅ tiers/
   ├── tier_1/manager/              ← Migrated, working
   ├── tier_2/
   │   ├── leads_orchestrator/      ← Migrated, working
   │   ├── outreach_orchestrator/   ← Migrated, working
   │   ├── audit_orchestrator/      ← Just created (skeleton)
   │   └── inbound_orchestrator/    ← Just created (skeleton)
   └── tier_3/
       ├── rag_agent/               ← Migrated from agent/
       ├── persistence_agent/       ← Migrated from agent/
       └── copywriter_agent/        ← Migrated from agent/

✅ core/
   ├── harness/                     ← Central harness framework
   ├── envelope/                    ← Message format
   ├── schemas/                     ← Migrated schemas
   ├── utils/                       ← Migrated utilities
   ├── exceptions/                  ← Central exceptions
   └── deep_agents/                 ← AI framework

✅ services/
   ├── redis/                       ← Message broker
   ├── persistence/                 ← Database layer
   ├── external_apis/               ← Third-party integrations
   └── vector_db/                   ← Embeddings/RAG

✅ deployment/
   ├── docker/                      ← Docker configs
   └── IAC_SETUP_TODO.md           ← Infrastructure roadmap
```

### ❌ **DUPLICATES & LEGACY PATHS (Need Cleanup)**

**Problem 1: Duplicate Orchestrators in `agent/orchestrators/`**
```
agent/orchestrators/
├── leads_orchestrator/          ← DUPLICATE (moved to tiers/tier_2/)
├── outreach_orchestrator/       ← DUPLICATE (moved to tiers/tier_2/)
├── audit_orchestrator/          ← OLD (moved to tiers/tier_2/)
├── inbound_orchestrator/        ← OLD (moved to tiers/tier_2/)
├── audit/                       ← LEGACY - unclear purpose
├── control/                     ← LEGACY - not in tiers yet!
├── reply_orchestrator.py        ← ORPHANED - not migrated
├── delivery_orchestrator.py     ← ORPHANED - not migrated
├── workflow_manager.py          ← ORPHANED - not migrated
├── base_orchestrator.py         ← LEGACY - should be in core
├── registry.py                  ← DUPLICATE (should consolidate)
├── queue/                       ← LEGACY - use Redis streams instead
├── plugins/                     ← LEGACY - unclear purpose
└── orch.md, layers.md          ← STALE DOCS
```

**Problem 2: Duplicate Agents in `agent/operational_agents/`**
```
agent/operational_agents/
├── rag_agent/                  ← DUPLICATE (moved to tiers/tier_3/)
├── persistence_agent/          ← DUPLICATE (moved to tiers/tier_3/)
├── copywriter/                 ← DUPLICATE (moved to tiers/tier_3/)
├── multi_channel_sequencer/    ← ORPHANED - not migrated
├── factory.py                  ← DUPLICATE (should use registry)
├── registry.py                 ← DUPLICATE (should consolidate)
└── stufftodo                   ← JUNK FILE
```

**Problem 3: Orphaned Tier 3 Agents**
```
tiers/tier_3/ (INCOMPLETE)
├── rag_agent/                  ← ✅ Exists
├── persistence_agent/          ← ✅ Exists
├── copywriter_agent/           ← ✅ Exists
├── multi_channel_sequencer/    ← ❌ MISSING (exists in agent/ instead)
├── rag_agent/                  ← ❌ MISSING from tier_3
└── NO booking_agent/           ← ❌ MISSING (mentioned in docs)
```

**Problem 4: Tier 2 - Missing & Orphaned**
```
Tier 2 Orchestrators Status:
✅ leads_orchestrator        (migrated to tiers/tier_2/)
✅ outreach_orchestrator     (migrated to tiers/tier_2/)
✅ audit_orchestrator        (skeleton in tiers/tier_2/)
✅ inbound_orchestrator      (skeleton in tiers/tier_2/)
❌ control_orchestrator      (EXISTS in agent/orchestrators/control but NOT migrated!)
❌ reply_orchestrator.py     (ORPHANED - not in tiers)
❌ delivery_orchestrator.py  (ORPHANED - not in tiers)
```

**Problem 5: Legacy Infrastructure in `agent/Infastructure/`**
```
agent/Infastructure/          ← MISSPELLED + LEGACY
├── dispatcher/
├── orchestration_engine/
├── queue/
└── worker/
These should be consolidated into:
  - core/harness/
  - services/
  - Never used (check git history)
```

**Problem 6: Stray Legacy Files**
```
agent/manager/tools/          ← Should be in tiers/tier_1/manager/
agent/tools/                  ← Should be in services/ (db_write, delivery, persistence, redis)
agent/config/                 ← Should be in config/profiles/
```

### 🔴 **CRITICAL ISSUES**

1. **control_orchestrator is completely unmigrated**
   - Exists in: `agent/orchestrators/control/`
   - Should be in: `tiers/tier_2/control_orchestrator/`
   - Status: BLOCKING - system references it but it's not in proper tier

2. **multi_channel_sequencer not migrated**
   - Exists in: `agent/operational_agents/multi_channel_sequencer/`
   - Should be in: `tiers/tier_3/multi_channel_sequencer/`
   - Status: BLOCKING - referenced by outreach orchestrator

3. **Orphaned orchestrators not handled**
   - reply_orchestrator.py (ORPHANED)
   - delivery_orchestrator.py (ORPHANED)
   - workflow_manager.py (ORPHANED)
   - Status: UNCLEAR - determine if legacy or needed

4. **Duplicate registry/factory patterns**
   - agent/orchestrators/registry.py
   - agent/operational_agents/registry.py
   - agent/operational_agents/factory.py
   - Status: NEEDS CONSOLIDATION - pick one pattern

---

## Cleanup Plan (Priority Order)

### PHASE 1: MIGRATE CRITICAL TIER 2 ORCHESTRATORS (2 hours)

**Task 1.1: Migrate control_orchestrator to tiers/tier_2/**
```bash
# Create skeleton like audit_orchestrator
tiers/tier_2/control_orchestrator/
├── __init__.py
├── control_orchestrator.py      (core logic from agent/)
├── control_orchestrator_harness.py
├── consumer.py                  (Redis streams)
├── README.md
├── schemas/
├── tests/
└── tools/
```
- [ ] Create directory structure
- [ ] Extract control logic from `agent/orchestrators/control/`
- [ ] Create harness wrapper
- [ ] Create consumer for orchestrator queue
- [ ] Document purpose, configuration, TODO items

**Task 1.2: Add deprecation warning to agent/orchestrators/control/__init__.py**
```python
"""DEPRECATED: This module has moved to tiers.tier_2.control_orchestrator"""
```

### PHASE 2: MIGRATE CRITICAL TIER 3 AGENTS (2 hours)

**Task 2.1: Migrate multi_channel_sequencer to tiers/tier_3/**
```bash
tiers/tier_3/multi_channel_sequencer/
├── __init__.py
├── sequencer.py                 (core logic)
├── sequencer_harness.py
├── consumer.py                  (Redis streams)
├── README.md
├── schemas/
├── tests/
└── tools/
```
- [ ] Create directory structure
- [ ] Extract sequencer logic from `agent/operational_agents/multi_channel_sequencer/`
- [ ] Create harness wrapper
- [ ] Document channel types (email, linkedin, phone, etc.)

**Task 2.2: Add deprecation warning to agent/operational_agents/multi_channel_sequencer/__init__.py**

### PHASE 3: CONSOLIDATE DUPLICATE REGISTRIES (1 hour)

**Task 3.1: Create central registry in core/**
```
core/registry/
├── __init__.py
├── orchestrator_registry.py      (all tier_2 orchestrators)
├── agent_registry.py            (all tier_3 agents)
├── tool_registry.py             (all tools)
└── README.md
```
- [ ] Define registry pattern (singleton, loader functions, etc.)
- [ ] Consolidate `agent/orchestrators/registry.py`
- [ ] Consolidate `agent/operational_agents/registry.py`
- [ ] Update imports across codebase

**Task 3.2: Add deprecation warnings to old registries**

### PHASE 4: CLEAN UP LEGACY/ORPHANED FILES (1.5 hours)

**Task 4.1: Analyze & archive legacy files**
- [ ] `agent/Infastructure/` - Check if used, archive if not
- [ ] `reply_orchestrator.py` - Used? Archive if not
- [ ] `delivery_orchestrator.py` - Used? Archive if not
- [ ] `workflow_manager.py` - Used? Archive if not
- [ ] `base_orchestrator.py` - Move to core/base_orchestrator.py if still used

**Task 4.2: Move legitimate files to proper locations**
- [ ] `agent/manager/tools/` → `tiers/tier_1/manager/tools/`
- [ ] `agent/tools/` → `services/` (split appropriately)
- [ ] `agent/config/` → `config/profiles/` (migrate configs)

**Task 4.3: Archive old structures**
```bash
# Move to archive/ for reference
archive/legacy-orchestrators/
  - agent/orchestrators/audit/
  - agent/orchestrators/queue/
  - agent/orchestrators/plugins/
  
archive/legacy-agents/
  - legacy files
```

### PHASE 5: CLEAN UP AGENT/ DIRECTORY (1 hour)

**Task 5.1: Remove fully migrated directories**
```bash
# Remove (after verification they're in tiers/core/services/)
agent/orchestrators/leads_orchestrator/     ← REMOVE
agent/orchestrators/outreach_orchestrator/  ← REMOVE
agent/operational_agents/rag_agent/         ← REMOVE
agent/operational_agents/persistence_agent/ ← REMOVE
agent/operational_agents/copywriter/        ← REMOVE
```

**Task 5.2: Remove duplicate/stale files**
```bash
# Remove
agent/orchestrators/orch.md
agent/orchestrators/layers.md
agent/operational_agents/stufftodo
agent/operational_agents/factory.py       (consolidate into registry)
```

**Task 5.3: Clean up agent/ structure**
```bash
agent/
├── manager/              (deprecated → tiers/tier_1/manager)
├── harness/              (deprecated → core/harness)
├── schemas/              (deprecated → core/schemas)
├── utils/                (deprecated → core/utils)
├── tools/                (move to services/)
├── orchestrators/        (MOSTLY EMPTY after cleanup)
│   ├── __init__.py       (deprecation warning)
│   └── [legacy items]
└── operational_agents/   (MOSTLY EMPTY after cleanup)
    ├── __init__.py       (deprecation warning)
    └── [legacy items]
```

---

## File-by-File Actions

### REMOVE (Safe - duplicates)
- [ ] `agent/orchestrators/leads_orchestrator/` - Duplicate of `tiers/tier_2/leads_orchestrator/`
- [ ] `agent/orchestrators/outreach_orchestrator/` - Duplicate of `tiers/tier_2/outreach_orchestrator/`
- [ ] `agent/operational_agents/rag_agent/` - Duplicate of `tiers/tier_3/rag_agent/`
- [ ] `agent/operational_agents/persistence_agent/` - Duplicate of `tiers/tier_3/persistence_agent/`
- [ ] `agent/operational_agents/copywriter/` - Duplicate of `tiers/tier_3/copywriter_agent/`

### MOVE (Consolidate)
- [ ] `agent/manager/tools/` → `tiers/tier_1/manager/tools/`
- [ ] `agent/tools/db_write/` → `services/persistence/tools/db_write/`
- [ ] `agent/tools/delivery/` → `services/external_apis/tools/delivery/`
- [ ] `agent/tools/persistence/` → `services/persistence/tools/`
- [ ] `agent/tools/redis/` → `services/redis/tools/`

### MIGRATE (Move to tiers/)
- [ ] `agent/orchestrators/control/` → `tiers/tier_2/control_orchestrator/`
- [ ] `agent/operational_agents/multi_channel_sequencer/` → `tiers/tier_3/multi_channel_sequencer/`

### ARCHIVE (Unclear purpose)
- [ ] `agent/Infastructure/` - Move to `archive/legacy-infrastructure/`
- [ ] `agent/orchestrators/audit/` - Move to `archive/legacy-orchestrators/audit/`
- [ ] `agent/orchestrators/plugins/` - Move to `archive/legacy-orchestrators/plugins/`
- [ ] `agent/orchestrators/queue/` - Move to `archive/legacy-orchestrators/queue/`
- [ ] `reply_orchestrator.py` - Move to `archive/legacy-orchestrators/`
- [ ] `delivery_orchestrator.py` - Move to `archive/legacy-orchestrators/`
- [ ] `workflow_manager.py` - Move to `archive/legacy-orchestrators/`

### DELETE (Junk)
- [ ] `agent/operational_agents/stufftodo` - Junk file
- [ ] `agent/orchestrators/orch.md` - Stale docs
- [ ] `agent/orchestrators/layers.md` - Stale docs

### CONSOLIDATE (Patterns)
- [ ] `agent/orchestrators/registry.py` → `core/registry/orchestrator_registry.py`
- [ ] `agent/operational_agents/registry.py` → `core/registry/agent_registry.py`
- [ ] `agent/operational_agents/factory.py` → `core/registry/` (merge into registry)

### UPDATE (Deprecation warnings)
- [ ] `agent/orchestrators/__init__.py` - Add deprecation header
- [ ] `agent/operational_agents/__init__.py` - Add deprecation header
- [ ] `agent/orchestrators/control/__init__.py` - Point to tiers/tier_2/
- [ ] `agent/operational_agents/multi_channel_sequencer/__init__.py` - Point to tiers/tier_3/

---

## Expected Result

After cleanup:

```
✅ CLEAN THREE-TIER STRUCTURE
tiers/
├── tier_1/manager/
├── tier_2/
│   ├── leads_orchestrator/
│   ├── outreach_orchestrator/
│   ├── audit_orchestrator/
│   ├── inbound_orchestrator/
│   └── control_orchestrator/           ← NEW (migrated)
└── tier_3/
    ├── rag_agent/
    ├── persistence_agent/
    ├── copywriter_agent/
    └── multi_channel_sequencer/        ← NEW (migrated)

✅ CLEAN CORE FRAMEWORK
core/
├── registry/                           ← NEW (consolidated)
├── harness/
├── envelope/
├── schemas/
├── utils/
├── exceptions/
└── deep_agents/

✅ CLEAN SERVICES LAYER
services/
├── redis/
├── persistence/
├── external_apis/
└── vector_db/

✅ MINIMAL LEGACY AGENT/
agent/
├── __init__.py (deprecation warning)
├── orchestrators/
│   └── __init__.py (deprecation warning, empty)
├── operational_agents/
│   └── __init__.py (deprecation warning, empty)
└── [any truly legacy files not yet handled]

✅ ARCHIVE FOR REFERENCE
archive/
├── legacy-infrastructure/
├── legacy-orchestrators/
└── legacy-agents/
```

---

## Estimated Effort

- **Phase 1** (Migrate tier_2 control): 2 hours
- **Phase 2** (Migrate tier_3 sequencer): 2 hours
- **Phase 3** (Consolidate registries): 1 hour
- **Phase 4** (Analyze & archive legacy): 1.5 hours
- **Phase 5** (Clean up agent/): 1 hour
- **Testing & Verification**: 1.5 hours
- **Total: ~9 hours**

---

## Risk Assessment

**Low Risk:**
- Removing duplicate orchestrators/agents
- Archiving legacy Infrastructure/
- Removing junk files (stufftodo, stale docs)

**Medium Risk:**
- Moving manager/tools to tier_1/
- Moving tools to services/

**Higher Risk:**
- Migrating control_orchestrator (need to verify it's fully working)
- Consolidating registries (multiple import paths may exist)

---

## Question: Which Phase First?

Would you like to:
1. **Start with Phase 1** (migrate control_orchestrator) - 2 hours
2. **Start with Phase 3** (consolidate registries first) - 1 hour - helps understand what's used
3. **Start with Phase 5** (clean obvious duplicates) - 1 hour - quick wins
4. **Full cleanup marathon** - All phases (9 hours)

What's your preference?
