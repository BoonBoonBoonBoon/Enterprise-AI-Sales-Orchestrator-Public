from typing import Dict, Any
from agent.tools.delivery.interface import DeliveryAdapter


class NoOpDeliveryAdapter:
    """A no-op delivery adapter for tests and dry-run mode.

    The adapter returns a uniform result dict and does not perform any side-effects.
    """

    def __init__(self, disabled: bool = False):
        self.disabled = disabled

    def send(self, channel: str, payload: Dict[str, Any], meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
        if self.disabled:
            return {"status": "DISABLED", "reason": "delivery disabled"}
        # echo back minimal provider-like response
        return {"status": "SENT", "channel": channel, "provider_id": "noop-1234", "meta": meta}


__all__ = ["NoOpDeliveryAdapter"]
