"""
Metrics Collector with Prometheus export support
"""

import time
from typing import Dict, Optional, List
from collections import defaultdict
import threading

try:
    from prometheus_client import (
        Counter, Histogram, Gauge, Summary,
        CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


class MetricsCollector:
    """Singleton metrics collector with Prometheus export"""
    
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        if MetricsCollector._instance is not None:
            raise RuntimeError("Use MetricsCollector.get_instance()")
        
        self.prometheus_enabled = PROMETHEUS_AVAILABLE
        if self.prometheus_enabled:
            self.registry = CollectorRegistry()
            self._counters = {}
            self._histograms = {}
            self._gauges = {}
        else:
            # Fallback to in-memory dict for basic metrics
            self._metrics = defaultdict(float)
        
        self._lock = threading.Lock()
    
    def increment(self, name: str, value: float = 1.0, tags: Optional[Dict] = None):
        """Increment a counter"""
        tags = tags or {}
        
        if self.prometheus_enabled:
            metric = self._get_or_create_counter(name, list(tags.keys()))
            metric.labels(**tags).inc(value)
        else:
            key = f"{name}:{','.join(f'{k}={v}' for k, v in sorted(tags.items()))}"
            self._metrics[key] += value
    
    def histogram(self, name: str, value: float, tags: Optional[Dict] = None):
        """Record a histogram value"""
        tags = tags or {}
        
        if self.prometheus_enabled:
            metric = self._get_or_create_histogram(name, list(tags.keys()))
            metric.labels(**tags).observe(value)
        else:
            # Simple average tracking
            key = f"{name}:avg:{','.join(f'{k}={v}' for k, v in sorted(tags.items()))}"
            count_key = f"{name}:count:{','.join(f'{k}={v}' for k, v in sorted(tags.items()))}"
            self._metrics[count_key] += 1
            self._metrics[key] = (
                (self._metrics[key] * (self._metrics[count_key] - 1) + value) / self._metrics[count_key]
            )
    
    def gauge(self, name: str, value: float, tags: Optional[Dict] = None):
        """Set a gauge value"""
        tags = tags or {}
        
        if self.prometheus_enabled:
            metric = self._get_or_create_gauge(name, list(tags.keys()))
            metric.labels(**tags).set(value)
        else:
            key = f"{name}:{','.join(f'{k}={v}' for k, v in sorted(tags.items()))}"
            self._metrics[key] = value
    
    def _get_or_create_counter(self, name: str, label_names: List[str]):
        if not self.prometheus_enabled:
            return None
        
        key = (name, tuple(sorted(label_names)))
        if key not in self._counters:
            with self._lock:
                if key not in self._counters:
                    self._counters[key] = Counter(
                        name.replace('.', '_').replace('-', '_'),
                        f'Counter for {name}',
                        labelnames=label_names,
                        registry=self.registry
                    )
        return self._counters[key]
    
    def _get_or_create_histogram(self, name: str, label_names: List[str]):
        if not self.prometheus_enabled:
            return None
        
        key = (name, tuple(sorted(label_names)))
        if key not in self._histograms:
            with self._lock:
                if key not in self._histograms:
                    self._histograms[key] = Histogram(
                        name.replace('.', '_').replace('-', '_'),
                        f'Histogram for {name}',
                        labelnames=label_names,
                        registry=self.registry,
                        buckets=(10, 50, 100, 250, 500, 1000, 2500, 5000, 10000)  # ms buckets
                    )
        return self._histograms[key]
    
    def _get_or_create_gauge(self, name: str, label_names: List[str]):
        if not self.prometheus_enabled:
            return None
        
        key = (name, tuple(sorted(label_names)))
        if key not in self._gauges:
            with self._lock:
                if key not in self._gauges:
                    self._gauges[key] = Gauge(
                        name.replace('.', '_').replace('-', '_'),
                        f'Gauge for {name}',
                        labelnames=label_names,
                        registry=self.registry
                    )
        return self._gauges[key]
    
    def export_prometheus(self) -> bytes:
        """Export metrics in Prometheus format"""
        if self.prometheus_enabled:
            return generate_latest(self.registry)
        else:
            # Return simple text format
            lines = []
            for key, value in sorted(self._metrics.items()):
                lines.append(f"{key} {value}")
            return '\n'.join(lines).encode('utf-8')
    
    def get_content_type(self) -> str:
        """Get Prometheus content type header"""
        if self.prometheus_enabled:
            return CONTENT_TYPE_LATEST
        else:
            return "text/plain"
