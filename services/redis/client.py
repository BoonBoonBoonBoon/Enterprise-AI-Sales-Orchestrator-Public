"""Redis Streams client for agent communication.

Environment variables supported:
- REDIS_URL: full connection URL (preferred, supports rediss:// for TLS)
- REDIS_HOST (default: localhost)
- REDIS_PORT (default: 6379)
- REDIS_DB (default: 0)
- REDIS_PASSWORD (optional)
- REDIS_NAMESPACE (default: agentic) used for namespacing streams
- REDIS_TLS_ENABLED (default: 0) set to 1 to enable TLS
- REDIS_TLS_CERT_PATH (optional) path to TLS certificate
- REDIS_TLS_KEY_PATH (optional) path to TLS private key
- REDIS_TLS_CA_CERT_PATH (optional) path to CA certificate
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


class RedisStreamsClient:
	"""Redis Streams client with optional TLS support.

	Provides XADD, XREAD, XGROUP, XREADGROUP, XACK operations for Redis Streams.
	If REDIS_URL is set, it is preferred (handles TLS via rediss://). Otherwise,
	falls back to host/port/db/password envs.
	
	TLS Configuration:
	- Use rediss:// URL scheme for automatic TLS
	- Or set REDIS_TLS_ENABLED=1 with optional cert paths
	"""

	def __init__(
		self,
		url: Optional[str] = None,
		host: Optional[str] = None,
		port: Optional[int] = None,
		db: Optional[int] = None,
		password: Optional[str] = None,
		namespace: Optional[str] = None,
		tls_enabled: Optional[bool] = None,
		tls_cert_path: Optional[str] = None,
		tls_key_path: Optional[str] = None,
		tls_ca_cert_path: Optional[str] = None,
	):
		if redis is None:
			raise ImportError("Please 'pip install redis' to use RedisPubSub")

		self.ns = namespace or os.getenv("REDIS_NAMESPACE", "agentic")
		url = url or os.getenv("REDIS_URL")
		
		# TLS configuration
		tls_enabled = tls_enabled if tls_enabled is not None else bool(int(os.getenv("REDIS_TLS_ENABLED", "0")))
		
		if url:
			# URL-based connection (supports rediss:// for TLS)
			self.client = redis.from_url(url, decode_responses=True)
		else:
			# Manual connection with optional TLS
			connection_kwargs = {
				"host": host or os.getenv("REDIS_HOST", "localhost"),
				"port": int(port or os.getenv("REDIS_PORT", "6379")),
				"db": int(db or os.getenv("REDIS_DB", "0")),
				"password": password or os.getenv("REDIS_PASSWORD"),
				"decode_responses": True,
			}
			
			# Add TLS configuration if enabled
			if tls_enabled:
				ssl_cert_reqs = "required"  # Require valid cert by default
				ssl_kwargs = {"ssl": True, "ssl_cert_reqs": ssl_cert_reqs}
				
				# Add cert paths if provided
				cert_path = tls_cert_path or os.getenv("REDIS_TLS_CERT_PATH")
				key_path = tls_key_path or os.getenv("REDIS_TLS_KEY_PATH")
				ca_cert_path = tls_ca_cert_path or os.getenv("REDIS_TLS_CA_CERT_PATH")
				
				if cert_path:
					ssl_kwargs["ssl_certfile"] = cert_path
				if key_path:
					ssl_kwargs["ssl_keyfile"] = key_path
				if ca_cert_path:
					ssl_kwargs["ssl_ca_certs"] = ca_cert_path
				
				connection_kwargs.update(ssl_kwargs)
			
			self.client = redis.Redis(**connection_kwargs)
		
		self.pubsub = self.client.pubsub()

	def _chan(self, channel: str) -> str:
		"""Prefix channel with namespace unless it's already a fully-qualified stream key.

		We treat keys like '{tenant}:manager:*', '{tenant}:orchestrators:*', '{tenant}:agents:*'
		as already absolute and do not add an extra namespace prefix.
		"""
		if not self.ns:
			return channel
		# If the key is already prefixed with the configured namespace/tenant, don't double-prefix.
		# This commonly happens for non-stream keys like '{tenant}:outreach:auto_send'.
		if channel.startswith(f"{self.ns}:"):
			return channel
		# If it's already a canonical system stream key, don't prefix again.
		if ":manager:" in channel or ":orchestrators:" in channel or ":agents:" in channel:
			return channel
		return f"{self.ns}:{channel}"

	# --------------------
	# Hash helpers (non-stream state)
	# --------------------
	def hset(self, name: str, key: str, value: str) -> int:
		"""Set a field in a hash (HSET)."""
		return int(self.client.hset(self._chan(name), key, value))

	def hget(self, name: str, key: str) -> Optional[str]:
		"""Get a field from a hash (HGET)."""
		return self.client.hget(self._chan(name), key)

	def hdel(self, name: str, *keys: str) -> int:
		"""Delete one or more fields from a hash (HDEL)."""
		return int(self.client.hdel(self._chan(name), *keys))

	def hexists(self, name: str, key: str) -> bool:
		"""Check if a hash field exists (HEXISTS)."""
		return bool(self.client.hexists(self._chan(name), key))

	def hgetall(self, name: str) -> Dict[str, str]:
		"""Get all fields and values in a hash (HGETALL)."""
		data = self.client.hgetall(self._chan(name))
		return dict(data) if isinstance(data, dict) else {}

	def xlen(self, stream: str) -> int:
		"""Get stream length (XLEN)."""
		return int(self.client.xlen(self._chan(stream)))

	def xinfo_stream(self, stream: str) -> Dict[str, Any]:
		"""Get stream info (XINFO STREAM)."""
		return self.client.xinfo_stream(self._chan(stream))

	def xpending(self, stream: str, group: str) -> Dict[str, Any]:
		"""Get pending summary for a consumer group (XPENDING)."""
		return self.client.xpending(self._chan(stream), group)

	def create_consumer_group(self, stream: str, group: str, id: str = "0", mkstream: bool = True) -> bool:
		"""Compatibility wrapper around XGROUP CREATE.

		Returns True if created, False if already exists.
		"""
		return self.xgroup_create(stream=stream, group=group, id=id, mkstream=mkstream)

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
		# Use exact trimming when maxlen is provided to keep tests deterministic.
		if maxlen is not None:
			return self.client.xadd(stream_name, payload, maxlen=maxlen, approximate=False)
		return self.client.xadd(stream_name, payload)

	@staticmethod
	def _decode_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
		"""Best-effort decode of JSON-encoded envelope fields.

		We only decode known structured keys to avoid coercing scalar strings (e.g. UUIDs)
		into other Python types.
		"""
		for key in ("payload", "metadata", "tags"):
			val = fields.get(key)
			if isinstance(val, str):
				try:
					parsed = json.loads(val)
					fields[key] = parsed
				except Exception:
					pass
		return fields

	def _decode_xread_response(
		self,
		res: List[Tuple[str, List[Tuple[str, Dict[str, Any]]]]],
	) -> List[Tuple[str, List[Tuple[str, Dict[str, Any]]]]]:
		decoded: List[Tuple[str, List[Tuple[str, Dict[str, Any]]]]] = []
		for stream_name, entries in res:
			decoded_entries: List[Tuple[str, Dict[str, Any]]] = []
			for msg_id, fields in entries:
				decoded_entries.append((msg_id, self._decode_fields(dict(fields))))
			decoded.append((stream_name, decoded_entries))
		return decoded

	def xread(
		self,
		streams: Dict[str, str],
		count: Optional[int] = None,
		block: Optional[int] = None,
	) -> List[Tuple[str, List[Tuple[str, Dict[str, Any]]]]]:
		"""Read from one or more streams. streams is mapping of stream->last_id."""
		ns_streams = {self._chan(k): v for k, v in streams.items()}
		return self._decode_xread_response(self.client.xread(ns_streams, count=count, block=block))

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
		return self._decode_xread_response(
			self.client.xreadgroup(group, consumer, ns_streams, count=count, block=block)
		)

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
