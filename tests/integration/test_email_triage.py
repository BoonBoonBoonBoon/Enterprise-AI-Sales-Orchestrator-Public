"""
Integration test for email triage flow.

Tests the Tier-0 pre-filter → Tier-2 Inbound Orchestrator → Tier-3 Classifier flow.
"""
import pytest
from typing import Dict, Any


def make_inbound_task(
    from_email: str,
    subject: str,
    body: str = "",
    pre_filter_category: str = None,
    pre_filter_confidence: float = 0.0,
) -> Dict[str, Any]:
    """Build a mock inbound task envelope like Manager would send."""
    return {
        "metadata": {"task_id": f"test-{id(subject)}"},
        "payload": {
            "context": {
                "email_event": {
                    "message_id": f"msg-{id(subject)}",
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


class TestPreFilter:
    """Test Tier-0 pre-filter (cheap header-based classification)."""

    def test_bounce_detection(self):
        from services.email.pre_filter import pre_filter_email

        result = pre_filter_email(
            from_email="mailer-daemon@example.com",
            subject="Delivery Status Notification (Failure)",
            body="Your message could not be delivered.",
        )
        assert result.category == "bounce"
        assert result.confidence >= 0.9

    def test_newsletter_detection_with_list_unsubscribe(self):
        from services.email.pre_filter import pre_filter_email

        result = pre_filter_email(
            from_email="newsletter@company.com",
            subject="Weekly Digest",
            body="Here's what happened this week...",
            list_unsubscribe="<mailto:unsubscribe@company.com>",
        )
        assert result.category in ("newsletter", "marketing")
        assert result.confidence >= 0.7

    def test_marketing_detection(self):
        from services.email.pre_filter import pre_filter_email

        result = pre_filter_email(
            from_email="promo@company.com",
            subject="Limited-time offer: 50% off",
            body="Redeem this offer now! Unsubscribe anytime.",
            list_unsubscribe="<mailto:unsubscribe@company.com>",
            x_mailer="Customer.io",
        )
        assert result.category == "marketing"
        assert result.confidence >= 0.75

    def test_system_overrides_list_unsubscribe(self):
        from services.email.pre_filter import pre_filter_email

        result = pre_filter_email(
            from_email="support@product.com",
            subject="Security Advisor Summary for your account",
            body="You have 1 project that triggers warnings.",
            list_unsubscribe="<https://unsubscribe.example.com>",
        )
        assert result.category == "system"
        assert result.confidence >= 0.75

    def test_personal_email_passes_prefilter(self):
        from services.email.pre_filter import pre_filter_email

        result = pre_filter_email(
            from_email="john.smith@gmail.com",
            subject="Re: Question about your services",
            body="Hi, I wanted to follow up on our conversation.",
        )
        # Personal emails should NOT be categorized by pre-filter
        assert result.category is None or result.confidence < 0.5


class TestClassifierAgent:
    """Test Tier-3 Classifier Agent (rules-based classification)."""

    def test_personal_email_classification(self):
        from tiers.tier_3.classifier_agent import ClassifierAgent, ClassificationAction

        classifier = ClassifierAgent()
        result = classifier.classify({
            "from_email": "john.smith@gmail.com",
            "subject": "Re: Pricing question",
            "body": "Can we schedule a call to discuss?",
        })
        assert result.action == ClassificationAction.ROUTE_TO_LEADS
        assert result.confidence >= 0.7

    def test_newsletter_classification(self):
        from tiers.tier_3.classifier_agent import ClassifierAgent, ClassificationAction

        classifier = ClassifierAgent()
        result = classifier.classify({
            "from_email": "noreply@mailchimp.com",
            "subject": "Weekly Newsletter - Special Offers Inside!",
            "body": "Check out our latest deals...",
            "pre_filter": {"category": "newsletter", "confidence": 0.85},
        })
        assert result.action == ClassificationAction.STORE_ONLY

    def test_bounce_classification(self):
        from tiers.tier_3.classifier_agent import ClassifierAgent, ClassificationAction

        classifier = ClassifierAgent()
        result = classifier.classify({
            "from_email": "mailer-daemon@example.com",
            "subject": "Delivery failure",
            "body": "Message undeliverable",
            "pre_filter": {"category": "bounce", "confidence": 0.95},
        })
        assert result.action == ClassificationAction.DROP


class TestInboundOrchestrator:
    """Test Tier-2 Inbound Orchestrator (integration with classifier)."""

    def test_orchestrator_classifies_personal_email(self):
        """Verify orchestrator correctly classifies and routes personal emails."""
        from tiers.tier_3.classifier_agent import ClassifierAgent, ClassificationAction

        # We test the classifier directly since the orchestrator requires Redis
        classifier = ClassifierAgent()
        email_event = {
            "from_email": "prospect@company.com",
            "subject": "Interested in your product",
            "body": "I would like to learn more about your pricing.",
            "pre_filter": {"category": None, "confidence": 0.0},
        }
        result = classifier.classify(email_event)
        
        assert result.action == ClassificationAction.ROUTE_TO_LEADS
        assert result.category.value in ("personal", "business_inquiry")

    def test_orchestrator_stores_marketing_email(self):
        """Verify orchestrator correctly stores marketing emails without reply."""
        from tiers.tier_3.classifier_agent import ClassifierAgent, ClassificationAction

        classifier = ClassifierAgent()
        email_event = {
            "from_email": "marketing@hubspot.com",
            "subject": "50% off - Limited time offer!",
            "body": "Don't miss out on this exclusive deal...",
            "pre_filter": {"category": "newsletter", "confidence": 0.8},
        }
        result = classifier.classify(email_event)
        
        assert result.action == ClassificationAction.STORE_ONLY


class TestEndToEndTriageFlow:
    """End-to-end tests for the full triage pipeline."""

    def test_full_triage_flow_personal_email(self):
        """Test full flow: pre-filter → classifier → routing decision."""
        from services.email.pre_filter import pre_filter_email
        from tiers.tier_3.classifier_agent import ClassifierAgent, ClassificationAction

        # 1. Pre-filter
        pre_result = pre_filter_email(
            from_email="ceo@bigcorp.com",
            subject="Partnership opportunity",
            body="I'd like to discuss a potential collaboration.",
        )
        
        # 2. Classify
        classifier = ClassifierAgent()
        email_event = {
            "from_email": "ceo@bigcorp.com",
            "subject": "Partnership opportunity",
            "body": "I'd like to discuss a potential collaboration.",
            "pre_filter": {
                "category": pre_result.category,
                "confidence": pre_result.confidence,
            },
        }
        class_result = classifier.classify(email_event)
        
        # 3. Assert routing - ROUTE_TO_LEADS or REVIEW both acceptable for personal email
        # (REVIEW still gets routed to leads for human oversight)
        assert class_result.action in (
            ClassificationAction.ROUTE_TO_LEADS,
            ClassificationAction.REVIEW,
        )
        # Should NOT be stored-only or dropped
        assert class_result.action not in (
            ClassificationAction.STORE_ONLY,
            ClassificationAction.DROP,
        )

    def test_full_triage_flow_bounce(self):
        """Test full flow for bounce email: should be dropped."""
        from services.email.pre_filter import pre_filter_email
        from tiers.tier_3.classifier_agent import ClassifierAgent, ClassificationAction

        # 1. Pre-filter
        pre_result = pre_filter_email(
            from_email="MAILER-DAEMON@mail.example.com",
            subject="Undelivered Mail Returned to Sender",
            body="This is the mail system at host mail.example.com.",
        )
        assert pre_result.category == "bounce"
        
        # 2. Classify
        classifier = ClassifierAgent()
        class_result = classifier.classify({
            "from_email": "MAILER-DAEMON@mail.example.com",
            "subject": "Undelivered Mail Returned to Sender",
            "body": "This is the mail system at host mail.example.com.",
            "pre_filter": {
                "category": pre_result.category,
                "confidence": pre_result.confidence,
            },
        })
        
        # 3. Assert drop
        assert class_result.action == ClassificationAction.DROP


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
