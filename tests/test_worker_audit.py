from agent.Infastructure.queue.in_memory import InMemoryQueue
from agent.high_level_agents.orchestrators.registry import Registry
from agent.Infastructure.worker.worker import Worker
from agent.high_level_agents.audit.store import InMemoryAuditStore


class FakeOrch:
    def run(self, payload):
        return {"metadata": {}, "records": [payload]}


class BadOrch:
    def run(self, payload):
        raise RuntimeError("boom")


def test_worker_persists_envelope_to_audit_store():
    q = InMemoryQueue(visibility_timeout=1.0, requeue_check_interval=0.1)
    reg = Registry()
    reg.register("fake", FakeOrch)
    audit = InMemoryAuditStore()
    worker = Worker(q, reg, audit_store=audit)
    job = {"run_id": "r1", "orchestrator": "fake", "payload": {"x": 1}}
    jid = q.enqueue("orchestrate", job)
    worker.run_once(timeout=0.5)
    item = q.dequeue("orchestrate", timeout=0.1)
    assert item is None
    assert len(audit.envelopes) == 1
    q.stop()


def test_worker_persists_failure_to_audit_store():
    q = InMemoryQueue(visibility_timeout=1.0, requeue_check_interval=0.1)
    reg = Registry()
    reg.register("bad", BadOrch)
    audit = InMemoryAuditStore()
    worker = Worker(q, reg, audit_store=audit)
    job = {"run_id": "r2", "orchestrator": "bad", "payload": {"x": 2}}
    jid = q.enqueue("orchestrate", job)
    worker.run_once(timeout=0.5)
    # after retries/backoff the job should be acked
    item = q.dequeue("orchestrate", timeout=0.1)
    assert item is None
    assert len(audit.failures) >= 1
    q.stop()
