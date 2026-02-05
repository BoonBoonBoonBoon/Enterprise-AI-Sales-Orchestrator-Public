FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

RUN apt-get update -y && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY api/gateway/pyproject.toml /app/pyproject.toml

RUN pip install --upgrade pip && \
    pip install -e .

COPY api/gateway /app/api/gateway
COPY core /app/core
COPY services /app/services
COPY config /app/config

EXPOSE 8000

CMD ["uvicorn", "api.gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
