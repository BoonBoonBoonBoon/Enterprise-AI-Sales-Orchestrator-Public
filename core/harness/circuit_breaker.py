"""
Circuit Breaker Pattern Implementation

Prevents cascading failures by failing fast when a service is degraded.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Service is failing, requests fail immediately
- HALF_OPEN: Testing if service has recovered

Transitions:
- CLOSED → OPEN: When failure threshold exceeded
- OPEN → HALF_OPEN: After recovery timeout
- HALF_OPEN → CLOSED: When success threshold met
- HALF_OPEN → OPEN: When test requests fail
"""

from __future__ import annotations

import time
import threading
from enum import Enum
from typing import Callable, Any, Optional, TypeVar, Generic
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5           # Failures before opening
    success_threshold: int = 2           # Successes to close from half-open
    timeout: float = 60.0                # Seconds before trying half-open
    half_open_max_calls: int = 3         # Max test calls in half-open
    expected_exceptions: tuple = (Exception,)  # Exceptions to count as failures
    name: str = "circuit_breaker"        # Name for logging


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


class CircuitBreaker(Generic[T]):
    """
    Circuit breaker that fails fast when downstream service is degraded.
    
    Usage:
        circuit = CircuitBreaker(
            failure_threshold=5,
            timeout=60,
            name="redis_client"
        )
        
        try:
            result = circuit.call(redis_client.xadd, stream, data)
        except CircuitBreakerOpenError:
            # Handle circuit open (service degraded)
            logger.error("Redis circuit open, using fallback")
    """
    
    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = threading.RLock()
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            return self._state
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing fast)."""
        return self.state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self.state == CircuitState.HALF_OPEN
    
    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function through circuit breaker.
        
        Args:
            func: Function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result from func
            
        Raises:
            CircuitBreakerOpenError: When circuit is open
            Exception: Original exception from func if circuit allows
        """
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    logger.warning(
                        f"Circuit breaker {self.config.name} is OPEN. "
                        f"Failing fast. Last failure: {self._last_failure_time}"
                    )
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker {self.config.name} is open"
                    )
            
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    logger.warning(
                        f"Circuit breaker {self.config.name} HALF_OPEN call limit reached"
                    )
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker {self.config.name} is testing (half-open)"
                    )
                self._half_open_calls += 1
        
        # Execute function outside lock
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.config.expected_exceptions as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self._last_failure_time is None:
            return True
        
        elapsed = time.time() - self._last_failure_time
        return elapsed >= self.config.timeout
    
    def _on_success(self):
        """Handle successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                logger.info(
                    f"Circuit breaker {self.config.name} HALF_OPEN success "
                    f"({self._success_count}/{self.config.success_threshold})"
                )
                
                if self._success_count >= self.config.success_threshold:
                    self._transition_to_closed()
            
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0
    
    def _on_failure(self):
        """Handle failed call."""
        with self._lock:
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                logger.warning(
                    f"Circuit breaker {self.config.name} failed in HALF_OPEN, "
                    "reopening circuit"
                )
                self._transition_to_open()
            
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                logger.warning(
                    f"Circuit breaker {self.config.name} failure "
                    f"({self._failure_count}/{self.config.failure_threshold})"
                )
                
                if self._failure_count >= self.config.failure_threshold:
                    self._transition_to_open()
    
    def _transition_to_open(self):
        """Transition to OPEN state."""
        self._state = CircuitState.OPEN
        self._success_count = 0
        self._half_open_calls = 0
        logger.error(
            f"Circuit breaker {self.config.name} transitioned to OPEN. "
            f"Will retry after {self.config.timeout}s"
        )
    
    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state."""
        self._state = CircuitState.HALF_OPEN
        self._success_count = 0
        self._half_open_calls = 0
        logger.info(
            f"Circuit breaker {self.config.name} transitioned to HALF_OPEN "
            "(testing recovery)"
        )
    
    def _transition_to_closed(self):
        """Transition to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        logger.info(
            f"Circuit breaker {self.config.name} transitioned to CLOSED "
            "(service recovered)"
        )
    
    def reset(self):
        """Manually reset circuit breaker to CLOSED state."""
        with self._lock:
            self._transition_to_closed()
            logger.info(f"Circuit breaker {self.config.name} manually reset")
    
    def get_stats(self) -> dict:
        """Get current circuit breaker statistics."""
        with self._lock:
            return {
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure_time": (
                    datetime.fromtimestamp(self._last_failure_time).isoformat()
                    if self._last_failure_time else None
                ),
                "half_open_calls": self._half_open_calls,
                "config": {
                    "name": self.config.name,
                    "failure_threshold": self.config.failure_threshold,
                    "success_threshold": self.config.success_threshold,
                    "timeout": self.config.timeout,
                }
            }


def circuit_breaker(
    failure_threshold: int = 5,
    timeout: float = 60.0,
    success_threshold: int = 2,
    name: str = "default"
):
    """
    Decorator to wrap function with circuit breaker.
    
    Usage:
        @circuit_breaker(failure_threshold=3, timeout=30, name="my_service")
        def call_external_api():
            return requests.get("https://api.example.com")
    """
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        timeout=timeout,
        success_threshold=success_threshold,
        name=name
    )
    breaker = CircuitBreaker(config)
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)
        wrapper.__circuit_breaker__ = breaker
        return wrapper
    return decorator
