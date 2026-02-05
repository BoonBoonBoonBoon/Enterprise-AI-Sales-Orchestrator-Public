# Docker Deployment

This guide covers deploying the Agentic System with Docker Compose.

## Prerequisites

- Docker Desktop 4.0+
- Docker Compose 2.0+
- 8GB+ RAM available

## Quick Start

```powershell
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose                           │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Redis   │  │ Supabase │  │  Agents  │  │ Monitor  │   │
│  │          │  │ (Postgres│  │  (x5)    │  │ Stack    │   │
│  │  :6379   │  │  + API)  │  │          │  │          │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

### docker-compose.yml

```yaml
version: "3.8"

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  rag-agent:
    build:
      context: .
      dockerfile: deployment/docker/Dockerfile.agent
    command: python -m tiers.tier_3.rag_agent.consumer
    environment:
      - TENANT_ID=agentic-dev
      - REDIS_URL=redis://redis:6379/0
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
      - SUPABASE_JWT_SECRET=${SUPABASE_JWT_SECRET}
    depends_on:
      redis:
        condition: service_healthy

  persistence-agent:
    build:
      context: .
      dockerfile: deployment/docker/Dockerfile.agent
    command: python -m tiers.tier_3.persistence_agent.consumer
    environment:
      - TENANT_ID=agentic-dev
      - REDIS_URL=redis://redis:6379/0
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
      - SUPABASE_JWT_SECRET=${SUPABASE_JWT_SECRET}
    depends_on:
      redis:
        condition: service_healthy

  copywriter-agent:
    build:
      context: .
      dockerfile: deployment/docker/Dockerfile.agent
    command: python -m tiers.tier_3.copywriter_agent.consumer
    environment:
      - TENANT_ID=agentic-dev
      - REDIS_URL=redis://redis:6379/0
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      redis:
        condition: service_healthy

  leads-orchestrator:
    build:
      context: .
      dockerfile: deployment/docker/Dockerfile.agent
    command: python -m tiers.tier_2.leads_orchestrator.consumer
    environment:
      - TENANT_ID=agentic-dev
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - rag-agent
      - persistence-agent

  manager:
    build:
      context: .
      dockerfile: deployment/docker/Dockerfile.agent
    command: python -m tiers.tier_1.manager.consumer
    environment:
      - TENANT_ID=agentic-dev
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - leads-orchestrator

volumes:
  redis_data:
```

### Dockerfile

```dockerfile
# deployment/docker/Dockerfile.agent
FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run as non-root
RUN useradd -m appuser
USER appuser

# Default command (overridden by docker-compose)
CMD ["python", "-m", "tiers.tier_3.rag_agent.consumer"]
```

## Environment Variables

Create `.env` file:

```bash
# .env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_JWT_SECRET=your-jwt-secret
OPENAI_API_KEY=your-openai-api-key
TENANT_ID=agentic-dev
```

## Scaling

### Scale Agents

```powershell
# Scale RAG agent to 3 replicas
docker-compose up -d --scale rag-agent=3
```

### Check Replicas

```powershell
docker-compose ps
# NAME                REPLICAS   STATUS
# rag-agent           3/3        running
```

## Monitoring

### Add Observability Stack

```powershell
docker-compose -f docker-compose.yml -f deployment/docker-compose.observability.yml up -d
```

Access:

- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090

## Operations

### View Logs

```powershell
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f rag-agent

# Last 100 lines
docker-compose logs --tail=100 rag-agent
```

### Restart Service

```powershell
docker-compose restart rag-agent
```

### Stop All

```powershell
docker-compose down

# With volume cleanup
docker-compose down -v
```

### Update Images

```powershell
docker-compose build --no-cache
docker-compose up -d
```

## Health Checks

### Service Health

```powershell
docker-compose ps
# All should show "running (healthy)"
```

### Manual Checks

```powershell
# Redis
docker-compose exec redis redis-cli ping

# Test agent
docker-compose exec rag-agent python -c "print('ok')"
```

## Troubleshooting

### Container Won't Start

```powershell
# Check logs
docker-compose logs rag-agent

# Common issues:
# - Missing env vars → check .env file
# - Redis not ready → check depends_on
```

### Out of Memory

```powershell
# Check resource usage
docker stats

# Increase Docker memory in settings
```

## Related

- [Kubernetes Deployment](kubernetes.md)
- [Environment Variables](../../reference/config/env-vars.md)
- [Monitoring](../ops/monitoring.md)
