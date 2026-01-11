"""
Structured JSON logger with Loki push support
"""

import os
import json
import logging
import time
from typing import Dict, Any
from datetime import datetime

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class StructuredLogger:
    """JSON logger that pushes to Loki if configured"""
    
    def __init__(self, tier: str, component: str):
        self.tier = tier
        self.component = component
        self.logger = logging.getLogger(f"{tier}.{component}")
        self.loki_url = os.getenv("LOKI_URL")  # e.g., http://localhost:3100/loki/api/v1/push
        self.loki_enabled = bool(self.loki_url) and REQUESTS_AVAILABLE
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def _log(self, level: str, event: str, **kwargs):
        """Log structured message"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "tier": self.tier,
            "component": self.component,
            "event": event,
            **kwargs,
        }
        
        # Log to stdout (Docker logs)
        log_line = json.dumps(log_entry)
        getattr(self.logger, level.lower())(log_line)
        
        # Push to Loki if enabled
        if self.loki_enabled:
            self._push_to_loki(log_entry)
    
    def _push_to_loki(self, log_entry: Dict[str, Any]):
        """Push log to Loki"""
        try:
            payload = {
                "streams": [{
                    "stream": {
                        "tier": self.tier,
                        "component": self.component,
                        "tenant_id": log_entry.get("tenant_id", "unknown"),
                        "level": log_entry["level"],
                    },
                    "values": [
                        [str(int(time.time() * 1e9)), json.dumps(log_entry)]
                    ]
                }]
            }
            requests.post(
                self.loki_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=1.0  # Don't block on logging
            )
        except Exception as e:
            # Don't fail the application if logging fails
            self.logger.warning(f"Failed to push to Loki: {e}")
    
    def info(self, event: str, **kwargs):
        self._log("INFO", event, **kwargs)
    
    def error(self, event: str, **kwargs):
        self._log("ERROR", event, **kwargs)
    
    def warning(self, event: str, **kwargs):
        self._log("WARNING", event, **kwargs)
    
    def debug(self, event: str, **kwargs):
        self._log("DEBUG", event, **kwargs)
