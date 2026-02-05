"""Rate limiting middleware for the gateway.

Implements a sliding window rate limiter using Redis for distributed rate limiting.
Falls back to in-memory rate limiting if Redis is unavailable.
"""

import asyncio
import time
from collections import defaultdict
from typing import Optional, Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .config import settings


class InMemoryRateLimiter:
    """Simple in-memory rate limiter for single-instance deployments."""
    
    def __init__(self):
        self.requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> Tuple[bool, int, int]:
        """Check if request is allowed under rate limit.
        
        Returns:
            Tuple of (allowed, remaining, reset_time)
        """
        async with self._lock:
            now = time.time()
            window_start = now - window_seconds
            
            # Clean old requests
            self.requests[key] = [
                ts for ts in self.requests[key] if ts > window_start
            ]
            
            current_count = len(self.requests[key])
            remaining = max(0, max_requests - current_count)
            reset_time = int(window_start + window_seconds)
            
            if current_count >= max_requests:
                return False, 0, reset_time
            
            self.requests[key].append(now)
            return True, remaining - 1, reset_time


class RedisRateLimiter:
    """Redis-based rate limiter for distributed deployments."""
    
    def __init__(self):
        self._redis = None
    
    async def _get_redis(self):
        if self._redis is None:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                )
            except Exception:
                return None
        return self._redis
    
    async def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> Tuple[bool, int, int]:
        """Check if request is allowed under rate limit using Redis."""
        redis_client = await self._get_redis()
        if redis_client is None:
            # Redis unavailable - allow request (fail open)
            return True, max_requests, 0
        
        try:
            now = time.time()
            window_key = f"rate_limit:{key}:{int(now // window_seconds)}"
            
            pipe = redis_client.pipeline()
            pipe.incr(window_key)
            pipe.expire(window_key, window_seconds + 1)
            results = await pipe.execute()
            
            current_count = results[0]
            remaining = max(0, max_requests - current_count)
            reset_time = int((int(now // window_seconds) + 1) * window_seconds)
            
            if current_count > max_requests:
                return False, 0, reset_time
            
            return True, remaining, reset_time
        except Exception:
            # Redis error - fail open
            return True, max_requests, 0


# Global rate limiter instance
_in_memory_limiter = InMemoryRateLimiter()
_redis_limiter = RedisRateLimiter()


async def check_rate_limit(
    key: str,
    max_requests: Optional[int] = None,
    window_seconds: Optional[int] = None,
    use_redis: bool = True,
) -> Tuple[bool, int, int]:
    """Check rate limit for a given key.
    
    Args:
        key: Unique identifier for rate limiting (e.g., IP, user ID)
        max_requests: Maximum requests per window (default from settings)
        window_seconds: Window size in seconds (default from settings)
        use_redis: Whether to use Redis (falls back to in-memory if unavailable)
    
    Returns:
        Tuple of (allowed, remaining, reset_time)
    """
    max_requests = max_requests or settings.RATE_LIMIT_REQUESTS
    window_seconds = window_seconds or settings.RATE_LIMIT_WINDOW_SECONDS
    
    if use_redis and settings.REDIS_URL:
        return await _redis_limiter.check_rate_limit(key, max_requests, window_seconds)
    
    return await _in_memory_limiter.check_rate_limit(key, max_requests, window_seconds)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to apply rate limiting to requests.
    
    Rate limits are applied per IP address by default, with stricter limits
    on authentication endpoints to prevent brute force attacks.
    """
    
    # Paths with stricter rate limits (auth endpoints)
    AUTH_PATHS = {
        "/api/v1/auth/login": (5, 60),      # 5 requests per minute
        "/api/v1/auth/signup": (3, 60),     # 3 signups per minute
        "/api/v1/auth/dev-login": (10, 60), # 10 dev logins per minute
    }
    
    # Paths to skip rate limiting entirely
    SKIP_PATHS = {
        "/api/v1/docs",
        "/api/v1/redoc",
        "/api/v1/openapi.json",
        "/api/v1/health",
        "/",
    }
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request, considering proxies."""
        # Check X-Forwarded-For header first (for reverse proxies)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Take the first IP (original client)
            return forwarded.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        
        # Fall back to direct client IP
        if request.client:
            return request.client.host
        
        return "unknown"
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for certain paths
        path = request.url.path
        if path in self.SKIP_PATHS:
            return await call_next(request)
        
        # Get client identifier
        client_ip = self._get_client_ip(request)
        
        # Determine rate limit parameters
        if path in self.AUTH_PATHS:
            max_requests, window_seconds = self.AUTH_PATHS[path]
            rate_key = f"{client_ip}:{path}"
        else:
            max_requests = settings.RATE_LIMIT_REQUESTS
            window_seconds = settings.RATE_LIMIT_WINDOW_SECONDS
            rate_key = client_ip
        
        # Check rate limit
        allowed, remaining, reset_time = await check_rate_limit(
            rate_key, max_requests, window_seconds
        )
        
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests",
                    "retry_after": reset_time - int(time.time()),
                },
                headers={
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(max(1, reset_time - int(time.time()))),
                },
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        
        return response
