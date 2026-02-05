# Infrastructure Overview

This document provides a comprehensive overview of the Agentic System's production infrastructure.

## Architecture Summary

The Agentic System uses a **3-Tier Agent Orchestration** architecture deployed on **Kubernetes** with managed backing services.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Production Infrastructure                        │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    Kubernetes Cluster (EKS/AKS)                   │   │
│  │                                                                   │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │   │
│  │  │   Ingress   │  │   Ingress   │  │      cert-manager       │  │   │
│  │  │   (nginx)   │  │   (Portal)  │  │     (TLS/HTTPS)         │  │   │
│  │  └──────┬──────┘  └──────┬──────┘  └─────────────────────────┘  │   │
│  │         │                │                                       │   │
│  │         ▼                ▼                                       │   │
│  │  ┌─────────────┐  ┌─────────────┐                               │   │
│  │  │ API Gateway │  │   Portal    │                               │   │
│  │  │  (FastAPI)  │  │  (Next.js)  │                               │   │
│  │  └──────┬──────┘  └─────────────┘                               │   │
│  │         │                                                        │   │
│  │         ▼                                                        │   │
│  │  ┌─────────────────────────────────────────────────────────┐    │   │
│  │  │                    Worker Pods                           │    │   │
│  │  │  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │    │   │
│  │  │  │ Manager │ │  Leads   │ │ Outreach │ │    RAG     │  │    │   │
│  │  │  │ (Tier1) │ │  (Tier2) │ │  (Tier2) │ │  (Tier3)   │  │    │   │
│  │  │  └─────────┘ └──────────┘ └──────────┘ └────────────┘  │    │   │
│  │  │  ┌───────────┐ ┌────────────┐ ┌────────────────────┐   │    │   │
│  │  │  │Persistence│ │ Copywriter │ │ Channel Sequencer  │   │    │   │
│  │  │  │  (Tier3)  │ │   (Tier3)  │ │      (Tier3)       │   │    │   │
│  │  │  └───────────┘ └────────────┘ └────────────────────┘   │    │   │
│  │  └─────────────────────────────────────────────────────────┘    │   │
│  │                                                                   │   │
│  │  ┌─────────────────────────────────────────────────────────┐    │   │
│  │  │                 Secrets (CSI Driver)                     │    │   │
│  │  │    AWS Secrets Manager  │  Azure Key Vault              │    │   │
│  │  └─────────────────────────────────────────────────────────┘    │   │
│  │                                                                   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                     Managed Services (External)                   │   │
│  │                                                                   │   │
│  │  ┌─────────────────┐    ┌───────────────────────────────────┐   │   │
│  │  │   Redis Cloud   │    │            Supabase               │   │   │
│  │  │    (TLS)        │    │   PostgreSQL + Auth + RLS         │   │   │
│  │  │                 │    │   Vector Store (pgvector)         │   │   │
│  │  └─────────────────┘    └───────────────────────────────────┘   │   │
│  │                                                                   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Components

### Kubernetes Resources

| Resource    | Name             | Purpose                          |
| ----------- | ---------------- | -------------------------------- |
| Namespace   | `agentic-system` | Isolation for all resources      |
| ConfigMap   | `agentic-config` | Environment variables            |
| Deployments | 10 total         | Worker pods, API, Portal, Health |
| Services    | ClusterIP        | Internal networking              |
| Ingress     | nginx            | HTTPS routing                    |
| HPA         | Per deployment   | Auto-scaling based on CPU        |

### Worker Deployments

| Deployment            | Tier | Replicas | CPU (req/lim) | Memory (req/lim) |
| --------------------- | ---- | -------- | ------------- | ---------------- |
| manager               | 1    | 1        | 250m / 1000m  | 512Mi / 1Gi      |
| leads-orchestrator    | 2    | 1        | 250m / 1000m  | 512Mi / 1Gi      |
| outreach-orchestrator | 2    | 1        | 250m / 1000m  | 512Mi / 1Gi      |
| rag-agent             | 3    | 2        | 500m / 2000m  | 1Gi / 2Gi        |
| persistence-agent     | 3    | 1        | 250m / 1000m  | 512Mi / 1Gi      |
| copywriter-agent      | 3    | 2        | 500m / 2000m  | 1Gi / 2Gi        |
| scheduler-agent       | 3    | 1        | 100m / 500m   | 256Mi / 512Mi    |
| channel-sequencer     | 3    | 1        | 100m / 500m   | 256Mi / 512Mi    |

### Public-Facing Services

| Service     | Type      | Port | Ingress Path |
| ----------- | --------- | ---- | ------------ |
| API Gateway | ClusterIP | 8000 | `/api/*`     |
| Portal      | ClusterIP | 3000 | `/`          |

## Managed Services

### Redis Cloud

- **Type**: Managed Redis with TLS
- **URL Format**: `rediss://...` (note the `s` for TLS)
- **Purpose**: Redis Streams for inter-agent communication
- **Recommendation**: Redis Cloud or AWS ElastiCache/Azure Cache for Redis

### Supabase

- **Components**: PostgreSQL + Auth + Storage + RLS
- **Purpose**: Primary database, authentication, row-level security
- **Extensions**: pgvector for vector search (RAG)

## Security

### 3-Layer Authentication

1. **API Gateway**: JWT validation + rate limiting
2. **PostgreSQL GRANT**: Role-based permissions (`agent_reader`, `agent_writer`)
3. **RLS Policies**: Row-level security with tenant isolation

### Secrets Management

Secrets are stored in cloud secret managers and injected via CSI driver:

**AWS Secrets Manager:**

```yaml
secretName: agentic-system/prod
```

**Azure Key Vault:**

```yaml
keyVaultName: agentic-system-prod
```

**Required Secrets:**

| Secret                | Description                   |
| --------------------- | ----------------------------- |
| `REDIS_URL`           | Redis connection string (TLS) |
| `SUPABASE_URL`        | Supabase project URL          |
| `SUPABASE_ANON_KEY`   | Supabase anon key             |
| `SUPABASE_JWT_SECRET` | JWT signing secret            |
| `OPENAI_API_KEY`      | LLM API key                   |
| `GMAIL_REFRESH_TOKEN` | Email OAuth token             |

## CI/CD Pipeline

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  Push   │───▶│  Lint   │───▶│  Test   │───▶│  Build  │───▶│ Deploy  │
│         │    │ (ruff)  │    │(pytest) │    │(docker) │    │ (helm)  │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
```

- **Lint**: Ruff + Mypy static analysis
- **Test**: Pytest with Redis service, JUnit + coverage reports
- **Build**: Docker images (gated on lint + test)
- **Deploy**: Helm upgrade to K8s (manual approval)

## Scaling Strategy

### Horizontal Pod Autoscaler (HPA)

Workers scale based on CPU utilization:

```yaml
minReplicas: 2
maxReplicas: 10
targetCPUUtilizationPercentage: 70
```

### High-Throughput Agents

These agents handle more load and should have higher replica counts:

- **RAG Agent**: 2-5 replicas (retrieval-heavy)
- **Copywriter Agent**: 2-5 replicas (LLM calls)
- **Persistence Agent**: 1-3 replicas (database writes)

### Queue Depth Scaling

Future enhancement: Scale based on Redis stream pending message count using KEDA.

## Monitoring

### Health Endpoints

- `/health` - Liveness probe
- `/ready` - Readiness probe (checks Redis + Supabase)

### Observability Stack

See [Observability Guide](../ops/observability.md) for:

- Prometheus metrics
- Grafana dashboards
- Loki log aggregation
- Tempo distributed tracing

## Tenant Isolation Strategy

### Alpha (Internal per-client)

- One environment per client
- Separate Supabase project + Redis namespace
- Maximum isolation

### Public SaaS

- Single Supabase project
- Strict RLS policies with `tenant_id`
- Shared infrastructure, data isolation via RLS

## Related

- [Kubernetes Guide](kubernetes.md)
- [Helm Chart](helm.md)
- [CI/CD Guide](ci-cd.md)
- [Secrets Guide](secrets.md)
