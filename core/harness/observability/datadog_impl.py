"""
Datadog Observability Backend

Uses Datadog APM for distributed tracing and metrics.
Good for: Production with existing Datadog infrastructure

Installation:
    pip install ddtrace datadog
"""

import logging
from typing import Dict, Any

from core.harness.interfaces import IObservability

logger = logging.getLogger(__name__)

# Try to import Datadog (optional dependency)
try:
    from ddtrace import tracer
    import datadog
    
    DATADOG_AVAILABLE = True
except ImportError:
    DATADOG_AVAILABLE = False
    logger.warning(
        "Datadog not installed. Install with: pip install ddtrace datadog"
    )


class DatadogObservability(IObservability):
    """
    Datadog APM-based observability.
    
    Integrates with existing Datadog infrastructure.
    Provides distributed tracing and metrics.
    
    Requires installation:
        pip install ddtrace datadog
    
    Configuration:
        Set environment variables:
        - DD_SERVICE: Service name
        - DD_ENV: Environment (prod, staging, dev)
        - DD_AGENT_HOST: Datadog agent host
        - DD_TRACE_AGENT_PORT: Datadog agent port (default: 8126)
    
    Example:
        obs = DatadogObservability(service_name="agentic-system", env="production")
        
        with obs.start_span("operation") as span:
            span.set_attribute("key", "value")
            obs.record_metric("requests", 1.0, {"status": "success"})
    """
    
    def __init__(
        self,
        service_name: str = "agentic-system",
        env: str = "development"
    ):
        """
        Initialize Datadog observability.
        
        Args:
            service_name: Service name for Datadog APM
            env: Environment (production, staging, development)
        """
        if not DATADOG_AVAILABLE:
            raise ImportError(
                "Datadog not installed. Install with: pip install ddtrace datadog"
            )
        
        self.service_name = service_name
        self.env = env
        
        # Initialize Datadog
        datadog.initialize()
        
        # Configure tracer
        tracer.configure(
            hostname="localhost",
            port=8126,
        )
        
        logger.info(
            f"DatadogObservability initialized: service={service_name}, env={env}"
        )
    
    def start_span(self, name: str):
        """
        Start Datadog APM span (context manager).
        
        Args:
            name: Span name
        
        Returns:
            Datadog span context manager
        """
        return tracer.trace(
            name,
            service=self.service_name,
            resource=name
        )
    
    def record_metric(self, name: str, value: float, tags: Dict[str, str]):
        """
        Record metric to Datadog.
        
        Args:
            name: Metric name
            value: Metric value
            tags: Metric tags
        """
        # Convert tags dict to Datadog format
        tag_list = [f"{k}:{v}" for k, v in tags.items()]
        tag_list.append(f"service:{self.service_name}")
        tag_list.append(f"env:{self.env}")
        
        # Send gauge metric to Datadog
        datadog.statsd.gauge(name, value, tags=tag_list)
    
    def log_event(self, level: str, message: str, context: Dict[str, Any]):
        """
        Log event to Datadog (as event and span tag).
        
        Args:
            level: Log level
            message: Event message
            context: Event context
        """
        # Add to current span if exists
        span = tracer.current_span()
        if span:
            # Set span tags
            span.set_tag("event.level", level)
            span.set_tag("event.message", message)
            
            # Add context as tags
            for key, value in context.items():
                span.set_tag(f"event.{key}", value)
            
            # Mark span as error if level is ERROR or CRITICAL
            if level in ("ERROR", "CRITICAL"):
                span.error = 1
        
        # Also send as Datadog event
        tags = [f"{k}:{v}" for k, v in context.items()]
        tags.append(f"service:{self.service_name}")
        tags.append(f"env:{self.env}")
        tags.append(f"level:{level}")
        
        datadog.api.Event.create(
            title=message,
            text=str(context),
            tags=tags,
            alert_type="error" if level in ("ERROR", "CRITICAL") else "info"
        )
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        return f"DatadogObservability(service={self.service_name}, env={self.env})"
