To have this **in production** (website accessible publicly + backend agents running 24/7 remotely), you typically need to set up **hosting + managed services + deployment + security + monitoring**.

## What you need (software/services)

### 1) Public web + API (internet-facing)

- **Portal (Next.js)**: host on **Vercel** _or_ as a container on a VM/K8s
  - Uses: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL`
- **API Gateway** (your backend HTTP API; looks like gateway in repo):
  - Host as a container/service (VM/K8s)
  - Put behind **HTTPS reverse proxy**: **Caddy / Nginx / Traefik**
- **Domain + DNS** (Cloudflare/Route53/etc.) + **TLS certs** (Let’s Encrypt via proxy)

### 2) Private always-on workers (not internet-facing)

These must run continuously so “AI works in the backend” even when nobody is logged in:

- Tier 1 **Manager** consumer
- Tier 2 **Orchestrator** consumers
- Tier 3 **Agent** consumers (RAG, Persistence, Copywriter)
- They connect to **Redis Streams** + **Supabase** and should live on a VM/K8s, _not exposed to the public internet_.

### 3) Backing services (managed)

- **Supabase** (already your Postgres + RLS auth layer)
- **Redis** (use Redis Cloud or managed Redis with **TLS**: `rediss://...`)

### 4) Secrets + config (required for real production)

- A **secrets manager** (recommended): AWS SSM/Secrets Manager, Azure Key Vault, Doppler, 1Password Secrets, etc.
- At minimum: env vars injected at deploy time (never commit .env)

**Important:** your current .env includes live secrets (OpenAI keys, Supabase service key, Redis password, Gmail app password). Before production:

- **Rotate/revoke** all exposed keys
- Set `DEBUG=0`, `DEV_LOGIN_ENABLED=0`
- Ensure **service-role keys never reach the browser** (only `NEXT_PUBLIC_*` in the portal)

### 5) Observability + operations

- Central logs (Grafana/Loki, ELK, or cloud logging)
- Metrics + alerts (Prometheus/Grafana or cloud monitoring)
- Health checks / uptime monitoring  
  (repo references: OBSERVABILITY.md, DEV_OBSERVABILITY_GUIDE.md, `scripts/health_server.py`)

---

## Common deployment options (pick one)

### Option A (simplest): Vercel + one “backend VM” + managed Redis/Supabase

- **Vercel**: deploy portal
- **VM (Ubuntu/Windows Server)**: run API gateway + all consumers via Docker Compose
- **Redis Cloud + Supabase**: managed

### Option B: Single VM with Docker Compose (everything except Supabase/Redis)

- Reverse proxy + portal + api + workers as containers
- Uses repo docker-compose.yml (and cloud overlays like docker-compose.aws.yml / docker-compose.azure.yml if applicable)

### Option C: Kubernetes (most robust, most setup)

- Use k8s manifests
- Best for scaling/HA, more ops overhead

---

## Minimal “go-live” checklist

1. **Choose hosting** (Vercel + VM is the fastest).
2. **Set domain + HTTPS** (reverse proxy).
3. **Move secrets into a secrets manager**; rotate current keys.
4. **Deploy API gateway** and lock it down (CORS, auth, rate limits).
5. **Deploy workers** (manager/orchestrators/agents) as always-on services.
6. **Verify end-to-end** with repo smoke tests (`scripts/smoke_test_three_tier.py`, Supabase verify scripts).
7. **Add monitoring + alerts** so you know when Redis/Supabase/agents fail.

---

## Kubernetes-first production runbook (recommended)

### 0) Choose the managed services

- **Kubernetes**: EKS (AWS) or AKS (Azure).
- **Container registry**: ECR/ACR/GHCR.
- **Datastores**: Supabase (Postgres + Auth + RLS) and Redis Cloud (TLS `rediss://`).

### 1) Provision the cluster and ingress

- Create the cluster (EKS/AKS).
- Install **ingress-nginx** (or Traefik) and **cert-manager** for HTTPS.
- Optional: **external-dns** to auto-manage DNS records.

### 2) Use the repo’s secrets integration

This repo already includes CSI-based secrets for both Azure Key Vault and AWS Secrets Manager.

- Start here: [k8s/README.md](k8s/README.md)
- Base namespace/config: [k8s/base/namespace.yaml](k8s/base/namespace.yaml), [k8s/base/configmap.yaml](k8s/base/configmap.yaml)
- AWS secrets: [k8s/aws-secrets-manager/secret-provider-class.yaml](k8s/aws-secrets-manager/secret-provider-class.yaml)
- Azure secrets: [k8s/azure-keyvault/secret-provider-class.yaml](k8s/azure-keyvault/secret-provider-class.yaml)

**Production security defaults:**

- Set `DEBUG=0`, `DEV_LOGIN_ENABLED=0`.
- Never ship service-role keys to the browser (only `NEXT_PUBLIC_*` in the portal).

### 3) Build and push container images

- Worker image source: [deployment/docker/Dockerfile.worker](deployment/docker/Dockerfile.worker)
- Commands per service already exist in compose: [deployment/docker-compose.yml](deployment/docker-compose.yml)

You will publish images for:

- **Workers**: manager, leads_orchestrator, outreach_orchestrator, rag_agent, persistence_agent, copywriter_agent (plus any optional agents you use).
- **API Gateway**: if you run the API separately (see repo under api/).
- **Portal**: if you host the Next.js portal in K8s.

### 4) Deploy workloads into K8s

The current K8s YAMLs only deploy a sample worker, so you will add Deployments for each consumer (manager/orchestrators/agents) with the correct `command` from compose.

**Workers (private, 24/7):**

- Deployments for the Tier 1/2/3 consumers from [deployment/docker-compose.yml](deployment/docker-compose.yml).
- Use multiple replicas for agents that need throughput (RAG/Copywriter/Persistence).

**Public-facing:**

- **Portal** (Next.js) + **API Gateway** behind Ingress/HTTPS.
- Only expose HTTP services publicly; keep workers private.

### 5) Observability and health checks

- Use the repo’s stack or cloud monitoring.
- References: [deployment/OBSERVABILITY.md](deployment/OBSERVABILITY.md), [deployment/DEV_OBSERVABILITY_GUIDE.md](deployment/DEV_OBSERVABILITY_GUIDE.md).

### 6) Tenant isolation strategy (alpha → SaaS)

**Alpha (internal per-client login):**

- Safest: one client per environment config (separate Supabase project and Redis namespace).
- This isolates data even if RLS is misconfigured.

**Public SaaS:**

- Single Supabase project + strict RLS + `tenant_id` everywhere.
- Your services stay stateless; K8s redeploys won’t endanger data if migrations are backward-compatible.

---

## Missing pieces you still need to add

1. ✅ **K8s Deployments** for all consumers — now included in [k8s/base/](k8s/base/) and [charts/agentic-system/](charts/agentic-system/).
2. ✅ **API Gateway** and **Portal** Deployments + Services + Ingress — included.
3. ✅ **Autoscaling policies** (HPA) based on CPU — included.

> **📚 Full deployment documentation**: See [Deployment Guides](docs/guides/deploy/index.md) in the mkdocs site.

---

## GitLab setup (CI/CD + registry)

This repo now includes a **test-gated** GitLab pipeline: [.gitlab-ci.yml](.gitlab-ci.yml).

### Pipeline stages

| Stage    | Purpose                                | Gating                       |
| -------- | -------------------------------------- | ---------------------------- |
| `lint`   | Ruff + Mypy static analysis            | Blocks test                  |
| `test`   | Pytest + coverage (with Redis service) | Blocks build                 |
| `build`  | Docker images (worker, api, portal)    | Requires lint + test to pass |
| `deploy` | Helm deployment to K8s                 | Manual trigger after build   |

### Required GitLab CI variables

| Variable              | Description                                         |
| --------------------- | --------------------------------------------------- |
| `CI_REGISTRY_*`       | GitLab built-ins if using GitLab Container Registry |
| `KUBE_CONFIG`         | Base64-encoded kubeconfig for production            |
| `KUBE_CONFIG_STAGING` | Base64-encoded kubeconfig for staging (optional)    |

### Branch protection (enforce test-gating)

1. **Settings → Repository → Protected Branches**
2. Enable **"Pipelines must succeed"** on master/main
3. Broken code cannot be merged

> **📚 Full CI/CD documentation**: See [CI/CD Guide](docs/guides/deploy/ci-cd.md).

---

## Helm chart (what it is + how to use here)

**What is a Helm chart?**

Helm is a package manager for Kubernetes. A **Helm chart** is a parameterized bundle of K8s YAML templates + a `values.yaml` file so you can install/upgrade the whole stack with a single command and override settings per environment.

**Chart added for this repo:** [charts/agentic-system](charts/agentic-system)

### Chart contents

- Namespace + ConfigMap
- Secrets provider class (AWS/Azure CSI)
- Worker deployments (manager/orchestrators/agents)
- API gateway deployment + service
- Portal deployment + service
- Health server deployment + service
- Ingress + HPA

### Configure values

Edit [charts/agentic-system/values.yaml](charts/agentic-system/values.yaml):

- `images.*` (point to your registry)
- `config.*` (domain, CORS, NEXT*PUBLIC*\*, tenant defaults)
- `secrets.provider` (`aws` or `azure`)

### Install or upgrade

```bash
# Install
helm install agentic charts/agentic-system -n agentic-system --create-namespace

# Upgrade
helm upgrade agentic charts/agentic-system -n agentic-system

# With custom values
helm upgrade --install agentic charts/agentic-system \
  --set images.worker="my-registry/worker:v1.0.0" \
  --set config.TENANT_ID="production"
```

> **📚 Full Kubernetes documentation**: See [Kubernetes Guide](docs/guides/deploy/kubernetes.md).

---

## What the GitLab pipeline does

The GitLab pipeline in [.gitlab-ci.yml](.gitlab-ci.yml):

```
Push → Lint (ruff + mypy) → Test (pytest + coverage) → Build (Docker) → Deploy (Helm)
              ↓                     ↓                       ↓
         Code quality          JUnit report              Images pushed
         report                Coverage report           to registry
```

1. **Lint**: Runs `ruff check .` and `mypy .` — produces code quality report.
2. **Test**: Runs `pytest` with Redis service — produces JUnit + coverage reports.
3. **Build**: Builds Docker images for worker, api-gateway, portal (only if tests pass).
4. **Deploy**: Uses `helm upgrade --install` to deploy to K8s (manual trigger).

### Environments

- **Production**: Deploys to `agentic-system` namespace on master branch (manual).
- **Staging**: Deploys to `agentic-staging` namespace on develop branch (automatic).
