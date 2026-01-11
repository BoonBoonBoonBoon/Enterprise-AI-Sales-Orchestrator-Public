# Docker Compose Local Development Setup

## Quick Start

```bash
# 1. Copy .env.example to .env and configure
cp .env.example .env

# 2. Start all services
docker-compose up -d

# 3. Check health
curl http://localhost:8080/health | jq

# 4. View logs
docker-compose logs -f rag-worker

# 5. Stop all services
docker-compose down
```

## Services

- **redis** - Redis 7 (port 6379)
- **postgres** - PostgreSQL 15 (port 5432)
- **rag-worker** - RAG processing agent
- **persist-worker** - Persistence agent
- **copy-worker** - Copywriter agent
- **orchestrator** - Workflow manager
- **health-server** - Health monitoring endpoint (port 8080)

## Environment Variables

Required in `.env`:
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
LLM_PROVIDER=openai  # or anthropic or placeholder
OPENAI_API_KEY=your_openai_key  # if using OpenAI
ANTHROPIC_API_KEY=your_anthropic_key  # if using Anthropic
```

## Scaling Workers

Scale individual services:
```bash
# Scale RAG workers to 3 instances
docker-compose up -d --scale rag-worker=3

# Scale persistence workers to 2 instances
docker-compose up -d --scale persist-worker=2
```

## Health Monitoring

Access health endpoints:
```bash
# Full health check
curl http://localhost:8080/health

# Liveness probe
curl http://localhost:8080/healthz

# Readiness probe
curl http://localhost:8080/ready

# Prometheus metrics
curl http://localhost:8080/metrics
```

## Troubleshooting

View logs:
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f rag-worker

# Last 100 lines
docker-compose logs --tail=100 persist-worker
```

Restart services:
```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart rag-worker
```

Rebuild after code changes:
```bash
docker-compose up -d --build
```

## Data Persistence

Volumes for data persistence:
- `redis-data` - Redis AOF persistence
- `postgres-data` - PostgreSQL data

Remove volumes (⚠️ deletes all data):
```bash
docker-compose down -v
```

## Network

All services communicate on `agentic-network` bridge network.

Connect to services from host:
- Redis: `redis://localhost:6379`
- PostgreSQL: `postgresql://agentic:agentic_dev@localhost:5432/agentic`
- Health API: `http://localhost:8080`

## Production Considerations

This setup is for local development. For production:
1. Use managed Redis (Redis Cloud, AWS ElastiCache)
2. Use managed PostgreSQL (Supabase, AWS RDS)
3. Configure proper secrets management
4. Enable TLS for Redis
5. Use container orchestration (Kubernetes, ECS)
6. Configure resource limits and autoscaling
