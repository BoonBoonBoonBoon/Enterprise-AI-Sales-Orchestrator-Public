# Running Consumers

This guide covers running and managing agent consumers in the Agentic System.

## What is a Consumer?

A consumer is a long-running process that:

1. Listens on a Redis stream
2. Processes incoming messages
3. Publishes results

Each agent/orchestrator has its own consumer.

## Starting Consumers

### Individual Consumer

```powershell
# RAG Agent
& ".venv/Scripts/python.exe" -m tiers.tier_3.rag_agent.consumer

# Persistence Agent
& ".venv/Scripts/python.exe" -m tiers.tier_3.persistence_agent.consumer

# Copywriter Agent
& ".venv/Scripts/python.exe" -m tiers.tier_3.copywriter_agent.consumer

# Leads Orchestrator
& ".venv/Scripts/python.exe" -m tiers.tier_2.leads_orchestrator.consumer

# Outreach Orchestrator
& ".venv/Scripts/python.exe" -m tiers.tier_2.outreach_orchestrator.consumer

# Manager
& ".venv/Scripts/python.exe" -m tiers.tier_1.manager.consumer
```

### All Consumers (Development)

Create a script to start all:

```powershell
# scripts/startup/start_all.ps1

$env:PYTHONIOENCODING = "utf-8"
$venv = ".venv/Scripts/python.exe"

Start-Process -FilePath $venv -ArgumentList "-m tiers.tier_3.rag_agent.consumer"
Start-Process -FilePath $venv -ArgumentList "-m tiers.tier_3.persistence_agent.consumer"
Start-Process -FilePath $venv -ArgumentList "-m tiers.tier_3.copywriter_agent.consumer"
Start-Process -FilePath $venv -ArgumentList "-m tiers.tier_2.leads_orchestrator.consumer"
Start-Process -FilePath $venv -ArgumentList "-m tiers.tier_1.manager.consumer"

Write-Host "All consumers started"
```

## Consumer Configuration

### Environment Variables

```powershell
$env:TENANT_ID = "agentic-dev"
$env:REDIS_URL = "redis://localhost:6379/0"
$env:LOG_LEVEL = "INFO"
$env:PYTHONIOENCODING = "utf-8"
```

### Consumer Options

Consumers accept configuration via environment or constructor:

```python
harness = RAGAgentHarness(
    tenant_id="agentic-dev",
    redis_url="redis://localhost:6379/0",
    consumer_group="rag_workers",
    consumer_name="worker-1"
)
```

## Scaling Consumers

### Multiple Workers

Run multiple instances of the same consumer:

```powershell
# Terminal 1
$env:CONSUMER_NAME = "worker-1"
& ".venv/Scripts/python.exe" -m tiers.tier_3.persistence_agent.consumer

# Terminal 2
$env:CONSUMER_NAME = "worker-2"
& ".venv/Scripts/python.exe" -m tiers.tier_3.persistence_agent.consumer
```

Each worker in the consumer group gets different messages.

### Docker Scaling

```yaml
# docker-compose.yml
services:
  rag-agent:
    image: agentic-system
    command: python -m tiers.tier_3.rag_agent.consumer
    deploy:
      replicas: 3
```

## Health Monitoring

### Check Consumer Status

```powershell
# List consumer groups
redis-cli XINFO GROUPS agentic-dev:agents:rag:tasks

# Check pending messages
redis-cli XPENDING agentic-dev:agents:rag:tasks rag_workers

# Consumer details
redis-cli XINFO CONSUMERS agentic-dev:agents:rag:tasks rag_workers
```

### Healthy Output

```
1) name: rag_workers
2) consumers: 2
3) pending: 0
4) last-delivered-id: 1705234567890-0
```

### Unhealthy Signs

- `pending` growing continuously
- `consumers: 0` (no active workers)
- Stale `last-delivered-id`

## Graceful Shutdown

Consumers handle SIGINT (Ctrl+C):

```python
class AgentHarness:
    def __init__(self):
        self._running = True
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, sig, frame):
        self.logger.info("Shutdown requested")
        self._running = False

    def run(self):
        while self._running:
            self._process_messages()
        self._cleanup()
```

## Logging

### Configure Log Level

```powershell
$env:LOG_LEVEL = "DEBUG"  # DEBUG, INFO, WARNING, ERROR
```

### Log Output

```
2026-01-13 10:30:00 INFO     [rag_agent] Consumer started
2026-01-13 10:30:01 INFO     [rag_agent] Listening on agentic-dev:agents:rag:tasks
2026-01-13 10:30:05 INFO     [rag_agent] Received task: abc-123
2026-01-13 10:30:05 DEBUG    [rag_agent] Action: get_lead_context
2026-01-13 10:30:06 INFO     [rag_agent] Task completed: abc-123 (success)
```

## Troubleshooting

### Consumer Won't Start

```
Error: Redis connection refused
```

**Fix:** Ensure Redis is running:

```powershell
docker ps | findstr redis
# or
redis-cli ping
```

### Messages Not Processing

```
# Check stream has messages
redis-cli XLEN agentic-dev:agents:rag:tasks

# Check consumer group exists
redis-cli XINFO GROUPS agentic-dev:agents:rag:tasks
```

If group missing, consumer will create it on startup.

### Stuck Messages

```
# Check pending
redis-cli XPENDING agentic-dev:agents:rag:tasks rag_workers - + 10

# Claim stuck messages
redis-cli XCLAIM agentic-dev:agents:rag:tasks rag_workers worker-2 60000 <message-id>
```

## Related

- [Troubleshooting](troubleshooting.md)
- [Monitoring](monitoring.md)
- [Docker Deployment](../deploy/docker.md)
