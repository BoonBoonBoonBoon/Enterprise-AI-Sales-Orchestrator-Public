"""Tests for context forwarding through orchestrator→RAG→copywriter flow.

Validates that lead_data, campaign_context, and correlation_id are
correctly forwarded through the multi-worker pipeline.
"""
import pytest
from core.envelope.typed_envelope import task, result, to_redis_fields, from_redis_message, Priority


class TestCorrelationTracking:
    """Test correlation_id propagation across worker boundaries."""
    
    def test_correlation_id_chain(self):
        """Test correlation_id is preserved through task→result→task chain."""
        # Orchestrator creates initial task
        orchestrator_task = task(
            task_id="orch_001",
            payload={"query": {"table": "leads"}},
            source="orchestrator",
            destination="rag:tasks",
            campaign_id="campaign_123"
        )
        
        original_correlation_id = orchestrator_task.metadata.correlation_id
        
        # RAG worker receives task
        rag_fields = to_redis_fields(orchestrator_task)
        rag_task = from_redis_message(rag_fields)
        
        assert rag_task.metadata.correlation_id == original_correlation_id
        
        # RAG worker sends result
        rag_result = result(
            original=rag_task,
            payload={"records": [{"email": "test@example.com"}], "count": 1},
            source="rag_worker"
        )
        
        assert rag_result.metadata.correlation_id == original_correlation_id
        
        # Orchestrator receives result
        orch_result_fields = to_redis_fields(rag_result)
        orch_result = from_redis_message(orch_result_fields)
        
        assert orch_result.metadata.correlation_id == original_correlation_id
        
        # Orchestrator creates copywriter task
        copy_task = task(
            task_id="copy_001",
            payload={
                "lead_data": orch_result.payload["records"][0],
                "campaign_context": {},
                "instructions": {}
            },
            source="orchestrator",
            destination="copy:tasks",
            correlation_id=original_correlation_id  # Preserve original correlation
        )
        
        assert copy_task.metadata.correlation_id == original_correlation_id


class TestLeadDataForwarding:
    """Test lead_data forwarding from RAG→orchestrator→copywriter."""
    
    def test_lead_data_preservation(self):
        """Test lead_data is preserved through RAG result to copywriter task."""
        # RAG worker returns lead data
        rag_task = task(
            task_id="rag_query",
            payload={"query": {"table": "leads", "filters": {"email": "prospect@company.com"}}},
            source="orchestrator",
            destination="rag:tasks"
        )
        
        lead_record = {
            "id": "lead_456",
            "email": "prospect@company.com",
            "first_name": "Emma",
            "last_name": "Johnson",
            "company_name": "InnovateCo",
            "title": "CTO",
            "phone": "+1-555-0123",
            "linkedin": "linkedin.com/in/emmajohnson"
        }
        
        rag_result = result(
            original=rag_task,
            payload={"records": [lead_record], "count": 1},
            source="rag_worker"
        )
        
        # Orchestrator extracts lead_data from RAG result
        rag_result_fields = to_redis_fields(rag_result)
        parsed_result = from_redis_message(rag_result_fields)
        
        extracted_lead = parsed_result.payload["records"][0]
        
        # Orchestrator creates copywriter task with lead_data
        copy_task = task(
            task_id="copy_gen",
            payload={
                "lead_data": extracted_lead,
                "campaign_context": {},
                "instructions": {}
            },
            source="orchestrator",
            destination="copy:tasks",
            correlation_id=rag_result.metadata.correlation_id
        )
        
        # Copywriter receives task
        copy_fields = to_redis_fields(copy_task)
        copy_parsed = from_redis_message(copy_fields)
        
        # Verify all lead fields preserved
        assert copy_parsed.payload["lead_data"]["email"] == "prospect@company.com"
        assert copy_parsed.payload["lead_data"]["first_name"] == "Emma"
        assert copy_parsed.payload["lead_data"]["company_name"] == "InnovateCo"
        assert copy_parsed.payload["lead_data"]["title"] == "CTO"


class TestCampaignContextForwarding:
    """Test campaign_context forwarding to copywriter."""
    
    def test_campaign_context_enrichment(self):
        """Test orchestrator enriches and forwards campaign context."""
        # Orchestrator task with campaign metadata
        initial_task = task(
            task_id="orch_init",
            payload={"query": {"table": "leads"}},
            source="orchestrator",
            destination="rag:tasks",
            campaign_id="campaign_q1",
            tenant_id="tenant_abc",
            user_id="user_123"
        )
        
        # RAG returns lead
        rag_result = result(
            original=initial_task,
            payload={"records": [{"email": "lead@company.com", "first_name": "Alex"}], "count": 1},
            source="rag_worker"
        )
        
        # Orchestrator builds campaign context from metadata + external data
        campaign_context = {
            "campaign_id": rag_result.metadata.campaign_id,
            "campaign_name": "Q1 2025 Outreach",
            "step": 1,
            "total_steps": 3,
            "previous_subject": None,
            "days_since_last_contact": 0,
            "sender_name": "Sales Team",
            "sender_email": "sales@ourcompany.com"
        }
        
        # Orchestrator sends to copywriter with enriched context
        copy_task = task(
            task_id="copy_enriched",
            payload={
                "lead_data": rag_result.payload["records"][0],
                "campaign_context": campaign_context,
                "instructions": {"tone": "professional", "language": "en-US"}
            },
            source="orchestrator",
            destination="copy:tasks",
            campaign_id=rag_result.metadata.campaign_id,
            correlation_id=rag_result.metadata.correlation_id
        )
        
        # Copywriter receives enriched context
        copy_fields = to_redis_fields(copy_task)
        copy_parsed = from_redis_message(copy_fields)
        
        assert copy_parsed.payload["campaign_context"]["campaign_id"] == "campaign_q1"
        assert copy_parsed.payload["campaign_context"]["step"] == 1
        assert copy_parsed.payload["campaign_context"]["sender_name"] == "Sales Team"


class TestMultiTenantContext:
    """Test tenant_id and user_id forwarding."""
    
    def test_tenant_context_forwarding(self):
        """Test tenant and user IDs are forwarded through pipeline."""
        # Initial orchestrator task with tenant context
        orch_task = task(
            task_id="tenant_task",
            payload={"query": {"table": "leads"}},
            source="orchestrator",
            destination="rag:tasks",
            tenant_id="tenant_xyz",
            user_id="user_789",
            campaign_id="campaign_abc"
        )
        
        # RAG worker preserves context
        rag_fields = to_redis_fields(orch_task)
        rag_task = from_redis_message(rag_fields)
        
        assert rag_task.metadata.tenant_id == "tenant_xyz"
        assert rag_task.metadata.user_id == "user_789"
        
        # RAG result preserves context
        rag_result = result(
            original=rag_task,
            payload={"records": [{"email": "test@example.com"}], "count": 1},
            source="rag_worker"
        )
        
        assert rag_result.metadata.tenant_id == "tenant_xyz"
        assert rag_result.metadata.user_id == "user_789"
        
        # Copywriter task preserves context
        copy_task = task(
            task_id="copy_tenant",
            payload={
                "lead_data": rag_result.payload["records"][0],
                "campaign_context": {},
                "instructions": {}
            },
            source="orchestrator",
            destination="copy:tasks",
            tenant_id=rag_result.metadata.tenant_id,
            user_id=rag_result.metadata.user_id,
            correlation_id=rag_result.metadata.correlation_id
        )
        
        copy_fields = to_redis_fields(copy_task)
        copy_parsed = from_redis_message(copy_fields)
        
        assert copy_parsed.metadata.tenant_id == "tenant_xyz"
        assert copy_parsed.metadata.user_id == "user_789"


class TestEndToEndContextFlow:
    """Test complete end-to-end context flow through orchestrator→RAG→copywriter."""
    
    def test_full_pipeline_context(self):
        """Test complete context flow with all metadata preserved."""
        # Step 1: Orchestrator initiates RAG query
        orch_query = task(
            task_id="orch_001",
            payload={
                "query": {
                    "table": "leads",
                    "filters": {"email": "prospect@techcorp.com"},
                    "limit": 1
                }
            },
            source="orchestrator",
            destination="rag:tasks",
            tenant_id="tenant_001",
            user_id="user_456",
            campaign_id="campaign_q1_2025",
            priority=Priority.HIGH
        )
        
        original_correlation_id = orch_query.metadata.correlation_id
        
        # Step 2: RAG worker processes query
        rag_fields = to_redis_fields(orch_query)
        rag_task = from_redis_message(rag_fields)
        
        # Verify RAG received correct context
        assert rag_task.metadata.correlation_id == original_correlation_id
        assert rag_task.metadata.tenant_id == "tenant_001"
        assert rag_task.metadata.campaign_id == "campaign_q1_2025"
        assert rag_task.payload["query"]["table"] == "leads"
        
        # Step 3: RAG returns lead data
        lead_data = {
            "id": "lead_789",
            "email": "prospect@techcorp.com",
            "first_name": "Michael",
            "last_name": "Chen",
            "company_name": "TechCorp Systems",
            "title": "Director of Engineering",
            "industry": "SaaS",
            "employees": 150
        }
        
        rag_result = result(
            original=rag_task,
            payload={"records": [lead_data], "count": 1, "table": "leads"},
            source="rag_worker"
        )
        
        # Verify RAG result preserves context
        assert rag_result.metadata.correlation_id == original_correlation_id
        assert rag_result.metadata.tenant_id == "tenant_001"
        assert rag_result.metadata.campaign_id == "campaign_q1_2025"
        
        # Step 4: Orchestrator receives result and builds copywriter task
        rag_result_fields = to_redis_fields(rag_result)
        parsed_rag_result = from_redis_message(rag_result_fields)
        
        campaign_context = {
            "campaign_id": parsed_rag_result.metadata.campaign_id,
            "campaign_name": "Q1 2025 Enterprise Outreach",
            "step": 1,
            "total_steps": 4,
            "previous_subject": None,
            "days_since_last_contact": 0,
            "sender_name": "Sarah Williams",
            "sender_email": "sarah@ourcompany.com",
            "company_value_prop": "AI-powered sales automation"
        }
        
        instructions = {
            "tone": "professional",
            "language": "en-US",
            "max_length": 250,
            "include_cta": True,
            "cta": "schedule a 15-minute call",
            "personalization": ["company_name", "title", "industry"]
        }
        
        copy_task = task(
            task_id="copy_001",
            payload={
                "lead_data": parsed_rag_result.payload["records"][0],
                "campaign_context": campaign_context,
                "instructions": instructions
            },
            source="orchestrator",
            destination="copy:tasks",
            tenant_id=parsed_rag_result.metadata.tenant_id,
            user_id=parsed_rag_result.metadata.user_id,
            campaign_id=parsed_rag_result.metadata.campaign_id,
            correlation_id=parsed_rag_result.metadata.correlation_id,
            priority=Priority.HIGH
        )
        
        # Step 5: Copywriter receives task with full context
        copy_fields = to_redis_fields(copy_task)
        copy_parsed = from_redis_message(copy_fields)
        
        # Verify all context preserved
        assert copy_parsed.metadata.correlation_id == original_correlation_id
        assert copy_parsed.metadata.tenant_id == "tenant_001"
        assert copy_parsed.metadata.user_id == "user_456"
        assert copy_parsed.metadata.campaign_id == "campaign_q1_2025"
        assert copy_parsed.metadata.priority == Priority.HIGH
        
        # Verify lead_data complete
        assert copy_parsed.payload["lead_data"]["email"] == "prospect@techcorp.com"
        assert copy_parsed.payload["lead_data"]["first_name"] == "Michael"
        assert copy_parsed.payload["lead_data"]["company_name"] == "TechCorp Systems"
        assert copy_parsed.payload["lead_data"]["title"] == "Director of Engineering"
        
        # Verify campaign_context complete
        assert copy_parsed.payload["campaign_context"]["campaign_name"] == "Q1 2025 Enterprise Outreach"
        assert copy_parsed.payload["campaign_context"]["step"] == 1
        assert copy_parsed.payload["campaign_context"]["sender_name"] == "Sarah Williams"
        
        # Verify instructions complete
        assert copy_parsed.payload["instructions"]["tone"] == "professional"
        assert copy_parsed.payload["instructions"]["include_cta"] is True
        assert copy_parsed.payload["instructions"]["personalization"] == ["company_name", "title", "industry"]
        
        # Step 6: Copywriter returns result with preserved correlation
        copy_result = result(
            original=copy_parsed,
            payload={
                "subject": "Scaling engineering at TechCorp Systems",
                "body": "Hi Michael, I noticed your work in SaaS...",
                "lead_id": "lead_789",
                "campaign_id": "campaign_q1_2025"
            },
            source="copywriter_worker"
        )
        
        # Verify final result preserves original correlation
        assert copy_result.metadata.correlation_id == original_correlation_id
        assert copy_result.metadata.tenant_id == "tenant_001"
        assert copy_result.metadata.campaign_id == "campaign_q1_2025"


class TestErrorContextPreservation:
    """Test context is preserved even in error scenarios."""
    
    def test_error_preserves_correlation(self):
        """Test error envelopes preserve correlation_id."""
        from core.envelope.typed_envelope import error
        
        original_task = task(
            task_id="error_test",
            payload={"query": {"table": "leads"}},
            source="orchestrator",
            destination="rag:tasks",
            tenant_id="tenant_err",
            campaign_id="campaign_err"
        )
        
        original_correlation = original_task.metadata.correlation_id
        
        # Worker encounters error
        error_envelope = error(
            original=original_task,
            error_msg="Database connection timeout",
            source="rag_worker",
            code="DB_TIMEOUT"
        )
        
        # Verify error preserves all context
        assert error_envelope.metadata.correlation_id == original_correlation
        assert error_envelope.metadata.tenant_id == "tenant_err"
        assert error_envelope.metadata.campaign_id == "campaign_err"
        assert error_envelope.error == "Database connection timeout"
        assert error_envelope.error_code == "DB_TIMEOUT"
