# Observability Quick Start

Get full observability up and running in 5 minutes.

## Prerequisites

- Docker and Docker Compose installed
- Redis running (see main README.md)
- Python environment set up

## 1. Start Observability Stack

```bash
cd deployment
docker compose -f docker-compose.observability.yml up -d
```

**Services started:**
- Grafana → http://localhost:3000 (admin/admin)
- Prometheus → http://localhost:9090
- Loki → http://localhost:3100
- Tempo → http://localhost:3200

## 2. Configure Environment

Add to your `.env` file:

```bash
# Observability (all optional)
LOKI_URL=http://localhost:3100
METRICS_PORT=8000
ENABLE_OBSERVABILITY=1
```

## 3. Run the Manager

```bash
cd ..
python -m tiers.tier_1.manager.consumer
```

The Manager will:
- ✅ Auto-start metrics server on port 8000
- ✅ Log structured JSON to stdout (captured by Promtail)
- ✅ Push logs to Loki if `LOKI_URL` is set
- ✅ Write audit trail to Redis streams
- ✅ Expose `/metrics` endpoint for Prometheus

## 4. Send Test Request

```bash
# Send a test request to Redis
python scripts/send_test_request.py
```

Or via Python:

```python
import redis
from services.redis.client import RedisClient

redis_client = RedisClient()
redis_client.xadd(
    "tier_1:manager:requests",
    {
        "tenant_id": "test_tenant",
        "execution_id": "test_123",
        "goal": "Send outreach to new leads",
        "context": "{}",
    }
)
```

## 5. View Dashboards

**Open Grafana:** http://localhost:3000

**Login:** admin / admin (change on first login)

**Pre-built dashboards:**
- **Manager Overview** → Decision rates, latency, costs, paths
- More dashboards coming soon for Orchestrators and Agents

## 6. Query Logs

**Loki query examples:**

```logql
# All Manager logs
{component="manager_agent"}

# Only decisions
{component="manager_agent"} | json | event="decision"

# High-cost executions
{component="manager_agent"} | json | cost_usd > 0.001

# Failed requests
{component="manager_agent"} | json | level="ERROR"

# Specific tenant
{component="manager_agent", tenant_id="acme_corp"}
```

## 7. Metrics Examples

**Prometheus query examples:**

```promql
# Decisions per second
rate(manager_decisions_total[5m])

# P95 latency
histogram_quantile(0.95, rate(manager_latency_ms_bucket[5m]))

# Cost per tenant
sum by (tenant_id) (manager_cost_usd_total)

# LLM fallback usage
rate(manager_decisions_total{path="deterministic_pipeline", used_fallback="true"}[5m])
```

## 8. Check Audit Trail

View Redis audit streams:

```bash
redis-cli XREAD STREAMS manager:decisions:test_tenant:2025-01-13 0
```

## Troubleshooting

**No metrics showing up?**
- Check metrics server started: `curl http://localhost:8000/metrics`
- Verify Prometheus scraping: http://localhost:9090/targets

**No logs in Grafana?**
- Check Promtail logs: `docker logs promtail`
- Verify Loki receiving logs: `curl http://localhost:3100/ready`

**Dashboard not loading?**
- Check Grafana logs: `docker logs grafana`
- Verify datasources: Grafana → Configuration → Data Sources

## Stop Observability Stack

```bash
docker compose -f docker-compose.observability.yml down
```

Keep data:
```bash
docker compose -f docker-compose.observability.yml down --volumes
```

## Next Steps

- Read [OBSERVABILITY.md](./OBSERVABILITY.md) for architecture details
- Integrate observability into your Orchestrators (Tier 2)
- Integrate observability into your Agents (Tier 3)
- Set up alerts for error rates and costs
- Configure Prometheus remote write for long-term storage

---

**Cost:** $0.30/month for Docker hosting OR self-host for free  
**Alternative:** Cloud-managed services (~$100-300/month)
