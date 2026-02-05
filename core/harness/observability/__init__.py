"""
Observability Backends: Pluggable tracing/metrics implementations

All observability backends implement IObservability interface.
Choose based on infrastructure:
- SimpleLoggingObservability: Development, no dependencies (default)
- GrafanaStackObservability: Production with Grafana stack (recommended)
- OpenTelemetryObservability: Production, CNCF standard, vendor-agnostic
- DatadogObservability: Production with existing Datadog infrastructure
"""

from .simple_logging import SimpleLoggingObservability
from .grafana_stack import GrafanaStackObservability
from .opentelemetry_impl import OpenTelemetryObservability
from .datadog_impl import DatadogObservability

__all__ = [
    "SimpleLoggingObservability",
    "GrafanaStackObservability",
    "OpenTelemetryObservability",
    "DatadogObservability",
]
