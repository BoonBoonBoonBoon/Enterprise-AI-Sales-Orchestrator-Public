"""
Smoke tests for basic system health.

These tests verify critical infrastructure is available and configured.
"""

import pytest
import os
import redis


@pytest.mark.smoke
def test_redis_connectivity():
    """Test Redis is reachable and responding."""
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    client = None
    try:
        client = redis.from_url(redis_url, socket_connect_timeout=5)
        result = client.ping()
        assert result is True
        print(f"✅ Redis connected: {redis_url}")
    except redis.ConnectionError as e:
        pytest.fail(f"❌ Redis connection failed: {e}")
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
            try:
                client.connection_pool.disconnect()
            except Exception:
                pass


@pytest.mark.smoke
def test_redis_streams_available():
    """Test Redis streams functionality is available."""
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    client = redis.from_url(redis_url, decode_responses=True)
    
    # Test XADD command
    test_stream = "smoke:test:stream"
    try:
        message_id = client.xadd(test_stream, {"test": "data"})
        assert message_id is not None
		
        # Cleanup
        client.delete(test_stream)
        print("✅ Redis streams available")
    except Exception as e:
        pytest.fail(f"❌ Redis streams not available: {e}")
    finally:
        try:
            client.close()
        except Exception:
            pass
        try:
            client.connection_pool.disconnect()
        except Exception:
            pass


@pytest.mark.smoke
def test_environment_variables_configured():
    """Test critical environment variables are set."""
    required_vars = {
        'REDIS_URL': os.environ.get('REDIS_URL'),
    }
    
    optional_vars = {
        'OPENAI_API_KEY': os.environ.get('OPENAI_API_KEY'),
        'ANTHROPIC_API_KEY': os.environ.get('ANTHROPIC_API_KEY'),
        'DATABASE_URL': os.environ.get('DATABASE_URL'),
    }
    
    # Check required
    missing = [k for k, v in required_vars.items() if not v]
    if missing:
        pytest.fail(f"❌ Missing required env vars: {', '.join(missing)}")
    
    # Warn about optional
    missing_optional = [k for k, v in optional_vars.items() if not v]
    if missing_optional:
        print(f"⚠️  Optional env vars not set: {', '.join(missing_optional)}")
    
    print(f"✅ Environment variables configured")


@pytest.mark.smoke
def test_python_version():
    """Test Python version is 3.11+."""
    import sys
    
    version = sys.version_info
    assert version.major == 3
    assert version.minor >= 11
    
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")


@pytest.mark.smoke
def test_critical_imports():
    """Test critical modules can be imported."""
    try:
        from core.envelope.typed_envelope import Envelope
        from core.utils.graceful_shutdown import GracefulShutdownMixin
        from core.utils.rate_limiter import RateLimiter, RateLimitConfig
        
        assert Envelope is not None
        assert GracefulShutdownMixin is not None
        assert RateLimiter is not None
        assert RateLimitConfig is not None
        
        print("✅ Critical imports successful")
    except ImportError as e:
        pytest.fail(f"❌ Import failed: {e}")


@pytest.mark.smoke
def test_redis_memory_available():
    """Test Redis has sufficient memory available."""
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    client = redis.from_url(redis_url)
    try:
        info = client.info('memory')
        used_memory_mb = info['used_memory'] / (1024 * 1024)
        max_memory = info.get('maxmemory', 0)
		
        print(f"✅ Redis memory: {used_memory_mb:.2f} MB used")
		
        # Warn if using more than 1GB
        if used_memory_mb > 1024:
            print(f"⚠️  Redis using {used_memory_mb:.2f} MB (>1GB)")
    finally:
        try:
            client.close()
        except Exception:
            pass
        try:
            client.connection_pool.disconnect()
        except Exception:
            pass


@pytest.mark.smoke
def test_rate_limiter_configuration():
    """Test rate limiter can be initialized."""
    from core.utils.rate_limiter import RateLimiter, RateLimitConfig
    
    cfg = RateLimitConfig(rate_per_second=10, burst_size=20, backend="memory", enabled=True)
    limiter = RateLimiter(config=cfg)
    assert limiter.acquire(key="smoke", tokens=1, block=False) is True
    
    print("✅ Rate limiter initialized")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
