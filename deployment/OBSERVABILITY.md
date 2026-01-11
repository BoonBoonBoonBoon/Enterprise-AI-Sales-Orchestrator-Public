# Grafana Stack Observability

Complete observability setup for the Agentic System using Grafana, Loki, Prometheus, and Tempo.

## Quick Start

### 1. Start the Observability Stack

```powershell
# From the deployment directory
docker compose -f docker-compose.observability.yml up -d
```

### 2. Access Dashboards

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Loki**: http://localhost:3100
- **Tempo**: http://localhost:3200

### 3. Configure Your Services

Add to your service environment variables:

```yaml
environment:
  - LOKI_URL=http://loki:3100/loki/api/v1/push
  - METRICS_PORT=8000  # Expose /metrics endpoint
```

### 4. View Pre-built Dashboards

Navigate to Grafana → Dashboards → Agentic System folder:
- Manager Agent (Tier 1)
- Orchestrators (Tier 2) - *coming soon*
- Agents (Tier 3) - *coming soon*

---

## Architecture

```
Application Tier          Observability Tier
┌─────────────┐          ┌──────────────┐
│   Manager   │─logs────▶│     Loki     │
│   (Tier 1)  │─metrics─▶│  Prometheus  │
└─────────────┘─traces──▶│    Tempo     │
                         └──────────────┘
                               │
                               ▼
                         ┌──────────────┐
                         │   Grafana    │
                         └──────────────┘
```

---

## Cost

**Self-Hosted (Recommended)**:
- Software: $0 (open-source)
- Compute: ~$12-30/month (1 small VM) or $0 (on existing infrastructure)
- Storage: <5GB for 30-day retention

**vs. Managed Alternatives**:
- DataDog: ~$100-300/month
- New Relic: ~$99-299/month
- CloudWatch: ~$50-150/month

**Savings: 90-95%**

---

## Data Retention

**Default Settings**:
- Metrics (Prometheus): 30 days
- Logs (Loki): 7 days
- Traces (Tempo): 7 days

**Adjust in config files**:
- Prometheus: `deployment/prometheus/prometheus.yml` (--storage.tsdb.retention.time)
- Loki: `deployment/loki/loki-config.yml` (retention_period)

---

## Metrics Exposed

### Manager (Tier 1)

**Counters**:
- `manager_decisions_total{intent, tenant, component}` - Total decisions made
- `manager_errors_total{component, tenant}` - Total errors
- `manager_fallback_total{used_fallback, tenant}` - Fallback usage
- `manager_cost_usd{tenant, component}` - Cumulative cost in USD

**Histograms**:
- `manager_latency_ms{component, tenant}` - Execution latency
- `manager_confidence{tenant}` - Decision confidence scores

**Gauges**:
- `up{job="manager"}` - Service health (1=up, 0=down)

### Orchestrators (Tier 2) - *Coming Soon*

- `orchestrator_workflows_total`
- `orchestrator_agents_delegated`
- `orchestrator_state_transitions`

### Agents (Tier 3) - *Coming Soon*

- `agent_llm_calls_total`
- `agent_tokens_input`
- `agent_tokens_output`
- `agent_tool_calls`

---

## Logs Structure

All logs are JSON-formatted and pushed to Loki with labels:

```json
{
  "timestamp": "2025-11-18T10:30:45.123Z",
  "level": "INFO",
  "tier": "manager",
  "component": "manager_agent",
  "tenant_id": "demo",
  "execution_id": "exec_1731929445.123",
  "event": "decision",
  "intent": "outreach",
  "confidence": 0.85,
  "used_fallback": false,
  "reasons": ["rules:keyword:outreach"],
  "latency_ms": 45
}
```

**Query examples in Grafana Explore**:
```logql
# All manager decisions
{tier="manager",event="decision"}

# Decisions using fallback
{tier="manager",event="decision"} |= "used_fallback\":true"

# Errors for specific tenant
{tier="manager",level="ERROR",tenant_id="acme"}

# High latency decisions (>1s)
{tier="manager",event="decision"} | json | latency_ms > 1000
```

---

## Alerts

### Pre-configured Alerts

1. **Manager Error Rate** - Triggers when error rate >0.1/sec for 5 minutes
2. **High Fallback Usage** - Triggers when fallback >30% for 10 minutes
3. **Service Down** - Triggers when `up` metric = 0

### Add Custom Alerts

Edit dashboards in Grafana UI or add to:
`deployment/grafana/provisioning/alerting/` (create folder)

---

## Debugging Workflow

### 1. Check System Health

```bash
# View all service logs
docker compose -f docker-compose.observability.yml logs -f

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Test Loki ingestion
curl -G -s http://localhost:3100/loki/api/v1/labels
```

### 2. Query Recent Decisions

In Grafana → Explore → Loki:

```logql
{tier="manager",event="decision"} | json
```

### 3. Inspect Metrics

In Grafana → Explore → Prometheus:

```promql
# Decision rate per tenant
rate(manager_decisions_total[5m])

# P95 latency
histogram_quantile(0.95, rate(manager_latency_ms_bucket[5m]))

# Cost per hour by tenant
rate(manager_cost_usd[1h])
```

### 4. Trace Requests (Optional)

If Tempo is enabled and instrumented:

In Grafana → Explore → Tempo:
- Search by `execution_id` or `tenant_id`
- View full trace timeline

---

## Integration with Application

### Python Example (Manager)

```python
from core.observability import ObservabilityContext, start_metrics_server

# Start metrics server on initialization
start_metrics_server(port=8000)

# Wrap execution with observability
def execute(self, task):
    with ObservabilityContext(
        tier="manager",
        component="manager_agent",
        tenant_id=self.tenant_id,
        redis_client=self.redis,
    ) as obs:
        # Do work
        result = self._process(task)
        
        # Log decision
        obs.log_decision(
            intent="outreach",
            confidence=0.85,
            used_fallback=False,
            reasons=["rules:keyword:outreach"],
        )
        
        # Track cost
        obs.track_cost(0.0002)
        
        return result
```

---

## Troubleshooting

### Grafana can't connect to Prometheus

**Check**:
```bash
docker exec -it agentic_grafana curl http://prometheus:9090/api/v1/status/config
```

**Fix**: Ensure all services are on `agentic_network`

### No metrics appearing

**Check**:
1. Is the `/metrics` endpoint exposed? `curl http://localhost:8000/metrics`
2. Is Prometheus scraping? Check http://localhost:9090/targets
3. Are metric names correct? Check Prometheus → Graph → Metrics

### Loki not receiving logs

**Check**:
1. Is LOKI_URL set in application env?
2. Is Promtail running? `docker logs agentic_promtail`
3. Test direct push:
   ```bash
   curl -X POST http://localhost:3100/loki/api/v1/push \
     -H "Content-Type: application/json" \
     -d '{"streams":[{"stream":{"job":"test"},"values":[["'$(date +%s)000000000'","test message"]]}]}'
   ```

### High memory usage

**Adjust retention**:
- Prometheus: Lower `--storage.tsdb.retention.time` in docker-compose
- Loki: Lower `retention_period` in loki-config.yml

---

## Production Recommendations

### 1. Security

```yaml
# Change default Grafana password
environment:
  - GF_SECURITY_ADMIN_PASSWORD=<strong-password>
  
# Enable HTTPS (use nginx reverse proxy)
# Restrict network access (firewall rules)
```

### 2. Persistence

```yaml
# Use named volumes (already configured)
volumes:
  prometheus_data:
  loki_data:
  grafana_data:

# Backup regularly
docker run --rm -v prometheus_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/prometheus_backup.tar.gz /data
```

### 3. Scaling

For high-volume (>100K requests/day):

- **Loki**: Use S3/GCS backend instead of local filesystem
- **Prometheus**: Enable remote write to Thanos/Cortex
- **Tempo**: Use S3/GCS backend for traces

### 4. Multi-Region

Deploy stack per region, aggregate in central Grafana:

```yaml
# grafana/provisioning/datasources/datasources.yml
datasources:
  - name: Prometheus US-East
    url: http://prometheus-us-east:9090
  - name: Prometheus EU-West
    url: http://prometheus-eu-west:9090
```

---

## Next Steps

1. ✅ Start observability stack
2. ✅ Integrate Manager with ObservabilityContext
3. ⏳ Add Orchestrator dashboards
4. ⏳ Add Agent dashboards
5. ⏳ Set up alerting rules
6. ⏳ Configure PagerDuty/Slack notifications

---

## Support

- Grafana Docs: https://grafana.com/docs/
- Prometheus Docs: https://prometheus.io/docs/
- Loki Docs: https://grafana.com/docs/loki/
- Tempo Docs: https://grafana.com/docs/tempo/
