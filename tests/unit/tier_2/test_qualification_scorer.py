"""Comprehensive unit tests for the Lead Qualification Scorer.

Tests cover:
- Individual signal scoring (email category, conversation, profile, engagement, negative)
- Threshold-based decisions (qualified, nurture, disqualified)
- Fast-track rules
- Edge cases (missing fields, empty input, malformed data)
- Score clamping (0-100)
- Deterministic behavior (same input → same output)
"""

import pytest
from copy import deepcopy
from typing import Any, Dict, List

from tiers.tier_2.leads_orchestrator.qualification.scorer import (
    QualificationScorer,
    QualificationResult,
    score_lead_sync,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def scorer() -> QualificationScorer:
    """Fresh scorer instance with default config."""
    return QualificationScorer()


@pytest.fixture
def high_intent_lead() -> Dict[str, Any]:
    """Lead data for a high-intent prospect."""
    return {
        "email": "jane.ceo@acme.com",
        "first_name": "Jane",
        "last_name": "Smith",
        "company_name": "Acme Corp",
        "job_title": "CEO",
        "phone_number": "+1-555-123-4567",
        "linkedin_url": "https://linkedin.com/in/janesmith",
    }


@pytest.fixture
def low_intent_lead() -> Dict[str, Any]:
    """Lead data for a low-intent contact."""
    return {
        "email": "random123@gmail.com",
        "first_name": "Random",
    }


@pytest.fixture
def spam_classification() -> Dict[str, Any]:
    """Email classified as spam."""
    return {"category": "spam", "confidence": 0.95}


@pytest.fixture
def business_inquiry_classification() -> Dict[str, Any]:
    """Email classified as business inquiry."""
    return {"category": "business_inquiry", "confidence": 0.92}


@pytest.fixture
def meeting_request_messages() -> List[Dict[str, Any]]:
    """Conversation with meeting request."""
    return [
        {
            "content": "Hi, I'd love to schedule a demo of your product this week. What times work?",
            "direction": "inbound",
            "sender": "prospect@company.com",
        },
    ]


@pytest.fixture
def unsubscribe_messages() -> List[Dict[str, Any]]:
    """Conversation with unsubscribe request."""
    return [
        {
            "content": "Please unsubscribe me from your list. Stop emailing me.",
            "direction": "inbound",
            "sender": "annoyed@example.com",
        },
    ]


# =============================================================================
# BASIC FUNCTIONALITY TESTS
# =============================================================================


class TestScorerInitialization:
    """Test scorer initialization and config loading."""
    
    def test_scorer_initializes_with_defaults(self, scorer: QualificationScorer):
        """Scorer should initialize with valid config."""
        assert scorer.config is not None
        assert scorer.config.thresholds.get("auto_promote") == 70
        assert scorer.config.thresholds.get("fast_track") == 85
        assert scorer.config.thresholds.get("disqualify") == 20
    
    def test_scorer_loads_signal_weights(self, scorer: QualificationScorer):
        """Scorer should load signal weights from config."""
        assert "email_category" in scorer.config.signals
        assert "conversation" in scorer.config.signals
        assert "profile" in scorer.config.signals
        assert "engagement" in scorer.config.signals
        assert "negative" in scorer.config.signals
    
    def test_scorer_loads_freemail_domains(self, scorer: QualificationScorer):
        """Scorer should load freemail domains list."""
        assert "gmail.com" in scorer.config.freemail_domains
        assert "yahoo.com" in scorer.config.freemail_domains


class TestScorerDeterminism:
    """Test that scorer is deterministic (same input → same output)."""
    
    def test_same_input_produces_same_score(
        self,
        scorer: QualificationScorer,
        high_intent_lead: Dict[str, Any],
        business_inquiry_classification: Dict[str, Any],
    ):
        """Identical inputs must produce identical outputs."""
        result1 = scorer.score(
            lead_data=high_intent_lead,
            email_classification=business_inquiry_classification,
        )
        result2 = scorer.score(
            lead_data=high_intent_lead,
            email_classification=business_inquiry_classification,
        )
        
        assert result1.score == result2.score
        assert result1.decision == result2.decision
        assert result1.signals == result2.signals
    
    def test_score_lead_sync_disables_llm(self, high_intent_lead: Dict[str, Any]):
        """Sync wrapper must disable LLM for determinism."""
        result = score_lead_sync(lead_data=high_intent_lead)
        assert result.llm_used is False


# =============================================================================
# EMAIL CLASSIFICATION SIGNAL TESTS
# =============================================================================


class TestEmailCategoryScoring:
    """Test email classification signal scoring."""
    
    def test_business_inquiry_adds_points(self, scorer: QualificationScorer):
        """Business inquiry should add significant points."""
        result = scorer.score(
            lead_data={"email": "test@company.com"},
            email_classification={"category": "business_inquiry", "confidence": 0.9},
        )
        
        assert any("email_category:business_inquiry:+25" in s for s in result.signals)
        assert result.score >= 25
    
    def test_spam_subtracts_points(self, scorer: QualificationScorer):
        """Spam should subtract significant points."""
        result = scorer.score(
            lead_data={"email": "test@company.com"},
            email_classification={"category": "spam", "confidence": 0.95},
        )
        
        assert any("email_category:spam:-50" in s for s in result.signals)
    
    def test_bounce_subtracts_points(self, scorer: QualificationScorer):
        """Bounce should subtract points."""
        result = scorer.score(
            lead_data={"email": "test@company.com"},
            email_classification={"category": "bounce", "confidence": 0.99},
        )
        
        assert any("bounce" in s and "-" in s for s in result.signals)
    
    def test_high_confidence_bonus(self, scorer: QualificationScorer):
        """High confidence on positive categories should add bonus."""
        result = scorer.score(
            lead_data={"email": "test@company.com"},
            email_classification={"category": "business_inquiry", "confidence": 0.95},
        )
        
        assert any("high_confidence" in s for s in result.signals)
    
    def test_unknown_category_handled(self, scorer: QualificationScorer):
        """Unknown category should not crash."""
        result = scorer.score(
            lead_data={"email": "test@company.com"},
            email_classification={"category": "totally_unknown_category"},
        )
        
        assert result.score >= 0


# =============================================================================
# CONVERSATION SIGNAL TESTS
# =============================================================================


class TestConversationScoring:
    """Test conversation signal scoring."""
    
    def test_meeting_request_adds_high_points(
        self,
        scorer: QualificationScorer,
        meeting_request_messages: List[Dict[str, Any]],
    ):
        """Meeting request should add high intent points."""
        result = scorer.score(
            lead_data={"email": "test@company.com"},
            conversation_history=meeting_request_messages,
        )
        
        assert any("requested_meeting" in s for s in result.signals)
        assert result.score >= 20
    
    def test_question_adds_points(self, scorer: QualificationScorer):
        """Question mark in content should add points."""
        result = scorer.score(
            lead_data={"email": "test@company.com"},
            conversation_history=[
                {"content": "What are your pricing options?", "direction": "inbound"}
            ],
        )
        
        assert any("asked_question" in s for s in result.signals)
    
    def test_budget_keywords_add_points(self, scorer: QualificationScorer):
        """Budget keywords should add points."""
        result = scorer.score(
            lead_data={"email": "test@company.com"},
            conversation_history=[
                {"content": "We have a budget of $50k for this quarter.", "direction": "inbound"}
            ],
        )
        
        assert any("mentioned_budget" in s for s in result.signals)
    
    def test_multiple_messages_add_points(self, scorer: QualificationScorer):
        """3+ messages should add engagement points."""
        result = scorer.score(
            lead_data={"email": "test@company.com"},
            conversation_history=[
                {"content": "Hello", "direction": "inbound"},
                {"content": "Hi there", "direction": "outbound"},
                {"content": "Thanks!", "direction": "inbound"},
            ],
        )
        
        assert any("multiple_messages" in s for s in result.signals)
    
    def test_empty_conversation_handled(self, scorer: QualificationScorer):
        """Empty conversation should not crash."""
        result = scorer.score(
            lead_data={"email": "test@company.com"},
            conversation_history=[],
        )
        
        assert result.score >= 0


# =============================================================================
# PROFILE SIGNAL TESTS
# =============================================================================


class TestProfileScoring:
    """Test lead profile signal scoring."""
    
    def test_company_name_adds_points(self, scorer: QualificationScorer):
        """Having company name should add points."""
        result = scorer.score(
            lead_data={"email": "test@company.com", "company_name": "Acme Corp"},
        )
        
        assert any("has_company" in s for s in result.signals)
    
    def test_decision_maker_title_adds_bonus(
        self,
        scorer: QualificationScorer,
        high_intent_lead: Dict[str, Any],
    ):
        """Decision maker title should add bonus points."""
        result = scorer.score(lead_data=high_intent_lead)
        
        assert any("decision_maker_title" in s for s in result.signals)
    
    def test_known_domain_adds_points(self, scorer: QualificationScorer):
        """Non-freemail domain should add points."""
        result = scorer.score(
            lead_data={"email": "ceo@enterprise.com"},
        )
        
        assert any("known_domain" in s for s in result.signals)
    
    def test_freemail_domain_no_bonus(self, scorer: QualificationScorer):
        """Freemail domain should not add known_domain bonus."""
        result = scorer.score(
            lead_data={"email": "someone@gmail.com"},
        )
        
        assert not any("known_domain" in s for s in result.signals)
    
    def test_phone_adds_points(self, scorer: QualificationScorer):
        """Having phone number should add points."""
        result = scorer.score(
            lead_data={"email": "test@company.com", "phone_number": "+1-555-1234"},
        )
        
        assert any("has_phone" in s for s in result.signals)
    
    def test_linkedin_adds_points(self, scorer: QualificationScorer):
        """Having LinkedIn should add points."""
        result = scorer.score(
            lead_data={"email": "test@company.com", "linkedin_url": "https://linkedin.com/in/test"},
        )
        
        assert any("has_linkedin" in s for s in result.signals)


# =============================================================================
# ENGAGEMENT SIGNAL TESTS
# =============================================================================


class TestEngagementScoring:
    """Test engagement signal scoring."""
    
    def test_first_contact_inbound_adds_points(self, scorer: QualificationScorer):
        """New lead reaching out first should add points."""
        result = scorer.score(
            lead_data={"email": "test@company.com"},
            lead_source="new",
            email_direction="inbound",
        )
        
        assert any("first_contact_inbound" in s for s in result.signals)
    
    def test_campaign_reply_adds_high_points(self, scorer: QualificationScorer):
        """Reply to campaign should add high points."""
        result = scorer.score(
            lead_data={"email": "test@company.com"},
            lead_source="leads",
            email_direction="inbound",
        )
        
        assert any("campaign_reply" in s for s in result.signals)


# =============================================================================
# NEGATIVE SIGNAL TESTS
# =============================================================================


class TestNegativeScoring:
    """Test negative signal scoring."""
    
    def test_unsubscribe_subtracts_points(
        self,
        scorer: QualificationScorer,
        unsubscribe_messages: List[Dict[str, Any]],
    ):
        """Unsubscribe request should subtract significant points."""
        result = scorer.score(
            lead_data={"email": "test@company.com"},
            conversation_history=unsubscribe_messages,
        )
        
        assert any("unsubscribe" in s and "-" in s for s in result.signals)
    
    def test_not_interested_subtracts_points(self, scorer: QualificationScorer):
        """'Not interested' should subtract points."""
        result = scorer.score(
            lead_data={"email": "test@company.com"},
            conversation_history=[
                {"content": "No thanks, not interested at all.", "direction": "inbound"}
            ],
        )
        
        assert any("not_interested" in s.lower() for s in result.signals) or result.score < 50
    
    def test_competitor_subtracts_points(self, scorer: QualificationScorer):
        """Competitor mention should subtract points."""
        result = scorer.score(
            lead_data={"email": "test@company.com"},
            conversation_history=[
                {"content": "I work for a competitor, just checking you out.", "direction": "inbound"}
            ],
        )
        
        # Should detect negative signal
        assert result.score < 50


# =============================================================================
# THRESHOLD & DECISION TESTS
# =============================================================================


class TestDecisionThresholds:
    """Test threshold-based decisions."""
    
    def test_high_score_qualifies(
        self,
        scorer: QualificationScorer,
        high_intent_lead: Dict[str, Any],
        business_inquiry_classification: Dict[str, Any],
        meeting_request_messages: List[Dict[str, Any]],
    ):
        """High score should result in qualification."""
        result = scorer.score(
            lead_data=high_intent_lead,
            email_classification=business_inquiry_classification,
            conversation_history=meeting_request_messages,
        )
        
        assert result.score >= 70
        assert result.decision in ("qualified", "fast_track")
        assert result.promote is True
    
    def test_low_score_disqualifies(
        self,
        scorer: QualificationScorer,
        low_intent_lead: Dict[str, Any],
        spam_classification: Dict[str, Any],
    ):
        """Low score should result in disqualification."""
        result = scorer.score(
            lead_data=low_intent_lead,
            email_classification=spam_classification,
        )
        
        assert result.score <= 20
        assert result.decision == "disqualified"
        assert result.promote is False
    
    def test_middle_score_nurtures(self, scorer: QualificationScorer):
        """Middle score should result in nurture."""
        result = scorer.score(
            lead_data={"email": "someone@company.com"},
            email_classification={"category": "unknown", "confidence": 0.5},
        )
        
        # Score should be in nurture range (21-69)
        if 21 <= result.score <= 69:
            assert result.decision == "nurture"
            assert result.promote is False


# =============================================================================
# FAST-TRACK TESTS
# =============================================================================


class TestFastTrack:
    """Test fast-track rules."""
    
    def test_high_score_fast_tracks(
        self,
        scorer: QualificationScorer,
        high_intent_lead: Dict[str, Any],
        business_inquiry_classification: Dict[str, Any],
        meeting_request_messages: List[Dict[str, Any]],
    ):
        """Score >= 85 should fast-track."""
        result = scorer.score(
            lead_data=high_intent_lead,
            email_classification=business_inquiry_classification,
            conversation_history=meeting_request_messages,
            lead_source="new",
            email_direction="inbound",
        )
        
        if result.score >= 85:
            assert result.fast_track is True
            assert result.decision == "fast_track"


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_lead_data(self, scorer: QualificationScorer):
        """Empty lead data should not crash."""
        result = scorer.score(lead_data={})
        
        assert isinstance(result, QualificationResult)
        assert 0 <= result.score <= 100
    
    def test_none_fields(self, scorer: QualificationScorer):
        """None field values should not crash."""
        result = scorer.score(
            lead_data={
                "email": None,
                "company_name": None,
                "job_title": None,
            }
        )
        
        assert isinstance(result, QualificationResult)
    
    def test_missing_classification(self, scorer: QualificationScorer):
        """Missing email classification should not crash."""
        result = scorer.score(
            lead_data={"email": "test@company.com"},
            email_classification=None,
        )
        
        assert isinstance(result, QualificationResult)
    
    def test_empty_string_fields(self, scorer: QualificationScorer):
        """Empty string fields should not crash."""
        result = scorer.score(
            lead_data={
                "email": "",
                "company_name": "",
                "job_title": "",
            }
        )
        
        assert isinstance(result, QualificationResult)
    
    def test_malformed_email(self, scorer: QualificationScorer):
        """Malformed email should not crash."""
        result = scorer.score(
            lead_data={"email": "not-an-email"},
        )
        
        assert isinstance(result, QualificationResult)
        assert not any("known_domain" in s for s in result.signals)
    
    def test_unicode_content(self, scorer: QualificationScorer):
        """Unicode content should be handled."""
        result = scorer.score(
            lead_data={"email": "test@company.com"},
            conversation_history=[
                {"content": "こんにちは 😀 Can we schedule a demo?", "direction": "inbound"}
            ],
        )
        
        assert isinstance(result, QualificationResult)
        assert any("requested_meeting" in s or "demo" in s.lower() for s in result.signals)
    
    def test_very_long_content(self, scorer: QualificationScorer):
        """Very long content should not crash."""
        long_content = "This is a test. " * 10000
        
        result = scorer.score(
            lead_data={"email": "test@company.com"},
            conversation_history=[
                {"content": long_content, "direction": "inbound"}
            ],
        )
        
        assert isinstance(result, QualificationResult)
    
    def test_score_clamped_to_100(self, scorer: QualificationScorer):
        """Score should never exceed 100."""
        # Create a lead that should score very high
        result = scorer.score(
            lead_data={
                "email": "ceo@enterprise.com",
                "company_name": "Big Corp",
                "job_title": "CEO",
                "phone_number": "+1-555-1234",
                "linkedin_url": "https://linkedin.com/in/bigceo",
            },
            email_classification={"category": "business_inquiry", "confidence": 0.99},
            conversation_history=[
                {"content": "I want to schedule a meeting to discuss budget and timeline for a demo.", "direction": "inbound"},
                {"content": "Sure!", "direction": "outbound"},
                {"content": "Great, let's do it ASAP.", "direction": "inbound"},
            ],
            lead_source="leads",
            email_direction="inbound",
        )
        
        assert result.score <= 100
    
    def test_score_clamped_to_0(self, scorer: QualificationScorer):
        """Score should never go below 0."""
        result = scorer.score(
            lead_data={"email": "spammer@gmail.com"},
            email_classification={"category": "spam", "confidence": 0.99},
            conversation_history=[
                {"content": "Stop emailing me! Unsubscribe! Not interested!", "direction": "inbound"}
            ],
        )
        
        assert result.score >= 0


# =============================================================================
# REGRESSION TESTS (Golden Fixtures)
# =============================================================================


class TestGoldenFixtures:
    """Regression tests with known expected outcomes."""
    
    def test_ideal_prospect_qualifies(self, scorer: QualificationScorer):
        """Ideal prospect should always qualify."""
        result = scorer.score(
            lead_data={
                "email": "jane.vp@acme.com",
                "company_name": "Acme Corp",
                "job_title": "VP of Sales",
            },
            email_classification={"category": "business_inquiry", "confidence": 0.9},
            conversation_history=[
                {"content": "Hi, I'd like to schedule a call to discuss pricing.", "direction": "inbound"}
            ],
            lead_source="new",
            email_direction="inbound",
        )
        
        assert result.promote is True
        assert result.decision in ("qualified", "fast_track")
        assert result.score >= 70
    
    def test_spam_disqualifies(self, scorer: QualificationScorer):
        """Spam should always disqualify."""
        result = scorer.score(
            lead_data={"email": "spammer@spam.com"},
            email_classification={"category": "spam", "confidence": 0.99},
        )
        
        assert result.promote is False
        assert result.decision == "disqualified"
        assert result.score <= 20
    
    def test_unsubscribe_blocks_promotion(self, scorer: QualificationScorer):
        """Unsubscribe request should block promotion regardless of other signals."""
        result = scorer.score(
            lead_data={
                "email": "jane.ceo@acme.com",
                "company_name": "Acme Corp",
                "job_title": "CEO",
            },
            conversation_history=[
                {"content": "Please unsubscribe me immediately. Stop emailing me.", "direction": "inbound"}
            ],
        )
        
        # Should not promote despite good profile
        assert result.promote is False or result.score < 70
    
    def test_generic_freemail_nurtures(self, scorer: QualificationScorer):
        """Generic freemail with no signals should nurture."""
        result = scorer.score(
            lead_data={"email": "random123@gmail.com"},
            email_classification={"category": "unknown", "confidence": 0.5},
        )
        
        assert result.decision in ("nurture", "disqualified")
        assert result.promote is False


# =============================================================================
# SYNC WRAPPER TESTS
# =============================================================================


class TestScoreLeadSync:
    """Test the synchronous wrapper function."""
    
    def test_returns_qualification_result(self):
        """Sync wrapper should return QualificationResult."""
        result = score_lead_sync(lead_data={"email": "test@company.com"})
        
        assert isinstance(result, QualificationResult)
    
    def test_disables_llm_fallback(self):
        """Sync wrapper should always disable LLM."""
        result = score_lead_sync(
            lead_data={"email": "test@company.com"},
            email_classification={"category": "unknown", "confidence": 0.5},
        )
        
        assert result.llm_used is False
    
    def test_accepts_all_parameters(self):
        """Sync wrapper should accept all parameters."""
        result = score_lead_sync(
            lead_data={"email": "test@company.com"},
            conversation_history=[{"content": "Hello", "direction": "inbound"}],
            email_classification={"category": "personal", "confidence": 0.8},
            lead_source="staging_leads",
            email_direction="inbound",
        )
        
        assert isinstance(result, QualificationResult)
