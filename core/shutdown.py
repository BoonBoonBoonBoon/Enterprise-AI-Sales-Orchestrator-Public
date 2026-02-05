"""Graceful shutdown handling for consumers.

Provides a reusable pattern for handling SIGTERM/SIGINT signals
to enable clean shutdown with in-flight task completion.
"""
from __future__ import annotations

import logging
import signal
import threading
import time
from contextlib import contextmanager
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class ShutdownHandler:
    """
    Handles graceful shutdown for long-running consumers.
    
    Features:
    - Catches SIGTERM and SIGINT signals
    - Tracks in-flight task processing
    - Waits for current task to complete (with timeout)
    - Thread-safe stop flag
    
    Usage:
        handler = ShutdownHandler(name="MyConsumer")
        handler.register_signals()
        
        while not handler.should_stop:
            with handler.processing_context():
                # Process task
                ...
    """
    
    def __init__(
        self,
        name: str = "Consumer",
        shutdown_timeout: float = 30.0,
        on_shutdown: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize shutdown handler.
        
        Args:
            name: Name for logging (e.g., "RAGWorker", "ManagerConsumer")
            shutdown_timeout: Seconds to wait for in-flight tasks before forcing exit
            on_shutdown: Optional callback to run on shutdown
        """
        self.name = name
        self.shutdown_timeout = shutdown_timeout
        self.on_shutdown = on_shutdown
        
        self._stop = threading.Event()
        self._processing = False
        self._current_task_id: Optional[str] = None
        self._lock = threading.Lock()
    
    @property
    def should_stop(self) -> bool:
        """Check if shutdown has been requested."""
        return self._stop.is_set()
    
    @property
    def is_processing(self) -> bool:
        """Check if currently processing a task."""
        with self._lock:
            return self._processing
    
    def register_signals(self) -> None:
        """
        Register signal handlers for graceful shutdown.
        
        Should be called from the main thread before starting the consumer loop.
        """
        try:
            signal.signal(signal.SIGTERM, self._handle_signal)
            signal.signal(signal.SIGINT, self._handle_signal)
            logger.info(
                "[%s] Graceful shutdown enabled (SIGTERM/SIGINT will finish in-flight tasks)",
                self.name,
            )
        except Exception as e:
            # Signal handlers can only be set in main thread
            logger.warning(
                "[%s] Could not register signal handlers: %s",
                self.name,
                e,
            )
    
    def _handle_signal(self, signum: int, frame) -> None:
        """Handle SIGTERM/SIGINT signal."""
        sig_name = signal.Signals(signum).name
        logger.info("[%s] Received %s, initiating graceful shutdown...", self.name, sig_name)
        
        if self.is_processing:
            logger.info(
                "[%s] Waiting for in-flight task '%s' to complete (timeout: %.0fs)...",
                self.name,
                self._current_task_id or "unknown",
                self.shutdown_timeout,
            )
            
            # Wait for current task with timeout
            deadline = time.time() + self.shutdown_timeout
            while self.is_processing and time.time() < deadline:
                time.sleep(0.5)
            
            if self.is_processing:
                logger.warning(
                    "[%s] Task still processing after %.0fs, forcing shutdown",
                    self.name,
                    self.shutdown_timeout,
                )
        
        # Set stop flag
        self._stop.set()
        
        # Run custom callback if provided
        if self.on_shutdown:
            try:
                self.on_shutdown()
            except Exception as e:
                logger.error("[%s] Error in shutdown callback: %s", self.name, e)
        
        logger.info("[%s] Shutdown complete", self.name)
    
    def request_stop(self) -> None:
        """Programmatically request shutdown (e.g., from tests)."""
        self._stop.set()
    
    @contextmanager
    def processing_context(self, task_id: Optional[str] = None):
        """
        Context manager to track task processing.
        
        Args:
            task_id: Optional task identifier for logging
        
        Usage:
            with handler.processing_context("task-123"):
                process_task(...)
        """
        with self._lock:
            self._processing = True
            self._current_task_id = task_id
        try:
            yield
        finally:
            with self._lock:
                self._processing = False
                self._current_task_id = None


# Module-level singleton for simple use cases
_default_handler: Optional[ShutdownHandler] = None


def get_shutdown_handler(
    name: str = "Consumer",
    **kwargs,
) -> ShutdownHandler:
    """
    Get or create a shutdown handler.
    
    For simple single-consumer processes, use this to get a singleton.
    For multi-consumer processes, create handlers directly.
    """
    global _default_handler
    if _default_handler is None:
        _default_handler = ShutdownHandler(name=name, **kwargs)
    return _default_handler


__all__ = ["ShutdownHandler", "get_shutdown_handler"]
