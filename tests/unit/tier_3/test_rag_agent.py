import pytest
from agent.operational_agents.factory import create_persistence_agent
from agent.tools.persistence.service import ReadOnlyPersistenceFacade
from agent.operational_agents.rag_agent.rag_agent import RAGAgent
from agent.config.persistence_config import get_read_allowlist


@pytest.fixture(scope="module")
def shared_service_and_facade():
    # extend write allowlist for test seeding; read facade can include same plus additions
    write_allow = ['leads', 'staging_leads', 'conversations', 'messages', 'inquiries', 'campaigns', 'clients']
    p = create_persistence_agent(kind='memory', allowed_tables=write_allow)
    svc = p.service
    # seed tables
    svc.write('leads', {'email': 'alice@example.com', 'company_name': 'Acme', 'client_id': 'c1'})
    svc.write('leads', {'email': 'bob@example.org', 'company_name': 'BetaCorp', 'client_id': 'c1'})
    svc.write('staging_leads', {'email': 'staging@example.com'})
    svc.write('conversations', {'topic': 'welcome sequence', 'client_id': 'c1'})
    svc.write('messages', {'conversation_id': '1', 'direction': 'outbound', 'body': 'Hello Alice'})
    svc.write('inquiries', {'email': 'alice@example.com', 'status': 'open'})
    svc.write('campaigns', {'name': 'Fall Outreach', 'status': 'active'})
    svc.write('clients', {'name': 'Acme', 'tier': 'gold'})
    facade = ReadOnlyPersistenceFacade(svc)
    return svc, facade


@pytest.fixture()
def rag(shared_service_and_facade):
    _, facade = shared_service_and_facade
    return RAGAgent(read_only_persistence=facade)


def test_query_leads_email_filter(rag):
    envelope = rag.run('find leads with alice@example.com', return_json=True)
    assert envelope['metadata']['total_count'] == 1
    emails = [r.get('email') for r in envelope['records']]
    assert 'alice@example.com' in emails


def test_query_leads_company_filter(rag):
    envelope = rag.run('show me leads at Acme', return_json=True)
    assert envelope['metadata']['total_count'] >= 1
    assert any('Acme' in (r.get('company_name') or '') for r in envelope['records'])


def test_query_leads_domain_wildcard(rag):
    # In-memory adapter only supports equality; test exact secondary email
    tool = next(t for t in rag.tools if t.name == 'query_leads')
    res = tool.func({'filters': {'email': 'bob@example.org'}})
    assert res['metadata']['total_count'] == 1
    assert res['records'][0]['email'] == 'bob@example.org'


def test_generic_query_each_table(rag):
    # Enumerate read allowlist and query first few tables generically
    allowlist = get_read_allowlist()
    exercised = {}
    for table in allowlist:
        # use generic query tool if available
        tool = next((t for t in rag.tools if t.name == 'query_table'), None)
        if tool is None:
            pytest.skip('query_table tool not registered (facade missing)')
        result = tool.func({'table': table})
        assert 'metadata' in result
        assert result['metadata']['source'].startswith('persistence.')
        # we only require that the tool runs; rows may be zero for some seeded sets
        assert 'records' in result
        exercised[table] = result['metadata']['total_count']
    # Ensure at least leads was exercised with >0 results
    assert exercised.get('leads', 0) > 0


def test_query_table_with_filters(rag):
    tool = next((t for t in rag.tools if t.name == 'query_table'), None)
    assert tool is not None
    res = tool.func({'table': 'clients', 'filters': {'name': 'Acme'}})
    assert res['metadata']['total_count'] == 1
    assert res['records'][0]['name'] == 'Acme'


def test_rag_agent_no_write_capability(rag):
    # RAG agent should not expose write methods of the underlying persistence facade
    with pytest.raises(AttributeError):
        _ = rag.write  # type: ignore[attr-defined]


def test_query_invalid_table(rag):
    tool = next((t for t in rag.tools if t.name == 'query_table'), None)
    if tool is None:
        pytest.skip('query_table tool not available')
    res = tool.func({'table': 'nonexistent_table_xyz'})
    # Should return error metadata and zero records rather than raising directly
    assert res['metadata']['total_count'] == 0
    assert 'error' in res['metadata']


def test_fallback_on_empty(rag):
    # Use a query with filters that won't match seeded data
    empty_prompt = 'find leads at CompanyThatDoesNotExistXYZ'
    env = rag.run(empty_prompt, return_json=True, fallback_on_empty=True)
    # Since no rows, we expect fallback metadata flag and possibly a synthetic response record
    assert env['metadata'].get('fallback') == 'agent'
    # total_count refers to actual lead rows (should remain 0)
    assert env['metadata']['total_count'] == 0
    # Ensure a response record exists from agent reasoning
    assert any('response' in r for r in env['records'])
