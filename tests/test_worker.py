from unittest.mock import MagicMock
from agent.Infastructure.queue.in_memory import InMemoryQueue
from agent.Infastructure.worker.worker import Worker


def test_worker_runs_orchestrator(monkeypatch):
    q = InMemoryQueue(visibility_timeout=1.0, requeue_check_interval=0.1)
    # fake orchestrator class
    class FakeOrch:
        def run(self, payload):
            return {"metadata": {}, "records": [payload]}

    registry = MagicMock()
    registry.get.return_value = FakeOrch

    worker = Worker(q, registry)
    job = {"run_id": "r1", "orchestrator": "fake", "payload": {"x": 1}}
    jid = q.enqueue("orchestrate", job)
    worker.run_once(timeout=0.5)
    # after successful run, job should be acked and not reappear
    item = q.dequeue("orchestrate", timeout=0.1)
    assert item is None
    q.stop()
