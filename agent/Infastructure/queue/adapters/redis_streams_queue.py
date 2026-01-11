from __future__ import annotations

import os
import json
import time
import uuid
import warnings
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from agent.Infastructure.queue.interface import QueueInterface

try:
    import redis  # type: ignore
except Exception as e:
    redis = None  # pragma: no cover


warnings.warn(
    (
        "agent.Infastructure.queue.adapters.redis_streams_queue is deprecated. "
        "Use the Streams-native worker and client in agent.tools.redis instead: "
        "- worker: python -m agent.operational_agents.rag_agent.worker (consumes from REDIS_STREAM_TASKS)\n"
        "- enqueue: RedisPubSub().xadd(REDIS_STREAM_TASKS, {'data': json.dumps(task)})\n"
        "Configure names via REDIS_NAMESPACE/REDIS_STREAM_TASKS/REDIS_STREAM_RESULTS/REDIS_GROUP in .env."
    ),
    DeprecationWarning,
    stacklevel=2,
)


class RedisStreamsQueue(QueueInterface):
    """[DEPRECATED] Redis Streams implementation of legacy QueueInterface.

    This adapter will be removed in a future release. Prefer the Streams worker in
    `agent.operational_agents.rag_agent.worker` and the lightweight client in `agent.tools.redis.client`.

    - One Redis Stream per topic: `<ns>:stream:<topic>`
    - One Consumer Group per topic: `<ns>:grp:<topic>`
    - Messages stored as a single JSON field `data`
    - job_id is the Redis Stream entry ID (e.g., 1716234567890-0)
    - Delayed requeue via a ZSET `<ns>:delayed:<topic>` processed on dequeue
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        namespace: Optional[str] = None,
        consumer_name: Optional[str] = None,
    ):
        if redis is None:
            raise ImportError("Please install 'redis' package to use RedisStreamsQueue")

        self.redis_url = (
            redis_url
            or os.environ.get("REDIS_URL")
            or "redis://localhost:6379/0"
        )
        self.ns = namespace or os.environ.get("REDIS_NAMESPACE", "agentic")
        self.consumer = consumer_name or os.environ.get("REDIS_CONSUMER") or f"c-{uuid.uuid4().hex[:8]}"
        # Respect rediss:// scheme automatically; if REDIS_SSL_VERIFY=false, relax cert verification.
        ssl_kwargs = {}
        if self.redis_url.startswith('rediss://'):
            verify_env = os.environ.get('REDIS_SSL_VERIFY', 'true').lower()
            if verify_env in ('0', 'false', 'no'):
                ssl_kwargs['ssl_cert_reqs'] = None
        self.client = redis.Redis.from_url(self.redis_url, decode_responses=True, **ssl_kwargs)

    # Key helpers
    def _stream(self, topic: str) -> str:
        return f"{self.ns}:stream:{topic}"

    def _group(self, topic: str) -> str:
        return f"{self.ns}:grp:{topic}"

    def _job_index(self, job_id: str) -> str:
        return f"{self.ns}:job:{job_id}"

    def _delayed(self, topic: str) -> str:
        return f"{self.ns}:delayed:{topic}"

    def _ensure_group(self, topic: str) -> None:
        stream = self._stream(topic)
        group = self._group(topic)
        try:
            # MKSTREAM creates stream if missing; starting at beginning (0-0)
            self.client.xgroup_create(name=stream, groupname=group, id="0-0", mkstream=True)
        except Exception as e:
            # BUSYGROUP means it already exists
            if "BUSYGROUP" in str(e):
                return
            # Other errors might be transient; let them bubble up
            if "already exists" in str(e):
                return
            raise

    def _drain_delayed(self, topic: str) -> None:
        """Move due delayed messages from ZSET to stream."""
        zkey = self._delayed(topic)
        now_ms = int(time.time() * 1000)
        # Fetch a small batch to avoid large bursts
        items = self.client.zrangebyscore(zkey, min=0, max=now_ms, start=0, num=50, withscores=False)
        if not items:
            return
        stream = self._stream(topic)
        pipe = self.client.pipeline()
        for data in items:
            pipe.xadd(stream, {"data": data})
            pipe.zrem(zkey, data)
        pipe.execute()

    def enqueue(self, topic: str, message: Dict[str, Any]) -> str:
        self._ensure_group(topic)
        stream = self._stream(topic)
        # ensure job_id present but we will overwrite with Redis ID for tracking
        msg = dict(message)
        msg.setdefault("job_id", str(uuid.uuid4()))
        payload = json.dumps(msg, separators=(",", ":"))
        entry_id = self.client.xadd(stream, {"data": payload})
        # index job -> topic/group for ack lookup
        self.client.hset(self._job_index(entry_id), mapping={"topic": topic, "group": self._group(topic)})
        return entry_id

    def dequeue(self, topic: str, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        self._ensure_group(topic)
        # Drain any delayed due messages
        self._drain_delayed(topic)

        block_ms = 0 if timeout is None else int(max(timeout, 0) * 1000)
        stream = self._stream(topic)
        group = self._group(topic)
        res = self.client.xreadgroup(groupname=group, consumername=self.consumer, streams={stream: ">"}, count=1, block=block_ms)
        if not res:
            return None
        # res structure: [(stream, [(id, {field: value})])]
        _, entries = res[0]
        entry_id, fields = entries[0]
        data = fields.get("data")
        try:
            msg = json.loads(data) if data else {}
        except Exception:
            msg = {"raw": data}
        # Inject job_id from stream id
        msg["job_id"] = entry_id
        return msg

    def ack(self, job_id: str) -> None:
        # Lookup topic/group
        job_key = self._job_index(job_id)
        info = self.client.hgetall(job_key)
        if not info:
            # best-effort: nothing to ack
            return
        topic = info.get("topic")
        group = info.get("group")
        if not topic or not group:
            return
        stream = self._stream(topic)
        try:
            self.client.xack(stream, group, job_id)
            # Optionally trim job index
            self.client.delete(job_key)
        except Exception:
            # idempotent semantics: ignore failures
            pass

    def requeue(self, job: Dict[str, Any], delay: Optional[float] = None) -> str:
        topic = job.get("meta", {}).get("flow") or job.get("orchestrator") or job.get("topic") or "default"
        # Ensure we do not re-use stream id as job_id
        job = dict(job)
        job.pop("job_id", None)
        payload = json.dumps(job, separators=(",", ":"))
        if delay and delay > 0:
            zkey = self._delayed(topic)
            eta_ms = int(time.time() * 1000 + delay * 1000)
            self.client.zadd(zkey, {payload: eta_ms})
            # Return synthetic id
            return f"delayed-{uuid.uuid4().hex}"
        # immediate requeue
        stream = self._stream(topic)
        entry_id = self.client.xadd(stream, {"data": payload})
        self.client.hset(self._job_index(entry_id), mapping={"topic": topic, "group": self._group(topic)})
        return entry_id


__all__ = ["RedisStreamsQueue"]
