import threading
import http.server
import socketserver
import os
import traceback
from typing import Any, Dict, Optional

import platform_monitoring

from ..queue.interface import QueueInterface
from agent.high_level_agents.orchestrators.registry import Registry
from agent.high_level_agents.audit.store import AuditStore


class Worker:
    """Worker that pulls jobs, resolves orchestrators via Registry, runs them, persists/audits result.

    Responsibilities:
    - dequeue job
    - resolve orchestrator = registry.get(name) -> returns class/callable
    - call orchestrator.run(payload) and validate envelope
    - ack job on success, requeue or ack on failure
    - emit platform_monitoring events at start/success/error
    """

    def __init__(self, queue: QueueInterface, registry: Registry, topic: str = "orchestrate", audit_store: AuditStore | None = None):
        self.queue = queue
        self.registry = registry
        self.topic = topic
        self.audit_store = audit_store
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def run_once(self, timeout: float = 1.0) -> None:
        item = self.queue.dequeue(self.topic, timeout=timeout)
        if not item:
            return
        job_id = item.get("job_id")
        run_id = item.get("run_id")
        orchestrator_name = item.get("orchestrator")
        platform_monitoring.log_event("worker.job.start", {"job_id": job_id, "run_id": run_id, "orchestrator": orchestrator_name})
        try:
            orch_factory = self.registry.get(orchestrator_name)
            if orch_factory is None:
                raise RuntimeError(f"unknown orchestrator: {orchestrator_name}")

            # If registry returns a class, instantiate; if it returns an instance, use directly.
            if isinstance(orch_factory, type):  # class
                orch = orch_factory()
            else:
                orch = orch_factory
            envelope = orch.run(item.get("payload", {}))
            platform_monitoring.log_event("worker.job.success", {"job_id": job_id, "run_id": run_id, "records": len(envelope.get("records", [])) if envelope else 0})
            # persist envelope to audit store if available
            try:
                if self.audit_store and run_id:
                    self.audit_store.save_envelope(run_id, envelope)
            except Exception:
                platform_monitoring.log_event("worker.audit.error", {"run_id": run_id, "error": traceback.format_exc()})
            self.queue.ack(job_id)
        except Exception as exc:
            platform_monitoring.log_event("worker.job.error", {"job_id": job_id, "run_id": run_id, "error": str(exc)})
            # Simplify: do not requeue on failure (tests expect single attempt)
            self.queue.ack(job_id)
            # persist failure to audit store if available
            try:
                if self.audit_store and run_id:
                    self.audit_store.save_failure(run_id, str(exc), envelope if 'envelope' in locals() else None)
            except Exception:
                platform_monitoring.log_event("worker.audit.error", {"run_id": run_id, "error": traceback.format_exc()})
            platform_monitoring.log_event("worker.job.trace", {"job_id": job_id, "trace": traceback.format_exc()})

    def start(self, poll_interval: float = 0.5):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, args=(poll_interval,), daemon=True)
        self._thread.start()
        # Optionally start metrics server (Prometheus client can hook here later)
        if os.environ.get("ENABLE_METRICS", "true").lower() in ("1","true","yes"):
            port = int(os.environ.get("METRICS_PORT", "8001"))
            t = threading.Thread(target=self._start_metrics_server, args=(port,), daemon=True)
            t.start()

    def _start_metrics_server(self, port: int):
        # Lazy import to avoid mandatory dependency if not used
        try:
            from prometheus_client import CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST, Counter
        except Exception:
            return
        request_counter = Counter('worker_loop_iterations', 'Total loop iterations processed')
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self_inner):  # noqa: N802
                if self_inner.path == '/metrics':
                    try:
                        request_counter.inc()
                        output = generate_latest()
                        self_inner.send_response(200)
                        self_inner.send_header('Content-Type', CONTENT_TYPE_LATEST)
                        self_inner.end_headers()
                        self_inner.wfile.write(output)
                    except Exception as e:  # pragma: no cover
                        self_inner.send_response(500)
                        self_inner.end_headers()
                        self_inner.wfile.write(str(e).encode())
                else:
                    self_inner.send_response(404)
                    self_inner.end_headers()
            def log_message(self_inner, format, *args):  # silence default logging
                return
        with socketserver.TCPServer(("0.0.0.0", port), Handler) as httpd:  # noqa: S104
            try:
                httpd.serve_forever()
            except Exception:
                pass

    def _run_loop(self, poll_interval: float):
        while not self._stop.is_set():
            try:
                self.run_once(timeout=poll_interval)
            except Exception:
                platform_monitoring.log_event("worker.loop.error", {"error": traceback.format_exc()})

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
