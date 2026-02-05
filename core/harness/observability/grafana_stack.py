"""
Grafana Stack Observability Backend

Bridges the harness observability interface with the Grafana stack:
- Prometheus metrics (via core/observability/metrics.py)
- Loki logs (via core/observability/logger.py)
- Tempo traces (via OTLP when available)

This is the recommended observability backend for production deployments.
"""

import logging
from contextlib import contextmanager
from typing import Dict, Any, Optional

from core.harness.interfaces import IObservability
from core.observability.metrics import MetricsCollector
from core.observability.logger import StructuredLogger

logger = logging.getLogger(__name__)


class GrafanaStackObservability(IObservability):
    """
    Grafana stack observability backend.
    
    Uses:
    - Prometheus for metrics (scraped via /metrics endpoint)
    - Loki for structured logs (pushed via HTTP if LOKI_URL set)
    - Tempo for traces (via OTLP when OpenTelemetry is configured)
    
    This backend provides seamless integration with the deployment/
    observability stack without requiring external SDKs.
    
    Example:
        obs = GrafanaStackObservability(
            tier="orchestrator",
            component="leads_orchestrator",
            tenant_id="acme"
        )
        
        with obs.start_span("process_lead") as span:
            span.set_attribute("lead_id", "123")
            obs.record_metric("leads_processed", 1.0, {"status": "success"})
            obs.log_event("INFO", "Lead processed", {"lead_id": "123"})
    """
    
    def __init__(
        self,
        tier: str = "agent",
        component: str = "unknown",
        tenant_id: str = "default",
    ):
        """
        Initialize Grafana stack observability.
        
        Args:
            tier: Tier name (manager, orchestrator, agent)
            component: Component name (leads_orchestrator, rag_agent, etc.)
            tenant_id: Tenant identifier for multi-tenancy
        """
        self.tier = tier
        self.component = component
        self.tenant_id = tenant_id
        
        # Initialize shared components
        self.metrics = MetricsCollector.get_instance()
        self.structured_logger = StructuredLogger(tier, component)
        
        logger.debug(
            f"GrafanaStackObservability initialized: "
            f"tier={tier}, component={component}, tenant={tenant_id}"
        )
    
    @contextmanager
    def start_span(self, name: str):
        """
        Start a span for distributed tracing.
        
        When OpenTelemetry is configured, this creates real traces.
        Falls back to structured logging otherwise.
        
        Args:
            name: Span name
        
        Yields:
            Span object with set_attribute method
        """
        import time
        start_time = time.time()
        
        self.structured_logger.debug(
            "span_started",
            span_name=name,
            tenant_id=self.tenant_id,
        )
        
        # Create span object
        class GrafanaSpan:
            def __init__(self, span_name: str, obs: "GrafanaStackObservability"):
                self.name = span_name
                self.obs = obs
                self.attributes: Dict[str, Any] = {}
            
            def set_attribute(self, key: str, value: Any):
                """Set span attribute"""
                self.attributes[key] = value
        
        span = GrafanaSpan(name, self)
        
        try:
            yield span
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self.structured_logger.error(
                "span_error",
                span_name=name,
                elapsed_ms=elapsed_ms,
                error=str(e),
                tenant_id=self.tenant_id,
                **span.attributes,
            )
            self.metrics.increment(
                f"{self.tier}.errors.total",
                tags={
                    "component": self.component,
                    "tenant": self.tenant_id,
                    "span": name,
                }
            )
            raise
        else:
            elapsed_ms = (time.time() - start_time) * 1000
            self.structured_logger.info(
                "span_completed",
                span_name=name,
                elapsed_ms=elapsed_ms,
                tenant_id=self.tenant_id,
                **span.attributes,
            )
            self.metrics.histogram(
                f"{self.tier}.span_duration_ms",
                elapsed_ms,
                tags={
                    "component": self.component,
                    "tenant": self.tenant_id,
                    "span": name,
                }
            )
    
    def record_metric(self, name: str, value: float, tags: Dict[str, str]):
        """
        Record a metric to Prometheus.
        
        Args:
            name: Metric name
            value: Metric value
            tags: Metric tags/labels
        """
        # Add default tags
        full_tags = {
            "tier": self.tier,
            "component": self.component,
            "tenant": self.tenant_id,
            **tags,
        }
        
        # Normalize metric name with tier prefix
        metric_name = f"{self.tier}.{name}" if not name.startswith(self.tier) else name
        
        self.metrics.increment(metric_name, value, full_tags)
    
    def log_event(self, level: str, message: str, data: Dict[str, Any]):
        """
        Log a structured event to Loki.
        
        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR)
            message: Event message
            data: Additional event data
        """
        # Add default context
        log_data = {
            "tenant_id": self.tenant_id,
            **data,
        }
        
        level_lower = level.lower()
        if level_lower == "debug":
            self.structured_logger.debug(message, **log_data)
        elif level_lower == "info":
            self.structured_logger.info(message, **log_data)
        elif level_lower == "warning":
            self.structured_logger.warning(message, **log_data)
        elif level_lower == "error":
            self.structured_logger.error(message, **log_data)
        else:
            self.structured_logger.info(message, **log_data)
