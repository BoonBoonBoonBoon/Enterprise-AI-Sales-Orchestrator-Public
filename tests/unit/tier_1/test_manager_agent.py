"""
Unit Tests for Manager Agent

Tests the Manager Agent's core functionality:
- Shortcut detection and execution
- Goal analysis and delegation
- Tool routing
- Error handling
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from agent.manager.manager_agent import ManagerAgent
from agent.manager.shortcut_registry import ShortcutRegistry
from agent.manager.tools.delegation_tools import DelegationTools


class TestShortcutRegistry:
    """Test shortcut registry functionality."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis_mock = Mock()
        redis_mock.ping.return_value = True
        redis_mock.hgetall.return_value = {}
        redis_mock.keys.return_value = []
        return redis_mock
    
    @pytest.fixture
    def registry(self, mock_redis):
        """Create shortcut registry."""
        return ShortcutRegistry(mock_redis)
    
    def test_arithmetic_detection(self, registry):
        """Test detection of arithmetic expressions."""
        assert registry.can_shortcut("What is 2 + 2?")
        assert registry.can_shortcut("Calculate 10 * 5")
        assert registry.can_shortcut("100 / 4")
        assert not registry.can_shortcut("What is the weather?")
    
    def test_simple_calculation(self, registry):
        """Test simple arithmetic calculation."""
        result = registry.execute_shortcut("What is 2 + 2?")
        
        assert result["success"] is True
        assert result["result"] == 4
        assert result["shortcut_type"] == "calculation"
    
    def test_complex_calculation(self, registry):
        """Test complex arithmetic with parentheses."""
        result = registry.execute_shortcut("(10 + 5) * 2")
        
        assert result["success"] is True
        assert result["result"] == 30
    
    def test_datetime_shortcuts(self, registry):
        """Test date/time shortcuts."""
        result = registry.execute_shortcut("What is the current time?")
        
        assert result["success"] is True
        assert "result" in result
        # Should be ISO format timestamp
        datetime.fromisoformat(result["result"])
    
    def test_health_check_shortcut(self, registry):
        """Test health check shortcut."""
        result = registry.execute_shortcut("Run health check")
        
        assert result["success"] is True
        assert "redis" in result["result"]
        assert "timestamp" in result["result"]
    
    def test_invalid_expression(self, registry):
        """Test handling of invalid expression."""
        result = registry.execute_shortcut("Calculate invalid expression!")
        
        assert result["success"] is False
        assert "error" in result


class TestDelegationTools:
    """Test delegation tools functionality."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis_mock = Mock()
        redis_mock.xadd.return_value = b"1234567890-0"
        redis_mock.get.return_value = None
        return redis_mock
    
    @pytest.fixture
    def delegation(self, mock_redis):
        """Create delegation tools."""
        return DelegationTools(mock_redis, tenant_id="test")
    
    def test_delegate_coding_task(self, delegation, mock_redis):
        """Test coding task delegation."""
        result = delegation.delegate_to_coding_orchestrator(
            task="Generate Python script for data processing",
            requirements={"language": "python", "framework": "pandas"}
        )
        
        assert result["success"] is True
        assert "task_id" in result
        assert result["orchestrator"] == "coding"
        
        # Verify Redis xadd called
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        assert "test:coding:tasks" in call_args[0]
    
    def test_delegate_data_query(self, delegation, mock_redis):
        """Test data query delegation."""
        result = delegation.delegate_to_data_orchestrator(
            query="Find leads in tech industry",
            dataset="leads",
            filters={"industry": "tech"}
        )
        
        assert result["success"] is True
        assert result["orchestrator"] == "data"
        
        # Verify stream name
        call_args = mock_redis.xadd.call_args
        assert "test:data:tasks" in call_args[0]
    
    def test_delegate_api_request(self, delegation, mock_redis):
        """Test API request delegation."""
        result = delegation.delegate_to_api_orchestrator(
            endpoint="hubspot/contacts",
            operation="SYNC",
            parameters={"limit": 100}
        )
        
        assert result["success"] is True
        assert result["orchestrator"] == "api"
    
    def test_delegate_email_generation(self, delegation, mock_redis):
        """Test email generation delegation."""
        result = delegation.delegate_to_copywriter_orchestrator(
            lead_id="lead_123",
            campaign_id="campaign_456",
            context={"industry": "tech"}
        )
        
        assert result["success"] is True
        assert result["orchestrator"] == "copywriter"
    
    def test_check_task_status_not_found(self, delegation, mock_redis):
        """Test checking status of non-existent task."""
        mock_redis.get.return_value = None
        
        result = delegation.check_task_status("nonexistent_task")
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()
    
    def test_check_task_status_completed(self, delegation, mock_redis):
        """Test checking status of completed task."""
        mock_redis.get.side_effect = [
            b"completed",
            json.dumps({"output": "Task result"}).encode()
        ]
        
        result = delegation.check_task_status("task_123")
        
        assert result["success"] is True
        assert result["status"] == "completed"
        assert "result" in result


class TestManagerAgent:
    """Test Manager Agent core functionality."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis_mock = Mock()
        redis_mock.ping.return_value = True
        redis_mock.xadd.return_value = b"1234567890-0"
        redis_mock.hgetall.return_value = {}
        redis_mock.keys.return_value = []
        return redis_mock
    
    @pytest.fixture
    @patch('agent.manager.manager_agent.AgentExecutor')
    @patch('agent.manager.manager_agent.ChatOpenAI')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def manager(self, mock_llm, mock_executor, mock_redis):
        """Create Manager Agent with mocked dependencies."""
        # Mock LLM
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = "Mock response"
        mock_llm.return_value = mock_llm_instance
        
        # Mock agent executor
        mock_executor_instance = MagicMock()
        mock_executor_instance.invoke.return_value = {
            "output": "Task delegated",
            "intermediate_steps": []
        }
        mock_executor.return_value = mock_executor_instance
        
        manager = ManagerAgent(mock_redis, tenant_id="test")
        manager.executor = mock_executor_instance
        
        return manager
    
    def test_manager_initialization(self, manager):
        """Test Manager Agent initialization."""
        assert manager.tenant_id == "test"
        assert manager.shortcuts is not None
        assert manager.delegation is not None
        assert manager.tools is not None
    
    def test_shortcut_execution(self, manager):
        """Test Manager executing shortcut path."""
        result = manager.execute("What is 2 + 2?")
        
        assert result["success"] is True
        assert result["path"] == "shortcut"
        assert result["result"] == 4
        assert result["latency_ms"] < 100  # Should be fast
    
    def test_agent_delegation_path(self, manager):
        """Test Manager executing agent delegation path."""
        result = manager.execute("Find leads in tech industry")
        
        assert result["success"] is True
        assert result["path"] == "agent_delegation"
        assert "result" in result
    
    @patch('agent.manager.manager_agent.AgentExecutor')
    def test_error_handling(self, mock_executor_cls, manager, mock_redis):
        """Test Manager error handling."""
        # Make executor raise exception
        mock_executor = MagicMock()
        mock_executor.invoke.side_effect = Exception("Test error")
        manager.executor = mock_executor
        
        result = manager.execute("Test goal")
        
        assert result["success"] is False
        assert "error" in result
        assert "Test error" in result["error"]
    
    def test_health_check(self, manager):
        """Test Manager health check."""
        health = manager.health_check()
        
        assert "status" in health
        assert "components" in health
        assert "redis" in health["components"]
        assert "llm" in health["components"]
        assert "shortcuts" in health["components"]
    
    def test_get_task_result(self, manager, mock_redis):
        """Test getting task result."""
        mock_redis.get.side_effect = [
            b"completed",
            json.dumps({"output": "Task result"}).encode()
        ]
        
        result = manager.get_task_result("task_123")
        
        assert result["success"] is True
        assert result["status"] == "completed"


class TestManagerIntegration:
    """Integration tests with real Redis (optional - requires Redis running)."""
    
    @pytest.mark.integration
    @pytest.mark.skipif(True, reason="Requires Redis and OpenAI API key")
    def test_full_workflow(self):
        """
        Test full Manager workflow with real Redis.
        
        To run:
        1. Start Redis: docker compose up -d redis
        2. Set OPENAI_API_KEY environment variable
        3. Run: pytest -m integration tests/test_manager_agent.py
        """
        import redis
        
        redis_client = redis.Redis(host='localhost', port=6379)
        manager = ManagerAgent(redis_client, tenant_id="integration_test")
        
        # Test shortcut
        result = manager.execute("What is 5 + 5?")
        assert result["success"] is True
        assert result["result"] == 10
        
        # Test delegation (will create task in Redis)
        result = manager.execute("Find leads created today")
        assert result["success"] is True
        
        # Cleanup
        redis_client.delete("integration_test:coding:tasks")
        redis_client.delete("integration_test:data:tasks")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
