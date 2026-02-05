from typing import Dict, List

from tiers.tier_3.rag_agent.strategies import reply_context


class DummyAdapter:
    def __init__(self):
        self.calls: List[Dict[str, str]] = []

    def query(self, table: str, filters: Dict[str, str], limit: int, order_by: str = None, descending: bool = False):
        self.calls.append({"table": table, "filters": filters})

        if table == "leads":
            return [
                {"id": "L1", "email": filters.get("email"), "updated_at": "2026-01-01T00:00:00Z"}
            ]
        if table == "conversations":
            return [
                {"id": "C1", "thread_id": "thread-1", "subject": "Re: Hello", "updated_at": "2026-01-02T00:00:00Z"},
                {"id": "C2", "thread_id": "thread-2", "subject": "Other", "updated_at": "2026-01-01T00:00:00Z"},
            ]
        if table == "messages":
            return [
                {"id": "M1", "content": "First message", "created_at": "2026-01-01T00:00:00Z"},
                {"id": "M2", "content": "Second message", "created_at": "2026-01-01T01:00:00Z"},
            ]
        return []

    def read(self, table: str, id_value: str):
        return None


class DummyStagingAdapter(DummyAdapter):
    def query(self, table: str, filters: Dict[str, str], limit: int, order_by: str = None, descending: bool = False):
        self.calls.append({"table": table, "filters": filters})

        if table == "leads":
            return []
        if table == "staging_leads":
            return [
                {"id": "SL1", "email": filters.get("email"), "updated_at": "2026-01-01T00:00:00Z"}
            ]
        if table == "staging_conversations":
            return [
                {"id": "SC1", "thread_id": "thread-1", "subject": "Staging", "updated_at": "2026-01-02T00:00:00Z"}
            ]
        if table == "staging_messages":
            return [
                {"id": "SM1", "content": "Staging message", "sent_at": "2026-01-01T00:00:00Z"}
            ]
        return []


def test_build_reply_context_selects_thread_and_truncates():
    adapter = DummyAdapter()

    result = reply_context.build_reply_context(
        adapter,
        email="lead@example.com",
        thread_id="thread-1",
        max_messages=5,
        max_tokens=20,
        include_all_threads=False,
    )

    assert result["status"] == "success"
    assert result["lead_source"] == "leads"
    assert result["conversation"]["id"] == "C1"
    assert result["message_count"] == 1
    assert any(step.get("action") == "token_truncation" for step in result["query_trace"]["steps"])


def test_build_reply_context_lead_not_found():
    class EmptyAdapter(DummyAdapter):
        def query(self, table: str, filters: Dict[str, str], limit: int, order_by: str = None, descending: bool = False):
            return []

    adapter = EmptyAdapter()

    result = reply_context.build_reply_context(adapter, email="missing@example.com")

    assert result["status"] == "lead_not_found"


def test_build_reply_context_staging_source():
    adapter = DummyStagingAdapter()

    result = reply_context.build_reply_context(
        adapter,
        email="staging@example.com",
        include_all_threads=False,
    )

    assert result["status"] == "success"
    assert result["lead_source"] == "staging_leads"
    assert result["conversation_source"] == "staging_conversations"
    assert result["message_count"] == 1