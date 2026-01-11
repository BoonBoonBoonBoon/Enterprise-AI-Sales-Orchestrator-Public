"""Central configuration for Redis Streams keys and consumer groups.

All values can be overridden by environment variables.

Also includes operational settings for:
- Heartbeats (ops:hb)
- Idempotency locks (ops:idemp)
- Retry/DLQ controls
- Stream trimming
"""
from __future__ import annotations

import os

NAMESPACE = os.getenv("REDIS_NAMESPACE", "agentic")

# Stream key names (without namespace prefix)
STREAM_TASKS = os.getenv("REDIS_STREAM_TASKS", "rag:tasks")
STREAM_RESULTS = os.getenv("REDIS_STREAM_RESULTS", "rag:results")
# Write path streams (persistence workers)
STREAM_TASKS_WRITE = os.getenv("REDIS_STREAM_TASKS_WRITE", "persist:tasks")
STREAM_RESULTS_WRITE = os.getenv("REDIS_STREAM_RESULTS_WRITE", "persist:results")

# Consumer group name for workers
GROUP_WORKERS = os.getenv("REDIS_GROUP", "rag-workers")
GROUP_WRITERS = os.getenv("REDIS_GROUP_WRITERS", "persist-writers")

# -------------------------
# Operational settings (ops)
# -------------------------

# Heartbeats
OPS_HB_ENABLED = os.getenv("OPS_HB_ENABLED", "1").lower() in ("1", "true", "yes")
OPS_HB_TTL = int(os.getenv("OPS_HB_TTL", "30"))  # seconds
OPS_HB_INTERVAL = int(os.getenv("OPS_HB_INTERVAL", "10"))  # seconds

# Idempotency lock TTL
OPS_IDEMP_TTL = int(os.getenv("OPS_IDEMP_TTL", "60"))  # seconds

# Stream trimming (approximate, applies to results/DLQ writes)
STREAM_MAXLEN = int(os.getenv("REDIS_STREAM_MAXLEN", os.getenv("STREAM_MAXLEN", "0")) or 0) or None

# Retry / DLQ controls
MAX_RETRIES = int(os.getenv("REDIS_MAX_RETRIES", "2"))
RETRY_BACKOFF_MS = int(os.getenv("REDIS_RETRY_BACKOFF_MS", "0"))
ENABLE_DLQ = os.getenv("ENABLE_DLQ", "1").lower() in ("1", "true", "yes")

# DLQ streams (per domain)
STREAM_DLQ = os.getenv("REDIS_STREAM_DLQ", "rag:dlq")
STREAM_DLQ_WRITE = os.getenv("REDIS_STREAM_DLQ_WRITE", "persist:dlq")


def full_key(name: str) -> str:
    """Return the fully namespaced key for display/debug."""
    ns = NAMESPACE.strip("") if NAMESPACE else ""
    return f"{ns}:{name}" if ns else name


def hb_key(service: str, worker_id: str) -> str:
    """Build a heartbeat key name (without namespace)."""
    return f"ops:hb:{service}:{worker_id}"


def idemp_key(stream: str, msg_id: str) -> str:
    """Build an idempotency key (without namespace)."""
    return f"ops:idemp:{stream}:{msg_id}"


""" KEEP NOTE OF THIS AS WE WILL NEED TO CHANGE THE GROUPINGS 
   AND STREAMS LATER ONCE WE HAVE MULTIPLE STREAMS 
"""          

__all__ = [
    "NAMESPACE",
    "STREAM_TASKS",
    "STREAM_RESULTS",
    "STREAM_TASKS_WRITE",
    "STREAM_RESULTS_WRITE",
    "GROUP_WORKERS",
    "GROUP_WRITERS",
    # ops settings
    "OPS_HB_ENABLED",
    "OPS_HB_TTL",
    "OPS_HB_INTERVAL",
    "OPS_IDEMP_TTL",
    "STREAM_MAXLEN",
    "MAX_RETRIES",
    "RETRY_BACKOFF_MS",
    "ENABLE_DLQ",
    "STREAM_DLQ",
    "STREAM_DLQ_WRITE",
    "full_key",
    "hb_key",
    "idemp_key",
]
