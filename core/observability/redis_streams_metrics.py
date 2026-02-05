"""Redis Streams backlog/lag metrics for Prometheus.

Emits gauges:
- redis.stream.length
- redis.stream.pending
- redis.stream.oldest_pending_age_seconds
"""

from __future__ import annotations

import logging
import threading
import time
from typing import List, Optional, Tuple

from services.redis import RedisStreamsClient
from .metrics import MetricsCollector

logger = logging.getLogger(__name__)


def _parse_stream_id_ms(stream_id: Optional[str]) -> Optional[int]:
    if not stream_id or not isinstance(stream_id, str) or "-" not in stream_id:
        return None
    try:
        ms_str = stream_id.split("-", 1)[0]
        return int(ms_str)
    except Exception:
        return None


def start_redis_stream_metrics(
    *,
    redis_url: str,
    tenant_id: str,
    component: str,
    streams: List[Tuple[str, str]],
    interval_seconds: int = 10,
) -> Optional[threading.Thread]:
    """Start a background poller that emits Redis stream backlog metrics.

    Args:
        redis_url: Redis connection URL.
        tenant_id: Tenant for tagging.
        component: Component name for tagging.
        streams: List of (stream_name, consumer_group) pairs.
        interval_seconds: Poll interval.
    """
    if not redis_url:
        logger.warning("Redis URL missing; stream metrics disabled for %s", component)
        return None

    client = RedisStreamsClient(url=redis_url)
    metrics = MetricsCollector.get_instance()

    def poll() -> None:
        while True:
            for stream, group in streams:
                base_tags = {"tenant": tenant_id, "component": component, "stream": stream}
                try:
                    length = client.xlen(stream)
                except Exception as exc:
                    logger.debug("Failed to read XLEN for %s: %s", stream, exc)
                    length = 0
                metrics.gauge("redis.stream.length", length, tags=base_tags)

                if group:
                    pending_count = 0
                    oldest_age = 0.0
                    min_id = None
                    try:
                        pending = client.xpending(stream, group)
                        if isinstance(pending, dict):
                            pending_count = int(pending.get("pending") or pending.get("count") or 0)
                            min_id = pending.get("min") or pending.get("min_id") or pending.get("min-id")
                        elif isinstance(pending, (list, tuple)):
                            if len(pending) > 0:
                                pending_count = int(pending[0])
                            if len(pending) > 1:
                                min_id = pending[1]
                    except Exception as exc:
                        logger.debug("Failed to read XPENDING for %s/%s: %s", stream, group, exc)

                    if pending_count and min_id:
                        min_ms = _parse_stream_id_ms(min_id)
                        if min_ms is not None:
                            oldest_age = max(0.0, time.time() - (min_ms / 1000.0))

                    group_tags = {**base_tags, "group": group}
                    metrics.gauge("redis.stream.pending", pending_count, tags=group_tags)
                    metrics.gauge(
                        "redis.stream.oldest_pending_age_seconds",
                        oldest_age,
                        tags=group_tags,
                    )

            time.sleep(interval_seconds)

    thread = threading.Thread(
        target=poll,
        daemon=True,
        name=f"RedisStreamMetrics-{component}",
    )
    thread.start()
    logger.info("Redis stream metrics started for %s", component)
    return thread
