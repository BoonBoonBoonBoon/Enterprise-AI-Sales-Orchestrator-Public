import time
from agent.Infastructure.queue.in_memory import InMemoryQueue


def test_enqueue_dequeue_ack():
    q = InMemoryQueue(visibility_timeout=0.2, requeue_check_interval=0.05)
    job = {"run_id": "r1", "orchestrator": "lead", "payload": {"a": 1}}
    jid = q.enqueue("orchestrate", job)
    assert jid
    item = q.dequeue("orchestrate", timeout=0.5)
    assert item["job_id"] == jid
    q.ack(jid)
    # after ack, should not requeue
    time.sleep(0.3)
    none = q.dequeue("orchestrate", timeout=0.1)
    assert none is None
    q.stop()
