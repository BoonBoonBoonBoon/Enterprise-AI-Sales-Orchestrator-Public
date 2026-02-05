import pytest

from services.email.providers import InboundEmailEvent


class DummyRedisClient:
    def __init__(self, *, exists=False, xlen_value=0, raise_xlen=False):
        self.client = self
        self._exists = exists
        self._xlen = xlen_value
        self._raise_xlen = raise_xlen
        self.setex_calls = []
        self.added = None

    def _chan(self, key: str) -> str:
        return f"ns:{key}"

    def exists(self, key: str) -> int:
        return 1 if self._exists else 0

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.setex_calls.append((key, ttl, value))

    def xlen(self, key: str) -> int:
        if self._raise_xlen:
            raise RuntimeError("boom")
        return self._xlen

    def xadd(self, stream: str, fields: dict) -> str:
        self.added = (stream, fields)
        return "0-1"


def test_should_process_sets_dedup_key(monkeypatch):
    from services.email import inbox_poller

    client = DummyRedisClient(exists=False)
    key = inbox_poller.make_dedup_key("tenant", "gmail", "msg-1")

    assert inbox_poller.should_process(client, key) is True
    assert client.setex_calls


def test_should_process_skips_duplicates():
    from services.email import inbox_poller

    client = DummyRedisClient(exists=True)
    key = inbox_poller.make_dedup_key("tenant", "gmail", "msg-1")

    assert inbox_poller.should_process(client, key) is False
    assert not client.setex_calls


def test_check_backpressure_trips_threshold(monkeypatch):
    from services.email import inbox_poller

    monkeypatch.setattr(inbox_poller, "BACKPRESSURE_ENABLED", True)
    monkeypatch.setattr(inbox_poller, "MAX_PENDING_MESSAGES", 2)

    client = DummyRedisClient(xlen_value=5)

    assert inbox_poller.check_backpressure(client, "tenant") is True


def test_check_backpressure_disabled(monkeypatch):
    from services.email import inbox_poller

    monkeypatch.setattr(inbox_poller, "BACKPRESSURE_ENABLED", False)
    monkeypatch.setattr(inbox_poller, "MAX_PENDING_MESSAGES", 1)

    client = DummyRedisClient(xlen_value=10)

    assert inbox_poller.check_backpressure(client, "tenant") is False


def test_check_backpressure_handles_errors(monkeypatch):
    from services.email import inbox_poller

    monkeypatch.setattr(inbox_poller, "BACKPRESSURE_ENABLED", True)

    client = DummyRedisClient(raise_xlen=True)

    assert inbox_poller.check_backpressure(client, "tenant") is False


def test_apply_pre_filter_calls_classifier(monkeypatch):
    from services.email import inbox_poller

    captured = {}

    def fake_pre_filter_email(**kwargs):
        captured.update(kwargs)
        return inbox_poller.PreFilterResult("bounce", 0.99, "test")

    monkeypatch.setattr(inbox_poller, "pre_filter_email", fake_pre_filter_email)

    event = InboundEmailEvent(
        provider="gmail",
        message_id="msg-1",
        thread_id=None,
        subject="Test",
        body="Hello",
        from_email="from@example.com",
        to_email="to@example.com",
        received_at="2026-01-01T00:00:00Z",
        list_unsubscribe="<mailto:unsubscribe@example.com>",
        precedence="bulk",
        auto_response_suppress="OOF",
        x_mailer="Mailer",
        from_name="Tester",
    )

    result = inbox_poller.apply_pre_filter(event)

    assert result.category == "bounce"
    assert captured["from_email"] == "from@example.com"


def test_publish_event_writes_manager_task():
    from services.email import inbox_poller

    client = DummyRedisClient()
    event = InboundEmailEvent(
        provider="gmail",
        message_id="msg-1",
        thread_id=None,
        subject="Test",
        body="Hello",
        from_email="from@example.com",
        to_email="to@example.com",
        received_at="2026-01-01T00:00:00Z",
    )
    pre_filter = inbox_poller.PreFilterResult("system", 0.5, "ok")

    inbox_poller.publish_event(client, "tenant", event, pre_filter)

    assert client.added
    stream, fields = client.added
    assert stream == "tenant:manager:tasks"
    assert "data" in fields