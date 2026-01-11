"""
Observability Backends: Pluggable tracing/metrics implementations

All observability backends implement IObservability interface.
Choose based on infrastructure:
- SimpleLoggingObservability: Development, no dependencies (default)
- OpenTelemetryObservability: Production, CNCF standard, vendor-agnostic
- DatadogObservability: Production with existing Datadog infrastructure
"""

from .simple_logging import SimpleLoggingObservability
from .opentelemetry_impl import OpenTelemetryObservability
from .datadog_impl import DatadogObservability

__all__ = [
    "SimpleLoggingObservability",
    "OpenTelemetryObservability",
    "DatadogObservability",
]
