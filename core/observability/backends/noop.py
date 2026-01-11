"""
No-op APM backend (default, zero cost)
"""

from typing import Dict, Any
from .base import APMBackend


class NoOpBackend(APMBackend):
    """No-operation backend - does nothing, zero overhead"""
    
    def start_span(self, name: str, tags: Dict[str, Any]):
        pass
    
    def end_span(self, duration_ms: float, success: bool = True):
        pass
    
    def increment_counter(self, name: str, value: float, tags: Dict[str, Any]):
        pass
    
    def record_histogram(self, name: str, value: float, tags: Dict[str, Any]):
        pass
