from tiers.tier_1.manager.policy.router import get_routing_map, build_plan
from core.schemas.manager import UnifiedManagerRequest


def test_default_routing_map_loads():
    mapping = get_routing_map("demo")
    assert "outreach" in mapping
    assert isinstance(mapping["outreach"], list)


ess_req = UnifiedManagerRequest(tenant_id="demo", text="launch outreach")

def test_build_plan_uses_mapping():
    decision = build_plan("outreach", 0.7, ["matched:outreach"], ess_req)
    assert decision.orchestrators == ["outreach"]
    assert len(decision.tasks) == 1
    assert decision.tasks[0]["stream"].endswith(":orchestrators:outbound:tasks")
