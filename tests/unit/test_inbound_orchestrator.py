"""
Unit tests for Inbound Orchestrator.

Tests the Tier-2 Inbound Orchestrator routing logic with mocked Redis.
"""
import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, Any


def make_inbound_task(
    from_email: str,
    subject: str,
    body: str = "",
    pre_filter_category: str = None,
    pre_filter_confidence: float = 0.0,
    message_id: str = None,
    thread_id: str = None,
) -> Dict[str, Any]:
    """Build a mock inbound task envelope like Manager would send."""
    return {
        "metadata": {"task_id": f"test-{id(subject)}"},
        "payload": {
            "context": {
                "email_event": {
                    "message_id": message_id or f"msg-{id(subject)}",
                    "thread_id": thread_id,
                    "from_email": from_email,
                    "subject": subject,
                    "body": body,
                },
                "pre_filter": {
                    "category": pre_filter_category,
                    "confidence": pre_filter_confidence,
                    "reason": "test",
                },
            },
            "intent": "inbound",
        },
    }


class TestInboundOrchestratorRouting:
    """Test InboundOrchestrator routing logic."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client to avoid real connections."""
        with patch("tiers.tier_2.inbound_orchestrator.inbound_orchestrator.RedisStreamsClient") as mock:
            mock_instance = MagicMock()
            mock.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def orchestrator(self, mock_redis):
        """Create orchestrator with mocked Redis."""
        from tiers.tier_2.inbound_orchestrator.inbound_orchestrator import InboundOrchestrator
        return InboundOrchestrator(tenant_id="test-tenant")

    def test_personal_email_routed_to_leads(self, orchestrator, mock_redis):
        """Personal emails should recommend delegation to Leads (Manager-mediated)."""
        task = make_inbound_task(
            from_email="prospect@company.com",
            subject="Re: Question about pricing",
            body="I'd like to schedule a call to discuss your services.",
        )

        result = orchestrator.process_task(task)

        assert result["status"] == "success"
        assert result["routing"]["action"] == "delegate"
        assert result["routing"]["delegate"]["orchestrator"] == "leads"
        assert "reply" in result["routing"]["delegate"]["context"].get("actions_allowed", [])

        # Inbound orchestrator must not publish to other orchestrators/agents directly.
        mock_redis.xadd.assert_not_called()

    def test_newsletter_stored_only(self, orchestrator, mock_redis):
        """Newsletters should be delegated to Leads with store-only actions (Manager-mediated)."""
        task = make_inbound_task(
            from_email="noreply@mailchimp.com",
            subject="Weekly Newsletter - Great Deals!",
            body="Check out our amazing offers...",
            pre_filter_category="newsletter",
            pre_filter_confidence=0.85,
        )

        result = orchestrator.process_task(task)

        assert result["status"] == "success"
        assert result["routing"]["action"] == "delegate"
        assert result["routing"]["delegate"]["orchestrator"] == "leads"
        assert result["routing"]["delegate"]["context"].get("actions_allowed") == ["store"]

        # Inbound orchestrator does not publish directly.
        mock_redis.xadd.assert_not_called()

    def test_bounce_dropped(self, orchestrator, mock_redis):
        """Bounces should be dropped without storing or replying."""
        task = make_inbound_task(
            from_email="mailer-daemon@example.com",
            subject="Delivery Status Notification (Failure)",
            body="Your message could not be delivered.",
            pre_filter_category="bounce",
            pre_filter_confidence=0.95,
        )

        result = orchestrator.process_task(task)

        assert result["status"] == "success"
        assert result["routing"]["action"] == "dropped"
        assert result["routing"]["category"] == "bounce"

        # Verify Redis xadd was NOT called (nothing persisted)
        mock_redis.xadd.assert_not_called()

    def test_review_routed_to_leads(self, orchestrator, mock_redis):
        """Emails flagged for REVIEW should be routed to Leads for human oversight."""
        # Ambiguous email that triggers REVIEW action
        task = make_inbound_task(
            from_email="unknown@random.net",
            subject="Important information",
            body="Please see attached.",  # Vague, no clear personal/business signals
        )

        result = orchestrator.process_task(task)

        assert result["status"] == "success"
        # REVIEW is routed to leads for human oversight (as a delegation recommendation)
        assert result["routing"]["action"] != "dropped"
        if result["routing"]["action"] == "delegate":
            assert result["routing"]["delegate"]["orchestrator"] == "leads"

    def test_auto_reply_stored_only(self, orchestrator, mock_redis):
        """Auto-replies (OOO) should be stored without generating a reply."""
        task = make_inbound_task(
            from_email="someone@company.com",
            subject="Out of Office: John Smith",
            body="I am currently out of the office and will return on Monday.",
            pre_filter_category="auto_reply",
            pre_filter_confidence=0.90,
        )

        result = orchestrator.process_task(task)

        assert result["status"] == "success"
        # Auto-replies should NOT trigger a reply
        assert result["routing"]["action"] in ("delegate", "dropped")
        if result["routing"]["action"] == "delegate":
            assert result["routing"]["delegate"]["context"].get("actions_allowed") == ["store"]


class TestInboundOrchestratorEdgeCases:
    """Edge case tests for InboundOrchestrator."""

    @pytest.fixture
    def mock_redis(self):
        with patch("tiers.tier_2.inbound_orchestrator.inbound_orchestrator.RedisStreamsClient") as mock:
            mock_instance = MagicMock()
            mock.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def orchestrator(self, mock_redis):
        from tiers.tier_2.inbound_orchestrator.inbound_orchestrator import InboundOrchestrator
        return InboundOrchestrator(tenant_id="test-tenant")

    def test_missing_email_event(self, orchestrator, mock_redis):
        """Handle missing email_event gracefully."""
        task = {
            "metadata": {"task_id": "test-missing"},
            "payload": {
                "context": {},  # No email_event
                "intent": "inbound",
            },
        }

        result = orchestrator.process_task(task)

        # Should still return a result (may classify as unknown)
        assert result["status"] == "success"

    def test_empty_subject_and_body(self, orchestrator, mock_redis):
        """Handle empty subject and body."""
        task = make_inbound_task(
            from_email="user@example.com",
            subject="",
            body="",
        )

        result = orchestrator.process_task(task)

        # Should classify as unknown/review but not crash
        assert result["status"] == "success"

    def test_prefilter_low_confidence_ignored(self, orchestrator, mock_redis):
        """Low-confidence pre-filter results should not override classifier."""
        task = make_inbound_task(
            from_email="prospect@gmail.com",
            subject="Re: Pricing question",
            body="Can we discuss pricing next week?",
            pre_filter_category="newsletter",  # Wrong category
            pre_filter_confidence=0.3,  # Low confidence - should be ignored
        )

        result = orchestrator.process_task(task)

        assert result["status"] == "success"
        # Should still recommend delegation to leads (classifier overrides low-confidence pre-filter)
        assert result["routing"]["action"] == "delegate"
        assert result["routing"]["delegate"]["orchestrator"] == "leads"

    def test_from_field_alias(self, orchestrator, mock_redis):
        """Handle 'from' alias for 'from_email'."""
        task = {
            "metadata": {"task_id": "test-from-alias"},
            "payload": {
                "context": {
                    "email_event": {
                        "message_id": "msg-alias-test",
                        "from": "prospect@company.com",  # Using 'from' instead of 'from_email'
                        "subject": "Interested in your product",
                        "body": "I would like to learn more.",
                    },
                    "pre_filter": {"category": None, "confidence": 0.0, "reason": "test"},
                },
                "intent": "inbound",
            },
        }

        result = orchestrator.process_task(task)

        assert result["status"] == "success"


class TestClassificationMetadata:
    """Test that classification metadata is properly propagated."""

    @pytest.fixture
    def mock_redis(self):
        with patch("tiers.tier_2.inbound_orchestrator.inbound_orchestrator.RedisStreamsClient") as mock:
            mock_instance = MagicMock()
            mock.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def orchestrator(self, mock_redis):
        from tiers.tier_2.inbound_orchestrator.inbound_orchestrator import InboundOrchestrator
        return InboundOrchestrator(tenant_id="test-tenant")

    def test_classification_included_in_result(self, orchestrator, mock_redis):
        """Classification details should be included in the result."""
        task = make_inbound_task(
            from_email="ceo@bigcorp.com",
            subject="Partnership opportunity",
            body="I'd like to discuss a potential collaboration.",
        )

        result = orchestrator.process_task(task)

        assert "classification" in result
        classification = result["classification"]
        assert "category" in classification
        assert "confidence" in classification
        assert "action" in classification
        assert "signals" in classification

    def test_message_id_in_result(self, orchestrator, mock_redis):
        """Message ID should be included in the result."""
        task = make_inbound_task(
            from_email="user@example.com",
            subject="Test",
            body="Test body",
            message_id="unique-message-id-123",
        )

        result = orchestrator.process_task(task)

        assert result["message_id"] == "unique-message-id-123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
