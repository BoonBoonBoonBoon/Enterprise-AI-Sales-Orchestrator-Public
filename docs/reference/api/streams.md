# Stream Keys Reference

Complete reference for Redis Stream key naming conventions.

## Key Format

```
{tenant_id}:{tier_prefix}:{component_name}:{direction}
```

| Segment          | Description       | Examples                             |
| ---------------- | ----------------- | ------------------------------------ |
| `tenant_id`      | Tenant identifier | `agentic-dev`, `acme-corp`           |
| `tier_prefix`    | Component tier    | `manager`, `orchestrators`, `agents` |
| `component_name` | Component name    | `leads`, `rag`, `persistence`        |
| `direction`      | Task or result    | `tasks`, `results`                   |

## All Stream Keys

### Manager (Tier 1)

| Stream                     | Purpose               |
| -------------------------- | --------------------- |
| `{tenant}:manager:tasks`   | Incoming goals/events |
| `{tenant}:manager:results` | Manager decisions     |

### Orchestrators (Tier 2)

| Stream                                    | Purpose                 |
| ----------------------------------------- | ----------------------- |
| `{tenant}:orchestrators:leads:tasks`      | Lead processing tasks   |
| `{tenant}:orchestrators:leads:results`    | Lead processing results |
| `{tenant}:orchestrators:outbound:tasks`   | Outreach tasks          |
| `{tenant}:orchestrators:outbound:results` | Outreach results        |
| `{tenant}:orchestrators:inbound:tasks`    | Inbound handling tasks  |
| `{tenant}:orchestrators:inbound:results`  | Inbound results         |

### Agents (Tier 3)

| Stream                                | Purpose                  |
| ------------------------------------- | ------------------------ |
| `{tenant}:agents:rag:tasks`           | Context retrieval tasks  |
| `{tenant}:agents:rag:results`         | Retrieved context        |
| `{tenant}:agents:persistence:tasks`   | CRUD operations          |
| `{tenant}:agents:persistence:results` | CRUD results             |
| `{tenant}:agents:copywriter:tasks`    | Content generation       |
| `{tenant}:agents:copywriter:results`  | Generated content        |
| `{tenant}:agents:sequencing:tasks`    | Channel sequencing tasks |
| `{tenant}:agents:sequencing:results`  | Sequencing results       |

## Non-Stream Keys

Some workflows use Redis hashes for small pieces of state (not streams). For example, Outreach auto-send stores routing context here:

- `{tenant}:outreach:auto_send` (Redis hash keyed by `copy_task_id`)

## Building Keys

### Python Helper

```python
def build_stream_key(
    tenant_id: str,
    tier: str,
    component: str,
    direction: str = "tasks"
) -> str:
    """Build a stream key following naming conventions."""
    return f"{tenant_id}:{tier}:{component}:{direction}"

# Examples
build_stream_key("agentic-dev", "agents", "rag", "tasks")
# → "agentic-dev:agents:rag:tasks"

build_stream_key("agentic-dev", "orchestrators", "leads", "results")
# → "agentic-dev:orchestrators:leads:results"
```

### Stream Key Class

```python
from dataclasses import dataclass

@dataclass
class StreamKey:
    tenant_id: str
    tier: str
    component: str
    direction: str = "tasks"

    def __str__(self) -> str:
        return f"{self.tenant_id}:{self.tier}:{self.component}:{self.direction}"

    @property
    def tasks(self) -> str:
        return f"{self.tenant_id}:{self.tier}:{self.component}:tasks"

    @property
    def results(self) -> str:
        return f"{self.tenant_id}:{self.tier}:{self.component}:results"

# Usage
rag = StreamKey("agentic-dev", "agents", "rag")
print(rag.tasks)    # agentic-dev:agents:rag:tasks
print(rag.results)  # agentic-dev:agents:rag:results
```

## Consumer Groups

Each component should use a consistent consumer group name:

| Component            | Consumer Group        |
| -------------------- | --------------------- |
| Manager              | `manager_workers`     |
| LeadsOrchestrator    | `leads_workers`       |
| OutreachOrchestrator | `outreach_workers`    |
| RAGAgent             | `rag_workers`         |
| PersistenceAgent     | `persistence_workers` |
| CopywriterAgent      | `copywriter_workers`  |

## Communication Matrix

### Allowed Communications

| From     | To          | Stream                             |
| -------- | ----------- | ---------------------------------- |
| External | Manager     | `{t}:manager:tasks`                |
| Manager  | Leads       | `{t}:orchestrators:leads:tasks`    |
| Manager  | Outreach    | `{t}:orchestrators:outbound:tasks` |
| Leads    | RAG         | `{t}:agents:rag:tasks`             |
| Leads    | Persistence | `{t}:agents:persistence:tasks`     |
| Outreach | Copywriter  | `{t}:agents:copywriter:tasks`      |
| Outreach | Persistence | `{t}:agents:persistence:tasks`     |

### Forbidden Communications

| From       | To          | Why                      |
| ---------- | ----------- | ------------------------ |
| Leads      | Outreach    | ❌ Horizontal (Tier 2→2) |
| RAG        | Persistence | ❌ Horizontal (Tier 3→3) |
| Copywriter | RAG         | ❌ Horizontal (Tier 3→3) |

## Validation

### Check Stream Key

```python
import re

STREAM_PATTERN = re.compile(
    r"^[\w-]+:(manager|orchestrators|agents):[\w-]+:(tasks|results)$"
)

def validate_stream_key(key: str) -> bool:
    """Validate stream key follows convention."""
    return bool(STREAM_PATTERN.match(key))

# Tests
validate_stream_key("agentic-dev:agents:rag:tasks")  # True
validate_stream_key("agentic-dev:rag:tasks")         # False (missing tier)
validate_stream_key("agents:rag:tasks")              # False (missing tenant)
```

## Debugging

### List All Streams

```powershell
redis-cli KEYS "*:tasks"
redis-cli KEYS "*:results"
```

### Inspect Stream

```bash
# Stream info
redis-cli XINFO STREAM agentic-dev:agents:rag:tasks

# Consumer groups
redis-cli XINFO GROUPS agentic-dev:agents:rag:tasks

# Pending messages
redis-cli XPENDING agentic-dev:agents:rag:tasks rag_workers
```

### Read Messages

```bash
# Last 5 messages
redis-cli XREVRANGE agentic-dev:agents:rag:tasks + - COUNT 5
```

## Related

- [Redis Streams Concept](../../concepts/redis-streams.md)
- [Envelope Schema](envelope.md)
- [Multi-Tenancy](../../concepts/multi-tenancy.md)
