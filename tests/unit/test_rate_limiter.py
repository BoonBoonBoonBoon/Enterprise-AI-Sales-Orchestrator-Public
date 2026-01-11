"""Unit tests for `core.utils.rate_limiter`.

These tests target the current rate limiter API used by harness/workers:
- `TokenBucket` / `SlidingWindow` primitives
- `RateLimitConfig` + `RateLimiter`
"""

import time

import pytest

from core.utils.rate_limiter import RateLimitConfig, RateLimiter, SlidingWindow, TokenBucket


@pytest.mark.unit
class TestTokenBucket:
    """Test token bucket rate limiting algorithm."""
    
    def test_creation(self):
        """Test token bucket can be created with valid parameters."""
        bucket = TokenBucket(rate=10, capacity=10)
        assert bucket.rate == 10
        assert bucket.capacity == 10
        assert bucket.tokens == 10
    
    def test_acquire_within_capacity(self):
        """Test acquiring tokens within capacity succeeds."""
        bucket = TokenBucket(rate=10, capacity=10)
        
        # Should succeed for capacity number of requests
        for _ in range(10):
            assert bucket.acquire(block=False) is True
    
    def test_acquire_exceeds_capacity(self):
        """Test acquiring beyond capacity fails immediately."""
        bucket = TokenBucket(rate=10, capacity=5)
        
        # Exhaust capacity
        for _ in range(5):
            bucket.acquire(block=False)
        
        # Next request should fail
        assert bucket.acquire(block=False) is False
    
    def test_token_refill(self):
        """Test tokens are refilled over time."""
        bucket = TokenBucket(rate=10, capacity=10)
        
        # Exhaust bucket
        for _ in range(10):
            bucket.acquire(block=False)
        
        # Wait for refill (0.1 seconds = 1 token at rate=10/sec)
        time.sleep(0.15)
        
        # Should have 1-2 tokens now
        assert bucket.acquire(block=False) is True
    
    def test_zero_rate_always_blocks(self):
        """With rate=0, bucket should not refill after initial capacity."""
        bucket = TokenBucket(rate=0, capacity=2)
        assert bucket.acquire(block=False) is True
        assert bucket.acquire(block=False) is True
        assert bucket.acquire(block=False) is False
    
    def test_invalid_capacity_raises_error(self):
        """Test negative capacity raises ValueError."""
        with pytest.raises(ValueError):
            TokenBucket(rate=10, capacity=-1)


@pytest.mark.unit
class TestSlidingWindow:
    """Test sliding window rate limiting algorithm."""
    
    def test_creation(self):
        """Test sliding window can be created."""
        window = SlidingWindow(rate=10, window_size=1.0)
        assert window.rate == 10
        assert window.window_size == 1.0
    
    def test_acquire_within_rate(self):
        """Test acquiring within rate limit succeeds."""
        window = SlidingWindow(rate=5, window_size=1.0)
        
        # Should succeed for rate number of requests
        for _ in range(5):
            assert window.acquire(block=False) is True
    
    def test_acquire_exceeds_rate(self):
        """Test acquiring beyond rate fails."""
        window = SlidingWindow(rate=5, window_size=1.0)
        
        # Exhaust rate limit
        for _ in range(5):
            window.acquire(block=False)
        
        # Next request should fail
        assert window.acquire(block=False) is False
    
    def test_window_slides(self):
        """Test window slides and old requests are forgotten."""
        window = SlidingWindow(rate=5, window_size=0.5)
        
        # Make 5 requests
        for _ in range(5):
            window.acquire(block=False)
        
        # Wait for window to slide
        time.sleep(0.6)
        
        # Should be able to make new requests
        assert window.acquire(block=False) is True


@pytest.mark.unit
class TestRateLimiter:
    """Test unified rate limiter interface."""

    def test_disabled_rate_limiter_always_succeeds(self):
        """Disabled limiter should always allow."""
        limiter = RateLimiter(config=RateLimitConfig(enabled=False))
        for _ in range(100):
            assert limiter.acquire(key="any", block=False) is True

    def test_memory_backend_creates_local_limiter(self):
        """Memory backend should create a per-key limiter instance."""
        limiter = RateLimiter(
            config=RateLimitConfig(
                enabled=True,
                backend="memory",
                algorithm="token_bucket",
                rate_per_second=10,
                burst_size=10,
            )
        )
        assert limiter.acquire(key="worker-1", block=False) is True
        # After first acquire, the local limiter cache should have an entry.
        assert "worker-1" in limiter._local_limiters


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
