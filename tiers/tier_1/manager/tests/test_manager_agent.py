from tiers.tier_1.manager.manager_agent import ManagerAgent


class DummyRedis:
    def __init__(self):
        self.added = []

    def xadd(self, stream, fields):
        # record and return a dummy ID
        self.added.append((stream, fields))
        return "0-1"

    def ping(self):
        return True


def test_manager_agent_deterministic_pipeline_outreach():
        r = DummyRedis()
        m = ManagerAgent(r, tenant_id="t_demo", enable_llm_fallback=False, enable_deep_agent=False)
        res = m.execute("Launch a campaign for Q4 enterprise outreach with LinkedIn and email")
        assert res["success"] is True
        assert res["path"] == "deterministic_pipeline"
        assert res["intent"] in ("outreach", "start_campaign")
        # should attempt to enqueue even if Dummy
        assert isinstance(r.added, list)
        if res["orchestrators"]:
            # if mapped, we expect at least one enqueue attempt
            assert len(r.added) >= 1


def test_manager_does_not_emit_copy_or_agent_streams():
    r = DummyRedis()
    m = ManagerAgent(r, tenant_id="t_demo", enable_llm_fallback=False, enable_deep_agent=False)

    res = m.execute("Generate an outreach email for lead_123 in campaign_456")

    assert res["success"] is True
    assert res["path"] == "deterministic_pipeline"

    # Manager should never include generated copy in its own response
    assert "email_body" not in res
    assert "subject" not in res

    # Orchestrators list should not contain copywriter (only outbound path)
    assert "copywriter" not in res.get("orchestrators", [])
    assert any(o in ("outbound", "outreach") for o in res.get("orchestrators", []))

    # All enqueued streams must target orchestrators namespace, never agents
    streams = [s for s, _ in r.added]
    assert streams, "Expected manager to enqueue at least one orchestrator task"
    assert all(":agents:" not in s for s in streams)
    assert all(s.startswith("t_demo:orchestrators:") for s in streams)
