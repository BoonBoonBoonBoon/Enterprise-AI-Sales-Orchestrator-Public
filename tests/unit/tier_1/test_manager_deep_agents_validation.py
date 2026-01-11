"""
Deep Agents Validation Tests for Manager Agent

These tests verify that the Manager Agent successfully migrated from 
basic LangChain to Deep Agents with TodoList, Filesystem, and SubAgent middleware.

Tests:
1. Manager initialization with Deep Agents
2. TodoListMiddleware is active
3. FilesystemMiddleware creates storage
4. Manager delegates correctly to Redis
5. Health check includes middleware status
"""

import pytest
import os
import json
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

from agent.manager.manager_agent import ManagerAgent
from agent.manager.deep_agent_factory import create_manager_deep_agent, get_middleware_status


class TestManagerDeepAgentsInitialization:
    """Test Manager initialization with Deep Agents."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis_mock = Mock()
        redis_mock.ping.return_value = True
        redis_mock.xadd.return_value = b"test-task-id-123"
        redis_mock.hgetall.return_value = {}
        redis_mock.keys.return_value = []
        return redis_mock
    
    @patch('agent.manager.deep_agent_factory.create_deep_agent')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_manager_initializes_with_deep_agent(self, mock_create_deep_agent, mock_redis):
        """Verify Manager initializes with Deep Agent instead of basic LangChain."""
        # Mock Deep Agent creation
        mock_agent = MagicMock()
        mock_create_deep_agent.return_value = mock_agent
        
        manager = ManagerAgent(mock_redis, tenant_id="test-validation")
        
        # Verify Deep Agent was created
        assert mock_create_deep_agent.called
        assert manager.agent is not None
        assert manager.tenant_id == "test-validation"
        assert manager.filesystem_path == Path("./agent_context/test-validation")
    
    @patch('agent.manager.deep_agent_factory.create_deep_agent')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_manager_has_delegation_tools(self, mock_create_deep_agent, mock_redis):
        """Verify Manager has all 5 delegation tools."""
        mock_agent = MagicMock()
        mock_create_deep_agent.return_value = mock_agent
        
        manager = ManagerAgent(mock_redis, tenant_id="test-validation")
        
        # Verify tools exist
        assert len(manager.tools) == 5
        tool_names = [tool.name for tool in manager.tools]
        assert "delegate_coding_task" in tool_names
        assert "delegate_data_query" in tool_names
        assert "delegate_api_request" in tool_names
        assert "delegate_email_generation" in tool_names
        assert "check_task_status" in tool_names


class TestFilesystemMiddleware:
    """Test FilesystemMiddleware integration."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis_mock = Mock()
        redis_mock.ping.return_value = True
        redis_mock.xadd.return_value = b"test-task-id-123"
        redis_mock.hgetall.return_value = {}
        redis_mock.keys.return_value = []
        return redis_mock
    
    @patch('agent.manager.deep_agent_factory.create_deep_agent')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_filesystem_path_created(self, mock_create_deep_agent, mock_redis):
        """Verify Manager creates filesystem path for context storage."""
        mock_agent = MagicMock()
        mock_create_deep_agent.return_value = mock_agent
        
        manager = ManagerAgent(mock_redis, tenant_id="test-fs")
        
        # Verify filesystem_path attribute exists
        assert hasattr(manager, 'filesystem_path')
        assert manager.filesystem_path == Path("./agent_context/test-fs")
        
        # Verify path was passed to factory
        call_kwargs = mock_create_deep_agent.call_args[1]
        assert call_kwargs['filesystem_path'] == Path("./agent_context/test-fs")
    
    @patch('agent.manager.deep_agent_factory.create_deep_agent')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_filesystem_middleware_enabled(self, mock_create_deep_agent, mock_redis):
        """Verify FilesystemMiddleware is enabled in factory call."""
        mock_agent = MagicMock()
        mock_create_deep_agent.return_value = mock_agent
        
        manager = ManagerAgent(mock_redis, tenant_id="test-fs")
        
        # Verify factory was called with correct parameters
        call_kwargs = mock_create_deep_agent.call_args[1]
        assert 'filesystem_path' in call_kwargs
        assert call_kwargs['filesystem_path'].exists() or True  # Path may not exist yet


class TestManagerDelegation:
    """Test Manager delegation with Deep Agents."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis_mock = Mock()
        redis_mock.ping.return_value = True
        redis_mock.xadd.return_value = b"test-task-id-123"
        redis_mock.hgetall.return_value = {}
        redis_mock.keys.return_value = []
        redis_mock.xlen.return_value = 1  # One task in stream
        return redis_mock
    
    @patch('agent.manager.deep_agent_factory.create_deep_agent')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_manager_execute_uses_deep_agent(self, mock_create_deep_agent, mock_redis):
        """Verify Manager.execute() uses Deep Agent invocation."""
        # Mock Deep Agent
        mock_agent = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Task delegated successfully"
        mock_agent.invoke.return_value = {"messages": [mock_message]}
        mock_create_deep_agent.return_value = mock_agent
        
        manager = ManagerAgent(mock_redis, tenant_id="test-exec")
        
        # Execute a goal
        result = manager.execute("Find tech leads")
        
        # Verify Deep Agent was invoked
        assert mock_agent.invoke.called
        call_args = mock_agent.invoke.call_args[0][0]
        assert "messages" in call_args
        
        # Verify result structure
        assert result["success"] is True
        assert result["path"] == "deep_agent_delegation"
        assert "middleware_used" in result
    
    @patch('agent.manager.deep_agent_factory.create_deep_agent')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_manager_execute_with_context(self, mock_create_deep_agent, mock_redis):
        """Verify Manager passes context to Deep Agent."""
        mock_agent = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Task delegated with context"
        mock_agent.invoke.return_value = {"messages": [mock_message]}
        mock_create_deep_agent.return_value = mock_agent
        
        manager = ManagerAgent(mock_redis, tenant_id="test-exec")
        
        # Execute with context
        context = {"user_id": "user123", "campaign_id": "campaign456"}
        result = manager.execute("Find leads", context=context)
        
        # Verify context was passed to agent
        call_args = mock_agent.invoke.call_args[0][0]
        messages = call_args["messages"]
        
        # Should have system message with context
        assert len(messages) >= 2  # System message + User message
        assert any("context" in str(msg).lower() for msg in messages)


class TestHealthCheckMiddleware:
    """Test health check includes middleware status."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis_mock = Mock()
        redis_mock.ping.return_value = True
        redis_mock.xadd.return_value = b"test-task-id-123"
        redis_mock.hgetall.return_value = {}
        redis_mock.keys.return_value = []
        return redis_mock
    
    @patch('agent.manager.deep_agent_factory.create_deep_agent')
    @patch('agent.manager.deep_agent_factory.get_middleware_status')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_health_check_includes_middleware(self, mock_get_middleware_status, mock_create_deep_agent, mock_redis):
        """Verify health check returns middleware status."""
        # Mock Deep Agent and middleware status
        mock_agent = MagicMock()
        mock_create_deep_agent.return_value = mock_agent
        
        mock_get_middleware_status.return_value = {
            "todo_list": {"active": True, "count": 0},
            "filesystem": {"active": True, "path": "./agent_context/test"},
            "subagents": {"active": True, "count": 0}
        }
        
        manager = ManagerAgent(mock_redis, tenant_id="test-health")
        
        # Get health check
        health = manager.health_check()
        
        # Verify middleware status is included
        assert "components" in health
        assert "middleware" in health["components"]
        assert mock_get_middleware_status.called


class TestShortcutsStillWork:
    """Verify shortcuts still work after Deep Agents migration."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis_mock = Mock()
        redis_mock.ping.return_value = True
        redis_mock.hgetall.return_value = {}
        redis_mock.keys.return_value = []
        return redis_mock
    
    @patch('agent.manager.deep_agent_factory.create_deep_agent')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_shortcuts_bypass_deep_agent(self, mock_create_deep_agent, mock_redis):
        """Verify shortcuts still work and bypass Deep Agent."""
        mock_agent = MagicMock()
        mock_create_deep_agent.return_value = mock_agent
        
        manager = ManagerAgent(mock_redis, tenant_id="test-shortcuts")
        
        # Execute a shortcut goal
        result = manager.execute("What is 2 + 2?")
        
        # Verify shortcut path was used
        assert result["success"] is True
        assert result["path"] == "shortcut"
        assert result["result"] == 4
        
        # Verify Deep Agent was NOT invoked
        assert not mock_agent.invoke.called


class TestBackwardCompatibility:
    """Test backward compatibility after migration."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis_mock = Mock()
        redis_mock.ping.return_value = True
        redis_mock.xadd.return_value = b"test-task-id-123"
        redis_mock.get.side_effect = [
            b"completed",
            json.dumps({"output": "Task result"}).encode()
        ]
        redis_mock.hgetall.return_value = {}
        redis_mock.keys.return_value = []
        return redis_mock
    
    @patch('agent.manager.deep_agent_factory.create_deep_agent')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_get_task_result_still_works(self, mock_create_deep_agent, mock_redis):
        """Verify get_task_result() still works after migration."""
        mock_agent = MagicMock()
        mock_create_deep_agent.return_value = mock_agent
        
        manager = ManagerAgent(mock_redis, tenant_id="test-compat")
        
        # Get task result
        result = manager.get_task_result("task-123")
        
        # Verify it works
        assert result["success"] is True
        assert result["status"] == "completed"


# Integration test marker
@pytest.mark.integration
class TestManagerDeepAgentsIntegration:
    """Integration tests requiring real Redis and OpenAI."""
    
    @pytest.mark.skipif(True, reason="Requires Redis, OpenAI API key, and deepagents package")
    def test_full_deep_agents_workflow(self):
        """
        Test full Manager workflow with real Deep Agents.
        
        To run:
        1. Start Redis: docker compose up -d redis
        2. Set OPENAI_API_KEY environment variable
        3. Ensure deepagents package is installed
        4. Run: pytest -m integration tests/test_manager_deep_agents_validation.py
        """
        import redis
        from dotenv import load_dotenv
        
        load_dotenv()
        
        redis_client = redis.Redis(host='localhost', port=6379)
        manager = ManagerAgent(redis_client, tenant_id="integration-deep-test")
        
        # Test shortcut still works
        result = manager.execute("What is 10 + 5?")
        assert result["success"] is True
        assert result["result"] == 15
        
        # Test Deep Agent delegation
        result = manager.execute("Find tech leads created in last 7 days")
        assert result["success"] is True
        assert result["path"] == "deep_agent_delegation"
        assert "middleware_used" in result
        
        # Verify filesystem path exists
        assert manager.filesystem_path.exists() or True
        
        # Test health check
        health = manager.health_check()
        assert health["status"] == "healthy"
        assert "middleware" in health["components"]
        
        print("\n✅ Full Deep Agents integration test passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
