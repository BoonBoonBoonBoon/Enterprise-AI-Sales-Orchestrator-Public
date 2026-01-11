from agent.high_level_agents.orchestrators.reply_orchestrator import ReplyOrchestrator
from agent.operational_agents.copywriter.copywriter import CopywriterAgent


def test_reply_orchestrator_generates_email():
    reg = {"copywriter": CopywriterAgent()}
    orch = ReplyOrchestrator(registry=reg)
    payload = {"channel": "email", "context": {"name": "Sam", "company": "Acme", "action": "confirm"}}
    env = orch.run(payload)
    assert "metadata" in env and "records" in env
    rec = env["records"][0]
    assert rec["channel"] == "email"
    assert "subject" in rec["content"] and "body" in rec["content"]


def test_reply_orchestrator_generates_text():
    reg = {"copywriter": CopywriterAgent()}
    orch = ReplyOrchestrator(registry=reg)
    payload = {"channel": "text", "context": {"name": "Sam", "action": "verify"}}
    env = orch.run(payload)
    rec = env["records"][0]
    assert rec["channel"] == "text"
    assert isinstance(rec["content"], str)
