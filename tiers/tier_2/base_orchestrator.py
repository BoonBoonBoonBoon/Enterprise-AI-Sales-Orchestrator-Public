"""Base class for Tier 2 orchestrators.

Responsibilities:
- Accept a free-text request or an envelope.
- Coordinate operational agents (RAGAgent, PersistenceAgent) to perform multi-step flows.
- Return a canonical typed envelope (core.envelope.Envelope).
"""
from typing import Any, Dict, Optional
from datetime import datetime, timezone
import uuid

from core.envelope.typed_envelope import Envelope as TypedEnvelope, normalize_envelope


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
        """Validate envelope by normalizing into typed Envelope."""
        try:
            normalize_envelope(env, default_source="orchestrator")
            return True
        except Exception:
            return False

    def standardize_envelope(self, env: Any, *, default_source: str = "orchestrator") -> TypedEnvelope:
        """Normalize legacy or typed envelopes into the canonical typed envelope."""
        return normalize_envelope(env, default_source=default_source)

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
