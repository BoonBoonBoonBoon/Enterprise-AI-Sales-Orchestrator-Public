from agent.high_level_agents.control_layer.campaign_manager import CampaignManager
from agent.Infastructure.queue.in_memory import InMemoryQueue
from agent.high_level_agents.orchestrators.registry import Registry


def test_campaign_manager_enqueues_job():
    q = InMemoryQueue()
    reg = Registry()

    # fake orchestrator
    class FakeOrch:
        def run(self, payload):
            return {"metadata": {}, "records": [payload]}

    reg.register("lead_sync", FakeOrch)
    cm = CampaignManager(registry=reg, queue=q)
    res = cm.ingest_event({"flow": "lead_sync", "context": {"name": "Acme"}})
    assert res["status"] == "queued"
    assert "run_id" in res
    jid = res["job_id"]
    item = q.dequeue("orchestrate", timeout=0.5)
    assert item and item["job_id"] == jid
    q.stop()
