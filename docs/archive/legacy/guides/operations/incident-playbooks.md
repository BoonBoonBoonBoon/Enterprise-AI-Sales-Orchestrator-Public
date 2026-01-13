# Incident Playbooks

## Quick Reference

| Incident Type | Severity | MTTR Target | Jump To |
|--------------|----------|-------------|---------|
| No Active Consumers | 🔴 Critical | 2 min | [Playbook](#1-no-active-consumers) |
| High Consumer Lag | 🟡 Warning | 5 min | [Playbook](#2-high-consumer-lag) |
| DLQ Explosion | 🟡 Warning | 10 min | [Playbook](#3-dlq-explosion) |
| Worker Crash Loop | 🔴 Critical | 5 min | [Playbook](#4-worker-crash-loop) |
| Redis Connection Loss | 🔴 Critical | 1 min | [Playbook](#5-redis-connection-loss) |
| Disk Space Full | 🔴 Critical | 5 min | [Playbook](#6-disk-space-full-redis-aof) |
| Stream Growing Unbounded | 🟡 Warning | 15 min | [Playbook](#7-stream-growing-unbounded) |
| Slow Database Queries | 🟡 Warning | 10 min | [Playbook](#8-slow-database-queries) |
| Duplicate Message Processing | 🟢 Info | 5 min | [Playbook](#9-duplicate-message-processing) |
| Health Endpoint Down | 🔴 Critical | 2 min | [Playbook](#10-health-endpoint-down) |

---

## 1. No Active Consumers

### Symptoms
- Health check shows `consumers: 0` for one or more streams
- `/ready` endpoint returns 503
- Messages accumulating in streams with no processing
- Prometheus alert: `NoActiveConsumers`

### Root Causes
- Worker pods/containers crashed
- Deployment killed all replicas
- Worker startup failure (config error, dependency unavailable)
- Network partition preventing consumer registration

### Diagnosis

```bash
# Check consumer status
python scripts/ops.py health --all --pretty

# Check worker logs for crashes
docker-compose logs rag-worker --tail 100
# Or K8s:
kubectl logs -l app=rag-worker --tail=100

# Check if workers are running
docker-compose ps
# Or K8s:
kubectl get pods -l app=rag-worker
```

### Recovery Steps

**Step 1: Restart workers**
```bash
# Docker Compose
docker-compose restart rag-worker
docker-compose restart persist-worker

# Kubernetes
kubectl rollout restart deployment/rag-worker
kubectl rollout restart deployment/persist-worker
```

**Step 2: Verify consumer registration**
```bash
# Wait 10 seconds for startup
sleep 10

# Check health again
python scripts/ops.py health --all --pretty

# Should see consumers > 0
```

**Step 3: If still no consumers, check startup errors**
```bash
# Check recent logs
docker-compose logs rag-worker --since 1m

# Common issues:
# - Redis connection refused → check REDIS_HOST
# - Import errors → check requirements.txt installed
# - Config missing → check .env file
```

**Step 4: Scale up if needed**
```bash
# Docker Compose
docker-compose up -d --scale rag-worker=3

# Kubernetes
kubectl scale deployment/rag-worker --replicas=3
```

### Prevention
- Set up liveness probes to auto-restart crashed workers
- Configure readiness probes to remove unhealthy pods from load balancer
- Add Prometheus alerts for `consumers == 0` lasting > 1 minute

---

## 2. High Consumer Lag

### Symptoms
- Health check shows lag > 100 (or your threshold)
- Messages processed slowly despite consumers present
- End-to-end latency increasing
- Prometheus alert: `HighConsumerLag`

### Root Causes
- Insufficient worker capacity (need more replicas)
- Slow external dependencies (database, OpenAI API)
- CPU/memory contention on worker hosts
- Large batch of messages enqueued suddenly

### Diagnosis

```bash
# Check lag per stream
python scripts/ops.py health --all --pretty

# Example output:
# rag:tasks
#   Consumers: 2
#   Pending: 5
#   Lag: 150 ⚠️  (150 messages behind)

# Check worker resource usage
docker stats rag-worker
# Or K8s:
kubectl top pods -l app=rag-worker

# Check processing rate
python scripts/ops.py inspect rag:tasks --count 10
# Look at message timestamps - are they old?
```

### Recovery Steps

**Step 1: Scale up workers (quick fix)**
```bash
# Double the worker count
docker-compose up -d --scale rag-worker=4

# Kubernetes - use HPA or manual scaling
kubectl scale deployment/rag-worker --replicas=4

# Wait 30 seconds for new workers to start
sleep 30

# Check lag again
python scripts/ops.py health --all --pretty
```

**Step 2: Identify slow operations (if scaling doesn't help)**
```bash
# Enable distributed tracing (if not already enabled)
export OTEL_ENABLED=1
export OTEL_EXPORTER=jaeger

# Restart workers to pick up tracing
docker-compose restart rag-worker

# Open Jaeger UI: http://localhost:16686
# Find slow spans (database_query > 1s, openai_api_call > 5s)
```

**Step 3: Optimize slow operations**
- **Slow database queries:** Add indexes, optimize WHERE clauses
- **Slow API calls:** Increase timeout, add retry logic, use batch APIs
- **Memory leaks:** Restart workers, investigate with profiling

**Step 4: Temporary relief - pause upstream**
```bash
# If lag continues growing, pause orchestrator to stop new messages
# (Only if business allows)
docker-compose stop orchestrator

# Process backlog
# Monitor lag decreasing: watch -n 5 'python scripts/ops.py health'

# Resume when lag < 10
docker-compose start orchestrator
```

### Prevention
- Set up auto-scaling based on lag metric
- Add Prometheus alert for lag > 50 (warning) and lag > 200 (critical)
- Load test to understand maximum throughput per worker
- Use distributed tracing to identify performance regressions

---

## 3. DLQ Explosion

### Symptoms
- DLQ stream length growing rapidly (>100 messages)
- Same error appearing repeatedly in DLQ
- Health check shows high DLQ count
- Workers logging many errors

### Root Causes
- Systemic error affecting all messages (DB down, API key invalid)
- Schema change broke message processing
- Bug in worker code causing all messages to fail
- External service unavailable (OpenAI API down)

### Diagnosis

```bash
# Check DLQ contents
python scripts/ops.py dlq list --verbose

# Example output:
# persist:dlq
#   Messages: 347
#   Sample Errors:
#     - "duplicate key value violates unique constraint" (245 occurrences)
#     - "connection timeout to database" (102 occurrences)

# Inspect specific DLQ message
python scripts/ops.py inspect persist:dlq --count 1 --verbose
```

### Recovery Steps

**Step 1: Stop the bleeding (if systemic)**
```bash
# If all messages failing due to config issue, pause workers
docker-compose stop persist-worker

# Fix the root cause:
# - Database credentials incorrect → update .env
# - API key expired → rotate key
# - Schema changed → update code
```

**Step 2: Categorize errors**
```bash
# Run DLQ automation with dry-run
python scripts/dlq_automation.py persist:dlq --dry-run --verbose

# Check categorization:
# - Transient (102): Can retry immediately
# - Duplicate (245): Can auto-transform to upsert
# - Validation (0): Skip permanently
# - Permanent (0): Skip permanently
```

**Step 3: Auto-remediate fixable errors**
```bash
# Transform duplicates to upserts
python scripts/dlq_automation.py persist:dlq --auto-fix-duplicates --limit 50

# Retry transient errors
python scripts/dlq_automation.py persist:dlq --transient-only --limit 50

# Check DLQ size reduced
python scripts/ops.py dlq list
```

**Step 4: Manual intervention for permanent errors**
```bash
# Inspect unfixable errors
python scripts/ops.py inspect persist:dlq --count 10

# Options:
# 1. Fix data and replay: python scripts/ops.py dlq replay persist:dlq --limit 10
# 2. Skip and log: Move to dead-letter-dead-letter queue (manual)
# 3. Alert dev team to fix bug
```

**Step 5: Resume workers**
```bash
docker-compose start persist-worker

# Monitor for new DLQ messages
watch -n 5 'python scripts/ops.py dlq list'
```

### Prevention
- Set up DLQ automation cron job: `*/5 * * * * python scripts/dlq_automation.py persist:dlq --auto-fix-duplicates --transient-only`
- Add Prometheus alert for DLQ growth rate > 10 msgs/min
- Add schema validation before deploying code changes
- Use integration tests to catch breaking changes

---

## 4. Worker Crash Loop

### Symptoms
- Worker pods/containers restarting repeatedly
- CrashLoopBackOff in Kubernetes
- Logs show same error over and over
- No messages being processed

### Root Causes
- Unhandled exception in worker initialization
- Missing required environment variable
- Dependency unavailable (Redis, database)
- Out of memory (OOM killed)
- Syntax error in recently deployed code

### Diagnosis

```bash
# Check worker status
docker-compose ps
# Look for "Restarting (1)" status

# Kubernetes
kubectl get pods -l app=rag-worker
# Look for STATUS: CrashLoopBackOff, RESTARTS: 5+

# Check logs for crash reason
docker-compose logs rag-worker --tail 50
# Or K8s:
kubectl logs -l app=rag-worker --previous --tail=50

# Common errors:
# - ImportError: No module named 'xyz'
# - KeyError: 'REDIS_HOST'
# - redis.exceptions.ConnectionError
# - psycopg2.OperationalError
```

### Recovery Steps

**Step 1: Identify the error**
```bash
# Get last 20 lines before crash
docker-compose logs rag-worker --tail 20

# Look for:
# - Exception type (ImportError, KeyError, ConnectionError)
# - Stack trace showing problematic line
# - Environment variable references
```

**Step 2: Fix the root cause**

**Missing dependency:**
```bash
# Add to requirements.txt
echo "missing-package==1.0.0" >> requirements.txt

# Rebuild
docker-compose build rag-worker
docker-compose up -d rag-worker
```

**Missing environment variable:**
```bash
# Add to .env
echo "MISSING_VAR=value" >> .env

# Restart
docker-compose restart rag-worker
```

**Code bug:**
```bash
# Rollback to previous version
git checkout HEAD~1 agent/operational_agents/rag_agent/worker.py

# Rebuild and deploy
docker-compose build rag-worker
docker-compose up -d rag-worker

# Fix bug in separate branch and test before redeploying
```

**Out of memory:**
```bash
# Increase memory limit in docker-compose.yml
# services:
#   rag-worker:
#     deploy:
#       resources:
#         limits:
#           memory: 2G  # Increase from 1G

docker-compose up -d rag-worker
```

**Step 3: Verify recovery**
```bash
# Check worker is running
docker-compose ps rag-worker
# Should show "Up" status

# Check logs for successful startup
docker-compose logs rag-worker --tail 10
# Should see "Worker started" or similar

# Verify consumer registered
python scripts/ops.py health --all
```

### Prevention
- Add liveness probe with longer `initialDelaySeconds` to allow startup time
- Use health checks in CI/CD to catch crashes before production
- Add unit tests for worker initialization
- Monitor memory usage and set appropriate limits
- Use distributed tracing to catch exceptions in production

---

## 5. Redis Connection Loss

### Symptoms
- Workers logging `redis.exceptions.ConnectionError`
- Health endpoint returns 500
- All operations failing
- No messages being processed or enqueued

### Root Causes
- Redis server down or restarting
- Network partition between workers and Redis
- Redis hit max memory and evicting keys
- Redis credentials rotated but not updated in workers
- Firewall rule blocking Redis port

### Diagnosis

```bash
# Test Redis connectivity from worker host
docker-compose exec rag-worker redis-cli -h $REDIS_HOST -p $REDIS_PORT ping
# Should return: PONG

# Check Redis server status
redis-cli -h $REDIS_HOST -p $REDIS_PORT INFO server
# Or if using Redis Cloud, check dashboard

# Check worker logs
docker-compose logs rag-worker | grep -i "connection\|redis"

# Common errors:
# - "Connection refused" → Redis not running
# - "Authentication failed" → Wrong password
# - "Connection timeout" → Network issue
```

### Recovery Steps

**Step 1: Check Redis is running**
```bash
# Local Redis
docker-compose ps redis
# Should show "Up"

# If down, start it
docker-compose up -d redis

# Cloud Redis - check provider dashboard
```

**Step 2: Test connectivity**
```bash
# From worker container
docker-compose exec rag-worker ping redis
# Should get responses

# Try Redis CLI
docker-compose exec rag-worker redis-cli -h redis ping
```

**Step 3: Check credentials**
```bash
# Verify .env has correct values
cat .env | grep REDIS

# Update if needed
# REDIS_HOST=redis
# REDIS_PORT=6379
# REDIS_PASSWORD=your_password_here
# REDIS_DB=0

# Restart workers to pick up new config
docker-compose restart
```

**Step 4: Check Redis memory**
```bash
redis-cli INFO memory

# Look for:
# used_memory_human: 900M
# maxmemory: 1G
# maxmemory_policy: noeviction

# If near limit:
redis-cli CONFIG SET maxmemory 2gb
# Or configure eviction policy
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

**Step 5: Restart workers after Redis is healthy**
```bash
# Give Redis 10 seconds to stabilize
sleep 10

# Restart all services
docker-compose restart

# Verify health
python scripts/ops.py health --all
```

### Prevention
- Use Redis persistence (AOF) to recover after crashes
- Set up Redis monitoring (memory, connections, CPU)
- Configure Redis with `maxmemory` and appropriate eviction policy
- Use managed Redis (Redis Cloud, AWS ElastiCache) for HA
- Add connection retry logic with exponential backoff in workers

---

## 6. Disk Space Full (Redis AOF)

### Symptoms
- Redis logs: `Can't write to append-only file`
- Redis becomes read-only
- No new messages can be written to streams
- Health checks may still pass (reading works)

### Root Causes
- Redis AOF (append-only file) grew too large
- Log rotation not configured
- No disk monitoring alerts
- Sudden spike in message volume

### Diagnosis

```bash
# Check disk space on Redis host
df -h

# Example output:
# /dev/sda1       50G   49G   1.0G  98% /data  ← CRITICAL

# Check Redis data directory size
du -sh /var/lib/redis
# Or docker volume:
docker-compose exec redis du -sh /data

# Check Redis AOF size
ls -lh /var/lib/redis/appendonly.aof
```

### Recovery Steps

**Step 1: Free up space immediately (emergency)**
```bash
# Clean up old logs
docker-compose exec redis find /var/log -name "*.log" -mtime +7 -delete

# Clean up system logs
sudo journalctl --vacuum-time=2d

# Check space freed
df -h
```

**Step 2: Rewrite Redis AOF (compact)**
```bash
# Trigger AOF rewrite (creates new compact file)
redis-cli BGREWRITEAOF

# Monitor progress
redis-cli INFO persistence | grep aof_rewrite_in_progress
# Wait until: aof_rewrite_in_progress:0

# Check new AOF size
ls -lh /var/lib/redis/appendonly.aof
# Should be much smaller
```

**Step 3: Configure automatic AOF rewrite**
```bash
# Edit redis.conf or use CONFIG SET
redis-cli CONFIG SET auto-aof-rewrite-percentage 100
redis-cli CONFIG SET auto-aof-rewrite-min-size 64mb

# Save config
redis-cli CONFIG REWRITE
```

**Step 4: Long-term fix - increase disk or add rotation**
```bash
# Option 1: Increase disk size (cloud provider)
# AWS: Modify volume size in EC2 console
# Azure: Resize disk in portal

# Option 2: Add log rotation
sudo cat > /etc/logrotate.d/redis <<EOF
/var/log/redis/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
EOF

# Option 3: Use RDB snapshots instead of AOF (faster, less disk)
redis-cli CONFIG SET appendonly no
redis-cli CONFIG SET save "900 1 300 10 60 10000"
```

**Step 5: Resume normal operations**
```bash
# Verify Redis writable
redis-cli SET test_key test_value
redis-cli GET test_key
# Should return: "test_value"

# Restart workers
docker-compose restart

# Verify health
python scripts/ops.py health --all
```

### Prevention
- Set up disk space monitoring (alert at 80% full)
- Configure Redis with automatic AOF rewrite
- Use separate volume for Redis data
- Implement stream trimming (XTRIM) for old messages
- Consider RDB snapshots instead of AOF for less disk usage

---

## 7. Stream Growing Unbounded

### Symptoms
- Stream length growing continuously (>100k messages)
- Redis memory usage increasing
- No consumers processing or consumers can't keep up
- `XLEN` command shows huge numbers

### Root Causes
- No consumers active (see Playbook #1)
- Consumer lag too high (see Playbook #2)
- Messages not being acknowledged
- No MAXLEN configured on stream
- Orchestrator publishing faster than workers consume

### Diagnosis

```bash
# Check stream lengths
python scripts/ops.py health --all

# Detailed inspection
redis-cli XLEN rag:tasks
# Example: 156789 (very high)

# Check consumer group info
redis-cli XINFO GROUPS rag:tasks

# Check pending messages
redis-cli XPENDING rag:tasks rag-workers
# Shows: pending count, oldest pending message age
```

### Recovery Steps

**Step 1: Confirm consumers are active**
```bash
python scripts/ops.py health --all --pretty

# If consumers = 0, see Playbook #1
# If lag is high, see Playbook #2
```

**Step 2: Check for stuck pending messages**
```bash
# Get pending messages older than 5 minutes
python scripts/ops.py group claim rag:tasks rag-workers --idle-ms 300000

# This claims stuck messages from dead consumers
```

**Step 3: Scale up workers to drain backlog**
```bash
# Temporarily increase workers
docker-compose up -d --scale rag-worker=8

# Monitor stream length decreasing
watch -n 5 'redis-cli XLEN rag:tasks'
```

**Step 4: Add stream trimming (prevent future growth)**
```bash
# Option 1: Trim to last 10k messages (aggressive)
redis-cli XTRIM rag:tasks MAXLEN ~ 10000

# Option 2: Configure MAXLEN in code
# Edit orchestrator publish calls:
# redis.xadd("rag:tasks", fields, maxlen=10000, approximate=True)
```

**Step 5: Once drained, scale back down**
```bash
# Return to normal capacity
docker-compose up -d --scale rag-worker=2

# Verify stream length stable
watch -n 10 'redis-cli XLEN rag:tasks'
```

### Prevention
- Configure MAXLEN on all XADD calls: `redis.xadd(stream, fields, maxlen=10000)`
- Set up alerts for stream length > threshold
- Implement backpressure (pause orchestrator if lag > 1000)
- Use auto-scaling based on lag metric
- Regularly trim old processed messages

---

## 8. Slow Database Queries

### Symptoms
- High consumer lag despite workers present
- Distributed tracing shows `database_query` span > 1s
- Workers logging slow query warnings
- End-to-end latency increasing

### Root Causes
- Missing database indexes
- Large table scans (no WHERE clause optimization)
- Database connection pool exhausted
- Database CPU/memory maxed out
- Unoptimized query (N+1 problem, SELECT *)

### Diagnosis

```bash
# Check distributed tracing
# Open Jaeger: http://localhost:16686
# Find slow traces, look for "database_query" spans > 1s

# Check database query logs
# PostgreSQL:
psql -h $DB_HOST -U $DB_USER -c "SELECT query, mean_exec_time, calls FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"

# Check active connections
psql -h $DB_HOST -U $DB_USER -c "SELECT count(*) FROM pg_stat_activity;"

# Check table sizes
psql -h $DB_HOST -U $DB_USER -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size FROM pg_tables ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC LIMIT 10;"
```

### Recovery Steps

**Step 1: Identify slow queries from tracing**
```bash
# Example slow query from trace attributes:
# SELECT * FROM leads WHERE email ILIKE '%@example.com%'
# ↑ ILIKE with leading wildcard = full table scan
```

**Step 2: Add missing indexes**
```sql
-- Example: Index on email for ILIKE queries
CREATE INDEX idx_leads_email_lower ON leads (LOWER(email));

-- Index on frequently queried columns
CREATE INDEX idx_leads_campaign_id ON leads (campaign_id);
CREATE INDEX idx_leads_created_at ON leads (created_at);

-- Analyze table to update statistics
ANALYZE leads;
```

**Step 3: Optimize query**
```python
# Before (slow):
query = "SELECT * FROM leads WHERE email ILIKE '%@example.com%'"

# After (fast):
query = "SELECT id, email, name FROM leads WHERE email ILIKE 'user@example.com%'"
#        ↑ Specific columns      ↑ No leading wildcard (can use index)
```

**Step 4: Increase connection pool if needed**
```python
# In worker config
DB_POOL_SIZE = 20  # Increase from 10
DB_MAX_OVERFLOW = 10  # Allow burst
```

**Step 5: Monitor improvement**
```bash
# Check trace times in Jaeger
# database_query span should now be < 100ms

# Check consumer lag
python scripts/ops.py health --all
# Lag should decrease
```

### Prevention
- Add database query monitoring (slow query log)
- Use distributed tracing to identify regressions
- Add indexes based on query patterns
- Use connection pooling
- Implement query caching for read-heavy operations
- Run EXPLAIN ANALYZE on all queries before production

---

## 9. Duplicate Message Processing

### Symptoms
- Same message processed multiple times
- Duplicate database inserts (unique constraint errors)
- Logs show "already processed" warnings
- Distributed tracing shows multiple spans for same message_id

### Root Causes
- Worker didn't ACK message before crashing
- Worker timed out, message reclaimed by another consumer
- Manual replay from DLQ without checking if already processed
- Redis consumer group bug (rare)
- Idempotency key not implemented

### Diagnosis

```bash
# Check for duplicate message IDs in logs
docker-compose logs rag-worker | grep "message_id" | sort | uniq -d

# Check pending messages
redis-cli XPENDING rag:tasks rag-workers

# Check if message was ACKed
redis-cli XINFO CONSUMERS rag:tasks rag-workers

# Check DLQ for duplicates
python scripts/ops.py inspect persist:dlq --count 20
# Look for "duplicate key" errors
```

### Recovery Steps

**Step 1: Verify idempotency implemented**
```python
# Check worker code has idempotency key
# Example in persistence worker:
def process(self, fields):
    idempotency_key = fields.get("message_id")
    
    # Check if already processed
    if redis.exists(f"processed:{idempotency_key}"):
        logger.info(f"Skipping duplicate {idempotency_key}")
        return
    
    # Process message
    # ...
    
    # Mark as processed (TTL 24 hours)
    redis.setex(f"processed:{idempotency_key}", 86400, "1")
```

**Step 2: Fix duplicate constraint errors with upsert**
```python
# Before (fails on duplicate):
INSERT INTO leads (id, email, name) VALUES (?, ?, ?)

# After (idempotent):
INSERT INTO leads (id, email, name) VALUES (?, ?, ?)
ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email, name = EXCLUDED.name
```

**Step 3: Clean up DLQ duplicates**
```bash
# Auto-transform duplicates to upserts
python scripts/dlq_automation.py persist:dlq --auto-fix-duplicates --limit 100
```

**Step 4: Increase ACK timeout if needed**
```python
# In worker code
# If processing takes > 5 minutes, increase claim time
CLAIM_MIN_IDLE_TIME = 600000  # 10 minutes
```

### Prevention
- Implement idempotency keys for all workers
- Use database constraints (unique indexes) to catch duplicates
- Use UPSERT (INSERT ... ON CONFLICT) instead of INSERT
- Set appropriate ACK timeouts based on processing time
- Add distributed tracing to track message lifecycle
- Use at-most-once semantics if duplicates unacceptable

---

## 10. Health Endpoint Down

### Symptoms
- HTTP GET to `/health` returns connection refused or timeout
- Kubernetes readiness probe failing
- Load balancer removing service from rotation
- Prometheus scraping failing

### Root Causes
- Health server process crashed
- Port conflict (another service on 8080)
- Firewall blocking port
- Health server not started in deployment
- Out of memory killed health server

### Diagnosis

```bash
# Check if health server is running
docker-compose ps health-server
# Or K8s:
kubectl get pods -l app=health-server

# Check port is listening
netstat -tuln | grep 8080
# Or:
lsof -i :8080

# Try connecting locally
curl http://localhost:8080/healthz
# Should return: {"status": "alive"}

# Check logs
docker-compose logs health-server --tail 50
```

### Recovery Steps

**Step 1: Restart health server**
```bash
docker-compose restart health-server

# Or K8s:
kubectl rollout restart deployment/health-server

# Wait for startup
sleep 5
```

**Step 2: Test endpoints**
```bash
# Liveness
curl http://localhost:8080/healthz
# {"status": "alive"}

# Readiness
curl http://localhost:8080/ready
# {"status": "ready", "overall_status": "healthy"}

# Full health
curl http://localhost:8080/health | jq
```

**Step 3: If port conflict, change port**
```bash
# Edit docker-compose.yml
# services:
#   health-server:
#     command: ["python", "scripts/health_server.py", "--port", "8081"]
#     ports:
#       - "8081:8081"

docker-compose up -d health-server

# Test new port
curl http://localhost:8081/health
```

**Step 4: Fix startup crash**
```bash
# Check logs for error
docker-compose logs health-server

# Common issues:
# - Redis connection failed → check REDIS_HOST
# - Import error → rebuild image
# - Config missing → check .env
```

### Prevention
- Add liveness probe to auto-restart crashed health server
- Monitor health endpoint availability (meta-monitoring)
- Use process manager (systemd, supervisord) for auto-restart
- Set resource limits to prevent OOM
- Add health server to smoke tests in CI/CD

---

## Emergency Contact & Escalation

### On-Call Rotation
- **Primary:** [Your on-call engineer]
- **Secondary:** [Backup engineer]
- **Manager:** [Engineering manager]

### Escalation Path
1. **Severity 3 (Warning):** Ops team handles, notify in Slack
2. **Severity 2 (Critical):** Page on-call engineer, create incident
3. **Severity 1 (Outage):** Page on-call + manager, war room

### Communication Channels
- **Slack:** #agentic-system-alerts (automated)
- **Slack:** #incidents (manual updates)
- **PagerDuty:** agentic-system service
- **Status Page:** status.yourcompany.com

### Post-Incident
- Document in incident tracker
- Schedule postmortem within 48 hours
- Update runbooks with learnings
- Create Jira tickets for preventative work

---

## Monitoring Quick Links

- **Jaeger Tracing:** http://localhost:16686
- **Grafana Dashboards:** http://localhost:3000 (when implemented)
- **Health API:** http://localhost:8080/health
- **Prometheus:** http://localhost:9090 (when implemented)

## Tools Quick Reference

```bash
# Health check
python scripts/ops.py health --all --pretty

# Stream inspection
python scripts/ops.py inspect <stream> --count 10

# DLQ operations
python scripts/ops.py dlq list
python scripts/ops.py dlq replay <dlq-stream> --auto-fix

# Consumer group operations
python scripts/ops.py group reset <stream> <group> --id $
python scripts/ops.py group claim <stream> <group> --idle-ms 300000

# Scaling
python scripts/ops.py scale info
docker-compose up -d --scale rag-worker=5

# Distributed tracing
# Open http://localhost:16686, search by service or operation
```

---

**Last Updated:** October 26, 2025  
**Maintained By:** Platform Engineering Team  
**Feedback:** Create PR or Slack #agentic-system-docs
