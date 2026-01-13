# Monitoring

This guide covers monitoring the Agentic System in production.

## Monitoring Stack

| Component  | Purpose                    |
| ---------- | -------------------------- |
| Prometheus | Metrics collection         |
| Grafana    | Dashboards & visualization |
| Loki       | Log aggregation            |
| Tempo      | Distributed tracing        |

## Quick Setup

```powershell
# Start monitoring stack
docker-compose -f deployment/docker-compose.observability.yml up -d
```

Access dashboards:

- **Grafana:** http://localhost:3000 (admin/admin)
- **Prometheus:** http://localhost:9090

## Key Metrics

### Agent Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

# Task counters
tasks_processed = Counter(
    'agent_tasks_processed_total',
    'Total tasks processed',
    ['agent_name', 'status', 'tenant_id']
)

# Processing time
task_duration = Histogram(
    'agent_task_duration_seconds',
    'Task processing duration',
    ['agent_name', 'action']
)

# Active consumers
active_consumers = Gauge(
    'agent_active_consumers',
    'Number of active consumers',
    ['agent_name']
)
```

### Redis Stream Metrics

| Metric          | Description      |
| --------------- | ---------------- |
| Stream length   | Pending messages |
| Consumer lag    | Messages behind  |
| Pending entries | Unacknowledged   |

```python
# Collect Redis metrics
def collect_stream_metrics(redis, tenant_id: str):
    streams = [
        f"{tenant_id}:agents:rag:tasks",
        f"{tenant_id}:agents:persistence:tasks",
        # ... more streams
    ]

    for stream in streams:
        length = redis.xlen(stream)
        stream_length.labels(stream=stream).set(length)
```

## Grafana Dashboards

### Agent Overview Dashboard

Key panels:

1. **Tasks per Minute** — Line chart of throughput
2. **Error Rate** — Percentage of failed tasks
3. **P95 Latency** — 95th percentile processing time
4. **Consumer Status** — Active/inactive consumers

### Stream Health Dashboard

1. **Stream Lengths** — Messages waiting
2. **Consumer Lag** — Messages behind
3. **Pending Messages** — Unacknowledged

## Alerting

### Prometheus Alert Rules

```yaml
# prometheus/rules/alerts.yml
groups:
  - name: agentic-alerts
    rules:
      - alert: HighErrorRate
        expr: |
          rate(agent_tasks_processed_total{status="error"}[5m]) 
          / rate(agent_tasks_processed_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate on {{ $labels.agent_name }}"

      - alert: ConsumerDown
        expr: agent_active_consumers == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "No consumers for {{ $labels.agent_name }}"

      - alert: StreamBacklog
        expr: redis_stream_length > 1000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Stream backlog on {{ $labels.stream }}"
```

## Logging

### Structured Logging

```python
import structlog

logger = structlog.get_logger()

logger.info(
    "task_processed",
    task_id=task_id,
    tenant_id=tenant_id,
    action=action,
    duration_ms=duration,
    status="success"
)
```

### Log Format

```json
{
  "timestamp": "2026-01-13T10:30:00Z",
  "level": "info",
  "event": "task_processed",
  "task_id": "abc-123",
  "tenant_id": "agentic-dev",
  "action": "get_lead_context",
  "duration_ms": 45,
  "status": "success"
}
```

### Loki Queries

```
# All errors
{app="agentic-system"} |= "error"

# Specific agent
{app="agentic-system", agent="rag"} | json | duration_ms > 1000

# By tenant
{app="agentic-system"} | json | tenant_id = "acme-corp"
```

## Distributed Tracing

### OpenTelemetry Setup

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Configure
provider = TracerProvider()
exporter = OTLPSpanExporter(endpoint="http://localhost:4317")
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)
```

### Tracing Tasks

```python
@tracer.start_as_current_span("process_task")
def process_task(task: dict):
    span = trace.get_current_span()
    span.set_attribute("task_id", task["task_id"])
    span.set_attribute("tenant_id", task["tenant_id"])

    # Processing...
```

### Trace Propagation

Correlation IDs link spans across services:

```python
metadata = task.get("metadata", {})
correlation_id = metadata.get("correlation_id")

span.set_attribute("correlation_id", correlation_id)
```

## Health Endpoints

### Basic Health Check

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
async def health():
    redis_ok = check_redis()
    db_ok = check_database()

    return {
        "status": "healthy" if all([redis_ok, db_ok]) else "unhealthy",
        "redis": redis_ok,
        "database": db_ok
    }
```

### Readiness Check

```python
@app.get("/ready")
async def ready():
    # Check if consumer is processing
    return {"ready": consumer.is_running}
```

## Related

- [Troubleshooting](troubleshooting.md)
- [Incident Response](incident-response.md)
- [Running Consumers](consumers.md)
