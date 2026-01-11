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

from agent.tools.redis.client import RedisPubSub
from agent.tools.redis.messages import QueryTask


def main():
	# Load .env if python-dotenv is installed
	if load_dotenv:
		load_dotenv()
	r = RedisPubSub()
	task_stream = "rag:tasks"
	result_stream = "rag:results"
	# Publish a test query for an email; a worker should consume via consumer group
	task = QueryTask.create(table="leads", filters={"email": "jk@jk.com"}, limit=1)
	msg_id = r.xadd(task_stream, {"data": json.dumps(task.to_dict())})
	# Await response with matching task_id on results stream
	resp = r.wait_for_stream(
		stream=result_stream,
		predicate=lambda m: isinstance(m, dict) and m.get("task_id") == task.task_id,
		timeout=20.0,
		block_ms=1000,
		json_field="data",
	)
	print(json.dumps({
		"task_id": task.task_id,
		"enqueued": True,
		"message_id": msg_id,
		"response": resp,
		"received": bool(resp),
	}))


if __name__ == "__main__":
	main()
