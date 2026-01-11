"""
Simple Logging Observability Backend

Uses Python's standard logging module.
Good for: Local development, no external dependencies

Output: Plain text logs to stdout/stderr
"""

import logging
from contextlib import contextmanager
from typing import Dict, Any

from core.harness.interfaces import IObservability

logger = logging.getLogger(__name__)


class SimpleLoggingObservability(IObservability):
    """
    Simple logging-based observability.
    
    No external dependencies - uses standard Python logging.
    Perfect for development and testing.
    
    Example:
        obs = SimpleLoggingObservability()
        
        with obs.start_span("operation_name") as span:
            span.set_attribute("key", "value")
            # do work
            obs.record_metric("requests", 1.0, {"status": "success"})
            obs.log_event("INFO", "Task completed", {"duration_ms": 123})
    """
    
    def __init__(self, log_level: str = "INFO"):
        """
        Initialize simple logging observability.
        
        Args:
            log_level: Log level for output (DEBUG, INFO, WARNING, ERROR)
        """
        self.log_level = log_level
        self.logger = logging.getLogger("agentic-system.observability")
        
        # Set log level
        level = getattr(logging, log_level.upper(), logging.INFO)
        self.logger.setLevel(level)
        
        # Ensure handler exists
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    @contextmanager
    def start_span(self, name: str):
        """
        Start a logging-based span (context manager).
        
        Args:
            name: Span name
        
        Yields:
            Span object with set_attribute method
        """
        self.logger.info(f"[SPAN START] {name}")
        
        # Create simple span object
        class SimpleSpan:
            def __init__(self, span_name: str, obs_logger):
                self.name = span_name
                self.logger = obs_logger
                self.attributes = {}
            
            def set_attribute(self, key: str, value: Any):
                """Set span attribute (logged)"""
                self.attributes[key] = value
                self.logger.debug(f"[SPAN ATTR] {self.name} | {key}={value}")
        
        span = SimpleSpan(name, self.logger)
        
        try:
            yield span
        finally:
            # Log span completion with attributes
            if span.attributes:
                attrs_str = ", ".join(f"{k}={v}" for k, v in span.attributes.items())
                self.logger.info(f"[SPAN END] {name} | Attributes: {attrs_str}")
            else:
                self.logger.info(f"[SPAN END] {name}")
    
    def record_metric(self, name: str, value: float, tags: Dict[str, str]):
        """
        Record a metric (logged).
        
        Args:
            name: Metric name
            value: Metric value
            tags: Metric tags
        """
        tags_str = ", ".join(f"{k}={v}" for k, v in tags.items())
        self.logger.info(f"[METRIC] {name}={value} | Tags: {tags_str}")
    
    def log_event(self, level: str, message: str, context: Dict[str, Any]):
        """
        Log an event with context.
        
        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Log message
            context: Additional context
        """
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        log_level = getattr(logging, level.upper(), logging.INFO)
        self.logger.log(log_level, f"[EVENT] {message} | Context: {context_str}")
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        return f"SimpleLoggingObservability(log_level={self.log_level})"
