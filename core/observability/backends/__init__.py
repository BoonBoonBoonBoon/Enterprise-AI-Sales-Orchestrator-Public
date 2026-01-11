"""
APM Backend integrations (DataDog, OpenTelemetry, etc.)
"""

import os
from .base import APMBackend
from .noop import NoOpBackend


def get_backend() -> APMBackend:
    """Get configured APM backend or NoOp default"""
    backend_type = os.getenv("OBSERVABILITY_BACKEND", "noop").lower()
    
    if backend_type == "datadog":
        try:
            from .datadog import DataDogBackend
            return DataDogBackend()
        except ImportError:
            pass
    elif backend_type == "opentelemetry":
        try:
            from .opentelemetry import OpenTelemetryBackend
            return OpenTelemetryBackend()
        except ImportError:
            pass
    
    return NoOpBackend()


__all__ = ["APMBackend", "get_backend"]
