# Incident Response

This guide covers responding to incidents in the Agentic System.

## Severity Levels

| Level           | Description                | Response Time     |
| --------------- | -------------------------- | ----------------- |
| **P1 Critical** | System down, no processing | Immediate         |
| **P2 High**     | Major feature broken       | 1 hour            |
| **P3 Medium**   | Degraded performance       | 4 hours           |
| **P4 Low**      | Minor issue                | Next business day |

## Common Incidents

### Redis Down

**Symptoms:**

- Consumers can't start
- Tasks not processing
- "Connection refused" errors

**Response:**

```powershell
# Check Redis status
docker ps | findstr redis
redis-cli ping

# Restart Redis
docker restart redis

# Or start fresh
docker-compose up -d redis
```

**Verify:**

```powershell
redis-cli ping
# Should return: PONG
```

### Database Unreachable

**Symptoms:**

- "Supabase connection failed"
- RLS errors
- Timeout errors

**Response:**

```powershell
# Check Supabase status (local)
supabase status

# Restart local Supabase
supabase stop
supabase start

# Check remote - visit dashboard
```

**Verify:**

```python
from services.persistence.supabase_adapter import SupabaseAdapter
adapter = SupabaseAdapter(role="agent_reader")
adapter.query("leads", {}, limit=1)
```

### Consumer Crashed

**Symptoms:**

- Stream backlog growing
- No processing activity
- Process not running

**Response:**

```powershell
# Check if running
Get-Process -Name python -ErrorAction SilentlyContinue

# Restart consumer
& ".venv/Scripts/python.exe" -m tiers.tier_3.rag_agent.consumer
```

**Verify:**

```powershell
# Check stream is being consumed
redis-cli XINFO GROUPS agentic-dev:agents:rag:tasks
# Should show consumers > 0
```

### Message Stuck

**Symptoms:**

- Same message keeps failing
- Pending count not decreasing
- Consumer stuck

**Response:**

```bash
# Check pending messages
redis-cli XPENDING agentic-dev:agents:rag:tasks rag_workers - + 10

# If message is stuck, delete it
redis-cli XACK agentic-dev:agents:rag:tasks rag_workers <message-id>
redis-cli XDEL agentic-dev:agents:rag:tasks <message-id>
```

### LLM Rate Limited

**Symptoms:**

- "Rate limit exceeded" errors
- Copywriter tasks failing
- 429 HTTP responses

**Response:**

```python
# Check current usage
# OpenAI dashboard: platform.openai.com/usage

# Temporary: Reduce request rate
# Or: Switch to backup model
$env:LLM_MODEL = "gpt-3.5-turbo"
```

## Runbooks

### Full System Restart

```powershell
# 1. Stop all consumers
Get-Process -Name python | Stop-Process -Force

# 2. Restart infrastructure
docker-compose restart

# 3. Wait for services
Start-Sleep -Seconds 10

# 4. Verify services
redis-cli ping
supabase status

# 5. Start consumers
& ".venv/Scripts/python.exe" -m tiers.tier_1.manager.consumer &
& ".venv/Scripts/python.exe" -m tiers.tier_2.leads_orchestrator.consumer &
& ".venv/Scripts/python.exe" -m tiers.tier_3.rag_agent.consumer &
& ".venv/Scripts/python.exe" -m tiers.tier_3.persistence_agent.consumer &
```

### Clear Stream Backlog

```bash
# Check backlog size
redis-cli XLEN agentic-dev:agents:rag:tasks

# Trim to last 100 messages
redis-cli XTRIM agentic-dev:agents:rag:tasks MAXLEN 100

# Or delete all (careful!)
redis-cli DEL agentic-dev:agents:rag:tasks
```

### Reset Consumer Group

```bash
# Delete existing group
redis-cli XGROUP DESTROY agentic-dev:agents:rag:tasks rag_workers

# Consumer will recreate on next start
```

## Post-Incident

### Checklist

- [ ] Incident resolved
- [ ] Root cause identified
- [ ] Monitoring updated if needed
- [ ] Runbook updated
- [ ] Post-mortem scheduled (P1/P2)

### Post-Mortem Template

```markdown
# Incident: [Title]

**Date:** YYYY-MM-DD
**Duration:** X hours
**Severity:** P1/P2/P3/P4

## Summary

Brief description of what happened.

## Timeline

- HH:MM - Incident detected
- HH:MM - Investigation started
- HH:MM - Root cause identified
- HH:MM - Fix deployed
- HH:MM - Incident resolved

## Root Cause

What caused the incident.

## Impact

- X tasks failed
- Y minutes of downtime

## Action Items

- [ ] Action 1 (Owner, Due Date)
- [ ] Action 2 (Owner, Due Date)
```

## Related

- [Monitoring](monitoring.md)
- [Troubleshooting](troubleshooting.md)
- [Running Consumers](consumers.md)
