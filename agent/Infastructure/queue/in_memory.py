from collections import deque
import threading
import time
import uuid
from typing import Any, Dict, Optional

try:  # Prefer shim path
    from agent.high_level_agents.queue.interface import QueueInterface  # type: ignore
except Exception:  # Fallback to canonical Infastructure path if needed
    from agent.Infastructure.queue.interface import QueueInterface  # type: ignore


class InMemoryQueue(QueueInterface):
    """Thread-safe in-memory queue for local development and tests.

    Simple visibility timeout + requeue semantics are implemented so tests can
    exercise transient failures.
    """

    def __init__(self, visibility_timeout: float = 30.0, requeue_check_interval: float = 1.0):
        self._queues: Dict[str, deque] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._inflight: Dict[str, Dict[str, Any]] = {}
        self._visibility_timeout = visibility_timeout
        self._stop = threading.Event()
        self._cond = threading.Condition()
        self._requeue_interval = requeue_check_interval
        self._requeue_thread = threading.Thread(target=self._requeue_worker, daemon=True)
        self._requeue_thread.start()

    def _ensure_topic(self, topic: str):
        if topic not in self._queues:
            self._queues[topic] = deque()
            self._locks[topic] = threading.Lock()

    def enqueue(self, topic: str, message: Dict[str, Any]) -> str:
        jid = message.get("job_id") or str(uuid.uuid4())
        job = {"job_id": jid, **message}
        self._ensure_topic(topic)
        with self._locks[topic]:
            self._queues[topic].append(job)
        with self._cond:
            self._cond.notify_all()
        return jid

    def dequeue(self, topic: str, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        self._ensure_topic(topic)
        end = None if timeout is None else (time.time() + timeout)
        while True:
            with self._locks[topic]:
                if self._queues[topic]:
                    job = self._queues[topic].popleft()
                    self._inflight[job["job_id"]] = {"job": job, "expire": time.time() + self._visibility_timeout}
                    return job
            with self._cond:
                remaining = None if end is None else max(0, end - time.time())
                if remaining == 0:
                    return None
                self._cond.wait(timeout=remaining)
                if end is not None and time.time() >= end:
                    return None

    def ack(self, job_id: str) -> None:
        self._inflight.pop(job_id, None)

    def requeue(self, job: Dict[str, Any], delay: Optional[float] = None) -> str:
        topic = job.get("meta", {}).get("topic", "orchestrate")
        return self.enqueue(topic, job)

    def _requeue_worker(self):
        while not self._stop.is_set():
            now = time.time()
            expired = [jid for jid, info in list(self._inflight.items()) if info["expire"] <= now]
            for jid in expired:
                info = self._inflight.pop(jid, None)
                if info:
                    job = info["job"]
                    topic = job.get("meta", {}).get("topic", "orchestrate")
                    with self._locks.setdefault(topic, threading.Lock()):
                        self._queues.setdefault(topic, deque()).append(job)
                    with self._cond:
                        self._cond.notify_all()
            time.sleep(self._requeue_interval)

    def stop(self):
        self._stop.set()
        with self._cond:
            self._cond.notify_all()
        self._requeue_thread.join(timeout=1.0)
