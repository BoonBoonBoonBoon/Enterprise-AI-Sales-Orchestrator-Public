from agent.high_level_agents.orchestrators.reply_orchestrator import ReplyOrchestrator
from agent.operational_agents.copywriter.copywriter import CopywriterAgent
from agent.tools.delivery.adapters.noop_adapter import NoOpDeliveryAdapter


def test_reply_orchestrator_delivers_via_noop_adapter():
    reg = {"copywriter": CopywriterAgent(), "delivery": NoOpDeliveryAdapter(disabled=False)}
    orch = ReplyOrchestrator(registry=reg)
    payload = {"channel": "email", "context": {"name": "Sam", "company": "Acme", "action": "confirm"}, "deliver": True}
    env = orch.run(payload)
    assert "metadata" in env and "delivery" in env["metadata"]
    delivery = env["metadata"]["delivery"]
    assert delivery["status"] in ("SENT", "DISABLED")