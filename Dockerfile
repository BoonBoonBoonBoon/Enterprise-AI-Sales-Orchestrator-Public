# syntax=docker/dockerfile:1.7
# Multi-stage build for lean runtime image

ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

# Install system deps (add build-essential if native libs required later)
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Separate layer for requirements to leverage caching
COPY requirements.txt requirements-dev.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install -r requirements-dev.txt

# Copy application source
COPY agent ./agent
COPY config ./config
COPY platform_monitoring ./platform_monitoring
COPY scripts ./scripts
COPY run_agent.py ./
COPY README.md ./
# DEVELOPER_README.md may not exist in all contexts; COPY will fail if missing.
# If it's important, ensure it's present. For now we omit to keep build resilient.

# Non-root user (optional; comment out if needing root for debugging)
RUN useradd -m worker && chown -R worker:worker /app
USER worker

# Environment defaults (override via docker run / compose)
ENV QUEUE_BACKEND=redis \
    WORKER_TOPIC=orchestrate \
    REDIS_CONSUMER=worker-1

# Expose no ports (worker is a background consumer). Add if HTTP added later.
# EXPOSE 8000

# Healthcheck (lightweight Redis ping if REDIS_URL present)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD [ "/bin/sh", "-c", "if [ -n \"$REDIS_URL\" ]; then python - <<'PY' || exit 1\nimport os, sys\nurl=os.environ.get('REDIS_URL')\nif not url: sys.exit(0)\ntry:\n import redis\n r=redis.from_url(url)\n r.ping()\nexcept Exception as e:\n print('healthcheck redis ping failed', e)\n sys.exit(1)\nPY\n; fi" ]

# Default command launches the Streams-based write worker
CMD ["python", "-m", "agent.operational_agents.persistence_agent.write_worker"]
