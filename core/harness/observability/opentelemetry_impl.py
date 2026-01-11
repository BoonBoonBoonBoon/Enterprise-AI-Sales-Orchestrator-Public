"""
OpenTelemetry Observability Backend

Uses OpenTelemetry (CNCF standard) for distributed tracing.
Good for: Production, vendor-agnostic, exports to multiple backends

Exports to: Jaeger, Zipkin, Honeycomb, Datadog, New Relic, AWS X-Ray

Installation:
    pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
"""

import logging
from typing import Dict, Any, Optional

from core.harness.interfaces import IObservability

logger = logging.getLogger(__name__)

# Try to import OpenTelemetry (optional dependency)
try:
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, ConsoleMetricExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    logger.warning(
        "OpenTelemetry not installed. Install with: "
        "pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp"
    )


class OpenTelemetryObservability(IObservability):
    """
    OpenTelemetry-based observability (CNCF standard).
    
    Vendor-agnostic distributed tracing and metrics.
    Exports to any OTLP-compatible backend.
    
    Requires installation:
        pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
    
    Example:
        # Console exporter (development)
        obs = OpenTelemetryObservability(
            service_name="agentic-system",
            exporter_endpoint=None  # Uses console
        )
        
        # OTLP exporter (production)
        obs = OpenTelemetryObservability(
            service_name="agentic-system",
            exporter_endpoint="http://localhost:4317"  # Jaeger, Collector, etc.
        )
        
        # Usage
        with obs.start_span("operation") as span:
            span.set_attribute("key", "value")
            obs.record_metric("requests", 1.0, {"status": "success"})
    """
    
    def __init__(
        self,
        service_name: str = "agentic-system",
        exporter_endpoint: Optional[str] = None
    ):
        """
        Initialize OpenTelemetry observability.
        
        Args:
            service_name: Service name for traces/metrics
            exporter_endpoint: OTLP endpoint (None = console exporter for dev)
        """
        if not OPENTELEMETRY_AVAILABLE:
            raise ImportError(
                "OpenTelemetry not installed. Install with: "
                "pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp"
            )
        
        self.service_name = service_name
        self.exporter_endpoint = exporter_endpoint
        
        # Initialize tracer
        self._setup_tracer()
        
        # Initialize meter (metrics)
        self._setup_meter()
        
        logger.info(
            f"OpenTelemetryObservability initialized: service={service_name}, "
            f"endpoint={exporter_endpoint or 'console'}"
        )
    
    def _setup_tracer(self):
        """Set up OpenTelemetry tracer"""
        provider = TracerProvider()
        
        # Choose exporter
        if self.exporter_endpoint:
            # OTLP exporter to collector/backend
            exporter = OTLPSpanExporter(endpoint=self.exporter_endpoint)
        else:
            # Console exporter for development
            exporter = ConsoleSpanExporter()
        
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
        
        trace.set_tracer_provider(provider)
        self.tracer = trace.get_tracer(self.service_name)
    
    def _setup_meter(self):
        """Set up OpenTelemetry meter (metrics)"""
        # Choose exporter
        if self.exporter_endpoint:
            # OTLP metric exporter
            exporter = OTLPMetricExporter(endpoint=self.exporter_endpoint)
        else:
            # Console metric exporter for development
            exporter = ConsoleMetricExporter()
        
        reader = PeriodicExportingMetricReader(exporter)
        provider = MeterProvider(metric_readers=[reader])
        
        metrics.set_meter_provider(provider)
        self.meter = metrics.get_meter(self.service_name)
        
        # Create metric instruments
        self.counters = {}
        self.gauges = {}
    
    def start_span(self, name: str):
        """
        Start OpenTelemetry span (context manager).
        
        Args:
            name: Span name
        
        Returns:
            OpenTelemetry span context manager
        """
        return self.tracer.start_as_current_span(name)
    
    def record_metric(self, name: str, value: float, tags: Dict[str, str]):
        """
        Record metric to OpenTelemetry.
        
        Args:
            name: Metric name
            value: Metric value
            tags: Metric tags (attributes)
        """
        # Get or create counter
        if name not in self.counters:
            self.counters[name] = self.meter.create_counter(
                name=name,
                description=f"Counter for {name}"
            )
        
        # Record metric with attributes
        self.counters[name].add(value, attributes=tags)
    
    def log_event(self, level: str, message: str, context: Dict[str, Any]):
        """
        Log event to current OpenTelemetry span.
        
        Args:
            level: Log level
            message: Event message
            context: Event context (becomes span attributes)
        """
        span = trace.get_current_span()
        if span:
            # Add event to span
            span.add_event(message, attributes=context)
            
            # Also set as attributes if important
            if level in ("ERROR", "CRITICAL"):
                span.set_attribute("error", True)
                span.set_attribute("error.message", message)
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        return (
            f"OpenTelemetryObservability("
            f"service={self.service_name}, "
            f"endpoint={self.exporter_endpoint or 'console'})"
        )
