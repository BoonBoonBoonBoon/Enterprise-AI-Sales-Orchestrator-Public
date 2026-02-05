"""Regression tests using golden fixtures.

These tests run the scorer against known fixtures and verify
the output stays within expected bounds. Any drift should fail CI.
"""

import pytest
from typing import Any, Dict

from tiers.tier_2.leads_orchestrator.qualification.scorer import (
    QualificationScorer,
    score_lead_sync,
)
from tests.fixtures.qualification_golden import get_fixtures, GOLDEN_FIXTURES


@pytest.fixture
def scorer() -> QualificationScorer:
    """Fresh scorer instance."""
    return QualificationScorer()


class TestGoldenFixtureRegression:
    """Run all golden fixtures and verify expected outcomes."""
    
    @pytest.mark.parametrize(
        "fixture",
        GOLDEN_FIXTURES,
        ids=[f["name"] for f in GOLDEN_FIXTURES],
    )
    def test_fixture(self, scorer: QualificationScorer, fixture: Dict[str, Any]):
        """Test a single fixture against expected outcome."""
        inputs = fixture["inputs"]
        expected = fixture["expected"]
        
        result = scorer.score(
            lead_data=inputs.get("lead_data", {}),
            email_classification=inputs.get("email_classification"),
            conversation_history=inputs.get("conversation_history"),
            lead_source=inputs.get("lead_source", "new"),
            email_direction=inputs.get("email_direction", "inbound"),
        )
        
        # Check promote flag
        assert result.promote == expected["promote"], (
            f"Fixture '{fixture['name']}': expected promote={expected['promote']}, "
            f"got promote={result.promote} (score={result.score}, decision={result.decision})"
        )
        
        # Check decision is in allowed set
        assert result.decision in expected["decision_in"], (
            f"Fixture '{fixture['name']}': expected decision in {expected['decision_in']}, "
            f"got decision='{result.decision}'"
        )
        
        # Check score bounds
        assert expected["min_score"] <= result.score <= expected["max_score"], (
            f"Fixture '{fixture['name']}': expected score in "
            f"[{expected['min_score']}, {expected['max_score']}], got {result.score}"
        )
    
    def test_all_fixtures_load(self):
        """Verify fixtures module loads correctly."""
        fixtures = get_fixtures()
        assert len(fixtures) > 0
        assert all("name" in f for f in fixtures)
        assert all("inputs" in f for f in fixtures)
        assert all("expected" in f for f in fixtures)


class TestScorerStability:
    """Test scorer stability across multiple runs."""
    
    @pytest.mark.parametrize("fixture", GOLDEN_FIXTURES[:5], ids=[f["name"] for f in GOLDEN_FIXTURES[:5]])
    def test_deterministic_across_runs(self, scorer: QualificationScorer, fixture: Dict[str, Any]):
        """Same input should produce identical output across 10 runs."""
        inputs = fixture["inputs"]
        
        results = []
        for _ in range(10):
            result = scorer.score(
                lead_data=inputs.get("lead_data", {}),
                email_classification=inputs.get("email_classification"),
                conversation_history=inputs.get("conversation_history"),
                lead_source=inputs.get("lead_source", "new"),
                email_direction=inputs.get("email_direction", "inbound"),
            )
            results.append((result.score, result.decision, result.promote))
        
        # All results should be identical
        assert all(r == results[0] for r in results), (
            f"Non-deterministic results for '{fixture['name']}': {set(results)}"
        )


class TestSyncWrapperRegression:
    """Test sync wrapper produces same results as direct scorer."""
    
    @pytest.mark.parametrize("fixture", GOLDEN_FIXTURES[:5], ids=[f["name"] for f in GOLDEN_FIXTURES[:5]])
    def test_sync_matches_direct(self, scorer: QualificationScorer, fixture: Dict[str, Any]):
        """Sync wrapper should match direct scorer (with LLM disabled)."""
        inputs = fixture["inputs"]
        
        # Direct scorer with LLM disabled
        scorer.config.llm_fallback["enabled"] = False
        direct_result = scorer.score(
            lead_data=inputs.get("lead_data", {}),
            email_classification=inputs.get("email_classification"),
            conversation_history=inputs.get("conversation_history"),
            lead_source=inputs.get("lead_source", "new"),
            email_direction=inputs.get("email_direction", "inbound"),
        )
        
        # Sync wrapper
        sync_result = score_lead_sync(
            lead_data=inputs.get("lead_data", {}),
            email_classification=inputs.get("email_classification"),
            conversation_history=inputs.get("conversation_history"),
            lead_source=inputs.get("lead_source", "new"),
            email_direction=inputs.get("email_direction", "inbound"),
        )
        
        assert direct_result.score == sync_result.score
        assert direct_result.decision == sync_result.decision
        assert direct_result.promote == sync_result.promote
