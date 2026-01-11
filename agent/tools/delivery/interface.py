from __future__ import annotations

from typing import Protocol, Dict, Any


class DeliveryAdapter(Protocol):
    """Protocol for delivery adapters.

    Implementations must provide a `send` method that accepts a channel
    (e.g. 'email', 'text', 'whatsapp'), an envelope or message payload, and
    optional meta. Returns a delivery result dict with at least `status`.
    """

    def send(self, channel: str, payload: Dict[str, Any], meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
        ...


__all__ = ["DeliveryAdapter"]
