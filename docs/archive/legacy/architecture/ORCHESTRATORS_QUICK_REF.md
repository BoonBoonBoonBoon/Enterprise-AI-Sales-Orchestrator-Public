# Redis Architecture Quick Reference

**Last Updated**: November 29, 2025

## Hierarchical Redis Stream Structure

```
{tenant}/
├── orchestrators/                      ← Tier 2: Business Logic
│   ├── leads/
│   │   ├── tasks                       agentic-dev:orchestrators:leads:tasks
│   │   └── results                     agentic-dev:orchestrators:leads:results
│   └── outreach/
│       ├── tasks                       agentic-dev:orchestrators:outreach:tasks
│       └── results                     agentic-dev:orchestrators:outreach:results
│
├── agents/                             ← Tier 3: Execution
│   ├── rag/
│   │   ├── tasks                       agentic-dev:agents:rag:tasks
│   │   └── results                     agentic-dev:agents:rag:results
│   ├── persistence/
│   │   ├── tasks                       agentic-dev:agents:persistence:tasks
│   │   └── results                     agentic-dev:agents:persistence:results
│   └── [more agents...]
│
├── manager/                            ← Tier 1: Strategic
│   ├── tasks                           agentic-dev:manager:tasks
│   └── results                         agentic-dev:manager:results
│
└── system/                             ← System Streams
    ├── dlq                             agentic-dev:system:dlq
    ├── events                          agentic-dev:system:events
    ├── health                          agentic-dev:system:health
    └── audit                           agentic-dev:system:audit
```

## Key Pattern

**Pattern**: `{tenant}:orchestrators:{orchestrator_name}:{type}`

**Examples**:
- `agentic-dev:orchestrators:leads:tasks`
- `agentic-dev:orchestrators:leads:results`
- `agentic-dev:orchestrators:outreach:tasks`
- `agentic-dev:orchestrators:outreach:results`

## Stream Naming by Component

| Tier | Component | Pattern | Task Stream | Result Stream |
|------|-----------|---------|-------------|---------------|
| 1 | Manager | `{t}:manager` | `manager:tasks` | `manager:results` |
| 2 | Leads Orch. | `{t}:orchestrators:leads` | `orchestrators:leads:tasks` | `orchestrators:leads:results` |
| 2 | Outreach Orch. | `{t}:orchestrators:outreach` | `orchestrators:outreach:tasks` | `orchestrators:outreach:results` |
| 3 | RAG Agent | `{t}:agents:rag` | `agents:rag:tasks` | `agents:rag:results` |
| 3 | Persistence | `{t}:agents:persistence` | `agents:persistence:tasks` | `agents:persistence:results` |
| 3 | Copywriter | `{t}:agents:copywriter` | `agents:copywriter:tasks` | `agents:copywriter:results` |

## Data Flow

```
Manager Receives Request
    ↓
{tenant}:manager:tasks
    ↓
Manager Routes to Orchestrator
    ├─→ {tenant}:orchestrators:leads:tasks
    │   ↓
    │   Leads Orchestrator delegates to agents
    │   ├─→ {tenant}:agents:rag:tasks
    │   ├─→ {tenant}:agents:persistence:tasks
    │   └─→ {tenant}:agents:deduplication:tasks
    │
    └─→ {tenant}:orchestrators:outreach:tasks
        ↓
        Outreach Orchestrator delegates to agents
        ├─→ {tenant}:agents:copywriter:tasks
        ├─→ {tenant}:agents:booking:tasks
        └─→ {tenant}:agents:sequencing:tasks

Results Flow Upstream
{tenant}:agents:*:results
    ↓
{tenant}:orchestrators:leads:results
{tenant}:orchestrators:outreach:results
    ↓
{tenant}:manager:results
```

## Consumer Configuration

### Leads Orchestrator
```python
task_stream = f"{tenant_id}:orchestrators:leads:tasks"
result_stream = f"{tenant_id}:orchestrators:leads:results"
consumer_group = "leads-workers"
```

### Outreach Orchestrator
```python
task_stream = f"{tenant_id}:orchestrators:outreach:tasks"
result_stream = f"{tenant_id}:orchestrators:outreach:results"
consumer_group = "outreach-workers"
```

### Agent Example (RAG)
```python
task_stream = f"{tenant_id}:agents:rag:tasks"
result_stream = f"{tenant_id}:agents:rag:results"
consumer_group = "rag-workers"
```

## Key Files

| File | Purpose |
|------|---------|
| `tiers/tier_1/manager/policy/router.py` | Manager routes to orchestrators |
| `tiers/tier_1/manager/tools/delegation_tools.py` | Delegation to orchestrators |
| `tiers/tier_2/leads_orchestrator/consumer.py` | Leads consumer configuration |
| `tiers/tier_2/outreach_orchestrator/consumer.py` | Outreach consumer configuration |
| `docs/architecture/HIERARCHICAL_ORCHESTRATORS.md` | Full hierarchy documentation |
| `.github/copilot-instructions.md` | Canonical naming reference |

## Verification

### Check streams exist
```powershell
python -c "
import redis, os
from dotenv import load_dotenv
load_dotenv()
r = redis.from_url(os.getenv('REDIS_URL'))
for stream in ['orchestrators:leads:tasks', 'orchestrators:leads:results', 
               'orchestrators:outreach:tasks', 'orchestrators:outreach:results']:
    print(f'{stream}: {r.xlen(f\"agentic-dev:{stream}\")} messages')
"
```

### Run E2E test
```powershell
python fresh_test.py
```

### Check Redis browser
Navigate to `agentic-dev` → you should see `orchestrators/` folder with `leads/` and `outreach/` subfolders.

## Why This Structure?

✅ **Consistency**: Same pattern as `agents/` folder  
✅ **Clarity**: Hierarchy explicit in Redis browser  
✅ **Scalability**: Easy to add new orchestrators  
✅ **Maintainability**: Clear tier relationships  
✅ **Documentation**: Self-explanatory naming  

---

For detailed information, see [HIERARCHICAL_ORCHESTRATORS.md](./HIERARCHICAL_ORCHESTRATORS.md)
