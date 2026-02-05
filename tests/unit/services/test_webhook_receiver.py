from fastapi.testclient import TestClient

from services.email import webhook_receiver


class DummyRedis:
    def __init__(self):
        self.added = []


def test_webhook_rejects_invalid_secret(monkeypatch):
    monkeypatch.setattr(webhook_receiver, "WEBHOOK_SECRET", "secret")
    client = TestClient(webhook_receiver.app)

    resp = client.post(
        "/webhook/email/tenant",
        headers={"x-webhook-secret": "wrong"},
        json={
            "provider": "gmail",
            "message_id": "m1",
            "from": "a@example.com",
            "to": "b@example.com",
        },
    )

    assert resp.status_code == 401


def test_webhook_accepts_and_publishes(monkeypatch):
    monkeypatch.setattr(webhook_receiver, "WEBHOOK_SECRET", None)
    monkeypatch.setattr(webhook_receiver, "should_process", lambda *_: True)

    published = {}

    def fake_publish(redis_client, tenant_id, event, pre_filter_result):
        published["tenant"] = tenant_id
        published["event"] = event
        published["prefilter"] = pre_filter_result

    monkeypatch.setattr(webhook_receiver, "publish_event", fake_publish)

    def fake_prefilter(**kwargs):
        return webhook_receiver.PreFilterResult("system", 0.5, "ok")

    monkeypatch.setattr(webhook_receiver, "pre_filter_email", fake_prefilter)

    client = TestClient(webhook_receiver.app)
    resp = client.post(
        "/webhook/email/tenant",
        json={
            "provider": "gmail",
            "message_id": "m2",
            "from": "a@example.com",
            "to": "b@example.com",
            "subject": "Hi",
            "body": "Hello",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"
    assert published["tenant"] == "tenant"


def test_webhook_duplicate_short_circuit(monkeypatch):
    monkeypatch.setattr(webhook_receiver, "WEBHOOK_SECRET", None)
    monkeypatch.setattr(webhook_receiver, "should_process", lambda *_: False)

    client = TestClient(webhook_receiver.app)
    resp = client.post(
        "/webhook/email/tenant",
        json={
            "provider": "gmail",
            "message_id": "m3",
            "from": "a@example.com",
            "to": "b@example.com",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "duplicate"