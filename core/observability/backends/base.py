"""
Base APM backend interface
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class APMBackend(ABC):
    """Abstract base for APM integrations"""
    
    @abstractmethod
    def start_span(self, name: str, tags: Dict[str, Any]):
        """Start a new span/trace"""
        pass
    
    @abstractmethod
    def end_span(self, duration_ms: float, success: bool = True):
        """End the current span"""
        pass
    
    @abstractmethod
    def increment_counter(self, name: str, value: float, tags: Dict[str, Any]):
        """Increment a counter metric"""
        pass
    
    @abstractmethod
    def record_histogram(self, name: str, value: float, tags: Dict[str, Any]):
        """Record a histogram value"""
        pass
