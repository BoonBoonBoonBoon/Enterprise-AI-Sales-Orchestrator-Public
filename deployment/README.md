# Deployment Guide

This directory contains Docker and deployment configuration for the Agentic System with the new three-tier + services architecture.

## Directory Structure

```
deployment/
├── docker/
│   └── Dockerfile.worker          # Multi-stage build for all worker types
├── docker-compose.yml              # Orchestration for local/dev/prod
├── .env.example                    # Environment variables template
└── README.md                        # This file
```

## Quick Start (Local Development)

### Prerequisites

- Docker & Docker Compose (v20.10+)
- Python 3.11 (for local development, optional if using Docker)
- Git (with branch `hazard`)

### Setup

1. **Clone and enter the workspace:**

   ```bash
   cd "c:\Users\Elliot\Desktop\Agency Files\Important\Technicals\Agentic System"
   ```

2. **Create environment file from template:**

   ```bash
   cp deployment/.env.example .env
   ```

3. **Edit `.env` with your API keys:**

   ```bash
   # Required
   OPENAI_API_KEY=your-openai-api-key
   SUPABASE_URL=https://...supabase.co
   SUPABASE_ANON_KEY=your-anon-key

   # Optional (for production or advanced features)
   VECTOR_DB_BACKEND=pinecone
   PINECONE_API_KEY=...
   ```

4. **Build and start services:**

   ```bash
   # Start with local Redis + PostgreSQL
   docker compose --profile local up -d --build

   # OR start with external Redis (e.g., Redis Cloud)
   docker compose up -d --build
   ```

5. **Verify services are running:**
   ```bash
   curl http://localhost:8080/health | jq
   ```

## Architecture Overview

The deployment is organized into three tiers + services:

### Tier 1: Manager (Strategic)

- **Container:** `manager`
- **Role:** Coordinates system strategy and flow
- **Module:** `tiers.tier_1.manager.consumer`
- **Responsibilities:** Route tasks, manage state, orchestrate tier_2

### Tier 2: Orchestrators (Business Logic)

- **Containers:** `leads_orchestrator`, `outreach_orchestrator`
- **Role:** Coordinate domain-specific workflows
- **Modules:**
  - `tiers.tier_2.leads_orchestrator.consumer` (lead discovery → qualification)
  - `tiers.tier_2.outreach_orchestrator.consumer` (copy → scheduling → tracking)
- **Responsibilities:** Delegate to tier_3 agents, manage workflow state

### Tier 3: Agents (Operational)

- **Containers:** `rag_agent`, `persistence_agent`, `copywriter_agent`
- **Role:** Execute specialized tasks
- **Modules:**
  - `tiers.tier_3.rag_agent.consumer` (research & analysis)
  - `tiers.tier_3.persistence_agent.consumer` (database operations)
  - `tiers.tier_3.copywriter_agent.consumer` (content generation)
- **Responsibilities:** Perform unit tasks, interact with services

### Services Layer

- **Persistence Service** (`services/persistence/`) - Database adapters (Supabase, PostgreSQL, Snowflake)
- **Redis Service** (`services/redis/`) - Pub/Sub and Streams with consumer groups
- **Vector DB Service** (`services/vector_db/`) - Multi-backend similarity search (Pinecone, Weaviate)
- **External APIs Service** (`services/external_apis/`) - CrunchBase, LinkedIn, custom APIs

### Infrastructure

- **Redis:** Message broker for Streams-based async communication
- **PostgreSQL:** Primary database (optional local, typically Supabase in dev)
- **Health Server:** Exposes `/health`, `/healthz`, `/ready`, `/metrics` endpoints

## Docker Compose Usage

### Start Services

```bash
# Full stack with local Redis + Postgres
docker compose --profile local up -d --build

# Production (external Redis/DB)
docker compose up -d --build

# Watch logs
docker compose logs -f

# Follow specific service
docker compose logs -f persistence_agent
```

### Scale Services

```bash
# Scale persistence agent to 3 replicas
docker compose up -d --scale persistence_agent=3

# Scale copywriter to 2 replicas
docker compose up -d --scale copywriter_agent=2
```

### Stop Services

```bash
# Stop all
docker compose down

# Stop and remove volumes (⚠️ deletes data)
docker compose down -v
```

### Run One-Off Commands

```bash
# Run ingest CLI
docker compose --profile tools run --rm ingest_cli

# Execute shell in running container
docker compose exec persistence_agent /bin/bash

# Run Python snippet
docker compose exec manager python -c "import tiers; print(tiers.__file__)"
```

## Environment Variables

Key variables for each deployment scenario:

### Local Development

```env
REDIS_URL=redis://redis:6379/0      # Local compose Redis
SUPABASE_URL=                         # Leave empty or use dev Supabase
VECTOR_DB_BACKEND=in-memory          # Fast, no external dependency
```

### Staging (Cloud Services)

```env
REDIS_URL=redis://cloud-redis:6379   # Redis Cloud
SUPABASE_URL=https://...supabase.co  # Supabase staging project
VECTOR_DB_BACKEND=pinecone           # Pinecone staging space
OTEL_ENABLED=1                        # Enable tracing
```

### Production (High Availability)

```env
REDIS_URL=redis://prod-redis:6379    # Managed Redis with TLS
SUPABASE_URL=https://...supabase.co  # Supabase production project
VECTOR_DB_BACKEND=pinecone           # Pinecone production space
OTEL_ENABLED=1                        # Enable observability
LOG_LEVEL=INFO                        # Reduced verbosity
```

See `deployment/.env.example` for the complete list of variables.

## Dockerfile Structure

**Location:** `deployment/docker/Dockerfile.worker`

The Dockerfile is a multi-stage build that:

1. Installs Python 3.11 runtime and dependencies
2. Copies application source (core/, tiers/, services/, config/)
3. Creates non-root `worker` user for security
4. Sets up health checks (Redis ping)
5. Defaults to persistence agent consumer

All worker types (tier_1, tier_2, tier_3) use the same image with different `CMD` overrides in docker-compose.

## Troubleshooting

### Services won't start

```bash
# Check Docker daemon
docker ps

# Verify compose syntax
docker compose config

# View build logs
docker compose up --build
```

### Connection errors to Redis

```bash
# Test Redis connectivity
docker compose exec manager redis-cli -u $REDIS_URL ping

# Check Redis URL in .env
grep REDIS_URL .env
```

### Supabase `NameResolutionError` / host not found

If agents log errors like DNS resolution failures when calling Supabase, first verify the **Supabase project URL hostname actually exists**.

On Windows (host machine):

```powershell
Resolve-DnsName <your-project-ref>.supabase.co
```

If that fails (NXDOMAIN), your `SUPABASE_URL` is wrong (or the project was deleted). Copy the correct URL from **Supabase Dashboard → Settings → API** and restart the stack:

```bash
docker compose -f deployment/docker-compose.yml up -d
```

### Agent not consuming messages

```bash
# Check consumer group status
docker compose exec manager python -m services.redis.streams debug-groups

# Check stream content
docker compose exec manager redis-cli -u $REDIS_URL XLEN rag:tasks
```

### Inspect running container

```bash
# View environment
docker compose exec persistence_agent env | grep REDIS

# Check module imports
docker compose exec persistence_agent python -c "from tiers.tier_3 import persistence_agent; print(persistence_agent.__file__)"

# Run interactive shell
docker compose exec -it copywriter_agent /bin/bash
```

## Health Monitoring

The `health_server` service exposes metrics on `http://localhost:8080`:

```bash
# Basic health
curl http://localhost:8080/health | jq

# Readiness probe
curl http://localhost:8080/ready

# Metrics (Prometheus format)
curl http://localhost:8080/metrics
```

## Migration from Old Structure

If migrating from the old `agent/` structure:

1. **Update imports:** All modules now import from `core/`, `tiers/`, `services/`
2. **Fallback support:** Old imports still work via `agent/utils/` wrappers
3. **No breaking changes:** System works during transition period
4. **Gradual migration:** Update consumer paths incrementally

See `docs/MIGRATION.md` for detailed mapping.

## Production Deployment

### Kubernetes Example

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: manager
spec:
  replicas: 1
  selector:
    matchLabels:
      tier: tier-1
  template:
    metadata:
      labels:
        tier: tier-1
    spec:
      containers:
        - name: manager
          image: agentic/worker:latest
          env:
            - name: REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: redis-secrets
                  key: url
          command: ["python", "-m", "tiers.tier_1.manager.consumer"]
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "1Gi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
```

### ECS Example

```json
{
  "family": "agentic-persistence-agent",
  "containerDefinitions": [
    {
      "name": "persistence_agent",
      "image": "123456789.dkr.ecr.us-east-1.amazonaws.com/agentic/worker:latest",
      "command": ["python", "-m", "tiers.tier_3.persistence_agent.consumer"],
      "environment": [
        {
          "name": "REDIS_URL",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789:secret:redis-url"
        }
      ],
      "memory": 1024,
      "cpu": 512,
      "healthCheck": {
        "command": [
          "CMD-SHELL",
          "curl -f http://localhost:8080/health || exit 1"
        ],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
```

## Support

For issues:

1. Check logs: `docker compose logs -f [service]`
2. Verify `.env` configuration
3. Ensure Redis/DB connectivity
4. Review `docs/ARCHITECTURE.md` for system design
5. Check `docs/MIGRATION.md` for import paths

---

**Last Updated:** Task 15 - Deployment directory creation  
**Architecture:** Three-tier + services (Tasks 1-14 complete)  
**Status:** Ready for development and production deployment
