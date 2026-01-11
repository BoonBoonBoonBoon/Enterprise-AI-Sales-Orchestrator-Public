"""Persistence Write Worker (Streams)

Consumes write tasks from Redis Streams and performs governed writes via
PersistenceService (through PersistenceAgent). Publishes results to a
results stream for correlation by orchestrators.

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

# Ensure repo root on sys.path
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None

from agent.operational_agents.factory import create_persistence_agent
from agent.tools.redis.client import RedisPubSub
from agent.tools.redis import config as rconf


class WriteWorker:
    TASK_STREAM = rconf.STREAM_TASKS_WRITE
    RESULT_STREAM = rconf.STREAM_RESULTS_WRITE
    DLQ_STREAM = rconf.STREAM_DLQ_WRITE
    GROUP = rconf.GROUP_WRITERS

    def __init__(self, kind: str = "supabase"):
        self.agent = create_persistence_agent(kind=kind)
        self.redis = RedisPubSub()
        self.worker_id = str(os.getpid())
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

    def _publish_result(self, payload: Dict[str, Any]) -> None:
        maxlen = rconf.STREAM_MAXLEN
        self.redis.xadd(self.RESULT_STREAM, {"data": json.dumps(payload, default=str)}, maxlen=maxlen)

    def _publish_dlq(self, task: Dict[str, Any], error: str) -> None:
        try:
            maxlen = rconf.STREAM_MAXLEN
            self.redis.xadd(self.DLQ_STREAM, {"data": json.dumps({"task": task, "error": error}, default=str)}, maxlen=maxlen)
        except Exception:
            pass

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
        payload = fields.get("data")
        if isinstance(payload, str):
            try:
                task = json.loads(payload)
            except Exception:
                task = {}
        elif isinstance(payload, dict):
            task = payload
        else:
            task = fields

        # Idempotency lock
        lock_key = rconf.idemp_key(self.TASK_STREAM, msg_id)
        try:
            acquired = self.redis.client.set(self.redis._chan(lock_key), "1", nx=True, ex=rconf.OPS_IDEMP_TTL)
            if not acquired:
                # Another worker already processed; ack and skip
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
                res = self._handle_task(task)
                self._publish_result(res)
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
                res = {"task_id": task.get("task_id"), "success": False, "error": str(e)}
                if rconf.ENABLE_DLQ:
                    self._publish_dlq(task, str(e))
                else:
                    self._publish_result(res)
                try:
                    self.redis.xack(self.TASK_STREAM, self.GROUP, msg_id)
                except Exception:
                    pass
                break

    def start(self) -> None:
        print(
            f"[WriteWorker {self.worker_id}] listening on stream {rconf.full_key(self.TASK_STREAM)} in group {self.GROUP}..."
        )
        try:
            while True:
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
