# Quick Start

Get the Agentic System running locally in under 10 minutes.

## Prerequisites

- Python 3.11+ installed
- Redis running (Docker or local)
- Supabase account (free tier works)
- OpenAI API key

## Step 1: Clone and Install

```powershell
# Clone the repository
git clone https://github.com/BoonBoonBoonBoon/Agentic-System.git
cd Agentic-System

# Create virtual environment
python -m venv .venv

# Activate (PowerShell)
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Start Redis

**Option A: Docker (recommended)**

```powershell
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

**Option B: Use VS Code task**

```
Ctrl+Shift+P → Tasks: Run Task → "Redis: Start"
```

## Step 3: Configure Environment

```powershell
# Copy example config
Copy-Item .env.example .env
```

Edit `.env` with your values:

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_JWT_SECRET=your-jwt-secret
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=your-openai-api-key
TENANT_ID=agentic-dev
```

See [Environment Setup](environment.md) for all options.

## Step 4: Start Consumers

Open multiple terminals and start the agent consumers:

**Terminal 1 - Manager:**

```powershell
& ".venv/Scripts/python.exe" -m tiers.tier_1.manager.consumer
```

**Terminal 2 - Leads Orchestrator:**

```powershell
& ".venv/Scripts/python.exe" -m tiers.tier_2.leads_orchestrator.consumer
```

**Terminal 3 - RAG Agent:**

```powershell
& ".venv/Scripts/python.exe" -m tiers.tier_3.rag_agent.consumer
```

**Terminal 4 - Persistence Agent:**

```powershell
& ".venv/Scripts/python.exe" -m tiers.tier_3.persistence_agent.consumer
```

You should see each consumer log:

```
INFO - Listening on agentic-dev:manager:tasks...
```

## Step 5: Send a Test Task

In a new terminal, send a task to the system:

```powershell
& ".venv/Scripts/python.exe" -c @"
import json
from services.redis.client import get_redis_client

redis = get_redis_client()
task = {
    'task_id': 'test-001',
    'tenant_id': 'agentic-dev',
    'payload': {
        'action': 'health_check'
    },
    'metadata': {
        'source': 'quickstart'
    }
}
redis.xadd('agentic-dev:manager:tasks', {'data': json.dumps(task)})
print('Task sent!')
"@
```

Watch the Manager terminal — you should see the task being processed.

## Step 6: View Results

Check the result stream:

```powershell
& ".venv/Scripts/python.exe" -c @"
from services.redis.client import get_redis_client
redis = get_redis_client()
results = redis.xrange('agentic-dev:manager:results', count=5)
for msg_id, data in results:
    print(f'{msg_id}: {data}')
"@
```

## What's Running?

```
┌─────────────────────────────────────────────┐
│              Your Test Task                 │
└─────────────────────┬───────────────────────┘
                      ▼
┌─────────────────────────────────────────────┐
│            Manager Agent (T1)               │
│         Receives → Routes → Delegates       │
└─────────────────────┬───────────────────────┘
                      ▼
┌─────────────────────────────────────────────┐
│        Leads Orchestrator (T2)              │
│      Decomposes workflow into tasks         │
└─────────────────────┬───────────────────────┘
                      ▼
┌─────────────────────────────────────────────┐
│    RAG Agent (T3)    Persistence Agent (T3) │
│    Context retrieval      CRUD operations   │
└─────────────────────────────────────────────┘
```

## Next Steps

- [Your First Task](first-task.md) — Deeper tutorial on task flow
- [Concepts](../concepts/index.md) — Understand the architecture
- [Running Consumers](../guides/ops/consumers.md) — Production consumer management

## Troubleshooting

### "ModuleNotFoundError: No module named 'tiers'"

Ensure you're in the project root and venv is activated:

```powershell
cd "C:\path\to\Agentic-System"
.\.venv\Scripts\Activate.ps1
```

### "Redis connection refused"

Start Redis first (Step 2).

### "SUPABASE_URL not set"

Check `.env` exists and has correct values (Step 3).

### Consumer hangs without processing

Verify the stream name matches:

- Task sent to: `agentic-dev:manager:tasks`
- Consumer listening on: Same stream (check `TENANT_ID`)
