"""Redis pub/sub client for agent communication.

Environment variables supported:
- REDIS_URL: full connection URL (preferred)
- REDIS_HOST (default: localhost)
- REDIS_PORT (default: 6379)
- REDIS_DB (default: 0)
- REDIS_PASSWORD (optional)
- REDIS_NAMESPACE (default: agentic) used for namespacing channels
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, Optional, List, Tuple
import time

try:
	import redis  # type: ignore
except Exception as e:  # pragma: no cover
	redis = None  # type: ignore


class RedisPubSub:
	"""Lightweight Redis pub/sub wrapper.

	If REDIS_URL is set, it is preferred (handles TLS via rediss://). Otherwise,
	falls back to host/port/db/password envs.
	"""

	def __init__(
		self,
		url: Optional[str] = None,
		host: Optional[str] = None,
		port: Optional[int] = None,
		db: Optional[int] = None,
		password: Optional[str] = None,
		namespace: Optional[str] = None,
	):
		if redis is None:
			raise ImportError("Please 'pip install redis' to use RedisPubSub")

		self.ns = namespace or os.getenv("REDIS_NAMESPACE", "agentic")
		url = url or os.getenv("REDIS_URL")
		if url:
			self.client = redis.from_url(url, decode_responses=True)
		else:
			self.client = redis.Redis(
				host=host or os.getenv("REDIS_HOST", "localhost"),
				port=int(port or os.getenv("REDIS_PORT", "6379")),
				db=int(db or os.getenv("REDIS_DB", "0")),
				password=password or os.getenv("REDIS_PASSWORD"),
				decode_responses=True,
			)
		self.pubsub = self.client.pubsub()

	def _chan(self, channel: str) -> str:
		"""Prefix channel with namespace."""
		return f"{self.ns}:{channel}" if self.ns else channel

	def publish(self, channel: str, message: Dict[str, Any]) -> int:
		"""Publish JSON message to a namespaced channel."""
		payload = json.dumps(message, default=str)
		return int(self.client.publish(self._chan(channel), payload))

	def subscribe(self, channel: str, callback: Callable[[Dict[str, Any]], None]) -> None:
		"""Subscribe to a channel and invoke callback for each JSON message."""
		self.pubsub.subscribe(self._chan(channel))
		for raw in self.pubsub.listen():
			if raw.get("type") == "message":
				try:
					msg = json.loads(raw.get("data"))
					callback(msg)
				except Exception as e:
					try:
						print(f"[RedisPubSub] failed to handle message: {e}")
					except Exception:
						pass

	# -------------------------
	# Streams (XADD / XREAD / XREADGROUP / XACK)
	# -------------------------

	def xadd(self, stream: str, fields: Dict[str, Any], maxlen: Optional[int] = None) -> str:
		"""Add an entry to a stream. Returns message ID."""
		stream_name = self._chan(stream)
		# Ensure all values are strings
		payload = {k: json.dumps(v, default=str) if not isinstance(v, str) else v for k, v in fields.items()}
		return self.client.xadd(stream_name, payload, maxlen=maxlen)

	def xread(
		self,
		streams: Dict[str, str],
		count: Optional[int] = None,
		block: Optional[int] = None,
	) -> List[Tuple[str, List[Tuple[str, Dict[str, Any]]]]]:
		"""Read from one or more streams. streams is mapping of stream->last_id."""
		ns_streams = {self._chan(k): v for k, v in streams.items()}
		return self.client.xread(ns_streams, count=count, block=block)

	def xgroup_create(self, stream: str, group: str, id: str = "$", mkstream: bool = True) -> bool:
		"""Create a consumer group for a stream. Returns False if it exists."""
		try:
			self.client.xgroup_create(self._chan(stream), group, id=id, mkstream=mkstream)
			return True
		except Exception as e:
			# BUSYGROUP Consumer Group name already exists
			if "BUSYGROUP" in str(e).upper():
				return False
			raise

	def xreadgroup(
		self,
		group: str,
		consumer: str,
		streams: Dict[str, str],
		count: Optional[int] = None,
		block: Optional[int] = None,
	) -> List[Tuple[str, List[Tuple[str, Dict[str, Any]]]]]:
		"""Read entries from streams using a consumer group."""
		ns_streams = {self._chan(k): v for k, v in streams.items()}
		return self.client.xreadgroup(group, consumer, ns_streams, count=count, block=block)

	def xack(self, stream: str, group: str, *message_ids: str) -> int:
		"""Acknowledge one or more messages for a consumer group."""
		return int(self.client.xack(self._chan(stream), group, *message_ids))

	def wait_for_stream(
		self,
		stream: str,
		predicate: Callable[[Dict[str, Any]], bool],
		timeout: float = 10.0,
		block_ms: int = 1000,
		json_field: str = "data",
	) -> Optional[Dict[str, Any]]:
		"""Wait for a matching message on a stream using XREAD (no consumer group).

		Starts at '$' (only new messages). Expects entries to include a JSON payload field
		named by json_field (default 'data'). Returns the parsed JSON dict or None on timeout.
		"""
		deadline = time.monotonic() + timeout
		last_id = "$"  # new messages only
		stream_name = stream
		while time.monotonic() < deadline:
			remaining_ms = int(max(0, (deadline - time.monotonic()) * 1000))
			block = min(block_ms, remaining_ms) if remaining_ms > 0 else 0
			res = self.xread({stream_name: last_id}, count=10, block=block)
			if not res:
				continue
			for _, entries in res:
				for msg_id, fields in entries:
					last_id = msg_id
					data = fields.get(json_field)
					try:
						obj = json.loads(data) if isinstance(data, str) else data
						if isinstance(obj, dict) and predicate(obj):
							return obj
					except Exception:
						continue
		return None

	def wait_for(
		self,
		channel: str,
		predicate: Callable[[Dict[str, Any]], bool],
		timeout: float = 10.0,
		poll_interval: float = 0.1,
	) -> Optional[Dict[str, Any]]:
		"""Synchronously wait for a message on channel that matches predicate.

		Returns the message dict if found within timeout, otherwise None.
		This uses a dedicated pubsub instance to avoid interfering with long-lived
		subscriptions created via subscribe().
		"""
		ps = self.client.pubsub()
		try:
			ps.subscribe(self._chan(channel))
			end = time.monotonic() + timeout
			while time.monotonic() < end:
				raw = ps.get_message(ignore_subscribe_messages=True, timeout=poll_interval)
				if not raw:
					continue
				if raw.get("type") != "message":
					continue
				try:
					msg = json.loads(raw.get("data"))
					if predicate(msg):
						return msg
				except Exception:
					# Ignore malformed messages and continue
					continue
			return None
		finally:
			try:
				ps.close()
			except Exception:
				pass

	def close(self) -> None:
		try:
			self.pubsub.close()
			self.client.close()
		except Exception:
			pass


__all__ = ["RedisPubSub"]
