from tiers.tier_1.manager.intake.normalizer import normalize_input


def test_normalize_text():
    req = normalize_input("find 50 ai startups in sf", source="cli", tenant_id="t1")
    assert req.text and "startups" in req.text
    assert req.tenant_id == "t1"


def test_normalize_dict_goal():
    data = {"goal": "launch outreach campaign", "tenant_id": "t2"}
    req = normalize_input(data, source="redis")
    assert req.payload and req.payload["goal"] == "launch outreach campaign"
    assert req.tenant_id == "t2"
