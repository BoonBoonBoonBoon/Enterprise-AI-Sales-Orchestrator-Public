# Redis Migration Plan: Flat to Hierarchical
**Date:** November 20, 2025
**Status:** Migration Strategy

## 1. The Gap Analysis

| Component | Current Stream (Code) | Target Stream (MVP) | Status |
|-----------|-----------------------|---------------------|--------|
| **Manager** | `manager:tasks` (Implicit) | `{t}:manager:tasks` | ⚠️ Update Needed |
| **Leads Orch** | `leads:tasks` (Implicit) | `{t}:orch:leads:tasks` | ⚠️ Update Needed |
| **Outreach Orch** | `outreach:tasks` (Implicit) | `{t}:orch:outreach:tasks` | ⚠️ Update Needed |
| **RAG Agent** | `rag:tasks` | `{t}:agents:rag:tasks` | ❌ Mismatch |
| **Persistence** | `persist:tasks` | `{t}:agents:persist:tasks` | ❌ Mismatch |
| **Copywriter** | `copy:tasks` | `{t}:agents:copy:tasks` | ❌ Mismatch |

**Key Findings:**
1. Current code uses hardcoded strings in `streams.py`.
2. Current consumers often default to `default` tenant but don't enforce the prefix structure consistently.
3. No centralized `StreamKeyBuilder` exists in the codebase yet.

---

## 2. Migration Strategy: "Clean Slate"
Since the system is in the **MVP/Dev phase**, we recommend a **Clean Slate** migration rather than a complex dual-write strategy.

**Procedure:**
1. **Stop all services.**
2. **Flush Redis** (or delete specific old keys).
3. **Deploy new code** with `StreamKeyBuilder`.
4. **Run Setup Script** to create new consumer groups.
5. **Start services.**

---

## 3. Implementation Steps

### Step 1: Create `StreamKeyBuilder`
Modify `services/redis/streams.py` to include the builder class.

### Step 2: Refactor Consumers
Update `__init__` methods in:
- `tiers/tier_1/manager/consumer.py`
- `tiers/tier_2/leads_orchestrator/consumer.py`
- `tiers/tier_2/outreach_orchestrator/consumer.py`
- `tiers/tier_3/rag_agent/consumer.py` (and others)

**Change Pattern:**
```python
# OLD
self.stream = STREAM_TASKS

# NEW
self.stream = StreamKeyBuilder.agent_tasks(self.tenant_id, "rag")
```

### Step 3: Refactor Producers (Delegation Tools)
Update `tiers/tier_1/manager/tools/delegation_tools.py` to use the builder when sending tasks.

### Step 4: Create Setup Script
Create `scripts/setup_redis_streams.py` to initialize the groups.

```python
# Pseudo-code for setup script
tenants = ["default", "acme"]
components = ["manager", "leads", "outreach", "rag", "copy", "persist"]

for t in tenants:
    # Create Manager Stream
    r.xgroup_create(f"{t}:manager:tasks", "manager-workers", mkstream=True)
    # ... create others ...
```

---

## 4. Verification Checklist
- [ ] All streams follow `{t}:{tier}:{component}:{type}` pattern.
- [ ] `XINFO GROUPS` shows correct workers active on new streams.
- [ ] End-to-End test (Manager -> Leads -> RAG) passes with new streams.
- [ ] Old streams (`rag:tasks`) are empty/deleted.
