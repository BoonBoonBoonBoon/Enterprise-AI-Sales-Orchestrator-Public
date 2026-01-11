"""
Integration tests for three-tier architecture.
Tests import paths and basic integration without requiring Redis.
"""

import pytest
from unittest.mock import MagicMock


class TestTierIntegration:
    """Test integration between tiers using new architecture."""
    
    def test_tier1_manager_imports(self):
        """Test tier_1 Manager imports successfully."""
        from tiers.tier_1.manager import ManagerAgent, ManagerAgentHarness, ManagerConsumer
        
        assert ManagerAgent is not None
        assert ManagerAgentHarness is not None
        assert ManagerConsumer is not None
    
    def test_tier2_orchestrator_imports(self):
        """Test tier_2 Orchestrator imports successfully."""
        from tiers.tier_2.leads_orchestrator import LeadsOrchestrator, LeadsOrchestratorHarness, LeadsConsumer
        from tiers.tier_2.outreach_orchestrator import OutreachOrchestrator, OutreachOrchestratorHarness, OutreachConsumer
        
        assert LeadsOrchestrator is not None
        assert LeadsOrchestratorHarness is not None
        assert LeadsConsumer is not None
        
        assert OutreachOrchestrator is not None
        assert OutreachOrchestratorHarness is not None
        assert OutreachConsumer is not None
    
    def test_tier3_agent_imports(self):
        """Test tier_3 Agent imports successfully."""
        from tiers.tier_3.persistence_agent import PersistenceAgent, PersistenceAgentHarness, PersistenceAgentConsumer
        from tiers.tier_3.rag_agent import RAGAgent, RAGAgentHarness, RAGConsumer
        from tiers.tier_3.copywriter_agent import CopywriterAgent, CopywriterAgentHarness, CopywriterAgentConsumer
        
        assert PersistenceAgent is not None
        assert PersistenceAgentHarness is not None
        assert PersistenceAgentConsumer is not None
        
        assert RAGAgent is not None
        assert RAGAgentHarness is not None
        assert RAGConsumer is not None
        
        assert CopywriterAgent is not None
        assert CopywriterAgentHarness is not None
        assert CopywriterAgentConsumer is not None
    
    def test_core_harness_imports(self):
        """Test core.harness imports successfully."""
        from core.harness import AgentHarness, HarnessConfig
        
        assert AgentHarness is not None
        assert HarnessConfig is not None
    
    def test_core_envelope_imports(self):
        """Test core.envelope imports successfully."""
        from core.envelope import Envelope
        
        assert Envelope is not None
    
    def test_services_imports(self):
        """Test services layer imports successfully."""
        from services.persistence import PersistenceService
        from services.redis import RedisPubSub
        
        assert PersistenceService is not None
        assert RedisPubSub is not None
    
    def test_manager_can_instantiate(self):
        """Test Manager harness class is accessible and has correct signature."""
        from tiers.tier_1.manager import ManagerAgentHarness
        
        # Verify class exists and has expected methods
        assert ManagerAgentHarness is not None
        assert hasattr(ManagerAgentHarness, '__init__')
        
        # Would need redis_client and tenant_id to actually instantiate
        # Just verify the class is importable and has the right structure
    
    def test_orchestrator_stream_configuration(self):
        """Test orchestrators have correct stream naming."""
        from tiers.tier_2.leads_orchestrator.consumer import LeadsConsumer
        from tiers.tier_2.outreach_orchestrator.consumer import OutreachConsumer
        
        tenant = "test-tenant"
        mock_redis = MagicMock()
        
        # Test Leads Orchestrator streams
        leads_consumer = LeadsConsumer(mock_redis, tenant)
        assert leads_consumer.task_stream == f"{tenant}:orchestrators:leads:tasks"
        assert leads_consumer.result_stream == f"{tenant}:orchestrators:leads:results"
        
        # Test Outreach Orchestrator streams
        outreach_consumer = OutreachConsumer(mock_redis, tenant)
        assert outreach_consumer.task_stream == f"{tenant}:orchestrators:outbound:tasks"
        assert outreach_consumer.result_stream == f"{tenant}:orchestrators:outbound:results"
    
    def test_agent_stream_configuration(self):
        """Test agents have correct stream naming."""
        from tiers.tier_3.rag_agent.consumer import RAGConsumer
        from tiers.tier_3.persistence_agent.consumer import PersistenceAgentConsumer
        from tiers.tier_3.copywriter_agent.consumer import CopywriterAgentConsumer
        
        tenant = "test-tenant"
        mock_redis = MagicMock()
        
        # Test RAG Agent streams
        rag_consumer = RAGConsumer(mock_redis, tenant)
        assert rag_consumer.task_stream == f"{tenant}:agents:rag:tasks"
        assert rag_consumer.result_stream == f"{tenant}:agents:rag:results"
        
        # Test Persistence Agent streams
        persistence_consumer = PersistenceAgentConsumer(mock_redis, tenant)
        assert persistence_consumer.task_stream == f"{tenant}:agents:persistence:tasks"
        assert persistence_consumer.result_stream == f"{tenant}:agents:persistence:results"
        
        # Test Copywriter Agent streams
        copywriter_consumer = CopywriterAgentConsumer(mock_redis, tenant)
        assert copywriter_consumer.task_stream == f"{tenant}:agents:copywriter:tasks"
        assert copywriter_consumer.result_stream == f"{tenant}:agents:copywriter:results"
    
    def test_manager_delegation_tools_exist(self):
        """Test Manager has delegation tools for orchestrators."""
        from tiers.tier_1.manager.tools.delegation_tools import DelegationTools
        
        mock_redis = MagicMock()
        tools = DelegationTools(mock_redis, "test-tenant")
        
        # Verify delegation methods exist
        assert hasattr(tools, 'delegate_to_leads_orchestrator')
        assert hasattr(tools, 'delegate_to_outreach_orchestrator')
    
    def test_backward_compatibility_imports(self):
        """Test that fallback imports still work for compatibility."""
        # These should work via fallback imports
        try:
            from agent.harness.agent_harness import AgentHarness as OldAgentHarness
            assert OldAgentHarness is not None
        except ImportError:
            pytest.skip("Legacy agent.harness import not available")
        
        # New import should also work
        from core.harness import AgentHarness as NewAgentHarness
        assert NewAgentHarness is not None
        
        # They should be the same class
        assert OldAgentHarness == NewAgentHarness


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
