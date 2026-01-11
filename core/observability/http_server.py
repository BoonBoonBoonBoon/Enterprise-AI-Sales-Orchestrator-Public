"""
Simple HTTP server to expose /metrics endpoint
"""

import os
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from .metrics import MetricsCollector


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for /metrics and /health endpoints"""
    
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
            self.wfile.write(b'{"status":"healthy"}')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress request logging to avoid noise"""
        pass


def start_metrics_server(port: int = None, host: str = "0.0.0.0"):
    """
    Start HTTP server for metrics export in background thread
    
    Args:
        port: Port to listen on (default from env METRICS_PORT or 8000)
        host: Host to bind to (default: 0.0.0.0)
    
    Returns:
        HTTPServer instance
    """
    if port is None:
        port = int(os.getenv("METRICS_PORT", "8000"))
    
    server = HTTPServer((host, port), MetricsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="MetricsServer")
    thread.start()
    
    return server
