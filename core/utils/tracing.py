"""
OpenTelemetry Tracing Utilities

Provides distributed tracing infrastructure for the agentic system.
Trace context propagates through Redis Streams message metadata fields.

Features:
- Automatic span creation for worker operations
- Redis Streams context propagation
- Support for Jaeger, Zipkin, and OTLP exporters
- Zero-config fallback (no-op tracer when disabled)

Usage:
    # In worker initialization
    from agent.utils.tracing import init_tracer, TracedWorker
    
    tracer = init_tracer("rag-worker")
    
    # In message processing
    class RAGWorker(TracedWorker):
        def process(self, msg_id, fields):
            with self.start_span("process_rag_task", fields) as span:
                # Extract trace context from Redis message
                span.set_attribute("message_id", msg_id)
                # ... process ...
                
Environment Variables:
    OTEL_ENABLED=1                  # Enable tracing (default: 0)
    OTEL_SERVICE_NAME=agentic-rag   # Service name in traces
    OTEL_EXPORTER=jaeger|otlp|console  # Exporter type (default: console)
    OTEL_JAEGER_ENDPOINT=http://localhost:14268/api/traces
    OTEL_OTLP_ENDPOINT=http://localhost:4318
"""

import os
import logging
from typing import Dict, Any, Optional
from contextlib import contextmanager

# OpenTelemetry imports with fallback
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.trace import Status, StatusCode
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    trace = None  # type: ignore

logger = logging.getLogger(__name__)

# Global tracer instance
_tracer: Optional[Any] = None
_propagator: Optional[Any] = None


def init_tracer(service_name: str) -> Any:
    """
    Initialize OpenTelemetry tracer with configured exporter.
    
    Args:
        service_name: Name of the service (e.g., "rag-worker", "persistence-worker")
    
    Returns:
        Tracer instance (or no-op tracer if disabled/unavailable)
    
    Example:
        tracer = init_tracer("rag-worker")
    """
    global _tracer, _propagator
    
    # Check if tracing is enabled
    enabled = os.getenv("OTEL_ENABLED", "0").lower() in ("1", "true", "yes")
    
    if not enabled:
        logger.info(f"[Tracing] Disabled for {service_name}")
        return _get_noop_tracer()
    
    if not OTEL_AVAILABLE:
        logger.warning(f"[Tracing] OpenTelemetry not installed, tracing disabled for {service_name}")
        return _get_noop_tracer()
    
    # Override service name from env if provided
    service_name = os.getenv("OTEL_SERVICE_NAME", service_name)
    
    # Create resource with service name
    resource = Resource(attributes={
        SERVICE_NAME: service_name
    })
    
    # Create tracer provider
    provider = TracerProvider(resource=resource)
    
    # Configure exporter based on environment
    exporter_type = os.getenv("OTEL_EXPORTER", "console").lower()
    
    if exporter_type == "jaeger":
        endpoint = os.getenv("OTEL_JAEGER_ENDPOINT", "http://localhost:14268/api/traces")
        exporter = JaegerExporter(
            collector_endpoint=endpoint,
        )
        logger.info(f"[Tracing] Using Jaeger exporter: {endpoint}")
    
    elif exporter_type == "otlp":
        endpoint = os.getenv("OTEL_OTLP_ENDPOINT", "http://localhost:4318")
        exporter = OTLPSpanExporter(
            endpoint=f"{endpoint}/v1/traces",
        )
        logger.info(f"[Tracing] Using OTLP exporter: {endpoint}")
    
    else:  # console (default for development)
        exporter = ConsoleSpanExporter()
        logger.info(f"[Tracing] Using console exporter")
    
    # Add span processor
    provider.add_span_processor(BatchSpanProcessor(exporter))
    
    # Set global tracer provider
    trace.set_tracer_provider(provider)
    
    # Create tracer
    _tracer = trace.get_tracer(__name__)
    
    # Initialize propagator for context extraction/injection
    _propagator = TraceContextTextMapPropagator()
    
    logger.info(f"[Tracing] Initialized for {service_name}")
    return _tracer


def _get_noop_tracer():
    """Return a no-op tracer when tracing is disabled."""
    if OTEL_AVAILABLE:
        return trace.get_tracer(__name__)
    
    # Fallback no-op implementation
    class NoOpSpan:
        def __enter__(self):
            return self
        
        def __exit__(self, *args):
            pass
        
        def set_attribute(self, key, value):
            pass
        
        def set_status(self, status):
            pass
        
        def add_event(self, name, attributes=None):
            pass
    
    class NoOpTracer:
        def start_span(self, name, context=None, attributes=None):
            return NoOpSpan()
        
        def start_as_current_span(self, name, context=None, attributes=None):
            return NoOpSpan()
    
    return NoOpTracer()


def inject_trace_context(fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inject current trace context into Redis message fields.
    
    Args:
        fields: Redis message fields dictionary
    
    Returns:
        Updated fields with trace context (traceparent, tracestate)
    
    Example:
        fields = {"task_id": "123", "data": "..."}
        fields = inject_trace_context(fields)
        # Now includes: traceparent, tracestate fields
    """
    if not OTEL_AVAILABLE or not _propagator:
        return fields
    
    # Inject trace context into a carrier dict
    carrier: Dict[str, str] = {}
    _propagator.inject(carrier)
    
    # Add trace context fields to message
    if "traceparent" in carrier:
        fields["traceparent"] = carrier["traceparent"]
    if "tracestate" in carrier:
        fields["tracestate"] = carrier["tracestate"]
    
    return fields


def extract_trace_context(fields: Dict[str, Any]) -> Optional[Any]:
    """
    Extract trace context from Redis message fields.
    
    Args:
        fields: Redis message fields dictionary
    
    Returns:
        Trace context object (or None if no context present)
    
    Example:
        context = extract_trace_context(fields)
        with tracer.start_as_current_span("process", context=context):
            # This span is linked to the parent trace
            pass
    """
    if not OTEL_AVAILABLE or not _propagator:
        return None
    
    # Extract trace context from message fields
    carrier = {}
    if "traceparent" in fields:
        carrier["traceparent"] = fields["traceparent"]
    if "tracestate" in fields:
        carrier["tracestate"] = fields["tracestate"]
    
    if not carrier:
        return None
    
    # Extract and return context
    return _propagator.extract(carrier=carrier)


class TracedWorker:
    """
    Mixin class for workers that want automatic tracing support.
    
    Provides start_span() context manager that:
    - Extracts trace context from Redis message
    - Creates child span linked to parent trace
    - Automatically sets error status on exception
    
    Usage:
        class RAGWorker(TracedWorker):
            def __init__(self):
                self.tracer = init_tracer("rag-worker")
            
            def process(self, msg_id, fields):
                with self.start_span("process_rag_task", fields) as span:
                    span.set_attribute("message_id", msg_id)
                    # ... process ...
    """
    
    tracer: Any = None  # Set in __init__
    
    @contextmanager
    def start_span(self, name: str, fields: Optional[Dict[str, Any]] = None, **attributes):
        """
        Start a traced span with automatic context extraction.
        
        Args:
            name: Span name (e.g., "process_rag_task")
            fields: Redis message fields (for context extraction)
            **attributes: Additional span attributes
        
        Yields:
            Span object
        
        Example:
            with self.start_span("process_message", fields, task_id="123") as span:
                span.set_attribute("custom_attr", "value")
                # ... process ...
        """
        if not self.tracer:
            # No tracer configured, use no-op
            tracer = _get_noop_tracer()
        else:
            tracer = self.tracer
        
        # Extract parent context from message fields
        context = None
        if fields:
            context = extract_trace_context(fields)
        
        # Start span
        if OTEL_AVAILABLE and context:
            span = tracer.start_as_current_span(name, context=context)
        else:
            span = tracer.start_span(name)
        
        # Set initial attributes
        for key, value in attributes.items():
            try:
                span.set_attribute(key, str(value))
            except Exception:
                pass
        
        try:
            with span:
                yield span
        except Exception as e:
            # Mark span as error
            if OTEL_AVAILABLE and hasattr(span, 'set_status'):
                span.set_status(Status(StatusCode.ERROR, str(e)))
            raise


def trace_redis_operation(operation_name: str, stream: str, **attributes):
    """
    Decorator for tracing Redis operations.
    
    Args:
        operation_name: Operation name (e.g., "xadd", "xread")
        stream: Stream name
        **attributes: Additional span attributes
    
    Example:
        @trace_redis_operation("xadd", "rag:tasks", message_count=1)
        def publish_task(self, task):
            # ... redis operation ...
    """
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            if not hasattr(self, 'tracer') or not self.tracer:
                return func(self, *args, **kwargs)
            
            with self.start_span(
                f"redis.{operation_name}",
                None,
                stream=stream,
                **attributes
            ) as span:
                result = func(self, *args, **kwargs)
                return result
        
        return wrapper
    return decorator


# Example usage function (for documentation)
def _example_usage():
    """
    Example: Tracing a RAG worker operation
    
    This shows how to:
    1. Initialize tracer
    2. Extract context from incoming message
    3. Create child span
    4. Inject context into outgoing message
    """
    # 1. Initialize tracer (once at startup)
    tracer = init_tracer("rag-worker")
    
    # 2. Process incoming message
    msg_id = "1234567-0"
    fields = {
        "task_id": "abc123",
        "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",  # From parent
        "data": "..."
    }
    
    # 3. Extract context and create child span
    context = extract_trace_context(fields)
    with tracer.start_as_current_span("process_rag_query", context=context) as span:
        span.set_attribute("message_id", msg_id)
        span.set_attribute("task_id", fields["task_id"])
        
        # Simulate processing
        result = {"status": "success"}
        
        # 4. Inject context into outgoing message
        outgoing_fields = {
            "result_id": "xyz789",
            "data": "result data"
        }
        outgoing_fields = inject_trace_context(outgoing_fields)
        
        # Now outgoing_fields includes traceparent for next hop
        return result
