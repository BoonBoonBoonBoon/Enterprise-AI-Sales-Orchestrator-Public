# Scripts Directory

Operational scripts organized by category for system initialization, monitoring, and maintenance.

## Directory Structure

```
scripts/
├── startup/                     # Initialization scripts
│   ├── generate_mock_leads.py   # Create test lead data
│   ├── ingest_cli.py            # Enqueue ingestion tasks
│   └── __init__.py
├── monitoring/                  # Observability and health checks
│   ├── health_check.py          # Service health verification
│   ├── health_server.py         # HTTP health endpoint (port 8080)
│   ├── streams_health.py        # Redis stream status
│   ├── redis_health.py          # Redis connectivity checks
│   ├── redis_stream_smoke.py    # Stream smoke tests
│   └── __init__.py
├── maintenance/                 # Operations and maintenance
│   ├── streams_group_reset.py   # Reset consumer groups
│   ├── dlq_requeue.py          # Reprocess DLQ messages
│   ├── dlq_automation.py        # Automated DLQ handling
│   ├── check_namespace.py       # Stream namespace validation
│   └── __init__.py
├── README.md                    # This file
└── [legacy scripts]             # To be organized/deprecated

```

## Script Categories

### Startup Scripts (`scripts/startup/`)

Used during system initialization or deployment.

#### `generate_mock_leads.py`

**Purpose:** Generate test data for development and testing

**Usage:**

```bash
cd scripts/startup
python generate_mock_leads.py --count 100 --industry fintech
```

**Options:**

- `--count` - Number of leads to generate
- `--industry` - Filter by industry
- `--region` - Filter by region

**Output:** Enqueues tasks to RAG and Persistence agents

---

#### `ingest_cli.py`

**Purpose:** Manual task ingestion via CLI

**Usage:**

```bash
python ../ingest_cli.py --mode ingest --task-type lead_discovery
```

**Docker:**

```bash
docker compose --profile tools run --rm ingest_cli
```

**Options:**

- `--mode` - Ingestion mode (ingest, test, debug)
- `--task-type` - Task type to ingest
- `--count` - Number of tasks

---

### Monitoring Scripts (`scripts/monitoring/`)

Used for operational visibility and health checks.

#### `health_check.py`

**Purpose:** Verify service health and connectivity

**Usage:**

```bash
python health_check.py
```

**Checks:**

- Redis connectivity and version
- Database connectivity and migrations
- Vector DB availability
- External API endpoints
- Consumer group status

**Output:**

```
✓ Redis connected (v7.0.0)
✓ Database ready (migrations: 15/15)
✓ Vector DB accessible (Pinecone)
✓ Consumer groups healthy
✗ External API error (CrunchBase timeout)
```

---

#### `health_server.py`

**Purpose:** HTTP health check endpoint

**Usage:**

```bash
python health_server.py --host 0.0.0.0 --port 8080
```

**Endpoints:**

- `GET /health` - Full health status (JSON)
- `GET /healthz` - Kubernetes liveness probe
- `GET /ready` - Readiness probe
- `GET /metrics` - Prometheus metrics

**Docker:**

```yaml
# docker-compose.yml
health_server:
  command: ["python", "scripts/monitoring/health_server.py"]
  ports:
    - "8080:8080"
```

---

#### `streams_health.py`

**Purpose:** Monitor Redis Streams status

**Usage:**

```bash
python streams_health.py
```

**Monitors:**

- Stream sizes (rag:tasks, rag:results, etc.)
- Consumer group lag per agent
- Pending messages (to-be-retried)
- DLQ depth
- Message throughput (msg/sec)

**Output:**

```
Stream: rag:tasks
├─ Length: 1234 messages
├─ Consumer Group: rag-workers
│  ├─ Consumer 1: pending=5, idle=2.3s
│  ├─ Consumer 2: pending=4, idle=1.8s
│  └─ Lag: 9 messages
├─ DLQ Depth: 2 messages
└─ Throughput: 45 msg/sec
```

---

#### `redis_health.py`

**Purpose:** Check Redis connectivity and status

**Usage:**

```bash
python redis_health.py --url redis://localhost:6379
```

**Checks:**

- Connection (ping)
- Memory usage
- Key count
- Persistence mode
- Replication status

---

#### `redis_stream_smoke.py`

**Purpose:** Quick smoke test of Redis Streams

**Usage:**

```bash
python redis_stream_smoke.py
```

**Tests:**

- Create stream
- Add messages
- Create consumer group
- Consume messages
- Cleanup

---

### Maintenance Scripts (`scripts/maintenance/`)

Used for ongoing system operations.

#### `streams_group_reset.py`

**Purpose:** Reset consumer group to different position

**Usage:**

```bash
# Reset to latest (new messages only)
python streams_group_reset.py --stream rag:tasks --group rag-workers --position latest

# Reset to beginning (replay all)
python streams_group_reset.py --stream rag:tasks --group rag-workers --position start

# Reset to specific message ID
python streams_group_reset.py --stream rag:tasks --group rag-workers --position 1705326600000-0
```

**Options:**

- `--stream` - Stream name (rag:tasks, persist:tasks, etc.)
- `--group` - Consumer group name
- `--position` - start, latest, or message ID

---

#### `dlq_requeue.py`

**Purpose:** Reprocess messages from Dead-Letter Queue

**Usage:**

```bash
# Replay all DLQ messages
python dlq_requeue.py --stream rag:tasks:dlq --destination rag:tasks

# Replay specific count
python dlq_requeue.py --stream rag:tasks:dlq --destination rag:tasks --limit 10

# Replay with delay
python dlq_requeue.py --stream rag:tasks:dlq --destination rag:tasks --delay 5s
```

**Workflow:**

1. Read from \*.dlq stream
2. Apply fixes (if any)
3. Re-enqueue to original stream
4. Mark as requeued

---

#### `dlq_automation.py`

**Purpose:** Automatically handle DLQ messages

**Usage:**

```bash
# Run daemon that processes DLQ periodically
python dlq_automation.py --interval 60 --max-age 3600

# Run once
python dlq_automation.py --once
```

**Options:**

- `--interval` - Check interval (seconds)
- `--max-age` - Max age before archiving (seconds)
- `--once` - Single run only
- `--archive` - Archive processed messages

---

#### `check_namespace.py`

**Purpose:** Validate stream namespace and structure

**Usage:**

```bash
python check_namespace.py --namespace agentic-prod
```

**Validates:**

- Stream naming conventions
- Consumer group presence
- Required streams exist
- Retention policies

---

## Running Scripts in Docker

### One-off Execution

```bash
# Health check
docker compose exec manager python scripts/monitoring/health_check.py

# Generate mock data
docker compose exec manager python scripts/startup/generate_mock_leads.py

# Monitor streams
docker compose exec manager python scripts/monitoring/streams_health.py
```

### Background Service (health_server)

Already running via `docker compose`:

```bash
curl http://localhost:8080/health | jq
```

### In-Container Shell

```bash
# Interactive
docker compose exec -it manager /bin/bash

# Then run any script
python scripts/monitoring/redis_health.py
```

## Running Scripts Locally

### Prerequisites

```bash
# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\Activate.ps1  # PowerShell

# Set environment
export REDIS_URL=redis://localhost:6379
export SUPABASE_URL=https://xxx.supabase.co
export SUPABASE_KEY=<SUPABASE_JWT>
```

### Execute

```bash
# From root of workspace
python scripts/monitoring/health_check.py

# From scripts/ directory
cd scripts/monitoring
python health_check.py

# With arguments
python scripts/startup/generate_mock_leads.py --count 1000 --industry fintech
```

## Common Tasks

### Check System Health

```bash
python scripts/monitoring/health_check.py
curl http://localhost:8080/health | jq
```

### Monitor Consumer Lag

```bash
python scripts/monitoring/streams_health.py

# Watch continuously
watch -n 5 "python scripts/monitoring/streams_health.py"
```

### Generate Test Data

```bash
python scripts/startup/generate_mock_leads.py --count 100
```

### Reset Stream Consumer Group

```bash
# Start from latest
python scripts/maintenance/streams_group_reset.py \
  --stream rag:tasks \
  --group rag-workers \
  --position latest

# Start from beginning
python scripts/maintenance/streams_group_reset.py \
  --stream rag:tasks \
  --group rag-workers \
  --position start
```

### Reprocess Failed Messages

```bash
python scripts/maintenance/dlq_requeue.py \
  --stream rag:tasks:dlq \
  --destination rag:tasks
```

### Auto-manage DLQ

```bash
# Daemon mode (runs every 60 seconds)
python scripts/maintenance/dlq_automation.py --interval 60

# One-time execution
python scripts/maintenance/dlq_automation.py --once
```

## Script Organization Guidelines

### Startup Scripts

- Run during system initialization
- Set up infrastructure state
- Usually one-time or infrequent
- Examples: migrations, seeding, setup

### Monitoring Scripts

- Run continuously or periodically
- Provide operational visibility
- Used for debugging and observability
- Examples: health checks, metrics, diagnostics

### Maintenance Scripts

- Run on-demand for operations
- Fix or manage system state
- Handle edge cases and recovery
- Examples: cleanup, resets, repairs

## Adding New Scripts

### 1. Determine Category

- **Startup:** System initialization? → `scripts/startup/`
- **Monitoring:** Health checks/observability? → `scripts/monitoring/`
- **Maintenance:** Operations/fixes? → `scripts/maintenance/`
- **Other:** Root of `scripts/` (legacy)

### 2. Create Script

```python
#!/usr/bin/env python
"""Description of what script does.

Usage:
    python script_name.py [options]

Examples:
    python script_name.py --help
"""
import argparse
import logging

logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="What this does")
    parser.add_argument("--option", default="value", help="Description")
    args = parser.parse_args()

    logger.info(f"Running with: {args}")
    # Implementation

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
```

### 3. Add to .gitignore (if needed)

```
scripts/generated/  # If generating files
scripts/logs/       # If writing logs
```

### 4. Document in This README

Add entry under appropriate category with:

- Purpose
- Usage
- Options
- Output example

## Debugging

### Enable Verbose Logging

```bash
python scripts/monitoring/health_check.py --log-level DEBUG
```

### Connect to Redis Manually

```bash
redis-cli -u $REDIS_URL XLEN rag:tasks
redis-cli -u $REDIS_URL XINFO GROUPS rag:tasks
```

### Check Specific Stream

```bash
python -c "
from services.redis import RedisClient
r = RedisClient()
print(r.xinfo_stream('rag:tasks'))
"
```

## Performance Considerations

### Long-Running Operations

```bash
# Use nohup for background execution
nohup python scripts/maintenance/dlq_automation.py --interval 60 > dlq_automation.log 2>&1 &

# Or use systemd service
systemctl start agentic-dlq-automation
```

### Parallel Execution

```bash
# Multiple health checks in parallel
parallel ::: \
  "python scripts/monitoring/redis_health.py" \
  "python scripts/monitoring/streams_health.py" \
  "python scripts/monitoring/health_check.py"
```

### Scheduled Execution (Cron)

```bash
# Run health check every 5 minutes
*/5 * * * * cd /app && python scripts/monitoring/health_check.py >> health.log 2>&1

# Run DLQ automation every hour
0 * * * * cd /app && python scripts/maintenance/dlq_automation.py --once
```

## See Also

- `deployment/README.md` - Deployment procedures
- `docs/ARCHITECTURE.md` - System architecture
- `docs/REDIS_STREAMS.md` - Redis Streams details

---

**Last Updated:** Task 18 - Scripts reorganization  
**Categories:** Startup (4 scripts), Monitoring (6 scripts), Maintenance (4 scripts)  
**Status:** Directory structure created, scripts to be migrated
