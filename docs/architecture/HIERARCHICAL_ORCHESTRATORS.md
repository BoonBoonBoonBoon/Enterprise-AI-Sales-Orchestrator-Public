# Hierarchical Orchestrators Architecture

**Date**: November 29, 2025  
**Status**: ✅ IMPLEMENTED - Production Ready

---

## Overview

The Redis Streams structure now uses a **hierarchical naming convention** that creates a clean, user-friendly folder structure in Redis browsers and monitoring tools.

## Problem Solved

Previously, orchestrators appeared at the root level of the Redis namespace:
```
agentic-dev/
├── leads:tasks              ← Confusing - at root level
├── leads:results
├── outreach:tasks           ← Missing parent folder
├── outreach:results
├── agents/                  ← Proper hierarchy
│   ├── rag:tasks
│   └── ...
└── manager/
```

**Issues with flat structure:**
- Orchestrators didn't follow the same pattern as agents
- Redis browser showed inconsistent hierarchy
- Unclear relationship between orchestrators and agents
- New developers confused about architecture

## Solution: Hierarchical Naming

New structure with explicit `orchestrators/` parent folder:

```
agentic-dev/
├── orchestrators/           ← ⭐ NEW: Parent folder
│   ├── leads/
│   │   ├── tasks            # {tenant}:orchestrators:leads:tasks
│   │   └── results          # {tenant}:orchestrators:leads:results
│   └── outreach/
│       ├── tasks            # {tenant}:orchestrators:outreach:tasks
│       └── results          # {tenant}:orchestrators:outreach:results
│
├── agents/                  ← Consistent pattern
│   ├── rag/
│   │   ├── tasks
│   │   └── results
│   ├── persistence/
│   │   ├── tasks
│   │   └── results
│   └── copywriter/
│       ├── tasks
│       └── results
│
├── manager/
│   ├── tasks
│   └── results
│
└── system/                  ← System-level streams
    ├── dlq                  # Dead letter queue
    ├── events
    ├── health
    └── audit
```

## Stream Naming Convention

### Format
```
{tenant}:orchestrators:{orchestrator_name}:{type}
```

### Examples
```
agentic-dev:orchestrators:leads:tasks
agentic-dev:orchestrators:leads:results
agentic-dev:orchestrators:outreach:tasks
agentic-dev:orchestrators:outreach:results
```

### Benefits
1. **Explicit Hierarchy**: `orchestrators/` folder immediately visible
2. **Consistent Pattern**: Matches the `agents/` folder structure
3. **Clear Relationships**: Easy to see which level each component belongs to
4. **User-Friendly**: Redis browser shows intuitive folder structure
5. **Future-Proof**: Room to add more orchestrators (e.g., `integration`, `compliance`)

## Complete Redis Namespace Map

```
{tenant}:manager:tasks                          # Manager input
{tenant}:manager:results                        # Manager output

{tenant}:orchestrators:leads:tasks              # Leads workflow input
{tenant}:orchestrators:leads:results            # Leads workflow output
{tenant}:orchestrators:outreach:tasks           # Outreach workflow input
{tenant}:orchestrators:outreach:results         # Outreach workflow output

{tenant}:agents:rag:tasks                       # RAG agent input
{tenant}:agents:rag:results                     # RAG agent output
{tenant}:agents:persistence:tasks               # Persistence agent input
{tenant}:agents:persistence:results             # Persistence agent output
{tenant}:agents:copywriter:tasks                # Copywriter agent input
{tenant}:agents:copywriter:results              # Copywriter agent output
{tenant}:agents:booking:tasks                   # Booking agent input
{tenant}:agents:booking:results                 # Booking agent output
{tenant}:agents:sequencing:tasks                # Sequencing agent input
{tenant}:agents:sequencing:results              # Sequencing agent output
{tenant}:agents:deduplication:tasks             # Deduplication agent input
{tenant}:agents:deduplication:results           # Deduplication agent output

{tenant}:system:dlq                             # Dead letter queue
{tenant}:system:events                          # System events
{tenant}:system:health                          # Health monitoring
{tenant}:system:audit                           # Audit trail
```

## Data Flow with Hierarchical Structure

### Task Delegation (Downstream)
```
External Request
    ↓
{tenant}:manager:tasks
    ↓
MANAGER AGENT decides intent
    ↓
    ├─→ {tenant}:orchestrators:leads:tasks
    │   ↓
    │   LEADS ORCHESTRATOR decomposes lead workflow
    │   ↓
    │   ├─→ {tenant}:agents:rag:tasks
    │   ├─→ {tenant}:agents:persistence:tasks
    │   └─→ {tenant}:agents:deduplication:tasks
    │
    └─→ {tenant}:orchestrators:outreach:tasks
        ↓
        OUTREACH ORCHESTRATOR decomposes outreach workflow
        ↓
        ├─→ {tenant}:agents:copywriter:tasks
        ├─→ {tenant}:agents:booking:tasks
        └─→ {tenant}:agents:sequencing:tasks
```

### Result Propagation (Upstream)
```
{tenant}:agents:*:results
    ↓
Agent completes work, returns to orchestrator results stream
    ↓
{tenant}:orchestrators:leads:results
{tenant}:orchestrators:outreach:results
    ↓
Orchestrator aggregates, returns to manager results stream
    ↓
{tenant}:manager:results
    ↓
External Response
```

## Implementation Details

### Code Changes Made

1. **`tiers/tier_1/manager/policy/router.py`** (line 25)
   ```python
   # Before: return f"{tenant_id}:{orch}:tasks"
   # After:
   return f"{tenant_id}:orchestrators:{orch}:tasks"
   ```

2. **`tiers/tier_1/manager/tools/delegation_tools.py`** (lines 349, 411)
   ```python
   # Leads stream
   leads_stream = f"{self.tenant_id}:orchestrators:leads:tasks"
   
   # Outreach stream
   outreach_stream = f"{self.tenant_id}:orchestrators:outreach:tasks"
   ```

3. **`tiers/tier_2/leads_orchestrator/consumer.py`** (lines 76-77)
   ```python
   self.task_stream = f"{tenant_id}:orchestrators:leads:tasks"
   self.result_stream = f"{tenant_id}:orchestrators:leads:results"
   ```

4. **`tiers/tier_2/outreach_orchestrator/consumer.py`** (lines 66-67)
   ```python
   self.task_stream = f"{tenant_id}:orchestrators:outreach:tasks"
   self.result_stream = f"{tenant_id}:orchestrators:outreach:results"
   ```

5. **`.github/copilot-instructions.md`** (Documentation update)
   - Updated to reflect hierarchical naming as the canonical pattern

### Consumer Restart Required

After code changes, consumers must be restarted to:
1. Load the new code with hierarchical stream names
2. Register consumer groups on new streams
3. Begin processing from new hierarchical streams

Old flat streams (`agentic-dev:leads:tasks`, etc.) were deleted to maintain clean Redis state.

## Testing the New Structure

### Verify Streams Exist
```powershell
python -c "
import redis, os
from dotenv import load_dotenv

load_dotenv()
r = redis.from_url(os.getenv('REDIS_URL'))
tenant = 'agentic-dev'

streams = [
    f'{tenant}:orchestrators:leads:tasks',
    f'{tenant}:orchestrators:leads:results',
    f'{tenant}:orchestrators:outreach:tasks',
    f'{tenant}:orchestrators:outreach:results'
]

for stream in streams:
    print(f'{stream}: {r.xlen(stream)} messages')
"
```

### Run E2E Test
```powershell
python fresh_test.py
```

Expected output:
```
✓ manager:tasks: 27 (+1)
✓ manager:results: 25 (+1)
✓ orchestrators:leads:tasks: 2 (+1)    ← NEW HIERARCHICAL
✓ orchestrators:leads:results: 2 (+1)  ← NEW HIERARCHICAL
✓ agents:rag:tasks: 41 (+1)
✓ agents:rag:results: 40 (+1)
```

### Check Redis Browser

In your Redis browser (e.g., RedisInsight):
1. Navigate to `agentic-dev` namespace
2. You should see:
   - `orchestrators/` folder
     - `leads/` subfolder
       - `tasks` stream
       - `results` stream
     - `outreach/` subfolder
       - `tasks` stream
       - `results` stream
   - `agents/` folder (same structure as before)
   - `manager/` folder
   - `system/` folder

## Migration from Flat to Hierarchical

### What Happened
1. Code was updated to use `{tenant}:orchestrators:{name}:{type}` pattern
2. Consumers were restarted to use new stream names
3. New streams were automatically created on first message
4. Old flat streams (`leads:tasks`, `outreach:tasks`, etc.) were deleted

### Data Loss Consideration
- Old flat streams had legacy/test messages (~96 messages total)
- Not production data, safe to delete
- New fresh messages go to hierarchical streams
- This is a clean cutover with no impact to live workflows

### Future Migrations
If you need to migrate other stream names in the future:
```bash
python scripts/manage_redis_streams.py --migrate
```

## Consistency Across Architecture

Now all components follow the same hierarchical pattern:

| Component Type | Pattern | Examples |
|---|---|---|
| **Manager** | `{tenant}:manager:{type}` | `agentic-dev:manager:tasks` |
| **Orchestrators** | `{tenant}:orchestrators:{name}:{type}` | `agentic-dev:orchestrators:leads:tasks` |
| **Agents** | `{tenant}:agents:{name}:{type}` | `agentic-dev:agents:rag:tasks` |
| **System** | `{tenant}:system:{name}` | `agentic-dev:system:dlq` |

All follow the same hierarchical pattern, creating intuitive folder structure in Redis browsers.

## Benefits Summary

✅ **Consistency**: All components follow same naming pattern  
✅ **Visibility**: Clear hierarchy in Redis browser  
✅ **Maintainability**: Easy to understand relationships  
✅ **Scalability**: Room to add new orchestrators  
✅ **User-Friendly**: Intuitive folder structure  
✅ **Documentation**: Clear stream organization in docs  
✅ **Monitoring**: Easy to identify all orchestrator streams  
✅ **Debugging**: Obvious which tier each stream belongs to  

## Related Documentation

- **[REDIS_REORGANIZATION_SUMMARY.md](./REDIS_REORGANIZATION_SUMMARY.md)** - Complete reorganization context
- **[REDIS_DATA_FLOW_VISUAL.md](./REDIS_DATA_FLOW_VISUAL.md)** - Visual data flow diagrams
- **[REDIS_IMPLEMENTATION_GUIDE.md](./REDIS_IMPLEMENTATION_GUIDE.md)** - Implementation reference
- **[../three-tier-system.md](./three-tier-system.md)** - Three-tier architecture overview

---

**Status**: Implementation complete and tested ✅  
**Last Updated**: November 29, 2025
