"""Demo: Lead orchestrator querying via Redis Streams.

Start one or more workers separately, then run:
	python scripts/orchestrator_redis_demo.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure repo root on path
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
	sys.path.insert(0, str(repo_root))

try:
	from dotenv import load_dotenv  # type: ignore
except Exception:
	load_dotenv = None  # optional

from services.redis import RedisStreamsClient as RedisPubSub
from agent.utils.typed_envelope import task, to_redis_fields, Priority
import os


def main():
	# Load .env if python-dotenv is installed
	if load_dotenv:
		load_dotenv()
	r = RedisPubSub()
	task_stream = "rag:tasks"
	result_stream = "rag:results"
	
	# Build task envelope for RAG query
	envelope = task(
		task_id=os.urandom(8).hex(),
		payload={
			"query": {
				"table": "leads",
				"filters": {"email": "jk@jk.com"},
				"limit": 1
			}
		},
		source="orchestrator_redis_demo",
		destination=task_stream,
		priority=Priority.NORMAL
	)
	
	# Publish task
	msg_id = r.xadd(task_stream, to_redis_fields(envelope))
	
	# Await response with matching correlation_id on results stream
	resp = r.wait_for_stream(
		stream=result_stream,
		predicate=lambda m: isinstance(m, dict) and (
			m.get("correlation_id") == envelope.metadata.correlation_id or
			m.get("task_id") == envelope.metadata.task_id  # Fallback
		),
		timeout=20.0,
		block_ms=1000,
	)
	
	print(json.dumps({
		"task_id": envelope.metadata.task_id,
		"correlation_id": envelope.metadata.correlation_id,
		"enqueued": True,
		"message_id": msg_id,
		"response": resp,
		"received": bool(resp),
	}))


if __name__ == "__main__":
	main()
