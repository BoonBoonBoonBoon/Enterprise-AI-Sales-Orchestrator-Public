import os
import pytest
from agent.operational_agents.factory import create_persistence_agent, create_rag_agent
from agent.tools.persistence.service import ReadOnlyPersistenceFacade
from agent.operational_agents.rag_agent.rag_agent import RAGAgent

REAL_SUPABASE_AVAILABLE = (
    os.environ.get('USE_REAL_TESTS') == '1'
    and bool(os.environ.get('SUPABASE_URL') and (os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY')))
)

@pytest.mark.skipif(not REAL_SUPABASE_AVAILABLE, reason="Requires real Supabase credentials in env")
class TestPublicLeadsReal:
    @pytest.fixture(scope='class')
    def rag_real(self):
        # create rag agent via factory (assumes facade injection)
        rag = create_rag_agent(kind='supabase')
        return rag

    @pytest.fixture(scope='class')
    def one_valid_lead(self, rag_real):
        """Fetch a small list of leads and return one record as a source of valid values.

        This avoids hard-coding any specific ID/email/company in tests.
        """
        env = rag_real.run('find leads', return_json=True, limit=5)
        recs = env.get('records') or []
        if not recs:
            pytest.skip('No leads available in Supabase to sample for valid tests')
        # find a record with the expected fields
        for r in recs:
            if isinstance(r, dict) and (r.get('email') or r.get('company_name') or r.get('id')):
                return r
        pytest.skip('No usable lead (email/company_name/id) available to sample')

    def test_real_basic_query(self, rag_real):
        env = rag_real.run('find leads', return_json=True, limit=5)
        assert 'metadata' in env
        assert 'records' in env
        # can't guarantee >0 rows in all deployments, but surface debug
        print('[DEBUG real_basic_query] total_count=', env['metadata'].get('total_count'))

    def test_real_filter_email_wildcard(self, rag_real):
        env = rag_real.run('email contains gmail.com', return_json=True, limit=5)
        print('[DEBUG real_filter_email_wildcard] filters=', env['metadata'].get('query_filters'), 'count=', env['metadata'].get('total_count'))
        assert 'metadata' in env
        # Not asserting count > 0 since dataset varies, but ensure query didn't crash

    def test_real_fallback_when_empty(self, rag_real, monkeypatch):
        # Force an unlikely company to trigger fallback path
        env = rag_real.run('find leads at CompanyThatDoesNotExistXYZ', return_json=True, fallback_on_empty=True)
        print('[DEBUG real_fallback] metadata=', env['metadata'])
        assert env['metadata'].get('fallback') in (None, 'agent', 'reformulation', 'suppressed')

    def test_real_email_exact_success_and_fail(self, rag_real, one_valid_lead):
        valid_email = one_valid_lead.get('email')
        if not valid_email:
            pytest.skip('Sampled lead has no email')
        # Success: exact email
        env_ok = rag_real.run(f'find leads {valid_email}', return_json=True, limit=5)
        print('[DEBUG real_email_success] email=', valid_email, 'count=', env_ok['metadata'].get('total_count'))
        assert env_ok['metadata']['total_count'] >= 1
        # Fail: impossible email
        fake_email = 'zz_no_such_user_3971@nope.invalid'
        env_bad = rag_real.run(f'find leads {fake_email}', return_json=True, limit=5, fallback_on_empty=True)
        print('[DEBUG real_email_fail] email=', fake_email, 'count=', env_bad['metadata'].get('total_count'), 'fallback=', env_bad['metadata'].get('fallback'))
        assert env_bad['metadata']['total_count'] == 0

    def test_real_company_success_and_fail(self, rag_real, one_valid_lead):
        company = one_valid_lead.get('company_name')
        if not company:
            pytest.skip('Sampled lead has no company_name')
        # Success: company name
        env_ok = rag_real.run(f'find leads at {company}', return_json=True, limit=5)
        print('[DEBUG real_company_success] company=', company, 'count=', env_ok['metadata'].get('total_count'))
        assert env_ok['metadata']['total_count'] >= 1
        # Fail: unlikely company
        fake_company = 'CompanyThatDoesNotExist_9c5cb0a7'
        env_bad = rag_real.run(f'find leads at {fake_company}', return_json=True, limit=5, fallback_on_empty=True)
        print('[DEBUG real_company_fail] company=', fake_company, 'count=', env_bad['metadata'].get('total_count'), 'fallback=', env_bad['metadata'].get('fallback'))
        assert env_bad['metadata']['total_count'] == 0

    def test_real_id_success_and_fail(self, rag_real, one_valid_lead):
        vid = one_valid_lead.get('id')
        if not vid:
            pytest.skip('Sampled lead has no id')
        # Success: id exact
        env_ok = rag_real.run(f'id {vid}', return_json=True, limit=5)
        print('[DEBUG real_id_success] id=', vid, 'count=', env_ok['metadata'].get('total_count'))
        assert env_ok['metadata']['total_count'] >= 1
        # Fail: random-like id unlikely to exist
        fake_id = 'zzzz-not-a-real-id-9c5cb0a7'
        env_bad = rag_real.run(f'id {fake_id}', return_json=True, limit=5, fallback_on_empty=True)
        print('[DEBUG real_id_fail] id=', fake_id, 'count=', env_bad['metadata'].get('total_count'), 'fallback=', env_bad['metadata'].get('fallback'))
        assert env_bad['metadata']['total_count'] == 0


class TestPublicLeadsMock:
    @pytest.fixture(scope='class')
    def rag_mock(self):
        p = create_persistence_agent(kind='memory', allowed_tables=['leads'])
        svc = p.service
        # seed mock data
        svc.write('leads', {'email': 'alice@test.io', 'company_name': 'Acme', 'client_id': 'c1'})
        svc.write('leads', {'email': 'bob@test.io', 'company_name': 'Beta LLC', 'client_id': 'c1'})
        svc.write('leads', {'email': 'carol@test.io', 'company_name': 'Acme Incorporated', 'client_id': 'c2'})
        rag = RAGAgent(read_only_persistence=ReadOnlyPersistenceFacade(svc))
        return rag

    def test_mock_correct_filters(self, rag_mock):
        env = rag_mock.run('find leads at Acme', return_json=True)
        assert env['metadata']['total_count'] >= 1
        print('[DEBUG mock_correct_filters] count=', env['metadata']['total_count'])

    def test_mock_purposefully_wrong_filters(self, rag_mock):
        # Query with invalid email pattern to ensure it doesn't crash and returns zero
        env = rag_mock.run('email contains invalid_domain_xyz.unknown', return_json=True)
        assert env['metadata']['total_count'] == 0
        print('[DEBUG mock_wrong_filters] fallback=', env['metadata'].get('fallback'))

    def test_mock_no_data(self):
        p = create_persistence_agent(kind='memory', allowed_tables=['leads'])
        rag = RAGAgent(read_only_persistence=ReadOnlyPersistenceFacade(p.service))
        env = rag.run('find leads at Acme', return_json=True, fallback_on_empty=True)
        # Expect fallback since dataset empty
        assert env['metadata']['total_count'] == 0
        print('[DEBUG mock_no_data] metadata=', env['metadata'])

    def test_mock_reformulation(self, rag_mock, monkeypatch):
        # Use company variant that will require shortening (e.g., 'Beta LLC')
        env = rag_mock.run('find leads at Beta LLC', return_json=True)
        # Should match Beta LLC directly or via reformulation
        assert env['metadata']['total_count'] >= 1
        print('[DEBUG mock_reformulation] attempts=', env['metadata'].get('reformulation_attempts'))

    def test_mock_pagination_and_cache(self, rag_mock):
        env1 = rag_mock.run('find leads at Acme', return_json=True, limit=1, offset=0)
        env2 = rag_mock.run('find leads at Acme', return_json=True, limit=1, offset=1)
        assert env1['metadata']['total_count'] <= 1
        assert env2['metadata']['total_count'] <= 1
        print('[DEBUG mock_pagination] page1_count=', env1['metadata']['total_count'], 'page2_count=', env2['metadata']['total_count'])

    def test_mock_ilike_wildcard(self, rag_mock):
        # Should match all *@test.io using ilike-style contains
        env = rag_mock.run('email contains test.io', return_json=True, limit=10)
        print('[DEBUG mock_ilike_wildcard] filters=', env['metadata'].get('query_filters'), 'count=', env['metadata'].get('total_count'))
        assert env['metadata']['total_count'] >= 1


@pytest.mark.skipif(not REAL_SUPABASE_AVAILABLE, reason="Requires real Supabase credentials in env")
class TestFallbackLLMReal:
    @pytest.fixture(scope='class')
    def rag_real_llm(self):
        os.environ.setdefault('RAG_DEBUG', '1')
        return create_rag_agent(kind='supabase')

    def test_trigger_fallback_llm(self, rag_real_llm):
        env = rag_real_llm.run('find leads at UnlikelyCompanyZZZ', return_json=True, fallback_on_empty=True)
        print('[DEBUG fallback_llm] metadata=', env['metadata'])
        assert env['metadata'].get('fallback') in (None, 'agent', 'reformulation', 'suppressed')
