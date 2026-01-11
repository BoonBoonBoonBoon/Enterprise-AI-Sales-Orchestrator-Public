"""Persistence Write Worker (Streams)

Consumes write tasks from Redis Streams and performs governed writes via
PersistenceService (through PersistenceAgent). Publishes results to a
results stream for correlation by orchestrators.

Supports enhanced envelope with retry/DLQ lifecycle and error_code extraction.

Task schema (JSON in field 'data'):
{
  "task_id": str,
  "table": "leads" | ...,
  "op": "insert" | "upsert" | "batch_insert",
  "values": Dict | List[Dict],
  "on_conflict": Optional[List[str]],
  "returning": bool
}
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import threading
import time
import signal

# Ensure repo root on sys.path
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None

from tiers.tier_3.factory import create_persistence_agent
from services.redis import RedisStreamsClient, config as rconf
from core.envelope import from_redis_message, task, result, error, to_redis_fields, Status
from core.utils.rate_limiter import init_rate_limiter, get_rate_limiter


class WriteWorker:
    TASK_STREAM = rconf.STREAM_TASKS_WRITE
    RESULT_STREAM = rconf.STREAM_RESULTS_WRITE
    DLQ_STREAM = rconf.STREAM_DLQ_WRITE
    GROUP = rconf.GROUP_WRITERS

    def __init__(self, kind: str = "supabase"):
        self.agent = create_persistence_agent(kind=kind)
        self.redis = RedisStreamsClient()
        self.worker_id = str(os.getpid())
        self._processing = False  # Track if currently processing a message
        self._current_msg_id: str | None = None  # Track current message being processed
        
        # Initialize rate limiter
        self.rate_limiter = init_rate_limiter(redis_client=self.redis)
        
        # Ensure consumer group exists
        try:
            self.redis.xgroup_create(self.TASK_STREAM, self.GROUP, id="$", mkstream=True)
        except Exception:
            pass
        if os.getenv("REDIS_DEBUG", "0").lower() in ("1", "true", "yes"):
            print(
                f"[WriteWorker {self.worker_id}] ns={rconf.NAMESPACE} tasks={rconf.full_key(self.TASK_STREAM)} "
                f"results={rconf.full_key(self.RESULT_STREAM)} group={self.GROUP}"
            )

        # Heartbeat thread
        self._stop = threading.Event()
        if rconf.OPS_HB_ENABLED:
            def _hb_loop():
                key = rconf.hb_key("persist", self.worker_id)
                while not self._stop.is_set():
                    try:
                        self.redis.client.setex(self.redis._chan(key), rconf.OPS_HB_TTL, str(time.time()))
                    except Exception:
                        pass
                    self._stop.wait(rconf.OPS_HB_INTERVAL)
            self._hb_thread = threading.Thread(target=_hb_loop, daemon=True)
            self._hb_thread.start()

    def _publish_result(self, envelope, stream: str) -> None:
        """Publish result envelope to stream."""
        maxlen = rconf.STREAM_MAXLEN
        self.redis.xadd(stream, to_redis_fields(envelope), maxlen=maxlen)

    def _publish_dlq(self, envelope) -> None:
        """Publish error envelope to DLQ stream."""
        try:
            self.redis.xadd(self.DLQ_STREAM, to_redis_fields(envelope), maxlen=rconf.STREAM_MAXLEN)
        except Exception:
            pass

    def _extract_error_code(self, exc: Exception) -> Optional[str]:
        """Extract error code from exception (e.g., PostgreSQL error codes)."""
        # psycopg2/asyncpg: exc.pgcode or exc.sqlstate
        code = getattr(exc, 'pgcode', None) or getattr(exc, 'sqlstate', None) or getattr(exc, 'code', None)
        return str(code) if code else None

    def _handle_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task.get("task_id")
        table = task.get("table")
        op = (task.get("op") or "insert").lower()
        values = task.get("values")
        on_conflict: Optional[List[str]] = task.get("on_conflict")

        result: Dict[str, Any]
        if op in ("insert", "write"):
            inserted = self.agent.write(table, values)
            result = {"task_id": task_id, "success": True, "op": op, "row": inserted}
        elif op in ("batch_insert", "batch_write"):
            if not isinstance(values, list):
                raise ValueError("batch_insert requires values to be a list of records")
            rows = self.agent.batch_write(table, values)
            result = {"task_id": task_id, "success": True, "op": op, "rows": rows, "count": len(rows)}
        elif op == "upsert":
            row = self.agent.upsert(table, values, on_conflict=on_conflict)
            result = {"task_id": task_id, "success": True, "op": op, "row": row}
        else:
            raise ValueError(f"Unsupported op '{op}'")
        return result

    def process(self, msg_id: str, fields: Dict[str, Any]) -> None:
        self._processing = True
        self._current_msg_id = msg_id
        
        # Rate limiting: acquire token before processing
        worker_key = f"worker:{self.worker_id}"
        if not self.rate_limiter.acquire(worker_key, block=True, timeout=30.0):
            # Rate limit timeout - re-queue message
            print(f"[WriteWorker {self.worker_id}] Rate limit timeout for message {msg_id}, will retry")
            return  # Don't ACK, message will be retried
        
        try:
            # Parse task envelope
            task_envelope = from_redis_message(fields)
            write_spec = task_envelope.payload

            # Idempotency lock
            lock_key = rconf.idemp_key(self.TASK_STREAM, msg_id)
            try:
                acquired = self.redis.client.set(self.redis._chan(lock_key), "1", nx=True, ex=rconf.OPS_IDEMP_TTL)
                if not acquired:
                    try:
                        self.redis.xack(self.TASK_STREAM, self.GROUP, msg_id)
                    except Exception:
                        pass
                    return
            except Exception:
                pass

            retries = 0
            while True:
                try:
                    res = self._handle_task(write_spec)
                    
                    result_env = result(
                        original=task_envelope,
                        payload=res,
                        source="write_worker"
                    )
                    result_env.mark_processed()
                    self._publish_result(result_env, self.RESULT_STREAM)
                    
                    try:
                        self.redis.xack(self.TASK_STREAM, self.GROUP, msg_id)
                    except Exception:
                        pass
                    break
                    
                except Exception as e:
                    if retries < rconf.MAX_RETRIES:
                        retries += 1
                        if rconf.RETRY_BACKOFF_MS > 0:
                            time.sleep(rconf.RETRY_BACKOFF_MS / 1000.0)
                        continue
                    
                    # Exhausted retries
                    error_code = self._extract_error_code(e)
                    error_env = error(
                        original=task_envelope,
                        error_msg=str(e),
                        source="write_worker",
                        code=error_code
                    )
                    error_env.increment_retry()
                    
                    if error_env.status == Status.DLQ and rconf.ENABLE_DLQ:
                        self._publish_dlq(error_env)
                    else:
                        self._publish_result(error_env, self.RESULT_STREAM)
                    
                    try:
                        self.redis.xack(self.TASK_STREAM, self.GROUP, msg_id)
                    except Exception:
                        pass
                    break
        finally:
            self._processing = False
            self._current_msg_id = None

    def shutdown(self, signum=None, frame=None) -> None:
        """Graceful shutdown: finish in-flight task before exit."""
        print(f"\n[WriteWorker {self.worker_id}] Shutdown signal received (SIGTERM/SIGINT)")
        
        if self._processing:
            print(f"[WriteWorker {self.worker_id}] Waiting for in-flight message {self._current_msg_id} to complete...")
            # Wait up to 30 seconds for current task to finish
            for _ in range(60):
                if not self._processing:
                    break
                time.sleep(0.5)
            
            if self._processing:
                print(f"[WriteWorker {self.worker_id}] WARNING: Task still processing after 30s, forcing shutdown")
        
        self._stop.set()
        print(f"[WriteWorker {self.worker_id}] Shutdown complete")

    def start(self) -> None:
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)
        
        print(
            f"[WriteWorker {self.worker_id}] listening on stream {rconf.full_key(self.TASK_STREAM)} in group {self.GROUP}..."
        )
        print(f"[WriteWorker {self.worker_id}] Graceful shutdown enabled (SIGTERM/SIGINT will finish in-flight tasks)")
        
        try:
            while not self._stop.is_set():
                res = self.redis.xreadgroup(
                    group=self.GROUP,
                    consumer=self.worker_id,
                    streams={self.TASK_STREAM: ">"},
                    count=1,
                    block=5000,
                )
                if not res:
                    continue
                for _stream, entries in res:
                    for msg_id, fields in entries:
                        if self._stop.is_set():
                            print(f"[WriteWorker {self.worker_id}] Shutdown requested, not processing new messages")
                            break
                        self.process(msg_id, fields)
                        if os.getenv("WORKER_ONCE", "0").lower() in ("1", "true", "yes"):
                            print(f"[WriteWorker {self.worker_id}] WORKER_ONCE set, exiting after first task.")
                            self._stop.set()
                            return
        except KeyboardInterrupt:
            print("\nWriteWorker stopping...")
        finally:
            self._stop.set()
            try:
                self._hb_thread.join(timeout=1.0)  # type: ignore[attr-defined]
            except Exception:
                pass
            self.redis.close()


def main() -> int:
    if load_dotenv:
        load_dotenv()
    kind = os.getenv("PERSIST_KIND", "supabase")
    WriteWorker(kind=kind).start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
