import os
import warnings
from typing import Optional

from .in_memory import InMemoryQueue
from .interface import QueueInterface

try:
    from .adapters.redis_streams_queue import RedisStreamsQueue
except Exception:
    RedisStreamsQueue = None  # type: ignore


def build_queue(backend: Optional[str] = None, consumer_name: Optional[str] = None) -> QueueInterface:
    warnings.warn(
        (
            "agent.Infastructure.queue.factory.build_queue is deprecated for Redis usage. "
            "Prefer using Streams directly via agent.tools.redis.client and the worker "
            "agent.operational_agents.rag_agent.worker."
        ),
        DeprecationWarning,
        stacklevel=2,
    )
    backend = (backend or os.environ.get('QUEUE_BACKEND') or 'memory').lower()
    if backend == 'redis':
        if RedisStreamsQueue is None:
            raise ImportError("Redis backend requested but not available. Install 'redis' and ensure adapter is importable.")
        return RedisStreamsQueue(consumer_name=consumer_name)
    # default
    return InMemoryQueue()


__all__ = ["build_queue"]
