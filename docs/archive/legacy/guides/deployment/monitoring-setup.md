# Monitoring Setup Guide

Complete guide to setting up Prometheus, Grafana, and alerting for the Agentic System.

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Dashboards](#dashboards)
- [Alerting](#alerting)
- [Metrics Reference](#metrics-reference)
- [Troubleshooting](#troubleshooting)
- [Production Deployment](#production-deployment)

---

## Quick Start

### Local Development with Docker Compose

1. **Start monitoring stack:**

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

2. **Access dashboards:**

- **Grafana:** http://localhost:3000 (admin/admin)
- **Prometheus:** http://localhost:9090
- **Alertmanager:** http://localhost:9093

3. **View pre-configured dashboard:**

Navigate to Grafana → Dashboards → "Agentic System Overview"

### What You Get

- **8 monitoring panels:**

  - Stream lengths (all Redis streams)
  - Consumer lag (with thresholds)
  - DLQ growth (with alerts)
  - Worker throughput (msg/sec)
  - Active workers (gauge)
  - Total consumer lag (gauge)
  - Total DLQ messages (gauge)
  - Health server status (gauge)

- **13 alert rules:**

  - Consumer lag warnings and critical alerts
  - DLQ growth detection
  - Worker health monitoring
  - Stream backlog alerts
  - Throughput degradation detection

- **Auto-refresh:** Dashboard updates every 5 seconds

---

## Architecture

### Components

```
┌─────────────────┐
│   Workers       │──┐
│ (RAG/Copy/Pers) │  │
└─────────────────┘  │
                     │ metrics
┌─────────────────┐  │ :8001/metrics
│  Health Server  │──┤
│  (port 8080)    │  │
└─────────────────┘  │
                     │
┌─────────────────┐  │
│     Redis       │──┤
└─────────────────┘  │
         │           │
         │           ▼
┌────────▼────────────────┐
│  Redis Exporter         │
│  (port 9121)            │
└────────┬────────────────┘
         │ Redis metrics
         │
         ▼
┌─────────────────────────┐
│     Prometheus          │
│  - Scrapes metrics      │
│  - Evaluates alerts     │
│  - 15d retention        │
└────────┬────────────────┘
         │
         ├──────────────┐
         │              │
         ▼              ▼
┌─────────────┐  ┌─────────────┐
│  Grafana    │  │ Alertmanager│
│  Dashboards │  │  Routing    │
└─────────────┘  └─────────────┘
```

### Data Flow

1. **Workers expose metrics** on port 8001 (if implemented)
2. **Redis Exporter** scrapes Redis and exposes:
   - Stream lengths
   - Consumer lag
   - Connection stats
3. **Prometheus** scrapes all targets every 15s
4. **Prometheus** evaluates alert rules every 15s
5. **Alertmanager** routes alerts to configured channels
6. **Grafana** queries Prometheus for dashboards

---

## Configuration

### Prometheus Configuration

**File:** `monitoring/prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "health-server"
    static_configs:
      - targets: ["localhost:8080"]
    scrape_interval: 10s

  - job_name: "workers"
    static_configs:
      - targets:
          - "rag-worker:8001"
          - "copywriter-worker:8001"
          - "persistence-worker:8001"
    scrape_interval: 10s

  - job_name: "redis"
    static_configs:
      - targets: ["redis-exporter:9121"]
    scrape_interval: 10s
```

**Key Settings:**

- `scrape_interval`: How often to collect metrics (15s default)
- `evaluation_interval`: How often to evaluate alerts (15s default)
- `retention.time`: Data retention period (15d default)

### Grafana Datasource

**File:** `monitoring/grafana/datasources/prometheus.yml`

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
    jsonData:
      timeInterval: 5s
```

**Auto-provisioned on startup** - no manual configuration needed.

### Dashboard Provisioning

**File:** `monitoring/grafana/dashboards/dashboard-provider.yml`

```yaml
apiVersion: 1

providers:
  - name: "Agentic System Dashboards"
    orgId: 1
    folder: ""
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
```

**Dashboard JSON:** `monitoring/grafana/dashboards/agentic-overview.json`

---

## Dashboards

### Agentic System Overview

**Panels:**

#### 1. Stream Lengths

- **Type:** Time series (line chart)
- **Metric:** `redis_stream_length`
- **Purpose:** Monitor message backlog in all streams
- **Alert:** > 10,000 messages (warning)

#### 2. Consumer Lag

- **Type:** Time series (line chart)
- **Metric:** `redis_consumer_lag`
- **Thresholds:**
  - Yellow: > 1,000 messages
  - Red: > 5,000 messages
- **Purpose:** Detect processing delays

#### 3. DLQ Growth

- **Type:** Time series (line chart)
- **Metric:** `redis_stream_length{stream=~".*:dlq"}`
- **Thresholds:**
  - Orange: > 10 messages
  - Red: > 50 messages
- **Purpose:** Monitor failed messages

#### 4. Worker Throughput

- **Type:** Time series (line chart)
- **Metric:** `rate(worker_messages_processed_total[5m])`
- **Purpose:** Track processing rate (msg/sec)

#### 5. Active Workers (Gauge)

- **Metric:** `count(worker_heartbeat)`
- **Expected:** 3+ workers
- **Alert:** < 3 workers (warning)

#### 6. Total Consumer Lag (Gauge)

- **Metric:** `sum(redis_consumer_lag)`
- **Thresholds:**
  - Green: < 1,000
  - Yellow: 1,000-5,000
  - Red: > 5,000

#### 7. Total DLQ Messages (Gauge)

- **Metric:** `sum(redis_stream_length{stream=~".*:dlq"})`
- **Thresholds:**
  - Green: < 10
  - Yellow: 10-50
  - Red: > 50

#### 8. Health Server Status (Gauge)

- **Metric:** `up{job="health-server"}`
- **Values:** 1 = UP, 0 = DOWN

### Template Variables

**$namespace:** Filter metrics by environment (agentic-prod, agentic-dev, etc.)

### Auto-Refresh

**Interval:** 5 seconds  
**Time Range:** Last 15 minutes

---

## Alerting

### Alert Rules

**File:** `monitoring/prometheus/alerts/agentic-alerts.yml`

#### Critical Alerts

| Alert                 | Condition     | Duration | Action                    |
| --------------------- | ------------- | -------- | ------------------------- |
| CriticalConsumerLag   | lag > 5000    | 2m       | Scale workers immediately |
| HighDLQCount          | DLQ > 100     | 5m       | Review failed messages    |
| WorkerStalled         | 0 msg/sec     | 5m       | Check for deadlock/crash  |
| HealthServerDown      | up == 0       | 1m       | Restart health server     |
| RedisConnectionErrors | > 5 errors/5m | 2m       | Check Redis server        |

#### Warning Alerts

| Alert               | Condition      | Duration | Action               |
| ------------------- | -------------- | -------- | -------------------- |
| HighConsumerLag     | lag > 1000     | 5m       | Monitor closely      |
| DLQGrowth           | +10 msg/5m     | 2m       | Investigate failures |
| LowWorkerCount      | < 3 workers    | 2m       | Check scaling        |
| StreamBacklog       | > 10,000 msg   | 5m       | Consider scaling     |
| LowWorkerThroughput | < 1 msg/sec    | 10m      | Check performance    |
| HighRateLimitWaits  | > 10 waits/sec | 5m       | Increase rate limits |

### Alertmanager Configuration

**File:** `monitoring/alertmanager/alertmanager.yml`

```yaml
global:
  resolve_timeout: 5m

route:
  group_by: ["alertname", "cluster", "service"]
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: "default"
  routes:
    - match:
        severity: critical
      receiver: "critical"
    - match:
        severity: warning
      receiver: "warning"
```

#### Slack Integration (Optional)

```yaml
receivers:
  - name: "critical"
    slack_configs:
      - api_url: "YOUR_SLACK_WEBHOOK_URL"
        channel: "#alerts-critical"
        title: "Critical Alert: {{ .GroupLabels.alertname }}"
        text: "{{ range .Alerts }}{{ .Annotations.description }}{{ end }}"
```

#### PagerDuty Integration (Optional)

```yaml
receivers:
  - name: "critical"
    pagerduty_configs:
      - routing_key: "YOUR_PAGERDUTY_KEY"
        description: "{{ .GroupLabels.alertname }}"
```

---

## Metrics Reference

### Redis Exporter Metrics

| Metric                           | Type    | Description                         |
| -------------------------------- | ------- | ----------------------------------- |
| `redis_stream_length`            | Gauge   | Number of messages in stream        |
| `redis_consumer_lag`             | Gauge   | Pending messages for consumer group |
| `redis_connected_clients`        | Gauge   | Number of connected clients         |
| `redis_used_memory_bytes`        | Gauge   | Memory usage                        |
| `redis_commands_processed_total` | Counter | Total commands executed             |

**Labels:**

- `stream`: Stream name (e.g., `rag:tasks`, `copywriter:tasks:dlq`)
- `group`: Consumer group name (e.g., `rag-workers`)

### Worker Metrics (if implemented)

| Metric                               | Type      | Description             |
| ------------------------------------ | --------- | ----------------------- |
| `worker_messages_processed_total`    | Counter   | Messages processed      |
| `worker_heartbeat`                   | Gauge     | Worker alive (1 = yes)  |
| `worker_rate_limit_waits_total`      | Counter   | Rate limit wait events  |
| `worker_processing_duration_seconds` | Histogram | Message processing time |

**Labels:**

- `worker_type`: Worker type (e.g., `rag`, `copywriter`, `persistence`)
- `worker_id`: Worker instance ID
- `namespace`: Environment (e.g., `agentic-prod`)

### Health Server Metrics

| Metric                          | Type  | Description               |
| ------------------------------- | ----- | ------------------------- |
| `up`                            | Gauge | Server up (1) or down (0) |
| `health_check_duration_seconds` | Gauge | Health check duration     |

---

## Troubleshooting

### Prometheus Not Scraping Targets

**Symptoms:**

- Targets show as "DOWN" in Prometheus UI
- No data in Grafana

**Solutions:**

1. **Check target connectivity:**

```bash
docker exec -it observ_prometheus wget -O- http://redis-exporter:9121/metrics
```

2. **Verify prometheus.yml:**

```bash
docker exec -it observ_prometheus cat /etc/prometheus/prometheus.yml
```

3. **Check Prometheus logs:**

```bash
docker logs observ_prometheus
```

4. **Reload configuration:**

```bash
curl -X POST http://localhost:9090/-/reload
```

### Grafana Dashboard Not Showing Data

**Symptoms:**

- Dashboard panels show "No data"
- Queries return empty results

**Solutions:**

1. **Verify datasource connection:**

   - Grafana → Configuration → Data sources → Prometheus
   - Click "Test" button

2. **Check metric names:**

   - Prometheus UI → Graph → Enter metric name
   - Verify metrics exist

3. **Inspect panel query:**

   - Dashboard → Panel → Edit → Query inspector
   - Run query in Prometheus directly

4. **Check time range:**
   - Ensure time range includes data
   - Try "Last 1 hour"

### Alerts Not Firing

**Symptoms:**

- Alert condition met but no notification
- Alerts stuck in "Pending"

**Solutions:**

1. **Check alert rules:**

```bash
docker exec -it observ_prometheus cat /etc/prometheus/alerts/agentic-alerts.yml
```

2. **Verify Alertmanager connection:**

   - Prometheus UI → Status → Runtime & Build Information
   - Check "Alertmanagers" section

3. **Check Alertmanager logs:**

```bash
docker logs observ_alertmanager
```

4. **Test alert manually:**

```bash
curl -X POST http://localhost:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[{"labels":{"alertname":"test"},"annotations":{"summary":"Test alert"}}]'
```

### High Memory Usage

**Symptoms:**

- Prometheus container using excessive memory
- OOM kills

**Solutions:**

1. **Reduce retention time:**

```yaml
# prometheus.yml
command:
  - "--storage.tsdb.retention.time=7d" # Reduce from 15d
```

2. **Limit scrape frequency:**

```yaml
scrape_configs:
  - job_name: "redis"
    scrape_interval: 30s # Increase from 15s
```

3. **Add memory limits:**

```yaml
# docker-compose.monitoring.yml
prometheus:
  deploy:
    resources:
      limits:
        memory: 2G
```

---

## Production Deployment

### Kubernetes Deployment

**1. Create monitoring namespace:**

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: monitoring
```

**2. Deploy Prometheus:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      containers:
        - name: prometheus
          image: prom/prometheus:latest
          args:
            - "--config.file=/etc/prometheus/prometheus.yml"
            - "--storage.tsdb.retention.time=15d"
          ports:
            - containerPort: 9090
          volumeMounts:
            - name: config
              mountPath: /etc/prometheus
            - name: data
              mountPath: /prometheus
      volumes:
        - name: config
          configMap:
            name: prometheus-config
        - name: data
          persistentVolumeClaim:
            claimName: prometheus-data
```

**3. Use service discovery:**

```yaml
# prometheus.yml
scrape_configs:
  - job_name: "kubernetes-pods"
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names:
            - agentic-system
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
```

**4. Annotate worker pods:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-worker
spec:
  template:
    metadata:
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8001"
        prometheus.io/path: "/metrics"
```

### High Availability

**Prometheus HA:**

```yaml
# Use Thanos or Prometheus federation
# Deploy 2+ Prometheus instances
# Use external storage (S3, GCS)
```

**Grafana HA:**

```yaml
# Use external database (PostgreSQL)
# Deploy 2+ Grafana instances
# Use load balancer
```

### Security Best Practices

1. **Change default credentials:**

```yaml
environment:
  GF_SECURITY_ADMIN_USER: ${ADMIN_USER}
  GF_SECURITY_ADMIN_PASSWORD: ${ADMIN_PASSWORD}
```

2. **Enable authentication:**

```yaml
# Grafana: OAuth2, LDAP, or SAML
# Prometheus: Basic auth or OAuth2 proxy
```

3. **Use TLS:**

```yaml
# Configure HTTPS for Grafana
# Use ingress controller with TLS
```

4. **Network isolation:**

```yaml
# Firewall rules for scrape targets
# Private subnets for monitoring stack
```

### Backup and Recovery

**1. Backup Prometheus data:**

```bash
# Snapshot API
curl -X POST http://localhost:9090/api/v1/admin/tsdb/snapshot

# Or use volume backups
docker run --rm -v prometheus-data:/data -v $(pwd)/backup:/backup \
  alpine tar czf /backup/prometheus-$(date +%Y%m%d).tar.gz /data
```

**2. Backup Grafana dashboards:**

```bash
# Export dashboards via API
curl -H "Authorization: Bearer ${API_KEY}" \
  http://localhost:3000/api/dashboards/uid/${DASHBOARD_UID} > backup.json
```

**3. Backup alertmanager config:**

```bash
cp monitoring/alertmanager/alertmanager.yml backups/
```

### Performance Tuning

**1. Optimize query performance:**

```yaml
# Use recording rules for expensive queries
groups:
  - name: agentic_recordings
    interval: 30s
    rules:
      - record: job:redis_stream_length:sum
        expr: sum(redis_stream_length) by (job)
```

**2. Limit metric cardinality:**

```yaml
# Drop unnecessary labels
metric_relabel_configs:
  - source_labels: [__name__]
    regex: "high_cardinality_metric_.*"
    action: drop
```

**3. Use remote storage:**

```yaml
# prometheus.yml
remote_write:
  - url: "https://prometheus-remote-storage:9201/write"
```

---

## Next Steps

1. **Add worker metrics endpoint:**

   - Implement `/metrics` endpoint in workers
   - Expose on port 8001
   - Use Prometheus client library

2. **Customize alerts:**

   - Adjust thresholds for your workload
   - Add Slack/PagerDuty integration
   - Create runbooks for each alert

3. **Create custom dashboards:**

   - Business metrics (emails sent, queries processed)
   - Cost tracking (API calls, compute time)
   - User-facing SLIs

4. **Implement SLOs:**

   - Define SLIs (latency, availability, throughput)
   - Set SLO targets (99.9% uptime)
   - Track error budgets

5. **Advanced features:**
   - Distributed tracing (Jaeger/Tempo)
   - APM (Application Performance Monitoring)
   - Cost attribution per tenant

---

## References

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Redis Exporter](https://github.com/oliver006/redis_exporter)
- [Alertmanager Guide](https://prometheus.io/docs/alerting/latest/alertmanager/)

---

**Related Documentation:**

- [Secrets](./secrets.md) - Credential management
- [Rate Limiting](../../api/rate-limiting.md) - Rate limiting configuration
- [Technical TODOs](../../roadmap/technical-todos.md) - Overall progress
