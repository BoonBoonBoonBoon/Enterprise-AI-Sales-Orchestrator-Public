# Scripts Reference

This reference documents the utility scripts in the `scripts/` directory.

## Directory Structure

```
scripts/
├── db/              # Database operations
├── demos/           # Example/demo scripts
├── deployment/      # Deployment utilities
├── diagnostics/     # System diagnostics
├── monitoring/      # Monitoring tools
├── redis/           # Redis operations
├── sql/             # SQL scripts
├── startup/         # Service startup
├── testing/         # Test utilities
├── utils/           # General utilities
└── windows/         # Windows-specific
```

---

## Database Scripts

### `scripts/db/reset.py`

Reset database to clean state.

```powershell
.\.venv\Scripts\python.exe scripts/db/reset.py
```

Options:

- `--confirm` - Skip confirmation prompt
- `--keep-clients` - Preserve clients table

### `scripts/db/seed.py`

Seed database with sample data.

```powershell
.\.venv\Scripts\python.exe scripts/db/seed.py
```

Options:

- `--tenant` - Target tenant ID
- `--leads N` - Number of leads to create

---

## Redis Scripts

### `scripts/redis/inspect_streams.py`

View Redis stream contents.

```powershell
.\.venv\Scripts\python.exe scripts/redis/inspect_streams.py
```

Options:

- `--tenant` - Filter by tenant
- `--stream` - Specific stream name
- `--count N` - Number of messages

### `scripts/redis/clear_streams.py`

Clear stream data.

```powershell
.\.venv\Scripts\python.exe scripts/redis/clear_streams.py --tenant agentic-dev
```

Options:

- `--tenant` - Target tenant (required)
- `--confirm` - Skip prompt
- `--preserve-groups` - Keep consumer groups

### `scripts/redis/monitor.py`

Real-time stream monitoring.

```powershell
.\.venv\Scripts\python.exe scripts/redis/monitor.py
```

Displays:

- Active streams
- Consumer lag
- Message rates

---

## Startup Scripts

### `scripts/startup/run_all.ps1`

Start all consumers.

```powershell
.\scripts\startup\run_all.ps1
```

Starts:

1. RAG Agent
2. Persistence Agent
3. Copywriter Agent
4. Leads Orchestrator
5. Outreach Orchestrator
6. Manager

### `scripts/startup/run_tier.ps1`

Start specific tier.

```powershell
.\scripts\startup\run_tier.ps1 -Tier 3
```

Options:

- `-Tier 1|2|3` - Which tier to start

---

## Diagnostics

### `scripts/diagnostics/health_check.py`

Check system health.

```powershell
.\.venv\Scripts\python.exe scripts/diagnostics/health_check.py
```

Checks:

- Redis connectivity
- Supabase connectivity
- Consumer group status
- Environment variables

Output:

```
✓ Redis: Connected
✓ Supabase: Connected
✓ Consumer groups: 5/5 active
✓ Environment: All required vars set
```

### `scripts/diagnostics/trace_task.py`

Trace a task through the system.

```powershell
.\.venv\Scripts\python.exe scripts/diagnostics/trace_task.py --task-id <uuid>
```

Output:

```
Task: abc123
├── Manager received: 10:00:00
├── Leads started: 10:00:01
│   ├── RAG delegated: 10:00:02
│   └── RAG completed: 10:00:03
├── Leads completed: 10:00:04
└── Manager result: 10:00:05
Total: 5.2s
```

---

## Testing Scripts

### `scripts/testing/e2e_flow.py`

Run end-to-end flow test.

```powershell
.\.venv\Scripts\python.exe scripts/testing/e2e_flow.py
```

### `scripts/testing/load_test.py`

Load testing utility.

```powershell
.\.venv\Scripts\python.exe scripts/testing/load_test.py --rps 10 --duration 60
```

Options:

- `--rps N` - Requests per second
- `--duration N` - Test duration (seconds)
- `--agent` - Target agent

---

## Demo Scripts

### `scripts/demos/manager_demo.py`

Demonstrate Manager routing.

```powershell
.\.venv\Scripts\python.exe scripts/demos/manager_demo.py
```

### `scripts/demos/copywriter_demo.py`

Demonstrate email generation.

```powershell
.\.venv\Scripts\python.exe scripts/demos/copywriter_demo.py
```

---

## Deployment Scripts

### `scripts/deployment/build.ps1`

Build Docker images.

```powershell
.\scripts\deployment\build.ps1 -Tag v1.0.0
```

### `scripts/deployment/deploy.ps1`

Deploy to environment.

```powershell
.\scripts\deployment\deploy.ps1 -Environment staging
```

---

## Monitoring

### `scripts/monitoring/metrics.py`

Export Prometheus metrics.

```powershell
.\.venv\Scripts\python.exe scripts/monitoring/metrics.py
```

Exposes:

- `agentic_tasks_total`
- `agentic_task_duration_seconds`
- `agentic_consumer_lag`

### `scripts/monitoring/alerts.py`

Check alert conditions.

```powershell
.\.venv\Scripts\python.exe scripts/monitoring/alerts.py
```

---

## Windows-Specific

### `scripts/windows/setup.ps1`

Windows environment setup.

```powershell
.\scripts\windows\setup.ps1
```

Installs:

- Python dependencies
- Redis (via chocolatey)
- Environment config

### `scripts/windows/kill_consumers.ps1`

Kill all Python consumers.

```powershell
.\scripts\windows\kill_consumers.ps1
```

---

## Script Guidelines

### Running Scripts

Always use the venv Python:

```powershell
# Correct
.\.venv\Scripts\python.exe scripts/my_script.py

# Or activate venv first
.\.venv\Scripts\Activate.ps1
python scripts/my_script.py
```

### Script Template

```python
#!/usr/bin/env python
"""Script description."""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import settings

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default=settings.tenant_id)
    args = parser.parse_args()

    # Script logic here
    print(f"Running for tenant: {args.tenant}")

if __name__ == "__main__":
    main()
```

## Related

- [Consumer Commands](consumers.md)
- [Running Consumers Guide](../../guides/ops/consumers.md)
- [Troubleshooting](../../guides/ops/troubleshooting.md)
