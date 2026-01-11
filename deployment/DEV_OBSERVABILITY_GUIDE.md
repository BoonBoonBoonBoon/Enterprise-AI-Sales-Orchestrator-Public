# Developer Observability Quick Guide

**Fast reference for debugging and monitoring during development.**

---

## 🚀 Quick Start (3 steps)

```bash
# 1. Start Grafana + Prometheus
cd deployment
docker compose -f docker-compose.observability.yml up -d

# 2. Run Manager
cd ..
.\.venv\Scripts\Activate.ps1
python -m tiers.tier_1.manager.consumer

# 3. Send test request
python scripts/test_observability.py
```

---

## 📺 Terminal Logs (Easiest)

### **View Real-time Logs**
Just run the Manager and watch the terminal:

```bash
python -m tiers.tier_1.manager.consumer
```

**You'll see structured JSON:**
```json
{
  "timestamp": "2025-11-18T19:55:45.123Z",
  "event": "decision",
  "tenant_id": "acme_corp",
  "intent": "outreach",
  "confidence": 0.92,
  "path": "deterministic_pipeline",
  "used_fallback": false,
  "cost_usd": 0.0,
  "latency_ms": 45.2
}
```

### **Filter Logs**
```powershell
# Only decisions
python -m tiers.tier_1.manager.consumer | Select-String "decision"

# Only errors
python -m tiers.tier_1.manager.consumer | Select-String "ERROR"

# Save to file
python -m tiers.tier_1.manager.consumer > logs/manager.jsonl
```

---

## 🗄️ Redis Audit Streams (History)

### **View Recent Decisions**
```bash
# All decisions for today (tenant: acme_corp)
redis-cli XREAD STREAMS manager:decisions:acme_corp:2025-11-18 0

# Last 10 decisions
redis-cli XREVRANGE manager:decisions:acme_corp:2025-11-18 + - COUNT 10

# Last 100 decisions
redis-cli XREVRANGE manager:decisions:acme_corp:2025-11-18 + - COUNT 100
```

### **Stream Info**
```bash
# How many messages in stream?
redis-cli XLEN manager:decisions:acme_corp:2025-11-18

# Stream metadata
redis-cli XINFO STREAM manager:decisions:acme_corp:2025-11-18
```

### **Filter by Time**
```bash
# Decisions after specific timestamp (Unix ms)
redis-cli XREAD STREAMS manager:decisions:acme_corp:2025-11-18 1700326545000

# Time range (oldest to newest)
redis-cli XRANGE manager:decisions:acme_corp:2025-11-18 1700326545000 1700326600000
```

### **Query All Tenants**
```bash
# List all decision streams
redis-cli KEYS "manager:decisions:*"

# Count decisions across all tenants
redis-cli --scan --pattern "manager:decisions:*" | ForEach-Object { redis-cli XLEN $_ }
```

### **Quick Query Script**
Create `scripts/query_redis_decisions.py`:

```python
import redis
import json
from datetime import date

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

tenant_id = "acme_corp"
stream_key = f"manager:decisions:{tenant_id}:{date.today()}"

# Get last 20 decisions
messages = r.xrevrange(stream_key, count=20)

for msg_id, data in messages:
    print(f"\n--- {msg_id} ---")
    print(json.dumps(data, indent=2))
```

Run it:
```bash
python scripts/query_redis_decisions.py
```

---

## 📊 Prometheus (Metrics)

### **Access Prometheus**
```
http://localhost:9090
```

### **Useful Queries**

**Total Decisions:**
```promql
manager_decisions_total
```

**Decisions per second (5min average):**
```promql
rate(manager_decisions_total[5m])
```

**Decisions by path:**
```promql
sum by (path) (manager_decisions_total)
```

**Decisions by intent:**
```promql
sum by (intent) (manager_decisions_total)
```

**P95 Latency:**
```promql
histogram_quantile(0.95, rate(manager_latency_ms_bucket[5m]))
```

**P50 Latency:**
```promql
histogram_quantile(0.50, rate(manager_latency_ms_bucket[5m]))
```

**Cost per tenant:**
```promql
sum by (tenant_id) (manager_cost_usd_total)
```

**LLM fallback usage:**
```promql
sum by (tenant_id) (manager_decisions_total{used_fallback="true"})
```

**Error rate:**
```promql
rate(manager_errors_total[5m])
```

### **Check Metrics Endpoint Directly**
```bash
# View raw metrics
curl http://localhost:8000/metrics

# Filter for manager metrics
curl http://localhost:8000/metrics | Select-String "manager_"

# Health check
curl http://localhost:8000/health
```

---

## 📈 Grafana (Dashboards)

### **Access Grafana**
```
http://localhost:3000
Login: admin / admin
```

### **Quick Queries in Explore**

1. **Open Grafana** → Click **Explore** (compass icon)
2. **Select Prometheus** from datasource dropdown
3. **Enter query:**

**Decision Rate:**
```promql
rate(manager_decisions_total[5m])
```

**Latency Over Time:**
```promql
histogram_quantile(0.95, rate(manager_latency_ms_bucket[5m]))
```

**Cost Attribution:**
```promql
sum by (tenant_id) (manager_cost_usd_total)
```

### **View Pre-built Dashboard**
1. Go to **Dashboards** → **Manager Overview**
2. See 12 panels with real-time metrics

### **Create Custom Dashboard**
1. Click **+ → Dashboard**
2. Add panel → Select Prometheus
3. Enter query
4. Choose visualization (Graph, Gauge, Table, etc.)
5. Save dashboard

---

## 🔍 Common Debug Workflows

### **"Did tenant X get routed correctly?"**

**Option 1: Redis**
```bash
redis-cli XREVRANGE manager:decisions:tenant_x:2025-11-18 + - COUNT 10
```

**Option 2: Terminal**
```bash
# Look for tenant_x in JSON output
python -m tiers.tier_1.manager.consumer | Select-String "tenant_x"
```

**Option 3: Prometheus**
```promql
manager_decisions_total{tenant_id="tenant_x"}
```

---

### **"How many times did we use LLM fallback today?"**

**Option 1: Prometheus**
```promql
sum(manager_decisions_total{used_fallback="true"})
```

**Option 2: Redis**
```bash
# Count messages with used_fallback in stream
redis-cli XRANGE manager:decisions:acme_corp:2025-11-18 - + | Select-String "used_fallback"
```

---

### **"What's the average latency?"**

**Prometheus:**
```promql
# P50
histogram_quantile(0.50, rate(manager_latency_ms_bucket[5m]))

# P95
histogram_quantile(0.95, rate(manager_latency_ms_bucket[5m]))

# P99
histogram_quantile(0.99, rate(manager_latency_ms_bucket[5m]))
```

---

### **"Show me recent errors"**

**Terminal:**
```bash
python -m tiers.tier_1.manager.consumer | Select-String "ERROR"
```

**Prometheus:**
```promql
rate(manager_errors_total[5m])
```

**Grafana Alert:**
Already configured in Manager dashboard - alerts if error rate >0.1/sec

---

### **"What path did request X take?"**

**Redis (search by execution_id):**
```bash
redis-cli XRANGE manager:decisions:acme_corp:2025-11-18 - + | Select-String "exec_1700326545"
```

**Terminal:**
```bash
# Grep terminal output
cat logs/manager.jsonl | Select-String "exec_1700326545"
```

---

## 🛠️ Development Tips

### **Local Log File**
Save terminal output for later analysis:

```bash
# Append to daily log file
python -m tiers.tier_1.manager.consumer >> "logs/manager_$(Get-Date -Format 'yyyy-MM-dd').jsonl"

# Then query it
cat logs/manager_2025-11-18.jsonl | Select-String "fallback"
```

### **Watch Redis Stream Live**
```bash
# Poll for new messages every second
while ($true) {
    redis-cli XREAD BLOCK 1000 STREAMS manager:decisions:acme_corp:2025-11-18 $
    Start-Sleep -Seconds 1
}
```

### **Monitor Metrics Live**
```bash
# Watch decision count
while ($true) {
    curl -s http://localhost:8000/metrics | Select-String "manager_decisions_total"
    Start-Sleep -Seconds 5
}
```

### **Quick Performance Check**
```bash
# Check Prometheus targets are healthy
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job, health}'

# Check Grafana is up
curl http://localhost:3000/api/health
```

---

## 📋 Cheat Sheet

| What | Where | Command |
|------|-------|---------|
| **Real-time logs** | Terminal | `python -m tiers.tier_1.manager.consumer` |
| **Decision history** | Redis | `redis-cli XREVRANGE manager:decisions:tenant:2025-11-18 + - COUNT 20` |
| **Metrics query** | Prometheus | http://localhost:9090 → `manager_decisions_total` |
| **Dashboard** | Grafana | http://localhost:3000 → Dashboards → Manager Overview |
| **Raw metrics** | HTTP | `curl http://localhost:8000/metrics` |
| **Stream count** | Redis | `redis-cli XLEN manager:decisions:tenant:2025-11-18` |
| **Error rate** | Prometheus | `rate(manager_errors_total[5m])` |
| **Latency p95** | Prometheus | `histogram_quantile(0.95, rate(manager_latency_ms_bucket[5m]))` |
| **Cost today** | Prometheus | `sum by (tenant_id) (manager_cost_usd_total)` |

---

## 🎯 Recommended Setup

**For everyday development:**
1. ✅ Keep Grafana + Prometheus running in background
2. ✅ Watch terminal output while coding
3. ✅ Check Redis streams when debugging specific requests
4. ✅ Use Grafana Explore for quick metric checks

**Before commits:**
1. Check error rate in Grafana
2. Verify tests pass (`pytest tiers/tier_1/manager/tests/`)
3. Scan terminal logs for unexpected errors
4. Quick Redis query to verify audit trail working

---

## 🔗 Quick Links

- **Grafana:** http://localhost:3000 (admin/admin)
- **Prometheus:** http://localhost:9090
- **Metrics:** http://localhost:8000/metrics
- **Health:** http://localhost:8000/health

**Documentation:**
- Full guide: [`deployment/OBSERVABILITY.md`](./OBSERVABILITY.md)
- Architecture: [`deployment/ARCHITECTURE.md`](./ARCHITECTURE.md)
- Setup: [`deployment/QUICKSTART.md`](./QUICKSTART.md)
- Cost analysis: [`tiers/tier_1/manager/COST_ANALYSIS.md`](../tiers/tier_1/manager/COST_ANALYSIS.md)
