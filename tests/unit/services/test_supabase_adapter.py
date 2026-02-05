import os

import pytest

from services.persistence.adapters.supabase_adapter import SupabaseAdapter


class DummyResponse:
    def __init__(self, status_code=200, json_data=None, text="OK"):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def json(self):
        if self._json_data is None:
            raise ValueError("no json")
        return self._json_data


def _build_adapter():
    os.environ["SUPABASE_SKIP_DNS_CHECK"] = "1"
    return SupabaseAdapter(
        url="https://example.supabase.co",
        key="jwt-token",
        anon_key="anon-key",
        client=object(),
    )


def test_rest_headers_custom_jwt():
    adapter = _build_adapter()

    headers = adapter._rest_headers()

    assert headers["apikey"] == "anon-key"
    assert headers["Authorization"] == "Bearer jwt-token"


def test_rest_query_ilike_translation(monkeypatch):
    adapter = _build_adapter()

    captured = {}

    class FakeSession:
        def get(self, url, headers=None, params=None, timeout=None):
            captured["url"] = url
            captured["params"] = params
            return DummyResponse(status_code=200, json_data=[])

    monkeypatch.setitem(os.environ, "RAG_DEEP_DEBUG", "0")
    monkeypatch.setattr(adapter, "_get_rest_session", lambda: FakeSession())

    adapter._rest_query(
        "leads",
        filters={"email": "%example.com"},
        limit=5,
        order_by="created_at",
        descending=True,
        select=["id", "email"],
    )

    assert captured["params"]["email"] == "ilike.*example.com"
    assert captured["params"]["limit"] == 5
    assert captured["params"]["order"] == "created_at.desc"
    assert captured["params"]["select"] == "id,email"


def test_rest_upsert_on_conflict(monkeypatch):
    adapter = _build_adapter()

    captured = {}

    class FakeSession:
        def post(self, url, headers=None, params=None, json=None, timeout=None):
            captured["params"] = params
            return DummyResponse(status_code=200, json_data=[{"id": "1"}])

    monkeypatch.setattr(adapter, "_get_rest_session", lambda: FakeSession())

    result = adapter._rest_upsert("leads", {"id": "1"}, on_conflict=["id", "email"])

    assert result["id"] == "1"
    assert captured["params"]["on_conflict"] == "id,email"


def test_rest_delete_handles_error(monkeypatch):
    adapter = _build_adapter()

    class FakeSession:
        def delete(self, url, headers=None, timeout=None):
            return DummyResponse(status_code=400, json_data=None, text="bad")

    monkeypatch.setattr(adapter, "_get_rest_session", lambda: FakeSession())

    result = adapter._rest_delete("leads", "abc")

    assert result["status_code"] == 400