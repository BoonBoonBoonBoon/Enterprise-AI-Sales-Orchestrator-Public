"""
Observability Context - Unified logging, metrics, and tracing

Supports multiple backends:
- Loki (logs) via HTTP push
- Prometheus (metrics) via /metrics endpoint
- Redis Streams (audit trail)
- Optional: DataDog, OpenTelemetry
"""

import os
import json
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager

try:
    import redis
except ImportError:
    redis = None

from .logger import StructuredLogger
from .metrics import MetricsCollector
from .audit_stream import AuditStreamWriter
from .backends import get_backend

logger = logging.getLogger(__name__)


class ObservabilityContext:
    """
    Context manager for observability across all tiers.
    
    Usage:
        with ObservabilityContext(
            tier="manager",
            component="manager_agent",
            tenant_id=tenant_id,
        ) as obs:
            result = do_work()
            obs.log_decision(intent="outreach", confidence=0.85)
            obs.track_cost(0.0002)
    """
    
    def __init__(
        self,
        tier: str,  # manager | orchestrator | agent
        component: str,
        tenant_id: str = "default",
        execution_id: Optional[str] = None,
        redis_client: Optional[Any] = None,
    ):
        self.tier = tier
        self.component = component
        self.tenant_id = tenant_id
        self.execution_id = execution_id or f"exec_{time.time()}"
        self.redis_client = redis_client
        
        # Initialize components
        self.structured_logger = StructuredLogger(tier, component)
        self.metrics = MetricsCollector.get_instance()
        self.audit_stream = AuditStreamWriter(redis_client) if redis_client else None
        self.backend = get_backend()
        
        # Context tracking
        self.start_time = None
        self.metadata = {
            "tier": tier,
            "component": component,
            "tenant_id": tenant_id,
            "execution_id": self.execution_id,
        }
        self.decision_data = {}
    
    def __enter__(self):
        self.start_time = time.time()
        self.structured_logger.info("execution_started", **self.metadata)
        self.backend.start_span(f"{self.tier}.{self.component}", self.metadata)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed_ms = (time.time() - self.start_time) * 1000
        
        if exc_type:
            self.structured_logger.error(
                "execution_failed",
                error=str(exc_val),
                elapsed_ms=elapsed_ms,
                **self.metadata,
            )
            self.metrics.increment(
                f"{self.tier}.errors.total",
                tags={"component": self.component, "tenant": self.tenant_id}
            )
        else:
            self.structured_logger.info(
                "execution_completed",
                elapsed_ms=elapsed_ms,
                **self.metadata,
                **self.decision_data,
            )
        
        # Record latency
        self.metrics.histogram(
            f"{self.tier}.latency_ms",
            elapsed_ms,
            tags={"component": self.component, "tenant": self.tenant_id}
        )
        
        # Write to audit stream
        if self.audit_stream:
            self.audit_stream.write(
                tier=self.tier,
                tenant_id=self.tenant_id,
                execution_id=self.execution_id,
                data={
                    **self.metadata,
                    **self.decision_data,
                    "elapsed_ms": elapsed_ms,
                    "success": exc_type is None,
                }
            )
        
        # Close span
        self.backend.end_span(elapsed_ms, success=(exc_type is None))
        
        return False  # Don't suppress exceptions
    
    def log_decision(self, **kwargs):
        """Log decision metadata (intent, confidence, orchestrators, etc.)"""
        self.decision_data.update(kwargs)
        self.structured_logger.info("decision", **self.metadata, **kwargs)
        
        # Emit decision-specific metrics
        if "intent" in kwargs:
            self.metrics.increment(
                f"{self.tier}.decisions.total",
                tags={
                    "intent": kwargs["intent"],
                    "tenant": self.tenant_id,
                    "component": self.component,
                }
            )
        
        if "confidence" in kwargs:
            self.metrics.histogram(
                f"{self.tier}.confidence",
                kwargs["confidence"],
                tags={"tenant": self.tenant_id}
            )
        
        if "used_fallback" in kwargs:
            self.metrics.increment(
                f"{self.tier}.fallback.total",
                tags={
                    "used_fallback": str(kwargs["used_fallback"]),
                    "tenant": self.tenant_id,
                }
            )
    
    def track_cost(self, cost_usd: float, currency: str = "USD"):
        """Track estimated cost for this execution"""
        self.decision_data["cost_usd"] = cost_usd
        self.metrics.increment(
            f"{self.tier}.cost_usd",
            value=cost_usd,
            tags={"tenant": self.tenant_id, "component": self.component}
        )
        
        # Per-tenant cost tracking in Redis
        if self.redis_client:
            month_key = datetime.now().strftime("%Y-%m")
            cost_key = f"cost:{self.tier}:{self.tenant_id}:{month_key}"
            try:
                self.redis_client.incrbyfloat(cost_key, cost_usd)
                self.redis_client.expire(cost_key, 60 * 60 * 24 * 35)  # 35 days
            except Exception as e:
                logger.warning(f"Failed to track cost in Redis: {e}")
    
    def increment(self, metric_name: str, value: float = 1.0, tags: Optional[Dict] = None):
        """Increment a counter metric"""
        all_tags = {"tenant": self.tenant_id, "component": self.component}
        if tags:
            all_tags.update(tags)
        self.metrics.increment(f"{self.tier}.{metric_name}", value, all_tags)
    
    def histogram(self, metric_name: str, value: float, tags: Optional[Dict] = None):
        """Record a histogram metric"""
        all_tags = {"tenant": self.tenant_id, "component": self.component}
        if tags:
            all_tags.update(tags)
        self.metrics.histogram(f"{self.tier}.{metric_name}", value, all_tags)
    
    def gauge(self, metric_name: str, value: float, tags: Optional[Dict] = None):
        """Set a gauge metric"""
        all_tags = {"tenant": self.tenant_id, "component": self.component}
        if tags:
            all_tags.update(tags)
        self.metrics.gauge(f"{self.tier}.{metric_name}", value, all_tags)
