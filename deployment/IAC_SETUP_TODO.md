# Infrastructure as Code (IaC) Setup TODO

This document outlines the infrastructure-as-code requirements for deploying the three-tier agentic system to production.

## Overview

The system requires multi-environment infrastructure supporting:
- **Tier 1**: Manager (strategic planning)
- **Tier 2**: Orchestrators (leads, outreach, audit, inbound)
- **Tier 3**: Operational agents (RAG, persistence, copywriter)
- **Core**: Shared services (Redis, PostgreSQL, observability)

## 1. Kubernetes Manifests

### Required Resources

**Deployments** (`k8s/deployments/`)
- [ ] `tier1-manager-deployment.yaml` - Manager deployment (1 replica)
- [ ] `tier2-leads-deployment.yaml` - Leads orchestrator (2-5 replicas)
- [ ] `tier2-outreach-deployment.yaml` - Outreach orchestrator (2-5 replicas)
- [ ] `tier2-audit-deployment.yaml` - Audit orchestrator (1-3 replicas)
- [ ] `tier2-inbound-deployment.yaml` - Inbound orchestrator (2-5 replicas)
- [ ] `tier3-rag-deployment.yaml` - RAG agent (3-10 replicas)
- [ ] `tier3-persistence-deployment.yaml` - Persistence agent (3-10 replicas)
- [ ] `tier3-copywriter-deployment.yaml` - Copywriter agent (2-5 replicas)

**Services** (`k8s/services/`)
- [ ] `tier1-manager-service.yaml` - Internal ClusterIP
- [ ] `tier2-leads-service.yaml` - Internal ClusterIP
- [ ] `tier2-outreach-service.yaml` - Internal ClusterIP
- [ ] `tier2-audit-service.yaml` - Internal ClusterIP
- [ ] `tier2-inbound-service.yaml` - Internal ClusterIP
- [ ] `redis-service.yaml` - Internal ClusterIP (or external managed service)
- [ ] `postgres-service.yaml` - Internal ClusterIP (or external managed service)

**ConfigMaps** (`k8s/configmaps/`)
- [ ] `tier1-config.yaml` - Manager configuration
- [ ] `tier2-config.yaml` - Orchestrator shared config
- [ ] `tier3-config.yaml` - Operational agents shared config
- [ ] `redis-config.yaml` - Redis connection strings, pool sizes
- [ ] `postgres-config.yaml` - Database connection strings
- [ ] `observability-config.yaml` - OTEL endpoints, Jaeger, Datadog

**Secrets** (`k8s/secrets/`)
- [ ] `api-keys-secret.yaml` - OpenAI, Anthropic API keys
- [ ] `database-secret.yaml` - PostgreSQL credentials
- [ ] `redis-secret.yaml` - Redis passwords
- [ ] `external-services-secret.yaml` - Third-party integrations

**Ingress** (`k8s/ingress/`)
- [ ] `manager-ingress.yaml` - External API access (optional)
- [ ] `health-ingress.yaml` - Health check endpoints

### Deployment Strategy

**Rolling Updates**
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0
```

**Health Checks**
```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 5
```

## 2. Helm Charts

### Chart Structure

```
charts/
├── agentic-system/
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── values-dev.yaml
│   ├── values-staging.yaml
│   ├── values-prod.yaml
│   └── templates/
│       ├── tier1/
│       │   ├── manager-deployment.yaml
│       │   └── manager-service.yaml
│       ├── tier2/
│       │   ├── leads-deployment.yaml
│       │   ├── outreach-deployment.yaml
│       │   ├── audit-deployment.yaml
│       │   └── inbound-deployment.yaml
│       ├── tier3/
│       │   ├── rag-deployment.yaml
│       │   ├── persistence-deployment.yaml
│       │   └── copywriter-deployment.yaml
│       ├── core/
│       │   ├── redis-statefulset.yaml
│       │   ├── postgres-statefulset.yaml
│       │   └── configmaps.yaml
│       └── _helpers.tpl
```

### Values Configuration

**Development** (`values-dev.yaml`)
```yaml
environment: development

tier1:
  manager:
    replicas: 1
    resources:
      requests:
        memory: "512Mi"
        cpu: "250m"
      limits:
        memory: "1Gi"
        cpu: "500m"

tier2:
  leads:
    replicas: 1
  outreach:
    replicas: 1

tier3:
  rag:
    replicas: 2
  persistence:
    replicas: 2
  copywriter:
    replicas: 1

redis:
  enabled: true
  standalone: true
  
postgres:
  enabled: true
  standalone: true
```

**Production** (`values-prod.yaml`)
```yaml
environment: production

tier1:
  manager:
    replicas: 1
    resources:
      requests:
        memory: "2Gi"
        cpu: "1000m"
      limits:
        memory: "4Gi"
        cpu: "2000m"

tier2:
  leads:
    replicas: 5
    hpa:
      enabled: true
      minReplicas: 3
      maxReplicas: 10
      targetCPU: 70
  
  outreach:
    replicas: 5
    hpa:
      enabled: true
      minReplicas: 3
      maxReplicas: 10
      targetCPU: 70

tier3:
  rag:
    replicas: 10
    hpa:
      enabled: true
      minReplicas: 5
      maxReplicas: 20
      targetCPU: 80
  
  persistence:
    replicas: 10
    hpa:
      enabled: true
      minReplicas: 5
      maxReplicas: 20
      targetCPU: 80
  
  copywriter:
    replicas: 5
    hpa:
      enabled: true
      minReplicas: 3
      maxReplicas: 10
      targetCPU: 75

redis:
  enabled: false  # Use managed Redis (AWS ElastiCache, Azure Cache)
  
postgres:
  enabled: false  # Use managed PostgreSQL (AWS RDS, Azure Database)
```

## 3. Terraform Modules

### Cloud Provider Infrastructure

**AWS** (`terraform/aws/`)
- [ ] VPC and networking (subnets, security groups, NAT gateways)
- [ ] EKS cluster configuration
- [ ] ElastiCache Redis cluster (production)
- [ ] RDS PostgreSQL instance (production)
- [ ] S3 buckets for checkpointing
- [ ] CloudWatch log groups
- [ ] IAM roles and policies

**Azure** (`terraform/azure/`)
- [ ] Virtual Network and subnets
- [ ] AKS cluster configuration
- [ ] Azure Cache for Redis (production)
- [ ] Azure Database for PostgreSQL (production)
- [ ] Azure Blob Storage for checkpointing
- [ ] Application Insights
- [ ] Managed identities

### Terraform Structure

```
terraform/
├── environments/
│   ├── dev/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── terraform.tfvars
│   ├── staging/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── terraform.tfvars
│   └── prod/
│       ├── main.tf
│       ├── variables.tf
│       └── terraform.tfvars
├── modules/
│   ├── networking/
│   ├── k8s-cluster/
│   ├── redis/
│   ├── postgres/
│   ├── storage/
│   └── monitoring/
└── README.md
```

## 4. CI/CD Pipelines

### GitHub Actions Workflows

**Build & Test** (`.github/workflows/ci.yml`)
```yaml
on:
  pull_request:
    branches: [main, develop]
  
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: pytest tests/
      - name: Lint code
        run: ruff check .
      - name: Type check
        run: mypy .
```

**Deploy to Dev** (`.github/workflows/deploy-dev.yml`)
```yaml
on:
  push:
    branches: [develop]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build images
        run: docker build -t agentic-system:dev .
      - name: Push to registry
        run: docker push registry.example.com/agentic-system:dev
      - name: Deploy to dev
        run: helm upgrade --install agentic-system charts/agentic-system -f values-dev.yaml
```

**Deploy to Production** (`.github/workflows/deploy-prod.yml`)
```yaml
on:
  release:
    types: [published]

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v3
      - name: Build images
        run: docker build -t agentic-system:${{ github.ref_name }} .
      - name: Security scan
        run: trivy image agentic-system:${{ github.ref_name }}
      - name: Push to registry
        run: docker push registry.example.com/agentic-system:${{ github.ref_name }}
      - name: Deploy to production
        run: |
          helm upgrade --install agentic-system charts/agentic-system \
            -f values-prod.yaml \
            --set image.tag=${{ github.ref_name }}
```

## 5. Monitoring & Observability

### Prometheus Metrics

**Custom Metrics** (`monitoring/prometheus/`)
- [ ] `tier1_tasks_total` - Manager task counter
- [ ] `tier2_orchestrator_duration_seconds` - Orchestrator latency
- [ ] `tier3_agent_queue_depth` - Agent queue sizes
- [ ] `redis_stream_lag` - Stream consumer lag
- [ ] `postgres_connection_pool_usage` - DB connection utilization

### Grafana Dashboards

**Dashboards** (`monitoring/grafana/`)
- [ ] `system-overview.json` - High-level health metrics
- [ ] `tier1-manager.json` - Manager-specific metrics
- [ ] `tier2-orchestrators.json` - Orchestrator performance
- [ ] `tier3-agents.json` - Agent throughput and latency
- [ ] `redis-streams.json` - Stream health and lag
- [ ] `postgres-performance.json` - Database query performance

### Alerts

**AlertManager Rules** (`monitoring/alerts/`)
- [ ] High error rates (>5% failure)
- [ ] High latency (p95 > 5s)
- [ ] Queue depth overflow (>1000 pending)
- [ ] Resource exhaustion (CPU >90%, Memory >85%)
- [ ] Database connection pool saturation

## 6. Auto-Scaling Configuration

### Horizontal Pod Autoscalers (HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: tier2-leads-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: tier2-leads
  minReplicas: 3
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
    - type: Pods
      pods:
        metric:
          name: redis_stream_lag
        target:
          type: AverageValue
          averageValue: "100"
```

### Vertical Pod Autoscalers (VPA)

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: tier3-rag-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: tier3-rag
  updatePolicy:
    updateMode: "Auto"
```

## 7. Multi-Environment Strategy

### Environment Isolation

**Development**
- Single namespace: `agentic-dev`
- Standalone Redis/PostgreSQL
- Minimal replicas (1-2)
- Relaxed resource limits

**Staging**
- Single namespace: `agentic-staging`
- Managed Redis/PostgreSQL (dev tier)
- Medium replicas (2-3)
- Production-like configuration

**Production**
- Namespace per tenant: `agentic-{tenant_id}`
- Fully managed services
- Auto-scaling enabled (3-20 replicas)
- Strict resource limits and quotas

## 8. Backup & Disaster Recovery

### Backup Strategy

- [ ] Redis AOF persistence + daily snapshots to S3/Blob
- [ ] PostgreSQL automated backups (7-day retention)
- [ ] Workflow state snapshots (hourly to object storage)
- [ ] Configuration backups (Git + encrypted secrets)

### Disaster Recovery

- [ ] Multi-region deployment (active-passive)
- [ ] Database replication (read replicas)
- [ ] Redis cluster mode (multi-AZ)
- [ ] Automated failover procedures
- [ ] RTO: 15 minutes, RPO: 1 hour

## 9. Security Considerations

- [ ] Network policies (deny all by default)
- [ ] Pod security policies/standards
- [ ] Secrets encryption at rest (KMS)
- [ ] RBAC for service accounts
- [ ] Image vulnerability scanning
- [ ] TLS for inter-service communication
- [ ] API authentication (JWT, OAuth2)

## 10. Cost Optimization

- [ ] Spot instances for non-critical workloads
- [ ] Cluster autoscaler (scale down during off-hours)
- [ ] Resource quotas per namespace
- [ ] Reserved instances for baseline capacity
- [ ] S3/Blob lifecycle policies (archive old logs)

## Implementation Priority

### Phase 1 (MVP - 2 weeks)
1. Basic Kubernetes manifests (deployments, services)
2. Single environment (dev)
3. Local Redis/PostgreSQL
4. Manual deployment

### Phase 2 (Production-Ready - 4 weeks)
5. Helm charts with multi-environment support
6. Terraform for managed services
7. CI/CD pipelines
8. Basic monitoring (Prometheus + Grafana)

### Phase 3 (Enterprise - 6 weeks)
9. Auto-scaling (HPA + VPA)
10. Multi-region deployment
11. Advanced monitoring (custom metrics, alerts)
12. Backup & disaster recovery

## Resources

- Kubernetes Docs: https://kubernetes.io/docs/
- Helm Docs: https://helm.sh/docs/
- Terraform AWS Provider: https://registry.terraform.io/providers/hashicorp/aws/latest/docs
- Terraform Azure Provider: https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs
- Prometheus Operator: https://prometheus-operator.dev/
- Grafana Dashboards: https://grafana.com/grafana/dashboards/
