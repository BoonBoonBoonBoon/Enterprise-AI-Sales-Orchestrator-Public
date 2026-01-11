import pytest
from agent.operational_agents.factory import create_persistence_agent
from agent.tools.persistence.service import ReadOnlyPersistenceFacade
from agent.operational_agents.rag_agent.rag_agent import RAGAgent

@pytest.fixture(scope="module")
def rag_many():
    # allow writes for seeding
    write_allow = ['leads']
    p = create_persistence_agent(kind='memory', allowed_tables=write_allow)
    svc = p.service
    # seed 120 leads to exercise pagination + summary threshold (default SUMMARY_THRESHOLD=200 -> may not trigger summary here)
    for i in range(120):
        svc.write('leads', {
            'email': f'user{i}@example.com',
            'company_name': 'Acme' if i % 2 == 0 else 'Beta',
            'client_id': 'c1'
        })
    facade = ReadOnlyPersistenceFacade(svc)
    return RAGAgent(read_only_persistence=facade)

def test_first_page_limit_default(rag_many):
    # run without explicit limit -> DEFAULT_PAGE_LIMIT (50)
    env = rag_many.run('find leads at Acme', return_json=True)
    assert env['metadata']['total_count'] <= 50  # paginated slice count
    assert 'truncated' not in env['metadata']  # below summary threshold


def test_explicit_limit_and_offset(rag_many):
    env1 = rag_many.run('find leads at Acme', return_json=True, limit=20, offset=0)
    env2 = rag_many.run('find leads at Acme', return_json=True, limit=20, offset=20)
    assert env1['metadata']['total_count'] == 20
    assert env2['metadata']['total_count'] == 20
    ids_page1 = {r['provenance']['row_id'] for r in env1['records'] if 'provenance' in r}
    ids_page2 = {r['provenance']['row_id'] for r in env2['records'] if 'provenance' in r}
    assert ids_page1.isdisjoint(ids_page2)


def test_cache_hit(rag_many):
    env1 = rag_many.run('find leads at Acme', return_json=True, limit=10)
    env2 = rag_many.run('find leads at Acme', return_json=True, limit=10)
    # cache metadata only exists on tool path; run() fast path returns similar but we didn't embed cache flag
    # So instead directly invoke query_leads_tool to inspect cache behavior
    tool = next(t for t in rag_many.tools if t.name == 'query_leads')
    res1 = tool.func({'filters': {'company': 'Acme'}, 'limit': 15})
    res2 = tool.func({'filters': {'company': 'Acme'}, 'limit': 15})
    assert res1['metadata']['cache'] in ('hit', 'miss')
    assert res2['metadata']['cache'] == 'hit'


def test_limit_cap(rag_many):
    # Request an excessively large limit to ensure it is capped
    tool = next(t for t in rag_many.tools if t.name == 'query_leads')
    res = tool.func({'filters': {'company': 'Acme'}, 'limit': 999999})
    assert res['metadata']['limit'] <= 500  # capped by MAX_PAGE_LIMIT

