# CI/CD

This guide covers continuous integration and deployment for the Agentic System.

## Pipeline Overview

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  Push   │───▶│  Test   │───▶│  Build  │───▶│ Deploy  │
│         │    │         │    │         │    │         │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
                   │              │              │
                   ▼              ▼              ▼
              Unit Tests     Docker Image    Kubernetes
              Integration    Push to          Apply
              Lint/Type      Registry        Manifests
```

## GitHub Actions

### Test Workflow

```yaml
# .github/workflows/test.yml
name: Test

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: "pip"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Lint
        run: |
          ruff check .
          mypy .

      - name: Test
        env:
          REDIS_URL: redis://localhost:6379/0
          TENANT_ID: test
        run: |
          pytest tests/ -v --cov=. --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: ./coverage.xml
```

### Build Workflow

```yaml
# .github/workflows/build.yml
name: Build

on:
  push:
    branches: [main]
    tags: ["v*"]

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          file: deployment/docker/Dockerfile.agent
          push: true
          tags: |
            ghcr.io/${{ github.repository }}:${{ github.sha }}
            ghcr.io/${{ github.repository }}:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### Deploy Workflow

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    tags: ["v*"]

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production

    steps:
      - uses: actions/checkout@v4

      - name: Set up kubectl
        uses: azure/setup-kubectl@v3

      - name: Configure kubeconfig
        run: |
          echo "${{ secrets.KUBECONFIG }}" | base64 -d > kubeconfig
          export KUBECONFIG=kubeconfig

      - name: Update image tag
        run: |
          cd k8s/overlays/production
          kustomize edit set image ghcr.io/${{ github.repository }}:${{ github.ref_name }}

      - name: Deploy
        run: |
          kubectl apply -k k8s/overlays/production

      - name: Verify deployment
        run: |
          kubectl rollout status deployment/rag-agent -n agentic --timeout=300s
```

## Branch Strategy

```
main          ─────●─────●─────●─────●─────▶ Production
                   │     │
                   │     └── v1.2.0 (tag → deploy)
                   │
develop       ─────●─────●─────●─────●─────▶ Staging
                   │     │     │
                   │     │     └── feature-c
                   │     └── feature-b
                   └── feature-a
```

| Branch      | Environment | Deploy Trigger |
| ----------- | ----------- | -------------- |
| `main`      | Production  | Tag (`v*`)     |
| `develop`   | Staging     | Push           |
| `feature/*` | —           | PR tests only  |

## Secrets

### Required Secrets

| Secret                | Description              |
| --------------------- | ------------------------ |
| `SUPABASE_URL`        | Database URL             |
| `SUPABASE_ANON_KEY`   | API key                  |
| `SUPABASE_JWT_SECRET` | JWT secret               |
| `OPENAI_API_KEY`      | LLM API key              |
| `KUBECONFIG`          | K8s credentials (base64) |

### Setting Secrets

```bash
# GitHub CLI
gh secret set SUPABASE_URL --body "https://..."
gh secret set OPENAI_API_KEY --body "sk-..."

# Or use GitHub UI: Settings → Secrets → Actions
```

## Pre-commit Hooks

### .pre-commit-config.yaml

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic]

  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest tests/unit/ -x
        language: system
        pass_filenames: false
```

### Install

```bash
pip install pre-commit
pre-commit install
```

## Release Process

### Semantic Versioning

```
v1.2.3
│ │ │
│ │ └── Patch: Bug fixes
│ └──── Minor: New features (backward compatible)
└────── Major: Breaking changes
```

### Creating a Release

```bash
# 1. Update version
# Edit pyproject.toml or __version__

# 2. Update changelog
# Edit docs/roadmap/changelog.md

# 3. Commit
git add .
git commit -m "Release v1.2.0"

# 4. Tag
git tag v1.2.0

# 5. Push
git push origin main --tags
# → Triggers build and deploy workflows
```

## Environment Promotion

```
1. Developer pushes to feature branch
   └── Tests run on PR

2. PR merged to develop
   └── Deploy to staging

3. Testing verified in staging
   └── Create release PR to main

4. Release PR merged
   └── Tag created (v1.2.0)

5. Tag pushed
   └── Deploy to production
```

## Related

- [Docker Deployment](docker.md)
- [Kubernetes Deployment](kubernetes.md)
- [Secrets Management](secrets.md)
