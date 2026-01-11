from typing import Any, Dict, Optional
import threading
import time


class Dispatcher:
    """Simple in-process dispatcher enforcing per-agent concurrency limits.

    This is a lightweight placeholder. Replace with a queue system (Redis/RQ)
    for production.
    """

    def __init__(self, limits: Optional[Dict[str, int]] = None):
        # limits: agent_name -> max concurrent
        self.limits = limits or {}
        self._locks: Dict[str, threading.Semaphore] = {}
        for k, v in self.limits.items():
            self._locks[k] = threading.Semaphore(v)

    def submit(self, agent_name: str, func, *args, **kwargs):
        sem = self._locks.get(agent_name)
        if sem:
            acquired = sem.acquire(blocking=False)
            if not acquired:
                raise RuntimeError(f"Agent {agent_name} concurrency limit reached")
        try:
            return func(*args, **kwargs)
        finally:
            if sem:
                sem.release()


# TODOs for Dispatcher
# - Replace in-memory semaphores with a Redis-backed queue for production
# - Add metrics (calls, rejected due to concurrency, latency)
# - Add async submit variant for non-blocking dispatch
# - Add unit tests for concurrency limits and failure modes
