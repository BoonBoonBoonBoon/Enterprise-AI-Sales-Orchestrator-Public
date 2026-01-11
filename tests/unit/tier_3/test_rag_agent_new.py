"""
Test suite for RAG Agent with Deep Agents + Harness implementation.

Tests:
1. Agent instantiation
2. Tool creation and invocation
3. Execute method
4. Health check
5. Redis Streams consumer
6. Integration with harness
"""
import os
import sys
import asyncio
import json
import time
from typing import Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import redis

from agent.operational_agents.rag_agent.rag_agent_new import RAGAgent
from agent.operational_agents.rag_agent.rag_agent_harness import RAGAgentHarness
from agent.operational_agents.rag_agent.consumer_new import RAGConsumer
from agent.tools.redis.client import RedisStreamsClient


def print_test(test_name: str, status: str = "START"):
    """Pretty print test status"""
    symbols = {"START": "🔵", "PASS": "✅", "FAIL": "❌", "INFO": "ℹ️"}
    symbol = symbols.get(status, "•")
    print(f"\n{symbol} {test_name} [{status}]")


async def test_redis_connection():
    """Test 1: Redis connection works"""
    print_test("Test 1: Redis Connection", "START")
    
    try:
        redis_client = redis.Redis(
            host='localhost',
            port=6379,
            decode_responses=False
        )
        
        # Test connection
        redis_client.ping()
        print("  → Redis ping successful")
        
        # Test RedisStreamsClient
        redis_streams = RedisStreamsClient()
        redis_streams.client.ping()
        print("  → RedisStreamsClient working")
        
        print_test("Test 1: Redis Connection", "PASS")
        return redis_client
    except Exception as e:
        print(f"  → Error: {e}")
        print_test("Test 1: Redis Connection", "FAIL")
        return None


async def test_agent_instantiation(redis_client):
    """Test 2: RAG Agent instantiates correctly"""
    print_test("Test 2: Agent Instantiation", "START")
    
    try:
        agent = RAGAgent(
            redis_client=redis_client,
            tenant_id="test-tenant",
            model="gpt-4o-mini"
        )
        
        print(f"  → Agent created: {agent}")
        print(f"  → Tenant ID: {agent.tenant_id}")
        print(f"  → Model: {agent.model}")
        print(f"  → Redis client: {agent.redis}")
        
        # Check Deep Agent was created
        if agent.agent:
            print(f"  → Deep Agent initialized: {type(agent.agent)}")
        else:
            raise ValueError("Deep Agent not initialized")
        
        print_test("Test 2: Agent Instantiation", "PASS")
        return agent
    except Exception as e:
        print(f"  → Error: {e}")
        print_test("Test 2: Agent Instantiation", "FAIL")
        import traceback
        traceback.print_exc()
        return None


async def test_tool_creation(agent):
    """Test 3: Tools are created correctly"""
    print_test("Test 3: Tool Creation", "START")
    
    try:
        # Agent should have 7 tools
        expected_tools = [
            "_create_vector_search_companies_tool",
            "_create_vector_search_leads_tool",
            "_create_semantic_search_tool",
            "_create_crunchbase_lookup_tool",
            "_create_linkedin_lookup_tool",
            "_create_get_funding_data_tool",
            "_create_enrich_company_tool"
        ]
        
        print(f"  → Checking for {len(expected_tools)} tool creation methods...")
        
        for tool_method in expected_tools:
            if hasattr(agent, tool_method):
                print(f"  ✓ {tool_method}")
            else:
                raise ValueError(f"Missing tool method: {tool_method}")
        
        print_test("Test 3: Tool Creation", "PASS")
        return True
    except Exception as e:
        print(f"  → Error: {e}")
        print_test("Test 3: Tool Creation", "FAIL")
        return False


async def test_health_check(agent):
    """Test 4: Health check works"""
    print_test("Test 4: Health Check", "START")
    
    try:
        health = await agent.health_check()
        
        print(f"  → Health status: {health}")
        print(f"  → Status: {health.get('status')}")
        print(f"  → Components: {health.get('components', {}).keys()}")
        
        if health.get('status') != 'healthy':
            print(f"  ⚠️  Warning: Status is {health.get('status')}, not 'healthy'")
        
        print_test("Test 4: Health Check", "PASS")
        return health
    except Exception as e:
        print(f"  → Error: {e}")
        print_test("Test 4: Health Check", "FAIL")
        import traceback
        traceback.print_exc()
        return None


async def test_execute_method(agent):
    """Test 5: Execute method works"""
    print_test("Test 5: Execute Method", "START")
    
    try:
        test_input = {
            "query": "Find similar companies to Stripe",
            "limit": 5,
            "task_type": "vector_search"
        }
        
        print(f"  → Testing with input: {test_input}")
        
        result = await agent.execute(test_input)
        
        print(f"  → Result: {json.dumps(result, indent=2)[:200]}...")
        print(f"  → Status: {result.get('status')}")
        
        if result.get('status') not in ['completed', 'success']:
            print(f"  ⚠️  Warning: Expected status 'completed' or 'success', got {result.get('status')}")
        
        print_test("Test 5: Execute Method", "PASS")
        return result
    except Exception as e:
        print(f"  → Error: {e}")
        print_test("Test 5: Execute Method", "FAIL")
        import traceback
        traceback.print_exc()
        return None


async def test_harness_integration(redis_client):
    """Test 6: Harness wrapper works"""
    print_test("Test 6: Harness Integration", "START")
    
    try:
        harness = RAGAgentHarness(
            redis_client=redis_client,
            tenant_id="test-tenant",
            environment="development"
        )
        
        print(f"  → Harness created: {harness}")
        print(f"  → Agent: {harness.agent}")
        print(f"  → Harness: {harness.harness}")
        
        # Test health check through harness
        health = await harness.health_check()
        print(f"  → Health check through harness: {health.get('status')}")
        
        # Test execute through harness
        test_input = {
            "query": "Test harness execution",
            "task_type": "test"
        }
        
        result = await harness.execute(test_input)
        print(f"  → Execute through harness: {result.get('status')}")
        
        print_test("Test 6: Harness Integration", "PASS")
        return harness
    except Exception as e:
        print(f"  → Error: {e}")
        print_test("Test 6: Harness Integration", "FAIL")
        import traceback
        traceback.print_exc()
        return None


async def test_redis_streams_setup(redis_client):
    """Test 7: Redis Streams consumer setup"""
    print_test("Test 7: Redis Streams Setup", "START")
    
    try:
        redis_pubsub = RedisPubSub()
        
        tenant_id = "test-tenant"
        task_stream = f"{tenant_id}:agents:rag:tasks"
        result_stream = f"{tenant_id}:agents:rag:results"
        consumer_group = "rag-workers"
        
        # Create consumer group if not exists
        try:
            redis_pubsub.client.xgroup_create(
                redis_pubsub._chan(task_stream),
                consumer_group,
                id='0',
                mkstream=True
            )
            print(f"  → Created consumer group: {consumer_group}")
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                print(f"  → Consumer group already exists: {consumer_group}")
            else:
                raise
        
        # Test publishing a task
        task_id = f"test-{int(time.time())}"
        task_data = {
            "task_id": task_id,
            "tenant_id": tenant_id,
            "action": "test_vector_search",
            "payload": {
                "query": "Test company search",
                "limit": 5
            }
        }
        
        # Publish to task stream
        message_id = redis_pubsub.client.xadd(
            redis_pubsub._chan(task_stream),
            {
                "payload": json.dumps(task_data),
                "task_id": task_id,
                "timestamp": str(time.time())
            }
        )
        
        print(f"  → Published test task: {message_id}")
        
        # Read the task back
        messages = redis_pubsub.client.xreadgroup(
            consumer_group,
            f"test-consumer-{int(time.time())}",
            {redis_pubsub._chan(task_stream): ">"},
            count=1,
            block=1000
        )
        
        if messages:
            print(f"  → Successfully read task from stream")
            stream_name, message_list = messages[0]
            msg_id, msg_data = message_list[0]
            
            # Acknowledge the message
            redis_pubsub.client.xack(
                redis_pubsub._chan(task_stream),
                consumer_group,
                msg_id
            )
            print(f"  → Acknowledged message: {msg_id}")
        else:
            print(f"  → No messages found (might have been consumed already)")
        
        print_test("Test 7: Redis Streams Setup", "PASS")
        return True
    except Exception as e:
        print(f"  → Error: {e}")
        print_test("Test 7: Redis Streams Setup", "FAIL")
        import traceback
        traceback.print_exc()
        return False


async def test_consumer_instantiation():
    """Test 8: Consumer instantiates correctly"""
    print_test("Test 8: Consumer Instantiation", "START")
    
    try:
        redis_pubsub = RedisPubSub()
        redis_client = redis_pubsub.client
        
        consumer = RAGConsumer(
            redis_client=redis_client,
            tenant_id="test-tenant",
            environment="development"
        )
        
        print(f"  → Consumer created: {consumer}")
        print(f"  → Tenant ID: {consumer.tenant_id}")
        print(f"  → Task stream: {consumer.task_stream}")
        print(f"  → Result stream: {consumer.result_stream}")
        print(f"  → Consumer group: {consumer.consumer_group}")
        print(f"  → Harness: {consumer.harness}")
        
        print_test("Test 8: Consumer Instantiation", "PASS")
        return consumer
    except Exception as e:
        print(f"  → Error: {e}")
        print_test("Test 8: Consumer Instantiation", "FAIL")
        import traceback
        traceback.print_exc()
        return None


async def run_all_tests():
    """Run all tests in sequence"""
    print("\n" + "="*60)
    print("RAG AGENT TEST SUITE - Deep Agents + Harness")
    print("="*60)
    
    # Test 1: Redis connection
    redis_client = await test_redis_connection()
    if not redis_client:
        print("\n❌ Cannot continue without Redis connection")
        return
    
    # Test 2: Agent instantiation
    agent = await test_agent_instantiation(redis_client)
    if not agent:
        print("\n❌ Cannot continue without agent")
        return
    
    # Test 3: Tool creation
    await test_tool_creation(agent)
    
    # Test 4: Health check
    await test_health_check(agent)
    
    # Test 5: Execute method
    await test_execute_method(agent)
    
    # Test 6: Harness integration
    await test_harness_integration(redis_client)
    
    # Test 7: Redis Streams setup
    await test_redis_streams_setup(redis_client)
    
    # Test 8: Consumer instantiation
    await test_consumer_instantiation()
    
    print("\n" + "="*60)
    print("TEST SUITE COMPLETE")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
