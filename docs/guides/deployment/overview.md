# Deployment Guide

Complete procedures for deploying the Agentic System in different environments.

## Quick Start (Local Development)

### Prerequisites

- Docker & Docker Compose v20.10+
- Python 3.11
- Git with branch `hazard`

### Setup (5 minutes)

```bash
# 1. Clone and navigate
cd "c:\Users\Elliot\Desktop\Agency Files\Important\Technicals\Agentic System"

# 2. Create .env from template
cp deployment/.env.example .env

# 3. Add your API keys
# Edit .env with:
# - OPENAI_API_KEY=sk-...
# - SUPABASE_URL=...
# - SUPABASE_KEY=...

# 4. Start services
docker compose --profile local up -d --build

# 5. Verify
curl http://localhost:8080/health | jq
```

## Environment Profiles

### Local (Development)

```bash
# Includes: Redis, PostgreSQL (local), all agents
docker compose --profile local up -d
```

**Configuration:**
```env
REDIS_URL=redis://redis:6379/0        # Local Redis
SUPABASE_URL=                          # Optional (use local Postgres)
VECTOR_DB_BACKEND=in-memory            # Fast, no external dependency
```

**Services running:**
- manager (tier_1)
- leads_orchestrator, outreach_orchestrator (tier_2)
- rag_agent, persistence_agent, copywriter_agent (tier_3)
- redis, postgres (infrastructure)
- health_server (monitoring)

### Staging (Cloud Services)

```bash
docker compose up -d
```

**Configuration:**
```env
REDIS_URL=redis://staging-redis:6379    # Redis Cloud
SUPABASE_URL=https://staging.supabase.co
VECTOR_DB_BACKEND=pinecone              # Pinecone staging
OTEL_ENABLED=1                          # Tracing
```

### Production (High Availability)

```bash
# Use managed services, no local containers
docker swarm init
docker stack deploy -c deployment/docker-compose.yml agentic
```

**Configuration:**
```env
REDIS_URL=redis://prod-redis:6379      # Managed Redis
SUPABASE_URL=https://prod.supabase.co  # Production project
VECTOR_DB_BACKEND=pinecone             # Production space
OTEL_ENABLED=1                         # Observability
LOG_LEVEL=INFO                         # Reduced logging
```

## Docker Compose Operations

### Start Services

```bash
# With local services (Redis, Postgres)
docker compose --profile local up -d --build

# Without local services (use external)
docker compose up -d --build

# Watch logs
docker compose logs -f

# Specific service logs
docker compose logs -f persistence_agent
```

### Scale Services

```bash
# Scale persistence agent to 3 replicas
docker compose up -d --scale persistence_agent=3

# Scale copywriter to 5
docker compose up -d --scale copywriter_agent=5

# Check running containers
docker compose ps
```

### Stop Services

```bash
# Stop all (data preserved)
docker compose down

# Stop and delete volumes (WARNING: deletes data)
docker compose down -v

# Stop specific service
docker compose stop persistence_agent
```

### Execute Commands

```bash
# Interactive shell in container
docker compose exec manager /bin/bash

# Run Python command
docker compose exec persistence_agent python -c "import tiers; print(tiers.__file__)"

# Check environment
docker compose exec rag_agent env | grep REDIS
```

## Build Configuration

### Dockerfile

**Location:** `deployment/docker/Dockerfile.worker`

**Multi-stage build:**
1. Base image (python:3.11-slim)
2. Install dependencies
3. Copy application code
4. Create non-root user
5. Set health checks
6. Define entrypoint

**Key features:**
- Minimal image size (~500MB)
- Health checks included
- Security best practices (non-root user)
- Configurable via environment

### Build Images

```bash
# Build all images
docker compose build --no-cache

# Build specific image
docker compose build --no-cache manager

# Build without cache (ensures fresh dependencies)
docker compose build --no-cache --force-rm

# Check image sizes
docker images | grep agentic
```

## Environment Configuration

### Required Variables

```env
# API Keys
OPENAI_API_KEY=sk-proj-...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...

# Infrastructure
REDIS_URL=redis://redis:6379/0
TENANT_ID=agentic-prod
```

### Optional Variables

```env
# Vector Database
VECTOR_DB_BACKEND=pinecone
PINECONE_API_KEY=...
PINECONE_ENVIRONMENT=...

# External APIs
CRUNCHBASE_API_KEY=...
LINKEDIN_API_KEY=...

# Observability
OTEL_ENABLED=1
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
LOG_LEVEL=INFO
```

### Generate .env

```bash
# From template
cp deployment/.env.example .env

# From config file
python scripts/generate_env.py config/settings.yaml > .env

# Encrypt sensitive data
ansible-vault encrypt .env
```

## Health Checks

### Service Health

```bash
# HTTP health endpoint
curl http://localhost:8080/health

# Returns JSON
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:00Z",
  "services": {
    "redis": "connected",
    "database": "connected",
    "vector_db": "connected"
  }
}
```

### Redis Health

```bash
# Check Redis connectivity
docker compose exec manager redis-cli -u $REDIS_URL ping

# Check consumer groups
docker compose exec manager redis-cli -u $REDIS_URL XINFO GROUPS rag:tasks

# Check stream depth
docker compose exec manager redis-cli -u $REDIS_URL XLEN rag:tasks
```

### Database Health

```bash
# Check connection
docker compose exec persistence_agent psql $DATABASE_URL -c "SELECT NOW();"

# Check migrations
psql $DATABASE_URL -f scripts/check_migrations.sql
```

## Monitoring & Metrics

### Prometheus Metrics

```bash
# Scrape metrics endpoint
curl http://localhost:8080/metrics

# Filter by metric type
curl http://localhost:8080/metrics | grep "worker_processing_seconds"
```

### Key Metrics to Monitor

| Metric | Threshold | Action |
|--------|-----------|--------|
| Consumer lag | > 1000 messages | Scale up agents |
| Error rate | > 5% | Check logs, investigate failures |
| Processing latency p95 | > 5 seconds | Optimize agent or add resources |
| Cache hit rate | < 50% | Increase cache size |

### Logging

```bash
# View logs
docker compose logs -f

# Filter by service
docker compose logs -f persistence_agent

# Follow with timestamps
docker compose logs -f --timestamps

# Last 100 lines
docker compose logs --tail=100

# Export to file
docker compose logs > app.log
```

## Upgrading

### Update Application

```bash
# 1. Pull new code
git pull origin hazard

# 2. Rebuild images
docker compose build --no-cache

# 3. Restart services (rolling update)
docker compose up -d

# 4. Verify health
curl http://localhost:8080/health
```

### Update Dependencies

```bash
# 1. Update requirements.txt
pip freeze > requirements.txt
git add requirements.txt

# 2. Rebuild with new dependencies
docker compose build --no-cache requirements

# 3. Test before production deployment
docker-compose -f docker-compose.test.yml up
```

### Database Migrations

```bash
# Auto-migrate on startup (recommended)
MIGRATE_ON_STARTUP=1 docker compose up -d

# Manual migration
docker compose exec persistence_agent \
  alembic upgrade head

# Rollback
docker compose exec persistence_agent \
  alembic downgrade -1
```

## Troubleshooting

### Service Won't Start

```bash
# Check container logs
docker compose logs persistence_agent

# Check Docker daemon
docker ps

# Verify syntax
docker compose config

# Try rebuilding
docker compose build --no-cache persistence_agent
docker compose up -d persistence_agent
```

### Connection Errors

```bash
# Test Redis connectivity
docker compose exec manager redis-cli -u $REDIS_URL ping

# Test database
docker compose exec persistence_agent \
  psql $DATABASE_URL -c "SELECT 1;"

# Check environment
docker compose exec manager env | grep REDIS_URL
```

### High Latency

```bash
# Check consumer group lag
docker compose exec manager python -c \
  "from services.redis import StreamManager; \
   m = StreamManager(...); \
   print(m.consumer_lag('rag:tasks', 'rag-workers'))"

# Monitor resource usage
docker stats

# Check if scaling helps
docker compose up -d --scale rag_agent=5
```

### Memory Issues

```bash
# Check memory usage
docker compose stats

# Limit memory per service
# Edit docker-compose.yml:
# services:
#   persistence_agent:
#     mem_limit: 1g

# Monitor from inside container
docker compose exec persistence_agent \
  python -m memory_profiler script.py
```

## Backup & Recovery

### Backup Data

```bash
# Backup Redis streams to file
docker compose exec redis \
  redis-cli --rdb /backup/dump.rdb

# Backup database
docker compose exec postgres \
  pg_dump -U agentic agentic > /backup/db.sql

# Copy to host
docker cp agentic-redis-1:/backup/dump.rdb ./backup/
docker cp agentic-postgres-1:/backup/db.sql ./backup/
```

### Restore Data

```bash
# Restore Redis
docker cp ./backup/dump.rdb agentic-redis-1:/backup/
docker compose exec redis \
  redis-cli --pipe < /backup/dump.rdf

# Restore database
docker compose exec postgres \
  psql -U agentic agentic < /backup/db.sql
```

### Disaster Recovery

```bash
# 1. Stop services
docker compose down -v

# 2. Restore backups
docker cp ./backup/dump.rdf agentic-redis-1:/data/
docker cp ./backup/db.sql agentic-postgres-1:/

# 3. Start fresh
docker compose --profile local up -d

# 4. Verify
docker compose logs --tail=50
```

## Performance Tuning

### Resource Allocation

```yaml
# docker-compose.yml
services:
  manager:
    mem_limit: 512m
    cpus: 0.5
  
  persistence_agent:
    mem_limit: 1g
    cpus: 1
    
  copywriter_agent:
    mem_limit: 2g  # Higher for LLM processing
    cpus: 2
```

### Connection Pooling

```env
# Database
CONNECTION_POOL_SIZE=20
CONNECTION_POOL_TIMEOUT=30

# Redis
REDIS_POOL_SIZE=50
```

### Caching

```env
# In-memory embedding cache
EMBEDDING_CACHE_SIZE=10000

# Batch processing
BATCH_SIZE=128
```

## Security

### Secret Management

```bash
# Use .env files (development)
# Use secrets manager (production)
docker secret create openai_key -
# Enter: sk-proj-...

# In docker-compose:
services:
  manager:
    secrets:
      - openai_key
    environment:
      OPENAI_API_KEY_FILE: /run/secrets/openai_key
```

### Network Security

```yaml
# Restrict network access
networks:
  agentic-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/16
```

### TLS/SSL

```env
# Enable TLS for Redis
REDIS_URL=rediss://user:pass@redis:6380

# SSL certificate verification
SSL_VERIFY=true
SSL_CA_CERT=/etc/ssl/certs/ca-bundle.crt
```

## See Also

- `deployment/README.md` - Quick start guide
- `deployment/.env.example` - Environment template
- `ARCHITECTURE.md` - System design
- Docker Compose docs: https://docs.docker.com/compose

---

**Last Updated:** Task 17 - Deployment documentation  
**Supported Environments:** Local, Staging, Production  
**Container Orchestration:** Docker Compose, Docker Swarm, Kubernetes-ready
