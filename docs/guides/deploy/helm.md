# Helm Chart

This guide covers using the Helm chart to deploy the Agentic System.

## What is Helm?

Helm is a **package manager for Kubernetes**. Instead of applying dozens of YAML files individually, Helm bundles them into a **chart** that can be installed with a single command.

Benefits:

- **Parameterization**: Override values per environment without editing YAML
- **Versioning**: Track chart versions and rollback easily
- **Dependencies**: Manage related charts together
- **Templating**: Generate manifests dynamically from values

## Chart Location

The Agentic System Helm chart is at:

```
charts/agentic-system/
├── Chart.yaml              # Chart metadata (name, version)
├── values.yaml             # Default configuration values
└── templates/              # Kubernetes manifest templates
    ├── _helpers.tpl        # Template helper functions
    ├── namespace.yaml
    ├── configmap.yaml
    ├── secrets-aws.yaml
    ├── secrets-azure.yaml
    ├── deployments-workers.yaml
    ├── deployment-api-gateway.yaml
    ├── deployment-portal.yaml
    ├── deployment-health-server.yaml
    ├── services.yaml
    ├── ingress.yaml
    └── hpa.yaml
```

## values.yaml Reference

### Images

```yaml
images:
  worker: agentic/worker:latest # Worker/agent image
  apiGateway: agentic/api-gateway:latest # FastAPI gateway image
  portal: agentic/portal:latest # Next.js portal image
```

### Application Config

```yaml
config:
  # Tenant and environment
  TENANT_ID: "agentic-prod"
  DEBUG: "0"
  DEV_LOGIN_ENABLED: "0"

  # Redis
  REDIS_NAMESPACE: "agentic-prod"
  REDIS_STREAM_MAXLEN: "20000"
  ENABLE_DLQ: "1"

  # API Gateway
  HOST: "0.0.0.0"
  PORT: "8000"
  CORS_ORIGINS: "https://app.example.com"
  RATE_LIMIT_REQUESTS: "100"
  RATE_LIMIT_WINDOW_SECONDS: "60"

  # Portal (Next.js public vars)
  NEXT_PUBLIC_SUPABASE_URL: "https://your-project.supabase.co"
  NEXT_PUBLIC_SUPABASE_ANON_KEY: "REPLACE_ME"
  NEXT_PUBLIC_API_URL: "https://app.example.com/api"

  # LLM
  LLM_PROVIDER: "openai"
  ENABLE_LEAD_CONTEXT_ENRICHMENT: "1"
```

### Secrets Provider

```yaml
secrets:
  provider: aws # aws | azure

  aws:
    region: us-east-1
    secretName: agentic-system/prod

  azure:
    keyVaultName: agentic-system-prod
    tenantId: ""
    clientId: ""
```

### Workers

```yaml
workers:
  - name: manager
    command: ["python", "-m", "tiers.tier_1.manager.consumer"]
    replicas: 1
    resources:
      requests:
        cpu: "250m"
        memory: "512Mi"
      limits:
        cpu: "1000m"
        memory: "1Gi"

  - name: rag-agent
    command: ["python", "-m", "tiers.tier_3.rag_agent.consumer"]
    replicas: 2 # Scale for throughput
    resources:
      requests:
        cpu: "500m"
        memory: "1Gi"
```

### Ingress

```yaml
ingress:
  enabled: true
  host: app.example.com
  tlsSecretName: agentic-tls
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
```

### Autoscaling (HPA)

```yaml
hpa:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
```

## Installation

### Prerequisites

1. Kubernetes cluster (EKS, AKS, GKE, or local)
2. Helm 3.x installed
3. kubectl configured for your cluster
4. Container registry with built images

### Install Chart

```bash
# Basic install
helm install agentic charts/agentic-system \
  --namespace agentic-system \
  --create-namespace

# With custom values file
helm install agentic charts/agentic-system \
  --namespace agentic-system \
  --create-namespace \
  -f values-prod.yaml

# With inline overrides
helm install agentic charts/agentic-system \
  --namespace agentic-system \
  --create-namespace \
  --set config.TENANT_ID="my-tenant" \
  --set images.worker="my-registry/worker:v1.0.0"
```

### Upgrade Chart

```bash
# Upgrade with new values
helm upgrade agentic charts/agentic-system \
  --namespace agentic-system \
  --set images.worker="my-registry/worker:v1.1.0"

# Upgrade with --install (create if doesn't exist)
helm upgrade --install agentic charts/agentic-system \
  --namespace agentic-system \
  --create-namespace
```

### Rollback

```bash
# List revisions
helm history agentic -n agentic-system

# Rollback to previous
helm rollback agentic -n agentic-system

# Rollback to specific revision
helm rollback agentic 2 -n agentic-system
```

### Uninstall

```bash
helm uninstall agentic -n agentic-system
```

## Environment-Specific Values

Create separate values files per environment:

### values-staging.yaml

```yaml
config:
  TENANT_ID: "agentic-staging"
  DEBUG: "1"
  DEV_LOGIN_ENABLED: "1"
  CORS_ORIGINS: "https://staging.example.com"
  NEXT_PUBLIC_API_URL: "https://staging.example.com/api"

secrets:
  aws:
    secretName: agentic-system/staging

ingress:
  host: staging.example.com
```

### values-prod.yaml

```yaml
config:
  TENANT_ID: "agentic-prod"
  DEBUG: "0"
  DEV_LOGIN_ENABLED: "0"
  CORS_ORIGINS: "https://app.example.com"
  NEXT_PUBLIC_API_URL: "https://app.example.com/api"

secrets:
  aws:
    secretName: agentic-system/prod

ingress:
  host: app.example.com

workers:
  - name: rag-agent
    replicas: 5 # Higher for production

hpa:
  minReplicas: 3
  maxReplicas: 20
```

## CI/CD Integration

The GitLab CI pipeline uses Helm for deployment:

```yaml
# .gitlab-ci.yml (excerpt)
deploy:
  stage: deploy
  image: alpine/helm:3.14.0
  script:
    - helm upgrade --install agentic charts/agentic-system \
      --namespace agentic-system \
      --create-namespace \
      --set images.worker="${CI_REGISTRY_IMAGE}/worker:${IMAGE_TAG}" \
      --set images.apiGateway="${CI_REGISTRY_IMAGE}/api-gateway:${IMAGE_TAG}" \
      --set images.portal="${CI_REGISTRY_IMAGE}/portal:${IMAGE_TAG}" \
      --wait \
      --timeout 10m
```

See [CI/CD Guide](ci-cd.md) for the full pipeline.

## Debugging

### Dry Run

Preview what would be applied without actually installing:

```bash
helm install agentic charts/agentic-system \
  --namespace agentic-system \
  --dry-run \
  --debug
```

### Template Only

Generate the rendered YAML without installing:

```bash
helm template agentic charts/agentic-system > rendered.yaml
```

### Get Values

Show current values for an installed release:

```bash
helm get values agentic -n agentic-system
```

### Show Manifests

Show the actual manifests installed:

```bash
helm get manifest agentic -n agentic-system
```

## Related

- [Kubernetes Guide](kubernetes.md) - Full K8s deployment
- [CI/CD Guide](ci-cd.md) - Pipeline integration
- [Secrets Guide](secrets.md) - Secrets management
