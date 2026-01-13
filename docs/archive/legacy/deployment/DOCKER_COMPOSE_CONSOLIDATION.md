# Docker Compose File Organization

> **Status:** Needs Consolidation  
> **Current State:** Partial duplication between root and deployment/  
> **Recommendation:** Keep root compose files, deprecate deployment/docker-compose.yml

## Current Structure

### Root Directory (Primary)

| File                            | Purpose                       | Lines |
| ------------------------------- | ----------------------------- | ----- |
| `docker-compose.yml`            | Base development stack        | 365   |
| `docker-compose.override.yml`   | Local dev overrides (minimal) | 7     |
| `docker-compose.aws.yml`        | AWS Secrets Manager overlay   | 59    |
| `docker-compose.azure.yml`      | Azure Key Vault overlay       | 53    |
| `docker-compose.monitoring.yml` | Observability stack           | 126   |

### Deployment Directory (Secondary)

| File                                          | Purpose                          | Lines |
| --------------------------------------------- | -------------------------------- | ----- |
| `deployment/docker-compose.yml`               | Three-tier stack (updated paths) | 443   |
| `deployment/docker-compose.observability.yml` | Grafana/Loki/Prometheus          | ~200  |

## Duplication Analysis

### Overlapping Services

Both root and deployment versions define:

- Redis service (identical config)
- PostgreSQL service (identical config)
- Worker services (different paths)

### Key Differences

| Aspect            | Root Version                   | Deployment Version           |
| ----------------- | ------------------------------ | ---------------------------- |
| **Service paths** | Uses older `agent/` paths      | Uses new `tiers/` structure  |
| **Profiles**      | Has `local` profile for Redis  | No profiles                  |
| **Annotations**   | Heavily commented for learning | Less commented               |
| **Completeness**  | Missing some tier_3 agents     | More complete agent coverage |

## Recommended Consolidation

### Option A: Migrate Root to Use Deployment (Recommended)

1. Move `deployment/docker-compose.yml` content to root `docker-compose.yml`
2. Update all overlay files to match new service names
3. Keep `deployment/` for Kubernetes configs only
4. Delete `deployment/docker-compose.yml`

### Option B: Keep Both, Document Purpose

- Root: Development with older structure
- Deployment: Production-ready with new structure

## Proposed Structure After Consolidation

```
agentic-system/
├── docker-compose.yml              # Primary (merged from deployment/)
├── docker-compose.override.yml     # Local dev overrides
├── docker-compose.aws.yml          # AWS secrets overlay
├── docker-compose.azure.yml        # Azure secrets overlay
├── docker-compose.monitoring.yml   # Observability stack
├── deployment/
│   ├── docker/                     # Dockerfiles
│   ├── k8s/                        # Kubernetes manifests (move from root k8s/)
│   └── README.md                   # Deployment documentation
```

## Action Items

1. [ ] Merge `deployment/docker-compose.yml` improvements into root version
2. [ ] Update service paths from `agent/` to `tiers/`
3. [ ] Verify all overlay files work with updated base
4. [ ] Remove redundant `deployment/docker-compose.yml`
5. [ ] Move `k8s/` into `deployment/k8s/`

---

_Last Updated: January 2026_
