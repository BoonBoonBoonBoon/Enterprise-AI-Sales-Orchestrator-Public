import os
import random
import pytest
from datetime import datetime, timezone

from agent.operational_agents.rag_agent.rag_agent import RAGAgent
from agent.tools.persistence.service import PersistenceService, InMemoryAdapter, ReadOnlyPersistenceFacade

"""Randomized real-data style tests.

Each lead from the provided source data is represented as an individual
Python dict constant (no embedded raw SQL). Tests randomly choose one
for each strategy (email / company / id) so we exercise varied paths
while staying deterministic per day+strategy (seeded by date+strategy).
"""

# Individual lead dicts (minimal fields needed for RAG filters + provenance checks)
LEAD_BILL = {
    "id": "23fe054a-1823-4d37-9218-527beac9b0b1",
    "client_id": "3111512b-dc2b-4c3f-8153-2bc0b3e0761f",
    "campaign_id": "9646f98a-e987-4a8c-b786-9b82ea985d38",
    "email": "bill@gmail.com",
    "first_name": "bill",
    "last_name": "bob",
    "company_name": "bb builders",
    "job_title": "director",
}

LEAD_JK = {
    "id": "75991643-a653-43eb-8220-0ed9f03bc25f",
    "client_id": "3111512b-dc2b-4c3f-8153-2bc0b3e0761f",
    "campaign_id": "9646f98a-e987-4a8c-b786-9b82ea985d38",
    "email": "jk@jk.com",
    "first_name": "john",
    "last_name": "knowe",
    "company_name": "JK consturction",
    "job_title": "Director",
}

LEAD_FLOW = {
    "id": "a864fe7f-d615-447b-ba7b-85cee457107d",
    "client_id": "90fd5909-89fb-4a7f-afa9-d17810496768",
    "campaign_id": "9646f98a-e987-4a8c-b786-9b82ea985d38",
    "email": "workflow+example@example.com",
    "first_name": "Flow",
    "last_name": "Example",
    "company_name": "FlowCo",
    "job_title": "Ops Engineer",
}

LEAD_EM = {
    "id": "b9722cc0-18ad-45c2-9a6e-ae0ce068d33d",
    "client_id": "592c9b4c-77be-4303-ad46-1ffb1ede127e",
    "campaign_id": "9646f98a-e987-4a8c-b786-9b82ea985d38",
    "email": "Test@gmail.com",
    "first_name": "em",
    "last_name": "em",
    "company_name": "em",
    "job_title": "em",
}

LEAD_WEZ = {
    "id": "fd6bc6b5-e2e8-449d-93f9-2d1b6c9ac8a1",
    "client_id": "4ecd445c-1ff8-44a3-8a0c-404e7c69f031",
    "campaign_id": "9646f98a-e987-4a8c-b786-9b82ea985d38",
    "email": "wez@gmail.com",
    "first_name": "wez",
    "last_name": "mud",
    "company_name": "WM company",
    "job_title": "CEO",
}

# Aggregate container (order stable for deterministic seeding)
ALL_TEST_LEADS = [LEAD_BILL, LEAD_JK, LEAD_FLOW, LEAD_EM, LEAD_WEZ]

# Verbosity flag (set RAG_REALDATA_VERBOSE=0 to silence extra prints)
REALDATA_VERBOSE = os.environ.get("RAG_REALDATA_VERBOSE", "1").lower() not in ("0", "false")

def _color(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m"

def _dump(data, limit=1200):
    import json as _json
    try:
        s = _json.dumps(data, default=str)
    except Exception:
        s = str(data)
    if len(s) > limit:
        return s[:limit] + "...<truncated>"
    return s

def _show_send(strategy: str, filters):  # pragma: no cover - diagnostic output
    if not REALDATA_VERBOSE:
        return
    print(_color('36', f"[REALDATA SEND] strategy={strategy} filters={_dump(filters)}"))

def _show_recv(envelope):  # pragma: no cover - diagnostic output
    if not REALDATA_VERBOSE:
        return
    meta = envelope.get('metadata', {}) if isinstance(envelope, dict) else {}
    total = meta.get('total_count')
    print(_color('32', f"[REALDATA RECV] total={total} envelope={_dump(envelope)}"))

@pytest.fixture(scope="module")
def rag_agent_real_like():
    adapter = InMemoryAdapter()
    service = PersistenceService(adapter=adapter, allowed_tables=["leads"])  # legacy single allowlist ok
    # populate table with original ids preserved
    for row in ALL_TEST_LEADS:
        service.write("leads", dict(row))
    facade = ReadOnlyPersistenceFacade(service)
    os.environ.setdefault("RAG_CACHE_DISABLED", "0")
    os.environ.setdefault("RAG_DEBUG_IO", "1")  # enable colorized debug during this test module
    return RAGAgent(read_only_persistence=facade)

@pytest.mark.parametrize("strategy", ["email", "company", "id"])
def test_random_real_data_lookup(rag_agent_real_like, strategy):
    # Random deterministic seed based on strategy & date to vary across days but stable within run
    seed_material = f"{strategy}-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    random.seed(seed_material)
    row = random.choice(ALL_TEST_LEADS)

    if strategy == "email":
        filters = {"email": row["email"]}
    elif strategy == "company":
        # Use full company name (wildcard removed to align with equality semantics of flat filters)
        filters = {"company": row["company_name"]}
    else:  # id
        filters = {"id": row["id"]}

    env = rag_agent_real_like.query_leads_tool({"filters": filters, "limit": 10})
    _show_send(strategy, filters)
    _show_recv(env)

    assert env["metadata"]["total_count"] >= 1, "Expected at least one match for selected filter"
    # Ensure returned rows correspond to the filter applied (basic assertion)
    if "email" in filters:
        assert any(r["email"].lower() == filters["email"].lower() for r in env["records"])  # case insensitive
    if "id" in filters:
        assert any(r.get("id") == filters["id"] for r in env["records"])  # exact
    if "company" in filters:
        fragment = filters["company"].lower()
        assert any(r["company_name"].lower() == fragment for r in env["records"]) or any(fragment in r["company_name"].lower() for r in env["records"])  # exact or substring


def test_randomized_multiple_queries(rag_agent_real_like):
    # Issue several random queries mixing strategies
    strategies = ["email", "company", "id"]
    seen = 0
    for i in range(5):
        strat = random.choice(strategies)
        row = random.choice(ALL_TEST_LEADS)
        if strat == "email":
            filters = {"email": row["email"]}
        elif strat == "company":
            filters = {"company": row["company_name"]}
        else:
            filters = {"id": row["id"]}
        env = rag_agent_real_like.query_leads_tool({"filters": filters, "limit": 5})
        _show_send(strat, filters)
        _show_recv(env)
        assert env["metadata"]["total_count"] >= 1
        seen += 1
    assert seen == 5
