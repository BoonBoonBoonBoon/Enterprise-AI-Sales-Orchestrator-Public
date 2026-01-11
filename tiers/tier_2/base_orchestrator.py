"""Base class for Tier 2 orchestrators.

Responsibilities:
- Accept a free-text request or an envelope.
- Coordinate operational agents (RAGAgent, PersistenceAgent) to perform multi-step flows.
- Return a canonical envelope: {'metadata': {...}, 'records': [...]}
"""
from typing import Any, Dict, Optional
from datetime import datetime, timezone
import uuid


class BaseOrchestrator:
    """Minimal base class for high-level orchestrators.

    Implementations should override `run`.
    """

    def __init__(self, registry: Dict[str, Any] | None = None):
        # registry could hold instantiated operational agents or tool references
        self.registry = registry or {}

    def make_run_id(self, prefix: str = "run") -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{prefix}-{ts}-{uuid.uuid4().hex[:8]}"

    def validate_envelope(self, env: Any) -> bool:
        """Minimal envelope shape validator.

        Accepts dicts with 'metadata' (dict) and 'records' (list).
        """
        if not isinstance(env, dict):
            return False
        if 'metadata' not in env or 'records' not in env:
            return False
        if not isinstance(env['metadata'], dict):
            return False
        if not isinstance(env['records'], list):
            return False
        return True

    def get_agent(self, name: str) -> Optional[Any]:
        """Return a registered agent/tool by name or None."""
        return self.registry.get(name)

    def run(self, request: Any) -> Dict[str, Any]:
        """Run an orchestration flow.

        - `request` can be a free-text prompt, a dict payload, or an envelope.
        - Returns a canonical envelope.
        """
        raise NotImplementedError()


# For compatibility
ORCHESTRATOR_BASE = BaseOrchestrator
