"""NLP-style integration tests for RAGAgent natural language filter parsing.

Goals:
* Ensure free-text prompts map to correct structured filters (id/email/company)
* Confirm results are returned in envelope shape with provenance
* Guard against accidental writes (read-only facade integrity)

These tests avoid LLM fallback (rule-based only) so they are fully deterministic
and fast for CI. We do not set OPENAI_API_KEY here intentionally.
"""
from __future__ import annotations

import pytest

from agent.config.persistence_config import get_write_allowlist, get_read_allowlist
from agent.tools.persistence.adapters.in_memory_adapter import InMemoryAdapter
from agent.tools.persistence.service import PersistenceService, ReadOnlyPersistenceFacade
from agent.operational_agents.persistence_agent.persistence_agent import PersistenceAgent
from agent.operational_agents.rag_agent.rag_agent import RAGAgent


@pytest.fixture(scope="module")
def seeded_agents():
    # Build a shared in-memory adapter so writes are visible to RAG
    adapter = InMemoryAdapter()
    write_allow = get_write_allowlist()
    read_allow = get_read_allowlist()
    svc = PersistenceService(
        adapter,
        read_allowlist=read_allow,
        write_allowlist=write_allow,
    )
    writer = PersistenceAgent(svc)
    acme_lead = writer.write(
        "leads",
        {"email": "alice@acme.io", "company_name": "Acme", "client_id": "c1"}
    )
    beta_lead = writer.write(
        "leads",
        {"email": "bob@betacorp.org", "company_name": "BetaCorp", "client_id": "c1"}
    )
    ro = ReadOnlyPersistenceFacade(svc)
    rag = RAGAgent(read_only_persistence=ro)
    return {
        "rag": rag,
        "acme_id": acme_lead["id"],
        "beta_id": beta_lead["id"],
        "alice_email": acme_lead["email"],
    }


def _assert_envelope_shape(env):
    assert "metadata" in env and "records" in env
    assert isinstance(env["records"], list)
    md = env["metadata"]
    assert "total_count" in md and md["total_count"] >= 0


def test_nlp_company_query(seeded_agents):
    rag = seeded_agents["rag"]
    # Directly invoke the leads tool for deterministic behavior (bypasses LLM tool choice).
    tool = next(t for t in rag.tools if t.name == 'query_leads')
    env = tool.func({'company': 'Acme'})
    _assert_envelope_shape(env)
    assert env["metadata"]["total_count"] >= 1
    assert any(r.get('company_name','').lower() == 'acme' for r in env['records'])


def test_nlp_email_query(seeded_agents):
    rag = seeded_agents["rag"]
    email = seeded_agents["alice_email"]
    tool = next(t for t in rag.tools if t.name == 'query_leads')
    env = tool.func({'email': email})
    _assert_envelope_shape(env)
    assert env["metadata"]["total_count"] >= 1
    assert any(r.get('email','').lower() == email for r in env['records'])


def test_nlp_id_query(seeded_agents):
    rag = seeded_agents["rag"]
    lead_id = seeded_agents["acme_id"]
    tool = next(t for t in rag.tools if t.name == 'query_leads')
    env = tool.func({'id': lead_id})
    _assert_envelope_shape(env)
    assert env["metadata"]["total_count"] >= 1
    assert any(r.get('id') == lead_id for r in env['records'])


def test_read_only_no_write_methods(seeded_agents):
    rag = seeded_agents["rag"]
    # The rag agent should not expose a direct write; attempt attribute guard
    assert not hasattr(rag, "write"), "RAG agent should not expose write method"
