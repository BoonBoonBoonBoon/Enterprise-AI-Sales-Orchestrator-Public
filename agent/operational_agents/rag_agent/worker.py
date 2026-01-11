"""RAG Worker (Streams): consumes tasks from Redis Streams and writes results.

Usage:
	python -m agent.operational_agents.rag_agent.worker

Environment:
	- PERSIST_KIND=supabase|memory
	- REDIS_URL or REDIS_HOST/PORT/DB/PASSWORD
	- REDIS_NAMESPACE (default: agentic)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
import json
from typing import Any, Dict
import threading
import time

# Ensure repo root on sys.path when run as a module
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
	sys.path.insert(0, str(repo_root))

# Load .env as early as possible so downstream config modules see env vars at import time
try:
	from dotenv import load_dotenv  # type: ignore
	load_dotenv()
except Exception:
	pass

from agent.operational_agents.factory import create_rag_agent
from agent.tools.redis.client import RedisPubSub
from agent.tools.redis.messages import QueryTask, QueryResponse
from agent.tools.redis import config as rconf


class RAGWorker:
	TASK_STREAM = rconf.STREAM_TASKS
	RESULT_STREAM = rconf.STREAM_RESULTS
	DLQ_STREAM = rconf.STREAM_DLQ
	GROUP = rconf.GROUP_WORKERS

	def __init__(self, kind: str = "supabase"):
		self.rag = create_rag_agent(kind=kind)
		self.redis = RedisPubSub()
		self.worker_id = str(os.getpid())
		# Ensure consumer group exists
		created = False
		try:
			created = self.redis.xgroup_create(self.TASK_STREAM, self.GROUP, id="$", mkstream=True)
		except Exception:
			created = False
		if os.getenv("REDIS_DEBUG", "0").lower() in ("1", "true", "yes"):
			print(
				f"[RAGWorker {self.worker_id}] ns={rconf.NAMESPACE} tasks={rconf.full_key(self.TASK_STREAM)} "
				f"results={rconf.full_key(self.RESULT_STREAM)} group={self.GROUP} created={created}"
			)

		# Heartbeat thread
		self._stop = threading.Event()
		if rconf.OPS_HB_ENABLED:
			def _hb_loop():
				key = rconf.hb_key("rag", self.worker_id)
				while not self._stop.is_set():
					try:
						# namespaced key via client
						self.redis.client.setex(self.redis._chan(key), rconf.OPS_HB_TTL, str(time.time()))
					except Exception:
						pass
					self._stop.wait(rconf.OPS_HB_INTERVAL)
			self._hb_thread = threading.Thread(target=_hb_loop, daemon=True)
			self._hb_thread.start()

	def _ack(self, msg_id: str) -> None:
		try:
			self.redis.xack(self.TASK_STREAM, self.GROUP, msg_id)
		except Exception:
			pass

	def _publish_result(self, payload: Dict[str, Any], stream: str) -> None:
		maxlen = rconf.STREAM_MAXLEN
		self.redis.xadd(stream, {"data": json.dumps(payload, default=str)}, maxlen=maxlen)

	def process(self, msg_id: str, fields: Dict[str, Any]) -> None:
		# Expect JSON task under 'data' field if stream entries are stored as JSON
		payload = fields.get("data")
		if isinstance(payload, str):
			try:
				msg = json.loads(payload)
			except Exception:
				msg = {}
		elif isinstance(payload, dict):
			msg = payload
		else:
			msg = fields  # Accept direct field mapping as task

		task = QueryTask(**msg)

		# Idempotency lock
		lock_key = rconf.idemp_key(self.TASK_STREAM, msg_id)
		try:
			# SET NX with TTL
			acquired = self.redis.client.set(self.redis._chan(lock_key), "1", nx=True, ex=rconf.OPS_IDEMP_TTL)
			if not acquired:
				# Another worker already processing/processed; safe to ack and skip
				self._ack(msg_id)
				return
		except Exception:
			# On Redis error, continue without idempotency
			pass

		retries = 0
		while True:
			try:
				rows = self.rag._persistence.query(
					table=task.table,
					filters=task.filters,
					limit=task.limit,
					order_by=task.order_by,
					descending=task.descending,
					select=task.columns,
				)
				resp = QueryResponse(
					task_id=task.task_id,
					success=True,
					records=rows,
					metadata={"worker_id": self.worker_id, "table": task.table, "count": len(rows)},
				)
				self._publish_result(resp.to_dict(), self.RESULT_STREAM)
				self._ack(msg_id)
				break
			except Exception as e:
				if retries < rconf.MAX_RETRIES:
					retries += 1
					if rconf.RETRY_BACKOFF_MS > 0:
						time.sleep(rconf.RETRY_BACKOFF_MS / 1000.0)
					continue
					
				# Exhausted retries → DLQ or result with error
				error_resp = QueryResponse(
					task_id=task.task_id,
					success=False,
					records=[],
					metadata={"worker_id": self.worker_id},
					error=str(e),
				).to_dict()
				if rconf.ENABLE_DLQ:
					self._publish_result({"task": msg, "error": error_resp}, self.DLQ_STREAM)
				else:
					self._publish_result(error_resp, self.RESULT_STREAM)
				self._ack(msg_id)
				break

	def start(self) -> None:
		print(
			f"[RAGWorker {self.worker_id}] listening on stream {rconf.full_key(self.TASK_STREAM)} in group {self.GROUP}..."
		)
		try:
			while True:
				# Read new messages for this consumer
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
							print(f"[RAGWorker {self.worker_id}] WORKER_ONCE set, exiting after first task.")
							self._stop.set()
							return
		except KeyboardInterrupt:
			print("\nRAGWorker stopping...")
		finally:
			self._stop.set()
			try:
				self._hb_thread.join(timeout=1.0)  # type: ignore[attr-defined]
			except Exception:
				pass
			self.redis.close()



def main() -> int:
	kind = os.getenv("PERSIST_KIND", "supabase")
	RAGWorker(kind=kind).start()
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
