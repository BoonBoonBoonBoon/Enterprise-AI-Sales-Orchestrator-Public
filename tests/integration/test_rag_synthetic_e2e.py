"""
Integration-style synthetic RAG retrieval test.

This test boots RAGAgent with a stub Supabase adapter and ensures we get a
non-empty retrieval payload (synthetic corpus) without hitting external
services. It also stubs the deep agent to avoid network calls.
"""

import os
import types

import pytest

from tiers.tier_3.rag_agent import rag_agent as rag_module


class FakeSupabaseAdapter:
    """Minimal stub that returns a deterministic synthetic record."""

    def __init__(self, url: str, key: str, anon_key: str | None = None):
        self.url = url
        self.key = key
        self.anon_key = anon_key
        self.synthetic_records = [
            {
                "id": "lead_synth_1",
                "email": "synthetic@example.com",
                "company": "Synthetic Corp",
                "status": "active",
                "score": 88,
            }
        ]

    def query(
        self,
        table: str,
        filters: dict | None = None,
        limit: int = 50,
        order_by: str | None = None,
        descending: bool = False,
        select: str | None = None,
    ):
        return {"data": list(self.synthetic_records)[: limit]}

    def read(self, table: str, id_value: str):
        return {"data": self.synthetic_records[0]}


class FakeRedis:
    """No-op Redis stub used to satisfy constructor requirements."""

    def __getattr__(self, _name):  # pragma: no cover - defensive fallback
        def _noop(*_args, **_kwargs):
            return None

        return _noop


@pytest.fixture
def stub_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.test")
    monkeypatch.setenv("SUPABASE_RAG_JWT", "test-rag-jwt")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "test-anon")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service")


@pytest.fixture
def rag_agent(monkeypatch, stub_env):
    # Stub SupabaseAdapter to avoid network calls and return synthetic corpus
    monkeypatch.setattr(rag_module, "SupabaseAdapter", FakeSupabaseAdapter)

    # Stub deep agent creation to avoid LLM calls
    monkeypatch.setattr(rag_module, "create_deep_agent", lambda *args, **kwargs: types.SimpleNamespace())

    return rag_module.RAGAgent(redis_client=FakeRedis(), tenant_id="agentic-synth", model="stub-model")


def test_rag_retrieval_returns_records(rag_agent):
    # Build the search tool (StructuredTool); invoke with keyword payload
    search_tool = rag_agent._create_search_leads_tool()

    result = search_tool.invoke({
        "email": "synthetic@example.com",
        "status": "active",
        "limit": 5,
    })

    assert result["status"] == "success"
    assert result["count"] >= 1
    assert result["records"], "Expected at least one synthetic record"
    assert result["records"][0]["company"] == "Synthetic Corp"
    assert result["records"][0]["email"] == "synthetic@example.com"
