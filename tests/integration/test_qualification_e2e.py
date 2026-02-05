"""End-to-end qualification and promotion integration tests.

Tests the full flow:
1. Create staging lead
2. Run qualification scoring
3. Verify routing decision
4. Execute promotion (if qualified)
5. Verify data moved correctly

Requires:
- Supabase connection (SUPABASE_URL, SUPABASE_SERVICE_KEY)
- Real database tables

Usage:
  pytest tests/integration/test_qualification_e2e.py -v
  pytest tests/integration/test_qualification_e2e.py -v -k test_high_intent
"""
from __future__ import annotations

import os
import uuid
import pytest
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Skip all tests if supabase not configured
pytestmark = pytest.mark.skipif(
    not os.getenv("SUPABASE_URL") and not os.path.exists(".env"),
    reason="Supabase not configured"
)


def load_env():
    """Load .env file if exists."""
    import pathlib
    env_path = pathlib.Path('.env')
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.strip() and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                if k.strip() not in os.environ:
                    os.environ[k.strip()] = v.strip()


load_env()


@pytest.fixture(scope="module")
def supabase_client():
    """Get Supabase client."""
    try:
        from supabase import create_client
    except ImportError:
        pytest.skip("supabase package not installed")
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        pytest.skip("Supabase credentials not configured")
    
    return create_client(url, key)


@pytest.fixture(scope="module")
def test_client_id(supabase_client) -> str:
    """Get client_id from existing staging_leads (avoid clients table RLS)."""
    # Get client_id from existing staging lead to avoid clients table permission
    result = supabase_client.table("staging_leads").select("client_id").limit(1).execute()
    if result.data and result.data[0].get("client_id"):
        return result.data[0]["client_id"]
    
    # Fallback to leads table
    result = supabase_client.table("leads").select("client_id").limit(1).execute()
    if result.data and result.data[0].get("client_id"):
        return result.data[0]["client_id"]
    
    pytest.skip("No client_id found in staging_leads or leads")


@pytest.fixture(scope="module")
def test_campaign_id(supabase_client, test_client_id) -> str:
    """Get campaign_id from existing staging_leads (avoid campaigns table RLS)."""
    # Get campaign_id from existing staging lead
    result = supabase_client.table("staging_leads").select("campaign_id").limit(1).execute()
    if result.data and result.data[0].get("campaign_id"):
        return result.data[0]["campaign_id"]
    
    # Fallback to leads table
    result = supabase_client.table("leads").select("campaign_id").limit(1).execute()
    if result.data and result.data[0].get("campaign_id"):
        return result.data[0]["campaign_id"]
    
    # Try placeholder
    placeholder = os.getenv("CAMPAIGN_ID_PLACEHOLDER", "9646f98a-e987-4a8c-b786-9b82ea985d38")
    return placeholder


@pytest.fixture
def scorer():
    """Get qualification scorer."""
    from tiers.tier_2.leads_orchestrator.qualification.scorer import QualificationScorer
    return QualificationScorer()


def create_lead_record(
    lead_id: str,
    email: str,
    client_id: str,
    campaign_id: str,
    first_name: str = "Test",
    last_name: str = "Lead",
    company_name: str = "Test Corp",
    job_title: str = "Manager",
    current_status: str = "new",
    lead_score: Optional[int] = None,
    qualification_status: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a lead record with all required NOT NULL fields."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": lead_id,
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "company_name": company_name,
        "job_title": job_title,
        "phone_number": "",  # Required NOT NULL
        "client_id": client_id,
        "campaign_id": campaign_id,
        "current_status": current_status,
        "sequence_step": 1,
        "sequence_active": True,
        "booking_status": "not_booked",
        "last_contact_date": now,  # Required NOT NULL
        "next_action_date": now,  # Required NOT NULL
        "re_engagement_date": now,  # Required NOT NULL
        "lead_score": lead_score,
        "qualification_status": qualification_status,
    }


@pytest.fixture
def cleanup_leads(supabase_client):
    """Track and cleanup test leads after tests."""
    created_ids = {"staging_leads": [], "leads": []}
    yield created_ids
    
    # Cleanup
    for lead_id in created_ids["staging_leads"]:
        try:
            supabase_client.table("staging_leads").delete().eq("id", lead_id).execute()
        except Exception:
            pass
    
    for lead_id in created_ids["leads"]:
        try:
            supabase_client.table("leads").delete().eq("id", lead_id).execute()
        except Exception:
            pass


# =============================================================================
# QUALIFICATION SCORING INTEGRATION TESTS
# =============================================================================


class TestQualificationScoringIntegration:
    """Test qualification scoring with realistic data patterns."""
    
    def test_high_intent_business_inquiry(self, scorer):
        """High-intent business inquiry should score high and promote."""
        result = scorer.score(
            lead_data={
                "email": "ceo@microsoft.com",
                "company_name": "Microsoft Corporation",
                "job_title": "Chief Executive Officer",
            },
            conversation_history=[
                {
                    "content": "We're evaluating solutions for Q2. What's your pricing for enterprise?",
                    "direction": "inbound"
                },
                {
                    "content": "We need to make a decision by end of month.",
                    "direction": "inbound"
                }
            ],
            email_classification={
                "category": "business_inquiry",
                "confidence": 0.95
            },
            lead_source="staging_leads"
        )
        
        assert result.score >= 70, f"Expected score >= 70, got {result.score}"
        assert result.promote is True
        assert result.decision in ["qualified", "fast_track"]
        assert "mentioned_budget" in str(result.signals) or "mentioned_timeline" in str(result.signals)
    
    def test_spam_email_disqualified(self, scorer):
        """Spam email should be disqualified."""
        result = scorer.score(
            lead_data={
                "email": "winner@lottery-prize.net",
            },
            conversation_history=[
                {
                    "content": "Congratulations! You've won $1,000,000! Click here to claim!",
                    "direction": "inbound"
                }
            ],
            email_classification={
                "category": "spam",
                "confidence": 0.99
            },
            lead_source="new"
        )
        
        assert result.score < 20, f"Expected score < 20, got {result.score}"
        assert result.decision == "disqualified"
        assert result.promote is False
    
    def test_unsubscribe_request(self, scorer):
        """Unsubscribe request should be disqualified."""
        result = scorer.score(
            lead_data={"email": "unsubscribe@test.com"},
            conversation_history=[
                {"content": "Please unsubscribe me from this list", "direction": "inbound"}
            ],
            email_classification={"category": "unsubscribe", "confidence": 0.9}
        )
        
        assert result.decision == "disqualified"
        assert result.promote is False
    
    def test_freemail_nurture_path(self, scorer):
        """Freemail without strong signals goes to nurture."""
        result = scorer.score(
            lead_data={
                "email": "john.doe@gmail.com",
                "first_name": "John",
            },
            conversation_history=[
                {"content": "Hi, just checking in.", "direction": "inbound"}
            ],
            email_classification={"category": "unknown", "confidence": 0.5}
        )
        
        # Should not be promoted without strong signals
        assert result.score < 70 or result.decision == "nurture"
    
    def test_enterprise_fast_track(self, scorer):
        """Enterprise domain with C-level title fast-tracks."""
        result = scorer.score(
            lead_data={
                "email": "cto@fortune500corp.com",
                "company_name": "Fortune 500 Corp",
                "job_title": "CTO",
            },
            email_classification={"category": "business_inquiry", "confidence": 0.9},
            lead_source="inbound",
            email_direction="inbound"
        )
        
        # Should score high even without conversation
        assert result.score >= 50
        # With strong profile, should be qualified
        if result.score >= 70:
            assert result.promote is True


# =============================================================================
# DATABASE ROUTING INTEGRATION TESTS
# =============================================================================


class TestDatabaseRoutingIntegration:
    """Test that leads actually get routed to the right tables."""
    
    def test_staging_lead_creation(
        self, 
        supabase_client, 
        test_client_id, 
        test_campaign_id,
        cleanup_leads
    ):
        """Verify staging lead creation works."""
        unique_email = f"qa_staging_{uuid.uuid4().hex[:8]}@test.com"
        
        staging_lead = {
            "id": str(uuid.uuid4()),
            "email": unique_email,
            "first_name": "QA",
            "last_name": "Test",
            "company_name": "QA Test Corp",
            "job_title": "QA Engineer",
            "source": "integration_test",
            "client_id": test_client_id,
            "campaign_id": test_campaign_id,
            "qualification_status": "pending",
            "enrichment_status": "pending",
            "promotion_ready": False,
        }
        
        result = supabase_client.table("staging_leads").insert(staging_lead).execute()
        cleanup_leads["staging_leads"].append(staging_lead["id"])
        
        assert result.data is not None
        assert result.data[0]["email"] == unique_email
        
        # Verify we can query it back
        query = supabase_client.table("staging_leads").select("*").eq("id", staging_lead["id"]).execute()
        assert len(query.data) == 1
    
    def test_qualified_lead_creation(
        self,
        supabase_client,
        test_client_id,
        test_campaign_id,
        cleanup_leads
    ):
        """Verify qualified lead creation in leads table."""
        unique_email = f"qa_qualified_{uuid.uuid4().hex[:8]}@test.com"
        lead_id = str(uuid.uuid4())
        
        lead = create_lead_record(
            lead_id=lead_id,
            email=unique_email,
            client_id=test_client_id,
            campaign_id=test_campaign_id,
            first_name="Qualified",
            last_name="Lead",
            company_name="Qualified Corp",
            job_title="CEO",
        )
        
        result = supabase_client.table("leads").insert(lead).execute()
        cleanup_leads["leads"].append(lead_id)
        
        assert result.data is not None
        assert result.data[0]["email"] == unique_email
    
    def test_staging_to_leads_flow(
        self,
        supabase_client,
        test_client_id,
        test_campaign_id,
        scorer,
        cleanup_leads
    ):
        """Test full flow: staging → qualification → leads."""
        unique_email = f"qa_flow_{uuid.uuid4().hex[:8]}@enterprise.com"
        staging_id = str(uuid.uuid4())
        
        # 1. Create staging lead
        staging_lead = {
            "id": staging_id,
            "email": unique_email,
            "first_name": "Flow",
            "last_name": "Test",
            "company_name": "Enterprise Corp",
            "job_title": "VP of Engineering",
            "source": "integration_test",
            "client_id": test_client_id,
            "campaign_id": test_campaign_id,
            "qualification_status": "pending",
            "enrichment_status": "pending",
            "promotion_ready": False,
        }
        
        insert_result = supabase_client.table("staging_leads").insert(staging_lead).execute()
        cleanup_leads["staging_leads"].append(staging_id)
        assert insert_result.data
        
        # 2. Score the lead
        score_result = scorer.score(
            lead_data={
                "email": unique_email,
                "company_name": "Enterprise Corp",
                "job_title": "VP of Engineering",
            },
            conversation_history=[
                {"content": "Interested in your solution. What's your pricing?", "direction": "inbound"}
            ],
            email_classification={"category": "business_inquiry", "confidence": 0.85},
            lead_source="staging_leads"
        )
        
        # 3. Update staging lead with qualification result
        update_data = {
            "qualification_status": score_result.decision,
            "promotion_ready": score_result.promote,
        }
        
        update_result = supabase_client.table("staging_leads").update(
            update_data
        ).eq("id", staging_id).execute()
        
        assert update_result.data
        
        # 4. If qualified, create lead
        if score_result.promote:
            lead_id = str(uuid.uuid4())
            lead = create_lead_record(
                lead_id=lead_id,
                email=unique_email,
                client_id=test_client_id,
                campaign_id=test_campaign_id,
                first_name="Flow",
                last_name="Test",
                company_name="Enterprise Corp",
                job_title="VP of Engineering",
                current_status="qualified",
                qualification_status=score_result.decision,
                lead_score=score_result.score,
            )
            
            lead_result = supabase_client.table("leads").insert(lead).execute()
            cleanup_leads["leads"].append(lead_id)
            
            assert lead_result.data
            assert lead_result.data[0]["lead_score"] == score_result.score
            
            # 5. Archive staging lead
            archive_result = supabase_client.table("staging_leads").update({
                "archived_at": datetime.now(timezone.utc).isoformat(),
                "enrichment_status": "promoted"
            }).eq("id", staging_id).execute()
            
            assert archive_result.data


# =============================================================================
# EDGE CASE INTEGRATION TESTS
# =============================================================================


class TestEdgeCaseIntegration:
    """Test edge cases in the qualification flow."""
    
    def test_duplicate_email_handling(
        self,
        supabase_client,
        test_client_id,
        test_campaign_id,
        cleanup_leads
    ):
        """Test handling of duplicate emails."""
        unique_email = f"qa_dup_{uuid.uuid4().hex[:8]}@test.com"
        
        # Create first staging lead
        lead1 = {
            "id": str(uuid.uuid4()),
            "email": unique_email,
            "first_name": "First",
            "last_name": "Lead",
            "company_name": "Test Corp",
            "job_title": "Manager",
            "source": "test",
            "client_id": test_client_id,
            "campaign_id": test_campaign_id,
            "qualification_status": "pending",
            "enrichment_status": "pending",
            "promotion_ready": False,
        }
        
        result1 = supabase_client.table("staging_leads").insert(lead1).execute()
        cleanup_leads["staging_leads"].append(lead1["id"])
        assert result1.data
        
        # Try to create second with same email - depends on DB constraints
        lead2 = {
            "id": str(uuid.uuid4()),
            "email": unique_email,  # Same email
            "first_name": "Second",
            "last_name": "Lead",
            "company_name": "Other Corp",
            "job_title": "Director",
            "source": "test",
            "client_id": test_client_id,
            "campaign_id": test_campaign_id,
            "qualification_status": "pending",
            "enrichment_status": "pending",
            "promotion_ready": False,
        }
        
        try:
            result2 = supabase_client.table("staging_leads").insert(lead2).execute()
            if result2.data:
                cleanup_leads["staging_leads"].append(lead2["id"])
                # If we get here, duplicates are allowed - note for future
                pytest.skip("Duplicate emails allowed in staging_leads")
        except Exception as e:
            # Expected if unique constraint exists
            assert "duplicate" in str(e).lower() or "unique" in str(e).lower()
    
    def test_unicode_in_lead_data(
        self,
        supabase_client,
        test_client_id,
        test_campaign_id,
        scorer,
        cleanup_leads
    ):
        """Test unicode characters in lead data."""
        unique_email = f"qa_unicode_{uuid.uuid4().hex[:8]}@日本語.com"
        
        lead = {
            "id": str(uuid.uuid4()),
            "email": f"qa_unicode_{uuid.uuid4().hex[:8]}@example.com",  # Use safe email
            "first_name": "田中",
            "last_name": "太郎",
            "company_name": "株式会社テスト",
            "job_title": "社長",
            "source": "test",
            "client_id": test_client_id,
            "campaign_id": test_campaign_id,
            "qualification_status": "pending",
            "enrichment_status": "pending",
            "promotion_ready": False,
        }
        
        result = supabase_client.table("staging_leads").insert(lead).execute()
        cleanup_leads["staging_leads"].append(lead["id"])
        
        assert result.data
        assert result.data[0]["first_name"] == "田中"
        
        # Score with unicode data
        score_result = scorer.score(
            lead_data={
                "email": lead["email"],
                "company_name": "株式会社テスト",
                "job_title": "社長",
            },
            conversation_history=[
                {"content": "デモのスケジュールを設定できますか？", "direction": "inbound"}
            ]
        )
        
        assert isinstance(score_result.score, int)
    
    def test_very_long_content(self, scorer):
        """Test scoring with very long message content."""
        long_content = "Interested in your solution. " * 500  # ~14K chars
        
        result = scorer.score(
            lead_data={"email": "test@test.com"},
            conversation_history=[
                {"content": long_content, "direction": "inbound"}
            ]
        )
        
        assert isinstance(result.score, int)
        assert 0 <= result.score <= 100


# =============================================================================
# PROMOTION FLOW TESTS
# =============================================================================


class TestPromotionFlow:
    """Test the promotion from staging to leads."""
    
    def test_promotion_ready_flag(
        self,
        supabase_client,
        test_client_id,
        test_campaign_id,
        scorer,
        cleanup_leads
    ):
        """Test promotion_ready flag is set correctly."""
        unique_email = f"qa_promo_{uuid.uuid4().hex[:8]}@enterprise.com"
        staging_id = str(uuid.uuid4())
        
        # Create staging lead
        staging_lead = {
            "id": staging_id,
            "email": unique_email,
            "first_name": "Promo",
            "last_name": "Test",
            "company_name": "Big Enterprise Inc",
            "job_title": "CEO",
            "source": "test",
            "client_id": test_client_id,
            "campaign_id": test_campaign_id,
            "qualification_status": "pending",
            "enrichment_status": "pending",
            "promotion_ready": False,
        }
        
        insert_result = supabase_client.table("staging_leads").insert(staging_lead).execute()
        cleanup_leads["staging_leads"].append(staging_id)
        
        # Score with high-intent signals
        score_result = scorer.score(
            lead_data={
                "email": unique_email,
                "company_name": "Big Enterprise Inc",
                "job_title": "CEO",
            },
            conversation_history=[
                {"content": "We have budget approved for Q1. Can we schedule a call?", "direction": "inbound"},
                {"content": "Our timeline is end of January.", "direction": "inbound"}
            ],
            email_classification={"category": "business_inquiry", "confidence": 0.95},
            lead_source="staging_leads"
        )
        
        # Should be qualified
        assert score_result.promote is True, f"Expected promote=True, got {score_result}"
        
        # Update promotion_ready
        update_result = supabase_client.table("staging_leads").update({
            "promotion_ready": score_result.promote,
            "qualification_status": score_result.decision,
        }).eq("id", staging_id).execute()
        
        # Verify update
        verify = supabase_client.table("staging_leads").select("*").eq("id", staging_id).execute()
        assert verify.data[0]["promotion_ready"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
