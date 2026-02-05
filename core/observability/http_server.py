"""
Simple HTTP server to expose /metrics endpoint

Provides:
- /metrics - Prometheus-format metrics export
- /health - Health check endpoint
- Component-specific port mapping for multi-service deployments
"""

import os
import json
import logging
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from typing import Optional
from .metrics import MetricsCollector

logger = logging.getLogger(__name__)

# Default port mapping for each component (can be overridden via env vars)
# Format: METRICS_PORT_{COMPONENT} or fallback to METRICS_PORT
COMPONENT_PORT_DEFAULTS = {
    # Tier 1
    "manager": 8000,
    # Tier 2 Orchestrators
    "leads_orchestrator": 8010,
    "outreach_orchestrator": 8011,
    "inbound_orchestrator": 8012,
    "control_orchestrator": 8013,
    "audit_orchestrator": 8014,
    # Tier 3 Agents
    "persistence_agent": 8020,
    "rag_agent": 8021,
    "copywriter_agent": 8022,
    "channel_sequencer_agent": 8023,
    "classifier_agent": 8024,
    "scheduler_agent": 8025,
}


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for /metrics and /health endpoints"""
    
    # Store component name for health response
    component_name: str = "unknown"
    
    def do_GET(self):
        if self.path == '/metrics':
            metrics = MetricsCollector.get_instance()
            self.send_response(200)
            self.send_header('Content-Type', metrics.get_content_type())
            self.end_headers()
            self.wfile.write(metrics.export_prometheus())
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            health_data = {
                "status": "healthy",
                "component": self.component_name,
            }
            self.wfile.write(json.dumps(health_data).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress request logging to avoid noise"""
        pass


def get_metrics_port(component: Optional[str] = None) -> int:
    """
    Get metrics port for a component.
    
    Resolution order:
    1. METRICS_PORT_{COMPONENT} (e.g., METRICS_PORT_LEADS_ORCHESTRATOR)
    2. METRICS_PORT (global override)
    3. Component default from COMPONENT_PORT_DEFAULTS
    4. Fallback to 8000
    
    Args:
        component: Component name (e.g., "leads_orchestrator")
        
    Returns:
        Port number
    """
    if component:
        # Check for component-specific env var
        env_var = f"METRICS_PORT_{component.upper()}"
        if os.getenv(env_var):
            return int(os.getenv(env_var))
    
    # Check global METRICS_PORT
    if os.getenv("METRICS_PORT"):
        return int(os.getenv("METRICS_PORT"))
    
    # Use component default
    if component and component in COMPONENT_PORT_DEFAULTS:
        return COMPONENT_PORT_DEFAULTS[component]
    
    # Fallback
    return 8000


def start_metrics_server(
    port: Optional[int] = None,
    host: str = "0.0.0.0",
    component: Optional[str] = None,
) -> Optional[HTTPServer]:
    """
    Start HTTP server for metrics export in background thread.
    
    Args:
        port: Port to listen on (default: auto-resolve based on component)
        host: Host to bind to (default: 0.0.0.0)
        component: Component name for port resolution and health endpoint
    
    Returns:
        HTTPServer instance, or None if server failed to start
    """
    if port is None:
        port = get_metrics_port(component)
    
    try:
        # Set component name on handler class for health endpoint
        MetricsHandler.component_name = component or "unknown"
        
        server = HTTPServer((host, port), MetricsHandler)
        thread = threading.Thread(
            target=server.serve_forever,
            daemon=True,
            name=f"MetricsServer-{component or 'default'}"
        )
        thread.start()
        
        logger.info(
            f"Metrics server started: component={component}, "
            f"host={host}, port={port}, endpoints=[/metrics, /health]"
        )

        # Emit a minimal, always-on baseline so dashboards can query something
        # even before any tasks are processed.
        metrics = MetricsCollector.get_instance()
        metrics.gauge("component.up", 1, tags={"component": MetricsHandler.component_name})
        metrics.gauge(
            "component.start_time_seconds",
            time.time(),
            tags={"component": MetricsHandler.component_name},
        )
        
        return server
        
    except OSError as e:
        if e.errno == 10048:  # Address already in use (Windows)
            logger.warning(
                f"Metrics server port {port} already in use for {component}. "
                f"Metrics will not be exposed on this instance."
            )
        else:
            logger.error(f"Failed to start metrics server on port {port}: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")
        return None
