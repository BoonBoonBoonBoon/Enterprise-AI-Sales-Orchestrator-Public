"""
Persistence Agent Redis Streams Consumer

Handles:
- Consuming tasks from hierarchical Redis stream: {tenant}:agents:persistence:tasks
- Publishing results to: {tenant}:agents:persistence:results
- Typed envelope parsing and serialization
- Agent execution through harness
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Optional, Dict, Any, List

import redis.asyncio as redis
import redis as redis_sync

from .persistence_agent import PersistenceAgent
from .persistence_agent_harness import PersistenceAgentHarness
from services.persistence.service import PersistenceService
from core.envelope import (
    Envelope,
    from_redis_message,
    task as create_task_envelope,
    result as create_result_envelope,
    error as create_error_envelope,
    to_redis_fields,
)
from config.persistence_config import get_read_allowlist, get_write_allowlist

try:
    from services.persistence.adapters.supabase_adapter import SupabaseAdapter  # type: ignore
except Exception:  # Supabase optional in some environments
    SupabaseAdapter = None

logger = logging.getLogger(__name__)


class RedisHashAdapter:
    """Shared Redis-backed adapter to keep persistence state across workers."""

    def __init__(self, redis_url: str, tenant_id: str):
        self.redis = redis_sync.from_url(redis_url, decode_responses=True)
        self.tenant_id = tenant_id
        self.capabilities = {
            "equality_filters": True,
            "ordering": True,
            "limit": True,
            "projections": True,
            "ilike": True,
            "range_operators": False,
            "in_operator": False,
        }

    def _key(self, table: str) -> str:
        return f"{self.tenant_id}:persist:{table}"

    def _wildcard_match(self, value: Any, pattern: str) -> bool:
        if not isinstance(value, str):
            return False
        parts = pattern.lower().split("%")
        cursor = value.lower()
        pos = 0
        for part in parts:
            if not part:
                continue
            idx = cursor.find(part, pos)
            if idx == -1:
                return False
            pos = idx + len(part)
        return True

    def _all_rows(self, table: str) -> List[Dict[str, Any]]:
        raw_values = self.redis.hvals(self._key(table)) or []
        rows: List[Dict[str, Any]] = []
        for raw in raw_values:
            try:
                rows.append(json.loads(raw))
            except Exception:
                continue
        return rows

    def write(self, table: str, record: Dict[str, Any]) -> Dict[str, Any]:
        stored = {**record}
        stored.setdefault("id", str(uuid.uuid4()))
        self.redis.hset(self._key(table), stored["id"], json.dumps(stored))
        return stored

    def batch_write(self, table: str, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [self.write(table, r) for r in records]

    def upsert(self, table: str, record: Dict[str, Any], on_conflict: Optional[List[str]] = None) -> Dict[str, Any]:
        if not on_conflict:
            return self.write(table, record)
        for existing in self._all_rows(table):
            if all(existing.get(k) == record.get(k) for k in on_conflict):
                updated = {**existing, **record}
                updated.setdefault("id", existing.get("id"))
                self.redis.hset(self._key(table), updated["id"], json.dumps(updated))
                return updated
        return self.write(table, record)

    def read(self, table: str, id_value: Any, id_column: str = "id") -> Optional[Dict[str, Any]]:
        if id_column != "id":
            matches = self.query(table, filters={id_column: id_value}, limit=1)
            return matches[0] if matches else None
        raw = self.redis.hget(self._key(table), id_value)
        return json.loads(raw) if raw else None

    def query(
        self,
        table: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        order_by: Optional[str] = None,
        descending: bool = False,
        select: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        rows = self._all_rows(table)
        results: List[Dict[str, Any]] = []
        for row in rows:
            mismatch = False
            if filters:
                for k, v in filters.items():
                    row_val = row.get(k)
                    if isinstance(v, str) and "%" in v:
                        if not self._wildcard_match(row_val, v):
                            mismatch = True
                            break
                    elif row_val != v:
                        mismatch = True
                        break
            if mismatch:
                continue
            results.append(row)

        if order_by:
            results.sort(key=lambda r: r.get(order_by), reverse=descending)
        if select:
            results = [{k: r.get(k) for k in select} for r in results]
        if limit is not None:
            results = results[:limit]
        return results

    def get_columns(self, table: str) -> Optional[List[str]]:
        rows = self._all_rows(table)
        keys = set()
        for r in rows:
            keys.update(r.keys())
        return sorted(keys) if keys else []


class HybridSupabaseRedisAdapter:
    """Supabase primary adapter with Redis cache mirror for reads."""

    def __init__(self, primary: Any, cache: RedisHashAdapter):
        self.primary = primary
        self.cache = cache
        self.capabilities = getattr(primary, "capabilities", {})

    def write(self, table: str, record: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = self.primary.write(table, record)
            self.cache.write(table, result or record)
            return result
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("Supabase write failed, using Redis cache", extra={"error": str(exc)})
            return self.cache.write(table, record)

    def batch_write(self, table: str, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        try:
            result = self.primary.batch_write(table, records)
            for r in result or []:
                self.cache.write(table, r)
            return result
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("Supabase batch_write failed, using Redis cache", extra={"error": str(exc)})
            return [self.cache.write(table, r) for r in records]

    def upsert(self, table: str, record: Dict[str, Any], on_conflict: Optional[List[str]] = None) -> Dict[str, Any]:
        try:
            result = self.primary.upsert(table, record, on_conflict=on_conflict)
            self.cache.write(table, result or record)
            return result
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("Supabase upsert failed, using Redis cache: %s", str(exc), extra={"error": str(exc), "table": table, "record_keys": list(record.keys()) if record else []})
            return self.cache.upsert(table, record, on_conflict=on_conflict)

    def read(self, table: str, id_value: Any, id_column: str = "id") -> Optional[Dict[str, Any]]:
        record = None
        try:
            record = self.primary.read(table, id_value, id_column=id_column)
        except Exception:
            record = None
        if record:
            self.cache.write(table, record)
            return record
        return self.cache.read(table, id_value, id_column=id_column)

    def query(
        self,
        table: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        order_by: Optional[str] = None,
        descending: bool = False,
        select: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        try:
            result = self.primary.query(table, filters=filters, limit=limit, order_by=order_by, descending=descending, select=select)
            if result:
                for r in result:
                    self.cache.write(table, r)
                return result
        except Exception:
            result = None
        return self.cache.query(table, filters=filters, limit=limit, order_by=order_by, descending=descending, select=select)

    def get_columns(self, table: str) -> Optional[List[str]]:
        try:
            cols = self.primary.get_columns(table)
            if cols:
                return cols
        except Exception:
            cols = None
        return self.cache.get_columns(table)


class PersistenceAgentConsumer:
    """
    Redis Streams consumer for Persistence Agent.
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        tenant_id: str,
        consumer_group: str = "persistence_workers",
        consumer_name: Optional[str] = None,
        llm_config: Optional[Dict[str, Any]] = None,
    ):
        self.redis_client = redis_client
        self.tenant_id = tenant_id
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name or f"worker_{id(self)}"

        self.task_stream = f"{tenant_id}:agents:persistence:tasks"
        self.result_stream = f"{tenant_id}:agents:persistence:results"

        cache_adapter = RedisHashAdapter(redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"), tenant_id=tenant_id)
        adapter = cache_adapter
        if SupabaseAdapter and os.getenv("SUPABASE_URL"):
            supabase_key = os.getenv("SUPABASE_PERSISTENCE_JWT") or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
            if supabase_key:
                try:
                    supabase_adapter = SupabaseAdapter(
                        os.getenv("SUPABASE_URL"),
                        supabase_key,
                        anon_key=os.getenv("SUPABASE_ANON_KEY"),
                    )
                    adapter = HybridSupabaseRedisAdapter(primary=supabase_adapter, cache=cache_adapter)
                    logger.info("Persistence consumer using SupabaseAdapter with Redis cache")
                except Exception as e:
                    logger.warning(f"Supabase adapter init failed, using Redis cache fallback: {e}")
            else:
                logger.info("SUPABASE_URL set but no key provided; using Redis cache adapter")
        else:
            logger.info("Supabase adapter not available; using Redis cache adapter")

        service = PersistenceService(
            adapter=adapter,
            write_allowlist=get_write_allowlist(),
            read_allowlist=get_read_allowlist(),
        )

        model = llm_config.get("model", "gpt-4o-mini") if llm_config else "gpt-4o-mini"

        agent = PersistenceAgent(
            redis_client=redis_client,
            tenant_id=tenant_id,
            model=model,
            service=service,
        )
        self.harness = PersistenceAgentHarness(agent=agent)

        logger.info(
            f"Persistence consumer initialized for tenant '{tenant_id}'",
            extra={
                "tenant_id": tenant_id,
                "task_stream": self.task_stream,
                "result_stream": self.result_stream,
                "consumer_group": self.consumer_group,
                "consumer_name": self.consumer_name,
            },
        )

    @staticmethod
    def _normalize_result(result: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure persistence results always include status/result keys."""
        if not isinstance(result, dict):
            return {"status": "success", "result": result}

        status = result.get("status")
        if status == "completed":
            status = "success"
        if not status:
            status = "success"

        payload_result = result.get("result")
        if payload_result is None and "record" in result:
            payload_result = result.get("record")
        elif payload_result is None and "records" in result:
            payload_result = result.get("records")
        elif payload_result is None:
            payload_result = {k: v for k, v in result.items() if k not in {"status", "metadata"}}

        normalized = {k: v for k, v in result.items() if k not in {"status", "result"}}
        normalized["status"] = status
        normalized["result"] = payload_result
        return normalized

    async def ensure_consumer_group(self):
        try:
            await self.redis_client.xgroup_create(
                name=self.task_stream,
                groupname=self.consumer_group,
                id="0",
                mkstream=True,
            )
            logger.info(f"Created consumer group '{self.consumer_group}' on stream '{self.task_stream}'")
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                logger.error(f"Error creating consumer group: {e}")
                raise
            logger.debug(f"Consumer group '{self.consumer_group}' already exists")

    async def process_task(self, message_id: str, message_data: Dict[str, bytes]):
        try:
            envelope = from_redis_message(message_data)

            logger.info(
                f"Processing persistence task: {envelope.metadata.task_id}",
                extra={
                    "message_id": message_id,
                    "task_id": envelope.metadata.task_id,
                    "correlation_id": envelope.metadata.correlation_id,
                    "source": envelope.metadata.source,
                },
            )

            task_data = envelope.payload

            context = {
                "request_id": envelope.metadata.task_id,
                "correlation_id": envelope.metadata.correlation_id,
                "tenant_id": self.tenant_id,
                "source": envelope.metadata.source,
            }

            result = await self.harness.execute(task_data, context)
            logger.info("Persistence harness raw result", extra={"task_id": envelope.metadata.task_id, "result": result})
            result = self._normalize_result(result)
            logger.info("Persistence normalized result", extra={"task_id": envelope.metadata.task_id, "result": result})

            if result.get("status") == "error":
                result_envelope = create_error_envelope(
                    original=envelope,
                    error_msg=result.get("error", "Unknown error"),
                    source="agents:persistence",
                    code="PERSISTENCE_ERROR",
                )
            else:
                result_envelope = create_result_envelope(
                    original=envelope,
                    payload=result,
                    source="agents:persistence",
                )

            await self.redis_client.xadd(
                self.result_stream,
                to_redis_fields(result_envelope),
            )

            logger.info(
                f"Published persistence result: {envelope.metadata.task_id}",
                extra={
                    "task_id": envelope.metadata.task_id,
                    "result_stream": self.result_stream,
                    "status": result.get("status"),
                },
            )

            await self.redis_client.xack(
                self.task_stream,
                self.consumer_group,
                message_id,
            )

        except Exception as e:
            logger.error(
                f"Error processing persistence task: {e}",
                extra={"message_id": message_id},
                exc_info=True,
            )

    async def run(self, block_ms: int = 5000):
        await self.ensure_consumer_group()

        logger.info(
            f"Starting persistence consumer loop",
            extra={
                "consumer_group": self.consumer_group,
                "consumer_name": self.consumer_name,
                "task_stream": self.task_stream,
            },
        )

        while True:
            try:
                messages = await self.redis_client.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.consumer_name,
                    streams={self.task_stream: ">"},
                    count=1,
                    block=block_ms,
                )

                if not messages:
                    continue

                for _stream, stream_messages in messages:
                    for message_id, message_data in stream_messages:
                        await self.process_task(message_id, message_data)

            except asyncio.CancelledError:
                logger.info("Persistence consumer shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in persistence consumer loop: {e}", exc_info=True)
                await asyncio.sleep(5)


async def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_password = os.getenv("REDIS_PASSWORD")
    tenant_id = os.getenv("TENANT_ID", "agentic-dev")

    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        redis_client = redis.from_url(redis_url, decode_responses=False)
    else:
        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=False,
        )

    try:
        await redis_client.ping()
        logger.info(f"Connected to Redis at {redis_host}:{redis_port}")

        consumer = PersistenceAgentConsumer(
            redis_client=redis_client,
            tenant_id=tenant_id,
        )

        await consumer.run()

    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    asyncio.run(main())
