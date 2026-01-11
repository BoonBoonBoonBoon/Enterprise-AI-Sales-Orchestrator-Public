#!/usr/bin/env python3
"""
HTTP Health Check Server for Redis Streams

Lightweight HTTP server exposing health check endpoints for:
- Load balancer health probes
- Monitoring systems (Prometheus, Datadog, etc.)
- Kubernetes liveness/readiness probes
- CI/CD health gates

Endpoints:
    GET /health - Full health check with JSON response
    GET /healthz - Simple liveness probe (200 OK if Redis reachable)
    GET /ready - Readiness probe (200 OK if all systems healthy, 503 if degraded/unhealthy)
    GET /metrics - Prometheus-compatible metrics (optional)

Usage:
    # Start server on default port 8080
    python scripts/health_server.py

    # Custom port and host
    python scripts/health_server.py --port 8081 --host 0.0.0.0

    # Enable Prometheus metrics endpoint
    python scripts/health_server.py --enable-metrics

    # Custom alert thresholds
    python scripts/health_server.py --max-pending 500 --max-dlq 50

Example requests:
    curl http://localhost:8080/health
    curl http://localhost:8080/healthz
    curl http://localhost:8080/ready
    curl http://localhost:8080/metrics
"""

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from dotenv import load_dotenv

# Load .env BEFORE importing modules
load_dotenv()

# Import health checker
sys.path.insert(0, ".")
from scripts.health_check import HealthChecker


class HealthRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for health check endpoints."""

    # Class-level configuration (set by server initialization)
    checker: HealthChecker = None
    enable_metrics: bool = False

    def log_message(self, format, *args):
        """Custom log format."""
        print(f"[{self.log_date_time_string()}] {format % args}")

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/health":
            self._handle_health()
        elif self.path == "/healthz":
            self._handle_healthz()
        elif self.path == "/ready":
            self._handle_ready()
        elif self.path == "/metrics" and self.enable_metrics:
            self._handle_metrics()
        else:
            self._send_response(404, {"error": "Not found"})

    def _handle_health(self):
        """Full health check with detailed JSON response."""
        try:
            health = self.checker.check_health()
            status_code = 200 if health["status"] in ("healthy", "degraded") else 503
            self._send_response(status_code, health)
        except Exception as e:
            self._send_response(503, {"status": "error", "error": str(e)})

    def _handle_healthz(self):
        """Simple liveness probe - checks if service is running and can connect to Redis."""
        try:
            health = self.checker.check_health()
            if health.get("connection", {}).get("status") == "ok":
                self._send_response(200, {"status": "ok"})
            else:
                self._send_response(503, {"status": "error", "message": "Cannot connect to Redis"})
        except Exception as e:
            self._send_response(503, {"status": "error", "error": str(e)})

    def _handle_ready(self):
        """Readiness probe - checks if service is ready to accept traffic."""
        try:
            health = self.checker.check_health()
            if health["status"] == "healthy":
                self._send_response(200, {"status": "ready"})
            elif health["status"] == "degraded":
                # Degraded = warnings but still functional
                self._send_response(
                    200,
                    {
                        "status": "ready",
                        "warnings": [a["message"] for a in health.get("alerts", [])],
                    },
                )
            else:
                self._send_response(
                    503,
                    {
                        "status": "not_ready",
                        "reason": "unhealthy",
                        "alerts": health.get("alerts", []),
                    },
                )
        except Exception as e:
            self._send_response(503, {"status": "error", "error": str(e)})

    def _handle_metrics(self):
        """Prometheus-compatible metrics endpoint."""
        try:
            health = self.checker.check_health()

            # Convert health data to Prometheus exposition format
            lines = []
            lines.append("# HELP redis_streams_health Overall health status (0=unhealthy, 1=degraded, 2=healthy)")
            lines.append("# TYPE redis_streams_health gauge")
            status_value = {"unhealthy": 0, "degraded": 1, "healthy": 2}.get(health["status"], 0)
            lines.append(f'redis_streams_health{{namespace="{health["namespace"]}"}} {status_value}')

            # Stream metrics
            for stream_name, stream_data in health.get("streams", {}).items():
                if not stream_data.get("exists"):
                    continue

                lines.append(f"# HELP redis_stream_length_{stream_name.replace(':', '_')} Stream length")
                lines.append(f"# TYPE redis_stream_length_{stream_name.replace(':', '_')} gauge")
                lines.append(f'redis_stream_length{{stream="{stream_name}"}} {stream_data.get("length", 0)}')

                if "pending" in stream_data:
                    lines.append(f"# HELP redis_stream_pending_{stream_name.replace(':', '_')} Pending messages")
                    lines.append(f"# TYPE redis_stream_pending_{stream_name.replace(':', '_')} gauge")
                    lines.append(f'redis_stream_pending{{stream="{stream_name}"}} {stream_data.get("pending", 0)}')

                if "consumers" in stream_data:
                    lines.append(f"# HELP redis_stream_consumers_{stream_name.replace(':', '_')} Active consumers")
                    lines.append(f"# TYPE redis_stream_consumers_{stream_name.replace(':', '_')} gauge")
                    lines.append(f'redis_stream_consumers{{stream="{stream_name}"}} {stream_data.get("consumers", 0)}')

            # Heartbeat metrics
            for service, count in health.get("heartbeats", {}).items():
                lines.append(f"# HELP redis_heartbeats_{service} Active {service} workers")
                lines.append(f"# TYPE redis_heartbeats_{service} gauge")
                lines.append(f'redis_heartbeats{{service="{service}"}} {count}')

            # DLQ metrics
            for dlq_name, count in health.get("dlq", {}).items():
                lines.append(f"# HELP redis_dlq_{dlq_name} DLQ message count")
                lines.append(f"# TYPE redis_dlq_{dlq_name} counter")
                lines.append(f'redis_dlq{{stream="{dlq_name}"}} {count}')

            # Workflow state
            workflow_count = health.get("workflow_state", {}).get("active_workflows", 0)
            lines.append("# HELP redis_active_workflows Active workflow count")
            lines.append("# TYPE redis_active_workflows gauge")
            lines.append(f"redis_active_workflows {workflow_count}")

            # Aggregate metrics
            metrics = health.get("metrics", {})
            lines.append("# HELP redis_total_streams Total stream count")
            lines.append("# TYPE redis_total_streams gauge")
            lines.append(f'redis_total_streams {metrics.get("total_streams", 0)}')

            lines.append("# HELP redis_total_pending Total pending messages")
            lines.append("# TYPE redis_total_pending gauge")
            lines.append(f'redis_total_pending {metrics.get("total_pending", 0)}')

            lines.append("# HELP redis_total_dlq_messages Total DLQ messages")
            lines.append("# TYPE redis_total_dlq_messages counter")
            lines.append(f'redis_total_dlq_messages {metrics.get("total_dlq_messages", 0)}')

            lines.append("# HELP redis_active_consumers Total active consumers")
            lines.append("# TYPE redis_active_consumers gauge")
            lines.append(f'redis_active_consumers {metrics.get("active_consumers", 0)}')

            # Alerts
            lines.append("# HELP redis_alerts_total Total alert count")
            lines.append("# TYPE redis_alerts_total gauge")
            lines.append(f'redis_alerts_total {len(health.get("alerts", []))}')

            metrics_text = "\n".join(lines) + "\n"
            self._send_response(200, metrics_text, content_type="text/plain; version=0.0.4")

        except Exception as e:
            self._send_response(503, f"# Error generating metrics: {e}\n", content_type="text/plain")

    def _send_response(self, status_code: int, data: Any, content_type: str = "application/json"):
        """Send HTTP response."""
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()

        if isinstance(data, str):
            self.wfile.write(data.encode())
        else:
            self.wfile.write(json.dumps(data).encode())


def run_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    max_pending: int = 1000,
    max_dlq: int = 100,
    max_idle_sec: int = 300,
    enable_metrics: bool = False,
):
    """Run the health check HTTP server."""
    # Initialize health checker
    checker = HealthChecker(
        max_pending=max_pending,
        max_dlq=max_dlq,
        max_consumer_idle_sec=max_idle_sec,
        fail_on_unhealthy=False,
    )

    # Configure request handler
    HealthRequestHandler.checker = checker
    HealthRequestHandler.enable_metrics = enable_metrics

    # Create and start server
    server = HTTPServer((host, port), HealthRequestHandler)
    print(f"Redis Health Check Server running on http://{host}:{port}")
    print(f"Endpoints:")
    print(f"  - http://{host}:{port}/health   (full health check)")
    print(f"  - http://{host}:{port}/healthz  (liveness probe)")
    print(f"  - http://{host}:{port}/ready    (readiness probe)")
    if enable_metrics:
        print(f"  - http://{host}:{port}/metrics (Prometheus metrics)")
    print(f"\nPress Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()


def main():
    parser = argparse.ArgumentParser(description="HTTP Health Check Server for Redis Streams")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to (default: 8080)")
    parser.add_argument("--max-pending", type=int, default=1000, help="Max pending threshold")
    parser.add_argument("--max-dlq", type=int, default=100, help="Max DLQ threshold")
    parser.add_argument("--max-idle-sec", type=int, default=300, help="Max consumer idle seconds")
    parser.add_argument("--enable-metrics", action="store_true", help="Enable Prometheus /metrics endpoint")

    args = parser.parse_args()

    run_server(
        host=args.host,
        port=args.port,
        max_pending=args.max_pending,
        max_dlq=args.max_dlq,
        max_idle_sec=args.max_idle_sec,
        enable_metrics=args.enable_metrics,
    )


if __name__ == "__main__":
    main()
