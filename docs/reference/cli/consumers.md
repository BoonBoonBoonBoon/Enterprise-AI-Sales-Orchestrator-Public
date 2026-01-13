# Consumer Commands

This reference documents commands for running and managing agent consumers.

## Overview

Each agent/orchestrator runs as a consumer process that reads from Redis Streams.

## Consumer Modules

| Component             | Module Path                                   |
| --------------------- | --------------------------------------------- |
| Manager               | `tiers.tier_1.manager.consumer`               |
| Leads Orchestrator    | `tiers.tier_2.leads_orchestrator.consumer`    |
| Outreach Orchestrator | `tiers.tier_2.outreach_orchestrator.consumer` |
| RAG Agent             | `tiers.tier_3.rag_agent.consumer`             |
| Persistence Agent     | `tiers.tier_3.persistence_agent.consumer`     |
| Copywriter Agent      | `tiers.tier_3.copywriter_agent.consumer`      |

---

## Running Consumers

### Single Consumer

```powershell
# Always use venv Python
.\.venv\Scripts\python.exe -m tiers.tier_3.rag_agent.consumer
```

### With Environment Variables

```powershell
$env:TENANT_ID = "agentic-dev"
$env:LOG_LEVEL = "DEBUG"
.\.venv\Scripts\python.exe -m tiers.tier_3.rag_agent.consumer
```

### Background Process

```powershell
Start-Process -NoNewWindow -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "tiers.tier_3.rag_agent.consumer"
```

---

## Start All Consumers

### PowerShell Script

```powershell
# Start Tier 3 (Execution)
$tier3 = @(
    "tiers.tier_3.rag_agent.consumer",
    "tiers.tier_3.persistence_agent.consumer",
    "tiers.tier_3.copywriter_agent.consumer"
)

foreach ($module in $tier3) {
    Start-Process -NoNewWindow -FilePath ".\.venv\Scripts\python.exe" `
        -ArgumentList "-m", $module
    Start-Sleep -Seconds 2
}

# Start Tier 2 (Orchestration)
Start-Process -NoNewWindow -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "tiers.tier_2.leads_orchestrator.consumer"

Start-Process -NoNewWindow -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "tiers.tier_2.outreach_orchestrator.consumer"

Start-Sleep -Seconds 2

# Start Tier 1 (Manager)
Start-Process -NoNewWindow -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "tiers.tier_1.manager.consumer"
```

---

## Stop Consumers

### Graceful Shutdown

Send SIGINT (Ctrl+C) to the consumer process.

### Kill All

```powershell
# Find Python processes
Get-Process python | Where-Object {
    $_.CommandLine -like "*consumer*"
} | Stop-Process -Force

# Or kill all Python
Get-Process python | Stop-Process -Force
```

---

## Consumer Arguments

Most consumers accept these environment variables:

| Variable         | Default                    | Description             |
| ---------------- | -------------------------- | ----------------------- |
| `TENANT_ID`      | `agentic-dev`              | Multi-tenant identifier |
| `REDIS_URL`      | `redis://localhost:6379/0` | Redis connection        |
| `LOG_LEVEL`      | `INFO`                     | Logging verbosity       |
| `CONSUMER_GROUP` | `{agent}_group`            | Consumer group name     |
| `CONSUMER_NAME`  | `consumer_1`               | Unique consumer ID      |

---

## Scaling Consumers

### Multiple Instances

Run same consumer with different names:

```powershell
# Instance 1
$env:CONSUMER_NAME = "consumer_1"
.\.venv\Scripts\python.exe -m tiers.tier_3.rag_agent.consumer

# Instance 2 (separate terminal)
$env:CONSUMER_NAME = "consumer_2"
.\.venv\Scripts\python.exe -m tiers.tier_3.rag_agent.consumer
```

### Docker Compose Scaling

```powershell
docker-compose up -d --scale rag-agent=3
```

---

## Health Checks

### Check Consumer Status

```powershell
# List consumer groups
.\.venv\Scripts\python.exe -c "
from services.redis.client import get_redis_client
r = get_redis_client()
for key in r.scan_iter('*:tasks'):
    try:
        groups = r.xinfo_groups(key)
        print(f'{key}: {len(groups)} groups')
    except: pass
"
```

### Check Consumer Lag

```powershell
.\.venv\Scripts\python.exe -c "
from services.redis.client import get_redis_client
r = get_redis_client()
stream = 'agentic-dev:agents:rag:tasks'
groups = r.xinfo_groups(stream)
for g in groups:
    print(f'{g[\"name\"]}: lag={g[\"lag\"]} pending={g[\"pending\"]}')
"
```

---

## Debugging Consumers

### Enable Debug Logging

```powershell
$env:LOG_LEVEL = "DEBUG"
.\.venv\Scripts\python.exe -m tiers.tier_3.rag_agent.consumer
```

### Interactive Mode

```powershell
# Python shell with imports
.\.venv\Scripts\python.exe -i -c "
from tiers.tier_3.rag_agent.rag_agent_harness import RAGAgentHarness
harness = RAGAgentHarness('agentic-dev')
print('Harness ready. Use harness.process_task({...}) to test')
"
```

---

## Consumer Lifecycle

```
┌──────────────────────────────────────┐
│           Consumer Startup           │
├──────────────────────────────────────┤
│ 1. Load settings                     │
│ 2. Connect to Redis                  │
│ 3. Create/join consumer group        │
│ 4. Enter read loop                   │
└──────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────┐
│            Read Loop                 │
├──────────────────────────────────────┤
│ 1. XREADGROUP (block 5000ms)         │
│ 2. Parse TaskEnvelope                │
│ 3. process_task()                    │
│ 4. XADD result                       │
│ 5. XACK task                         │
│ 6. Loop                              │
└──────────────────────────────────────┘
              │
              ▼ (SIGINT)
┌──────────────────────────────────────┐
│         Graceful Shutdown            │
├──────────────────────────────────────┤
│ 1. Complete current task             │
│ 2. Close Redis connection            │
│ 3. Exit cleanly                      │
└──────────────────────────────────────┘
```

---

## VS Code Tasks

Use VS Code tasks for convenience:

```json
{
  "label": "Run RAG Agent",
  "type": "shell",
  "command": "${workspaceFolder}/.venv/Scripts/python.exe",
  "args": ["-m", "tiers.tier_3.rag_agent.consumer"],
  "isBackground": true,
  "problemMatcher": []
}
```

## Related

- [Scripts Reference](scripts.md)
- [Running Consumers Guide](../../guides/ops/consumers.md)
- [Harness Configuration](../config/harness.md)
