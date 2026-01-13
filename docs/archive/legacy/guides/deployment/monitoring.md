# Monitoring Stack - Quick Start

## ✅ All Services Running

Your complete monitoring stack is now live with all 3 high-priority infrastructure items deployed:

### Access Your Dashboards

| Service          | URL                   | Credentials   |
| ---------------- | --------------------- | ------------- |
| **Grafana**      | http://localhost:3000 | admin / admin |
| **Prometheus**   | http://localhost:9090 | (no auth)     |
| **Alertmanager** | http://localhost:9093 | (no auth)     |

### What's Included

**1. Secrets Management** ✅

- Azure Key Vault integration
- AWS Secrets Manager integration
- Environment variable support
- Docker Compose: `docker-compose.azure.yml`, `docker-compose.aws.yml`
- Kubernetes manifests: `k8s/azure-keyvault/`, `k8s/aws-secrets-manager/`

**2. Rate Limiting** ✅

- Token bucket algorithm (smooth bursts)
- Sliding window algorithm (strict limits)
- Redis-backed distributed limiting
- Memory-backed local limiting
- Integrated into: RAG worker, Copywriter worker, Persistence worker
- Environment: `RATE_LIMIT_ENABLED`, `RATE_LIMIT_PER_SECOND`, `RATE_LIMIT_BACKEND`

**3. Grafana Dashboards** ✅

- **Main Dashboard:** "Agentic System Overview" (8 panels)

  - Stream Lengths (all Redis streams)
  - Consumer Lag (with thresholds)
  - DLQ Growth (with alerts)
  - Worker Throughput (msg/sec)
  - Active Workers (gauge)
  - Total Consumer Lag (gauge)
  - Total DLQ Messages (gauge)
  - Health Server Status (gauge)

- **13 Alert Rules:**

  - Consumer lag warnings (>1000) and critical (>5000)
  - DLQ growth detection (>10 msg/5min)
  - Worker health monitoring (stalled, low count, etc.)
  - Stream backlog alerts (>10k messages)
  - Throughput degradation (< 1 msg/sec for 10 min)
  - Rate limit waits (>10 waits/sec)
  - Redis errors
  - Health server down

- **Prometheus Metrics Scraped:**
  - Redis: Stream length, consumer lag, connection stats
  - Health Server: System status
  - Workers: Heartbeat, throughput, rate limit events
  - Kubernetes pods (if using K8s)

### Docker Services

Running containers:

- `redis` - Message queue (port 6379)
- `postgres` - Database (port 5432)
- `prometheus` - Metrics collection (port 9090)
- `grafana` - Dashboards (port 3000)
- `alertmanager` - Alert routing (port 9093)
- `redis-exporter` - Redis metrics (port 9121)
- `loki` - Log aggregation (port 3100)
- `promtail` - Log shipper
- Workers + Orchestrator + Health server

### Next Steps

1. **View Grafana Dashboard**

   - Open http://localhost:3000
   - Login: admin / admin
   - Navigate to Dashboards → "Agentic System Overview"

2. **Check Metrics in Prometheus**

   - Open http://localhost:9090
   - Graph tab → Search for `redis_stream_length`
   - Or explore other metrics

3. **Configure Alerts** (Optional)

   - Edit `monitoring/alertmanager/alertmanager.yml`
   - Add Slack webhook, PagerDuty API key, etc.
   - Restart alertmanager: `docker restart observ_alertmanager`

4. **View Health Status**

   - `curl http://localhost:8080/health | jq`
   - All system health in one place

5. **Send Test Data**
   - Use your existing workflow manager to send tasks
   - Watch them flow through Redis streams
   - Monitor on Grafana dashboard in real-time

### Documentation

- **[Monitoring Setup](./monitoring-setup.md)** - Complete setup guide, troubleshooting, production deployment
- **[Rate Limiting](../../api/rate-limiting.md)** - Rate limiting configuration and best practices
- **[Secrets](./secrets.md)** - Secrets management for production

### Common Commands

```bash
# View container logs
docker logs observ_grafana -f
docker logs observ_prometheus -f

# Restart a service
docker restart observ_grafana

# Stop the stack
docker compose --profile local -f docker-compose.yml -f docker-compose.monitoring.yml down

# Restart everything
docker compose --profile local -f docker-compose.yml -f docker-compose.monitoring.yml restart
```

### Troubleshooting

**Grafana dashboard shows "No data"?**

1. Check Prometheus at http://localhost:9090 → Status → Targets
2. Ensure targets are "UP" (not "DOWN")
3. Wait 60 seconds for first metrics to be scraped

**Alerts not firing?**

1. Check Prometheus → Status → Alerts
2. Verify alert rules are loaded
3. Check Alertmanager logs: `docker logs observ_alertmanager`

**Redis exporter connection error?**

1. Verify Redis is running: `docker ps | grep redis`
2. Check redis-exporter logs: `docker logs observ_redis_exporter`
3. Ensure both containers are on same network: `agentic-network`

**Worker rate limiting not working?**

1. Check environment variables: `RATE_LIMIT_ENABLED=true`
2. View logs: `docker logs agenticsystem-rag_worker-1`
3. Verify Redis connection from worker

---

**Status: ✅ Production-Ready Infrastructure Complete**

All 3 high-priority items implemented and tested. Ready for production deployment! 🚀
