import os

import pytest


@pytest.fixture(scope="session")
def tenant_id() -> str:
    return os.getenv("TENANT_ID", "agentic-dev")


@pytest.fixture
def client():
    """Sync Redis client (decode_responses=True)."""
    import redis

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    r = redis.Redis.from_url(redis_url, decode_responses=True)
    r.ping()
    return r


@pytest.fixture(autouse=True)
def _cleanup_test_tenant_redis_keys(client):
    """Keep integration tests isolated from each other.

    We only delete keys belonging to the dedicated test tenant(s) and test namespace.
    """
    patterns = [
        "test-tenant:*",
        "test:test-tenant:*",
        "test:*",
    ]
    for pattern in patterns:
        for key in client.scan_iter(pattern):
            client.delete(key)
    yield


@pytest.fixture
async def redis_client():
    """Async Redis client for tests that use redis.asyncio."""
    import redis.asyncio as redis

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    r = redis.Redis.from_url(redis_url, decode_responses=True)
    await r.ping()
    try:
        yield r
    finally:
        try:
            await r.close()
        except Exception:
            pass
        try:
            await r.connection_pool.disconnect()
        except Exception:
            pass
