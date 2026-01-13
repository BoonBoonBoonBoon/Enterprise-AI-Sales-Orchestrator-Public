# Deployment Guides

Guides for deploying the Agentic System to various environments.

## Deployment Options

<div class="grid cards" markdown>

- :material-docker:{ .lg .middle } **Docker Compose**

  ***

  Local development and simple production deployments.

  [:octicons-arrow-right-24: Docker Guide](docker.md)

- :material-kubernetes:{ .lg .middle } **Kubernetes**

  ***

  Scalable production deployments with K8s.

  [:octicons-arrow-right-24: Kubernetes Guide](kubernetes.md)

- :material-pipe:{ .lg .middle } **CI/CD**

  ***

  Automated testing and deployment pipelines.

  [:octicons-arrow-right-24: CI/CD Guide](ci-cd.md)

- :material-key:{ .lg .middle } **Secrets**

  ***

  Secure secrets management across environments.

  [:octicons-arrow-right-24: Secrets Guide](secrets.md)

</div>

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Production Setup                          │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   GitHub     │───▶│   CI/CD      │───▶│  Container   │  │
│  │   (source)   │    │  (build)     │    │  Registry    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                   │          │
│                                                   ▼          │
│                              ┌────────────────────────────┐ │
│                              │       Kubernetes           │ │
│                              │                            │ │
│                              │  ┌────────┐ ┌────────┐    │ │
│                              │  │ Agent  │ │ Agent  │    │ │
│                              │  │  Pod   │ │  Pod   │    │ │
│                              │  └────────┘ └────────┘    │ │
│                              │                            │ │
│                              │  ┌────────────────────┐   │ │
│                              │  │       Redis        │   │ │
│                              │  └────────────────────┘   │ │
│                              │                            │ │
│                              └────────────────────────────┘ │
│                                          │                  │
│                                          ▼                  │
│                              ┌────────────────────┐        │
│                              │     Supabase       │        │
│                              │   (PostgreSQL)     │        │
│                              └────────────────────┘        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Environment Comparison

| Aspect           | Docker Compose  | Kubernetes  |
| ---------------- | --------------- | ----------- |
| **Complexity**   | Low             | High        |
| **Scalability**  | Limited         | Excellent   |
| **Best For**     | Dev, small prod | Large prod  |
| **Cost**         | Low             | Higher      |
| **Ops Overhead** | Minimal         | Significant |

## Quick Start

### Local Development

```powershell
# Start all services
docker-compose up -d
```

### Production (K8s)

```bash
# Apply manifests
kubectl apply -k k8s/overlays/production
```

## Prerequisites

- Docker 24.0+
- Docker Compose 2.0+
- Kubernetes 1.25+ (for K8s deployment)
- kubectl configured
- Access to container registry

## Next Steps

1. [Set up Docker locally](docker.md)
2. [Configure secrets](secrets.md)
3. [Set up CI/CD](ci-cd.md)
4. [Deploy to Kubernetes](kubernetes.md)
