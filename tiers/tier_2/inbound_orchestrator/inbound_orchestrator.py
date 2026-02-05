"""
Inbound Orchestrator Implementation

Orchestrates inbound communication processing including:
- Email/message intake
- Content classification (via Tier-3 Classifier Agent)
- Routing based on classification (Leads for reply, store-only, or drop)
"""

from typing import Any, Dict, List, Optional
import logging
import uuid

from core.envelope import Envelope, task as create_task_envelope, to_redis_fields
from services.redis import RedisStreamsClient
from tiers.tier_3.classifier_agent import (
    ClassifierAgent,
    ClassificationAction,
    ClassificationResult,
    EmailCategory,
)

logger = logging.getLogger(__name__)


class InboundOrchestrator:
    """
    Tier 2 Orchestrator for inbound communication processing.

    Coordinates intake and processing of inbound communications:
    1. Receives email events from Manager
    2. Calls Classifier Agent (Tier-3) for classification
    3. Routes based on classification:
       - ROUTE_TO_LEADS: Forward to Leads Orchestrator for reply
       - STORE_ONLY: Persist via Persistence Agent (no reply)
       - DROP: Discard (optionally log for audit)
       - REVIEW: Flag for human review
    """

    def __init__(self, tenant_id: str = "agentic-dev", config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Inbound Orchestrator.

        Args:
            tenant_id: Tenant identifier for stream namespacing
            config: Optional configuration dictionary
        """
        self.tenant_id = tenant_id
        self.config = config or {}
        self.classifier = ClassifierAgent()
        self.redis_client = RedisStreamsClient()
        logger.info("InboundOrchestrator initialized (tenant=%s)", tenant_id)

    def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an inbound communication task.

        Args:
            task: Task envelope dict containing inbound email event

        Returns:
            Result dict with classification and routing outcome
        """
        payload = task.get("payload", {})
        context = payload.get("context", {})
        email_event = context.get("email_event", {})
        pre_filter = context.get("pre_filter", {})
        task_id = task.get("metadata", {}).get("task_id", str(uuid.uuid4()))

        logger.info("Processing inbound task: %s (message_id=%s)", task_id, email_event.get("message_id"))

        # 1. Classify the email
        email_event["pre_filter"] = pre_filter
        classification = self.classifier.classify(email_event)

        logger.info(
            "Classification result: category=%s action=%s confidence=%.2f",
            classification.category.value,
            classification.action.value,
            classification.confidence,
        )

        # 2. Route based on classification action
        routing_result = self._route_by_action(
            task_id=task_id,
            email_event=email_event,
            classification=classification,
            original_task=task,
        )

        return {
            "status": "success",
            "task_id": task_id,
            "message_id": email_event.get("message_id"),
            "classification": classification.to_dict(),
            "routing": routing_result,
        }

    def _route_by_action(
        self,
        task_id: str,
        email_event: Dict[str, Any],
        classification: ClassificationResult,
        original_task: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Route the email based on classification action."""

        action = classification.action

        if action == ClassificationAction.ROUTE_TO_LEADS:
            return self._forward_to_leads(task_id, email_event, classification, original_task)

        elif action == ClassificationAction.STORE_ONLY:
            return self._store_only(task_id, email_event, classification)

        elif action == ClassificationAction.DROP:
            return self._drop_email(task_id, email_event, classification)

        elif action == ClassificationAction.REVIEW:
            # For now, treat REVIEW same as ROUTE_TO_LEADS (human can review in Leads flow)
            logger.info("Email flagged for REVIEW, routing to Leads for human oversight")
            return self._forward_to_leads(task_id, email_event, classification, original_task)

        else:
            logger.warning("Unknown action %s, defaulting to STORE_ONLY", action)
            return self._store_only(task_id, email_event, classification)

    def _forward_to_leads(
        self,
        task_id: str,
        email_event: Dict[str, Any],
        classification: ClassificationResult,
        original_task: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Forward email to Leads Orchestrator for reply processing."""
        # NOTE: Tier-2 orchestrators must not publish to other orchestrators' task streams.
        # We return a delegation recommendation for Manager (Tier-1) to mediate.
        return {
            "action": "delegate",
            "delegate": {
                "orchestrator": "leads",
                "goal": "process inbound email for reply",
                "intent": "inbound",
                "context": {
                    "email_event": email_event,
                    "classification": classification.to_dict(),
                    "actions_allowed": ["store", "enrich", "reply"],
                },
            },
            "category": classification.category.value,
        }

    def _store_only(
        self,
        task_id: str,
        email_event: Dict[str, Any],
        classification: ClassificationResult,
    ) -> Dict[str, Any]:
        """Store email without generating a reply."""
        # NOTE: Persistence does not implement the legacy `store_inbound_email` operation.
        # To ensure full staging lead/conversation/message persistence, we delegate to
        # LeadsOrchestrator (Tier-2), mediated by Manager (Tier-1).
        return {
            "action": "delegate",
            "delegate": {
                "orchestrator": "leads",
                "goal": "store inbound email (no reply)",
                "intent": "inbound",
                "context": {
                    "email_event": email_event,
                    "classification": classification.to_dict(),
                    "actions_allowed": ["store"],
                },
            },
            "category": classification.category.value,
        }

    def _drop_email(
        self,
        task_id: str,
        email_event: Dict[str, Any],
        classification: ClassificationResult,
    ) -> Dict[str, Any]:
        """Drop email without storing or replying."""
        logger.info(
            "Dropping email: message_id=%s category=%s reason=%s",
            email_event.get("message_id"),
            classification.category.value,
            classification.reasoning,
        )
        # Optionally: store in an audit/dropped log table for later review
        # For now, just return drop result
        return {
            "action": "dropped",
            "category": classification.category.value,
            "reason": classification.reasoning,
        }
