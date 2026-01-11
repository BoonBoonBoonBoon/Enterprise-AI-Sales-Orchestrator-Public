# Docker & Compose Setup

This document explains how to containerize and run the system locally with Docker and Docker Compose.

## Overview
We provide a multi-stage `Dockerfile` for building a worker image plus a `docker-compose.yml` that launches:
- `redis`: Redis Streams backend (ephemeral; no persistence for dev)
- `worker`: Consumer process that reads jobs (topic: `orchestrate`)
- (optional) `ingest_cli`: One-off container to enqueue a test ingestion event

Supabase + OpenAI credentials are injected via your local `.env` file at runtime (never baked into the image).

## Files Added
- `Dockerfile` – Builds a slim Python image with dependencies and worker entrypoint.
- `docker-compose.yml` – Orchestrates Redis + worker(s) + optional CLI tool.
- `README_DOCKER.md` – This guide.

## Prerequisites
1. Docker installed (Docker Desktop on macOS/Windows).
2. A `.env` file at repo root containing:
```
SUPABASE_URL=...
SUPABASE_KEY=...
OPENAI_API_KEY=...
```
(Do NOT include service role keys in public repos; rotate if exposed.)

## Build & Run (Quick Start)
```
# Build images and start services
docker compose --env-file .env up --build

# Tail logs
docker compose logs -f worker
```

## Scaling Workers
Horizontal scaling is just additional worker containers pointing at the same Redis stream:
```
docker compose up --build --scale worker=3
```
Each replica should use a unique consumer name; Compose will auto-suffix container names but we currently set `REDIS_CONSUMER=worker-1`. For multiple replicas, override with an environment variable patch or update the compose file to use container hostname as consumer.

### Option: Dynamic Consumer Name
You can modify `docker-compose.yml`:
```
    environment:
      REDIS_CONSUMER: ${HOSTNAME}
```
Or enhance `start_worker.py` to generate one if not provided.

## Running the Ingestion CLI
The optional `ingest_cli` service is behind a profile to avoid auto-start:
```
# Run a single ingestion event through application path
docker compose run --rm ingest_cli
```
This enqueues a job consumed by the `worker`.

## Health & Diagnostics
- Redis container has a healthcheck (PING)
- Worker image has a Docker `HEALTHCHECK` that pings Redis if `REDIS_URL` is set.
- Use existing scripts inside a running worker container:
```
# Open a shell in the worker
docker compose exec worker bash
python scripts/redis_health.py
```

## Development Flow
1. Edit code locally.
2. Rebuild image: `docker compose build worker`
3. Restart service: `docker compose up -d --no-deps worker`

For faster inner loops you can mount source instead of COPY (optional dev override):
```
  worker:
    volumes:
      - ./:/app
```
(Be aware this bypasses the Docker build layer caching.)

## Production Hardening (Next Steps)
- Use a production-grade Redis (TLS, persistence, auth enforced) – update `REDIS_URL=rediss://...`.
- Multi-stage: add a builder stage if compiling native deps later.
- Slim final image further by dropping build-essential after wheel installs.
- Add structured logging + metrics endpoint.
- Introduce a small API container (FastAPI) for ingestion HTTP interface.
- Parameterize topic / stream naming via env (already partially supported).
- Add DLQ consumer & exponential backoff (planned in codebase but not implemented yet).

## Security Notes
- Rotate any keys already committed.
- Never bake secrets into images; rely on env injection (Compose, orchestrator secrets, etc.).
- For production enable a non-root user (already set to `worker`).
- Consider image signing (cosign) and vulnerability scanning (Trivy, Grype) in CI.

## Cleanup
```
# Stop and remove containers
docker compose down

# Remove volumes (none defined yet) and images
docker image rm agentic/worker:dev
```

## Troubleshooting
| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Worker exits immediately | Missing Redis or bad URL | Check `REDIS_URL` env, ensure redis healthy |
| Jobs not consumed | Consumer group mismatch | Ensure topic matches produced messages (default orchestrate) |
| Redis WRONG_VERSION_NUMBER | Using rediss scheme with non-TLS port | Switch to redis:// or point to TLS port |
| Ingestion 4xx from Supabase | Missing required columns | Compare payload against required NOT NULL list |

## Future Enhancements
- Separate Dockerfile stages for test vs prod.
- Multi-arch builds (linux/amd64 + arm64) via buildx.
- Compose override file for local dev volume mounts.
- Add a Makefile or task runner for common docker commands.

---
Feel free to iterate further; this is a baseline to get containers running quickly.
