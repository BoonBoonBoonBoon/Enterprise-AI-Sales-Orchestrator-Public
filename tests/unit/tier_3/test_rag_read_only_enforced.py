"""Regression: Tier-3 RAG must not be able to write.

Even if a write-capable tool is accidentally added in the future, the adapter
used by `tiers.tier_3.rag_agent.rag_agent.RAGAgent` must refuse mutations.
"""

import types

import pytest

from tiers.tier_3.rag_agent import rag_agent as rag_module


class FakeSupabaseAdapter:
    def __init__(self, url: str, key: str, anon_key: str | None = None):
        self.url = url
        self.key = key
        self.anon_key = anon_key

    def read(self, table: str, id_value: str, id_column: str = "id"):
        return {"data": {"id": id_value}}

    def query(self, table: str, filters=None, limit=None, order_by=None, descending=False, select=None):
        return {"data": []}

    # Intentionally include write to ensure it gets blocked.
    def write(self, table: str, record: dict):  # pragma: no cover
        return {"status": "ok"}


class FakeRedis:
    def __getattr__(self, _name):  # pragma: no cover
        def _noop(*_args, **_kwargs):
            return None

        return _noop


@pytest.fixture
def rag_agent(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.test")
    monkeypatch.setenv("SUPABASE_RAG_JWT", "test-rag-jwt")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "test-anon")

    monkeypatch.setattr(rag_module, "SupabaseAdapter", FakeSupabaseAdapter)
    monkeypatch.setattr(rag_module, "create_deep_agent", lambda *args, **kwargs: types.SimpleNamespace())

    return rag_module.RAGAgent(redis_client=FakeRedis(), tenant_id="agentic-test", model="stub")


def test_rag_adapter_blocks_write(rag_agent):
    with pytest.raises(PermissionError):
        rag_agent.supabase.write("leads", {"id": "x"})
