"""Graceful Shutdown Mixin for Workers

Provides signal handling and graceful shutdown capabilities for worker processes.
Ensures in-flight tasks complete before termination.

Usage:
    class MyWorker(GracefulShutdownMixin):
        def process(self, msg_id, fields):
            with self.track_processing(msg_id):
                # Process message
                pass
        
        def start(self):
            self.install_signal_handlers()
            while not self.should_stop():
                # Poll for messages
                pass
"""
from __future__ import annotations

import signal
import time
import threading
from typing import Optional, Callable
from contextlib import contextmanager


class GracefulShutdownMixin:
    """Mixin providing graceful shutdown capabilities for workers.
    
    Features:
    - SIGTERM/SIGINT signal handling
    - In-flight task tracking
    - Configurable shutdown timeout
    - Clean shutdown logging
    """
    
    def __init__(self, *args, **kwargs):
        # Consume our kwargs so we don't forward unknown args to base classes.
        shutdown_timeout = kwargs.pop("shutdown_timeout", None)
        # Backward-compatible naming used in some places/tests.
        grace_period = kwargs.pop("grace_period", None)

        super().__init__(*args, **kwargs)
        self._stop = threading.Event()
        self._processing = False
        self._current_msg_id: Optional[str] = None

        timeout = shutdown_timeout if shutdown_timeout is not None else (grace_period if grace_period is not None else 30)
        self._shutdown_timeout_sec = int(timeout)
    
    @contextmanager
    def track_processing(self, msg_id: str):
        """Context manager to track message processing state.
        
        Usage:
            with self.track_processing(msg_id):
                # Process message
                pass
        """
        self._processing = True
        self._current_msg_id = msg_id
        try:
            yield
        finally:
            self._processing = False
            self._current_msg_id = None
    
    def should_stop(self) -> bool:
        """Check if worker should stop processing."""
        return self._stop.is_set()
    
    def request_shutdown(self):
        """Request worker shutdown (non-blocking)."""
        self._stop.set()
    
    def shutdown(self, signum=None, frame=None) -> None:
        """Graceful shutdown: finish in-flight task before exit.
        
        Args:
            signum: Signal number (from signal handler)
            frame: Current stack frame (from signal handler)
        """
        worker_name = self.__class__.__name__
        worker_id = getattr(self, 'worker_id', 'unknown')
        
        print(f"\n[{worker_name} {worker_id}] Shutdown signal received (SIGTERM/SIGINT)")
        
        if self._processing:
            print(f"[{worker_name} {worker_id}] Waiting for in-flight message {self._current_msg_id} to complete...")
            # Wait for current task to finish (with timeout)
            wait_iterations = self._shutdown_timeout_sec * 2  # Check every 0.5s
            for _ in range(wait_iterations):
                if not self._processing:
                    break
                time.sleep(0.5)
            
            if self._processing:
                print(
                    f"[{worker_name} {worker_id}] WARNING: Task still processing after {self._shutdown_timeout_sec}s, "
                    f"forcing shutdown"
                )
        
        self._stop.set()
        print(f"[{worker_name} {worker_id}] Shutdown complete")
    
    def install_signal_handlers(self):
        """Install SIGTERM and SIGINT handlers for graceful shutdown."""
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)
        
        worker_name = self.__class__.__name__
        worker_id = getattr(self, 'worker_id', 'unknown')
        print(f"[{worker_name} {worker_id}] Graceful shutdown enabled (SIGTERM/SIGINT will finish in-flight tasks)")
    
    def cleanup(self, cleanup_func: Optional[Callable] = None):
        """Perform cleanup operations before exit.
        
        Args:
            cleanup_func: Optional custom cleanup function
        """
        if cleanup_func:
            try:
                cleanup_func()
            except Exception as e:
                worker_name = self.__class__.__name__
                print(f"[{worker_name}] Cleanup error: {e}")


class GracefulShutdown:
    """Small helper for simple graceful shutdown state.

    Used by integration tests that expect `trigger_shutdown()` / `is_shutting_down()`.
    """

    def __init__(self, grace_period: int = 30):
        self.grace_period = int(grace_period)
        self._event = threading.Event()

    def trigger_shutdown(self) -> None:
        self._event.set()

    def is_shutting_down(self) -> bool:
        return self._event.is_set()


__all__ = ["GracefulShutdownMixin", "GracefulShutdown"]
