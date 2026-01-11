from typing import Any, Dict, Optional, Protocol


class QueueInterface(Protocol):
    """Protocol shim matching Infastructure.queue.interface.QueueInterface.

    Keeps legacy high_level_agents imports working while we converge packages.
    """

    def enqueue(self, topic: str, message: Dict[str, Any]) -> str:  # pragma: no cover - interface only
        ...  # noqa: D401,E701

    def dequeue(self, topic: str, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:  # pragma: no cover
        ...

    def ack(self, job_id: str) -> None:  # pragma: no cover
        ...

    def requeue(self, job: Dict[str, Any], delay: Optional[float] = None) -> str:  # pragma: no cover
        ...

__all__ = ["QueueInterface"]
