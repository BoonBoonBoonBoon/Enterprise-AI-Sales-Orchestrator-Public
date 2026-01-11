"""RAG Worker (Streams): consumes tasks from Redis Streams and writes results.

Supports context forwarding: when task includes forward_to.agent="copywriter",
RAG will enqueue a copywriter task with fetched lead data + forwarded instructions.

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
import signal

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

from tiers.tier_3.factory import create_rag_agent
from services.redis import RedisStreamsClient, QueryTask, QueryResponse, config as rconf
from core.envelope import from_redis_message, task, result, error, to_redis_fields, Status
from core.utils.tracing import init_tracer, inject_trace_context, TracedWorker
from core.utils.workflow_progress import WorkflowProgressTracker
from core.utils.rate_limiter import init_rate_limiter, get_rate_limiter


class RAGWorker(TracedWorker):
	TASK_STREAM = rconf.STREAM_TASKS
	RESULT_STREAM = rconf.STREAM_RESULTS
	DLQ_STREAM = rconf.STREAM_DLQ
	GROUP = rconf.GROUP_WORKERS

	def __init__(
		self,
		kind: str = "supabase",
		redis_url: str | None = None,
		task_stream: str | None = None,
		result_stream: str | None = None,
	):
		self.rag = create_rag_agent(kind=kind)
		# If explicit streams are provided (typically tests), treat them as fully-qualified
		# and avoid applying any namespace prefixing.
		if task_stream or result_stream:
			self.redis = RedisStreamsClient(url=redis_url, namespace="")
		else:
			self.redis = RedisStreamsClient(url=redis_url)

		if task_stream:
			self.TASK_STREAM = task_stream
		if result_stream:
			self.RESULT_STREAM = result_stream
		self.worker_id = str(os.getpid())
		self._processing = False  # Track if currently processing a message
		self._current_msg_id: str | None = None  # Track current message being processed
		
		# Initialize tracer for distributed tracing
		self.tracer = init_tracer(f"rag-worker-{self.worker_id}")
		
		# Initialize workflow progress tracker
		self.progress_tracker = WorkflowProgressTracker(self.redis.client)
		
		# Initialize rate limiter
		self.rate_limiter = init_rate_limiter(redis_client=self.redis)
		
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

	def _publish_result(self, envelope, stream: str) -> None:
		"""Publish result envelope to stream with trace context injection."""
		maxlen = rconf.STREAM_MAXLEN
		fields = to_redis_fields(envelope)
		
		# Inject trace context into outgoing message
		fields = inject_trace_context(fields)
		
		self.redis.xadd(stream, fields, maxlen=maxlen)

	def _forward_to_copywriter(self, task_envelope, lead_data: Dict[str, Any]) -> None:
		"""Forward fetched lead data + instructions to copywriter stream with trace context."""
		forward_spec = task_envelope.payload.get("forward_to", {})
		if forward_spec.get("agent") != "copywriter":
			return
		
		copy_envelope = task(
			source="rag_worker",
			task_id=f"copy-{lead_data.get('id', 'unknown')}",
			destination="copy:tasks",
			payload={
				"lead_data": lead_data,
				"campaign_context": forward_spec.get("campaign_context", {}),
				"instructions": forward_spec.get("instructions", {})
			},
			correlation_id=task_envelope.metadata.correlation_id,
			campaign_id=task_envelope.metadata.campaign_id,
			tags={
				**task_envelope.metadata.tags,
				"parent_task_id": task_envelope.metadata.task_id,
				"worker_id": self.worker_id
			}
		)
		
		# Inject trace context before publishing
		fields = to_redis_fields(copy_envelope)
		fields = inject_trace_context(fields)
		
		self.redis.xadd(
			rconf.full_key(rconf.STREAM_TASKS_COPY),
			fields,
			maxlen=rconf.STREAM_MAXLEN
		)

	def search_citations(self, query: str) -> list[dict[str, Any]]:
		"""Compatibility hook for tests/mocks.

		Some integration tests patch this method to stub citation lookup.
		"""
		try:
			fn = getattr(self.rag, "search_citations", None)
			if callable(fn):
				res = fn(query)
				return res if isinstance(res, list) else []
		except Exception:
			pass
		return []

	def process(self, msg_id: str, fields: Dict[str, Any]) -> None:
		try:
			self._processing = True
			self._current_msg_id = msg_id
			
			# Rate limiting: acquire token before processing
			worker_key = f"worker:{self.worker_id}"
			if not self.rate_limiter.acquire(worker_key, block=True, timeout=30.0):
				# Rate limit timeout - re-queue message
				print(f"[RAGWorker {self.worker_id}] Rate limit timeout for message {msg_id}, will retry")
				return  # Don't ACK, message will be retried
			
			# Start traced span for entire message processing
			with self.start_span(
				"process_rag_task",
				fields,
				message_id=msg_id,
				worker_id=self.worker_id,
				stream=self.TASK_STREAM
			) as span:
				# Parse task envelope
				task_envelope = from_redis_message(fields)
				query_spec = task_envelope.payload.get("query", {})
				
				span.set_attribute("task_id", task_envelope.metadata.task_id)
				span.set_attribute("correlation_id", task_envelope.metadata.correlation_id or "")
				span.set_attribute("table", query_spec.get("table", "leads"))
				
				# Convert to QueryTask for backward compat with existing RAG logic
				query_task = QueryTask(
					task_id=task_envelope.metadata.task_id,
					table=query_spec.get("table", "leads"),
					filters=query_spec.get("filters", {}),
					limit=query_spec.get("limit", 100),
					order_by=query_spec.get("order_by"),
					descending=query_spec.get("descending", False),
					columns=query_spec.get("columns")
				)

				# Idempotency lock
				lock_key = rconf.idemp_key(self.TASK_STREAM, msg_id)
				try:
					acquired = self.redis.client.set(self.redis._chan(lock_key), "1", nx=True, ex=rconf.OPS_IDEMP_TTL)
					if not acquired:
						span.add_event("duplicate_message_skipped")
						self._ack(msg_id)
						return
				except Exception:
					pass
				
				# Track workflow progress: RAG step started
				correlation_id = task_envelope.metadata.correlation_id
				if correlation_id:
					self.progress_tracker.update_step(correlation_id, "rag", status="in_progress")

				retries = 0
				while True:
					try:
						# Database query span
						with self.start_span("database_query", None, table=query_task.table) as db_span:
							rows = self.rag._persistence.query(
								table=query_task.table,
								filters=query_task.filters,
								limit=query_task.limit,
								order_by=query_task.order_by,
								descending=query_task.descending,
								select=query_task.columns,
							)
							db_span.set_attribute("rows_returned", len(rows))
						
						# Forward to copywriter if requested
						if rows:
							with self.start_span("forward_to_copywriter", None) as fwd_span:
								self._forward_to_copywriter(task_envelope, rows[0])
								fwd_span.add_event("forwarded_to_copywriter")
						
						# Publish result envelope
						result_env = result(
							original=task_envelope,
							payload={
								"records": rows,
								"count": len(rows),
								"table": query_task.table
							},
							source="rag_worker"
						)
						result_env.mark_processed()
						
						with self.start_span("publish_result", None, stream=self.RESULT_STREAM) as pub_span:
							self._publish_result(result_env, self.RESULT_STREAM)
							pub_span.set_attribute("result_count", len(rows))
						
						# Track workflow progress: RAG step completed
						if correlation_id:
							self.progress_tracker.update_step(
								correlation_id, "rag", 
								status="completed", 
								result_count=len(rows)
							)
						
						span.add_event("task_completed", {"rows": len(rows)})
						self._ack(msg_id)
						break
						
					except Exception as e:
						span.add_event("error_occurred", {"error": str(e), "retry": retries})
						
						if retries < rconf.MAX_RETRIES:
							retries += 1
							if rconf.RETRY_BACKOFF_MS > 0:
								time.sleep(rconf.RETRY_BACKOFF_MS / 1000.0)
							continue
						
					# Exhausted retries → DLQ or error result
					span.add_event("max_retries_exceeded", {"retries": retries})
					
					# Track workflow progress: RAG step failed
					if correlation_id:
						self.progress_tracker.update_step(
							correlation_id, "rag",
							status="failed",
							error=str(e)
						)
					
					error_env = error(
						original=task_envelope,
						error_msg=str(e),
						source="rag_worker",
						code=getattr(e, 'code', None)
					)
					error_env.increment_retry()
					
					if error_env.status == Status.DLQ and rconf.ENABLE_DLQ:
						self._publish_result(error_env, self.DLQ_STREAM)
					else:
						self._publish_result(error_env, self.RESULT_STREAM)
					
					self._ack(msg_id)
					break
		finally:
			self._processing = False
			self._current_msg_id = None

	def shutdown(self, signum=None, frame=None) -> None:
		"""Graceful shutdown: finish in-flight task before exit."""
		print(f"\n[RAGWorker {self.worker_id}] Shutdown signal received (SIGTERM/SIGINT)")
		
		if self._processing:
			print(f"[RAGWorker {self.worker_id}] Waiting for in-flight message {self._current_msg_id} to complete...")
			# Wait up to 30 seconds for current task to finish
			for _ in range(60):
				if not self._processing:
					break
				time.sleep(0.5)
			
			if self._processing:
				print(f"[RAGWorker {self.worker_id}] WARNING: Task still processing after 30s, forcing shutdown")
		
		self._stop.set()
		print(f"[RAGWorker {self.worker_id}] Shutdown complete")

	def start(self) -> None:
		# Register signal handlers for graceful shutdown
		signal.signal(signal.SIGTERM, self.shutdown)
		signal.signal(signal.SIGINT, self.shutdown)
		
		print(
			f"[RAGWorker {self.worker_id}] listening on stream {rconf.full_key(self.TASK_STREAM)} in group {self.GROUP}..."
		)
		print(f"[RAGWorker {self.worker_id}] Graceful shutdown enabled (SIGTERM/SIGINT will finish in-flight tasks)")
		
		try:
			while not self._stop.is_set():
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
						if self._stop.is_set():
							print(f"[RAGWorker {self.worker_id}] Shutdown requested, not processing new messages")
							break
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
