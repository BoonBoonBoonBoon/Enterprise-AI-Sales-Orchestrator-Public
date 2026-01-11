from typing import Any, Dict, Optional, Protocol


class QueueInterface(Protocol):
    """Abstract queue contract used by CampaignManager and Worker.

    Message shape used by the system:
      {
          "job_id": "<uuid>",
          "run_id": "<run id>",
          "orchestrator": "<orchestrator name>",
          "payload": {...},
          "meta": {...}
      }
    """

    def enqueue(self, topic: str, message: Dict[str, Any]) -> str:
        """Enqueue a message on topic. Return job_id."""

    def dequeue(self, topic: str, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Blocking pop from topic. Return full job dict or None on timeout."""

    def ack(self, job_id: str) -> None:
        """Acknowledge completion of job_id (idempotent)."""

    def requeue(self, job: Dict[str, Any], delay: Optional[float] = None) -> str:
        """Re-enqueue a job (optionally with delay). Returns new job_id."""
