# Kubernetes Deployment

This guide covers deploying the Agentic System to Kubernetes.

## Prerequisites

- Kubernetes cluster (1.25+)
- kubectl configured
- Helm 3.x
- Container registry access

## Deployment Options

| Method         | Best For                       | Complexity |
| -------------- | ------------------------------ | ---------- |
| **Helm Chart** | Production, repeatable deploys | Low        |
| **Raw YAML**   | Learning, customization        | Medium     |
| **Kustomize**  | Environment overlays           | Medium     |

!!! tip "Recommended: Use Helm"
The Helm chart at `charts/agentic-system/` is the recommended way to deploy. It includes all components with sensible defaults and easy customization via `values.yaml`.

## Quick Start with Helm

### 1. Configure Values

Edit `charts/agentic-system/values.yaml`:

```yaml
# Image configuration
images:
  worker: your-registry.com/agentic/worker:latest
  apiGateway: your-registry.com/agentic/api-gateway:latest
  portal: your-registry.com/agentic/portal:latest

# Application config
config:
  TENANT_ID: "your-tenant"
  CORS_ORIGINS: "https://your-domain.com"
  NEXT_PUBLIC_SUPABASE_URL: "https://your-project.supabase.co"
  NEXT_PUBLIC_API_URL: "https://your-domain.com/api"

# Secrets provider (aws or azure)
secrets:
  provider: aws
  aws:
    region: us-east-1
    secretName: agentic-system/prod
```

### 2. Install

```bash
# Install the chart
helm install agentic charts/agentic-system \
  --namespace agentic-system \
  --create-namespace

# Or upgrade if already installed
helm upgrade --install agentic charts/agentic-system \
  --namespace agentic-system \
  --create-namespace
```

### 3. Verify

```bash
kubectl get pods -n agentic-system
kubectl get ingress -n agentic-system
```

## Helm Chart Components

The chart deploys:

| Component             | Type       | Purpose                         |
| --------------------- | ---------- | ------------------------------- |
| Manager               | Deployment | Tier 1 - Task routing           |
| Leads Orchestrator    | Deployment | Tier 2 - Lead workflows         |
| Outreach Orchestrator | Deployment | Tier 2 - Outreach workflows     |
| RAG Agent             | Deployment | Tier 3 - Retrieval (replicas:2) |
| Persistence Agent     | Deployment | Tier 3 - CRUD operations        |
| Copywriter Agent      | Deployment | Tier 3 - AI content             |
| Scheduler Agent       | Deployment | Tier 3 - Scheduling             |
| Channel Sequencer     | Deployment | Tier 3 - Message sequencing     |
| API Gateway           | Deployment | HTTP API                        |
| Portal                | Deployment | Next.js frontend                |
| Health Server         | Deployment | Monitoring endpoints            |
| Ingress               | Ingress    | HTTPS routing                   |
| HPA                   | HPA        | Auto-scaling                    |

### Chart File Structure

```
charts/agentic-system/
├── Chart.yaml              # Chart metadata
├── values.yaml             # Default configuration
└── templates/
    ├── _helpers.tpl        # Template helpers
    ├── namespace.yaml
    ├── configmap.yaml
    ├── secrets-aws.yaml    # AWS Secrets Manager CSI
    ├── secrets-azure.yaml  # Azure Key Vault CSI
    ├── deployments-workers.yaml
    ├── deployment-api-gateway.yaml
    ├── deployment-portal.yaml
    ├── deployment-health-server.yaml
    ├── services.yaml
    ├── ingress.yaml
    └── hpa.yaml
```

### Customizing Values

Override values at install time:

```bash
helm install agentic charts/agentic-system \
  --set config.TENANT_ID="production" \
  --set images.worker="my-registry/worker:v1.0.0" \
  --set workers[0].replicas=3
```

Or create a custom values file:

```yaml
# values-prod.yaml
config:
  TENANT_ID: "production"
  DEBUG: "0"

workers:
  - name: rag-agent
    replicas: 5
```

```bash
helm install agentic charts/agentic-system -f values-prod.yaml
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                       │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   Namespace: agentic-system          │   │
│  │                                                      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │   │
│  │  │Deployment│  │Deployment│  │    Deployment    │  │   │
│  │  │ manager  │  │  leads   │  │ rag (replicas:2) │  │   │
│  │  └──────────┘  └──────────┘  └──────────────────┘  │   │
│  │                                                      │   │
│  │  ┌──────────────────────────────────────────────┐  │   │
│  │  │          External: Redis Cloud (TLS)          │  │   │
│  │  └──────────────────────────────────────────────┘  │   │
│  │                                                      │   │
│  │  ┌──────────────────────────────────────────────┐  │   │
│  │  │           ConfigMap / Secrets (CSI)           │  │   │
│  │  └──────────────────────────────────────────────┘  │   │
│  │                                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Raw YAML Deployment (Alternative)

```bash
# Create namespace
kubectl create namespace agentic

# Apply configurations
kubectl apply -k k8s/base/ -n agentic

# Check status
kubectl get pods -n agentic
```

## Manifests

### Namespace

```yaml
# k8s/base/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: agentic
```

### ConfigMap

```yaml
# k8s/base/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: agentic-config
data:
  TENANT_ID: "agentic-dev"
  REDIS_URL: "redis://redis:6379/0"
  LOG_LEVEL: "INFO"
```

### Secrets

```yaml
# k8s/base/secrets.yaml (use sealed-secrets in production)
apiVersion: v1
kind: Secret
metadata:
  name: agentic-secrets
type: Opaque
stringData:
  SUPABASE_URL: "https://your-project.supabase.co"
  SUPABASE_ANON_KEY: "eyJ..."
  SUPABASE_JWT_SECRET: "your-secret"
  OPENAI_API_KEY: "sk-..."
```

### Agent Deployment

```yaml
# k8s/base/rag-agent.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-agent
spec:
  replicas: 3
  selector:
    matchLabels:
      app: rag-agent
  template:
    metadata:
      labels:
        app: rag-agent
    spec:
      containers:
        - name: rag-agent
          image: your-registry/agentic-system:latest
          command: ["python", "-m", "tiers.tier_3.rag_agent.consumer"]
          envFrom:
            - configMapRef:
                name: agentic-config
            - secretRef:
                name: agentic-secrets
          resources:
            requests:
              memory: "256Mi"
              cpu: "100m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          livenessProbe:
            exec:
              command:
                - python
                - -c
                - "print('ok')"
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            exec:
              command:
                - python
                - -c
                - "from services.redis.client import get_redis_client; get_redis_client().ping()"
            initialDelaySeconds: 5
            periodSeconds: 10
```

### Redis StatefulSet

```yaml
# k8s/base/redis.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
spec:
  serviceName: redis
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          ports:
            - containerPort: 6379
          volumeMounts:
            - name: data
              mountPath: /data
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 1Gi
---
apiVersion: v1
kind: Service
metadata:
  name: redis
spec:
  ports:
    - port: 6379
  selector:
    app: redis
```

## Kustomize

### kustomization.yaml

```yaml
# k8s/base/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: agentic

resources:
  - namespace.yaml
  - configmap.yaml
  - secrets.yaml
  - redis.yaml
  - rag-agent.yaml
  - persistence-agent.yaml
  - copywriter-agent.yaml
  - leads-orchestrator.yaml
  - manager.yaml
```

### Environment Overlays

```yaml
# k8s/overlays/production/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

bases:
  - ../../base

patches:
  - patch: |-
      - op: replace
        path: /spec/replicas
        value: 5
    target:
      kind: Deployment
      name: rag-agent

configMapGenerator:
  - name: agentic-config
    behavior: merge
    literals:
      - LOG_LEVEL=WARNING
```

## Scaling

### Horizontal Pod Autoscaler

```yaml
# k8s/base/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: rag-agent-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: rag-agent
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

### Manual Scaling

```bash
kubectl scale deployment rag-agent --replicas=5 -n agentic
```

## Operations

### Check Status

```bash
# Pods
kubectl get pods -n agentic

# Logs
kubectl logs -f deployment/rag-agent -n agentic

# Describe
kubectl describe deployment rag-agent -n agentic
```

### Rolling Update

```bash
# Update image
kubectl set image deployment/rag-agent \
  rag-agent=your-registry/agentic-system:v1.2.0 \
  -n agentic

# Check rollout
kubectl rollout status deployment/rag-agent -n agentic
```

### Rollback

```bash
kubectl rollout undo deployment/rag-agent -n agentic
```

## Secrets Management

### AWS Secrets Manager

```yaml
# k8s/aws-secrets-manager/secret-store.yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
```

### Azure Key Vault

```yaml
# k8s/azure-keyvault/secret-store.yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: azure-secrets
spec:
  provider:
    azurekv:
      vaultUrl: "https://your-vault.vault.azure.net"
```

## Related

- [Docker Deployment](docker.md)
- [Secrets Management](secrets.md)
- [CI/CD](ci-cd.md)
