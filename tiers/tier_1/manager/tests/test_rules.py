from tiers.tier_1.manager.intent.rules import classify_by_rules
from core.schemas.manager import UnifiedManagerRequest


def test_rules_detect_outreach_from_text():
    req = UnifiedManagerRequest(text="Launch a campaign with LinkedIn and email")
    intent, conf, _ = classify_by_rules(req)
    assert intent == "outreach"
    assert conf > 0


def test_rules_detect_start_campaign_from_payload_goal():
    req = UnifiedManagerRequest(payload={"goal": "start campaign for Q4"})
    intent, conf, _ = classify_by_rules(req)
    assert intent in ("start_campaign", "outreach")
    assert conf > 0
