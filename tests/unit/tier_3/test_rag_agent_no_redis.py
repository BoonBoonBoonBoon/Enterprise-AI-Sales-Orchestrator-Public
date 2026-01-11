"""
Test RAG Agent structure without requiring Redis.

Tests:
1. Import structure
2. Class definitions
3. Method signatures
4. Tool creation patterns
"""
import os
import sys
import inspect

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def print_test(test_name: str, status: str = "START"):
    """Pretty print test status"""
    symbols = {"START": "🔵", "PASS": "✅", "FAIL": "❌", "INFO": "ℹ️"}
    symbol = symbols.get(status, "•")
    print(f"\n{symbol} {test_name} [{status}]")


def test_imports():
    """Test 1: All imports work"""
    print_test("Test 1: Module Imports", "START")
    
    try:
        # Test new RAG Agent imports
        from agent.operational_agents.rag_agent import rag_agent_new
        from agent.operational_agents.rag_agent import rag_agent_harness
        from agent.operational_agents.rag_agent import consumer_new
        
        print("  → rag_agent_new: ✓")
        print("  → rag_agent_harness: ✓")
        print("  → consumer_new: ✓")
        
        # Check for expected classes
        assert hasattr(rag_agent_new, 'RAGAgent'), "RAGAgent class not found"
        assert hasattr(rag_agent_harness, 'RAGAgentHarness'), "RAGAgentHarness class not found"
        assert hasattr(consumer_new, 'RAGConsumer'), "RAGConsumer class not found"
        
        print("  → RAGAgent class: ✓")
        print("  → RAGAgentHarness class: ✓")
        print("  → RAGConsumer class: ✓")
        
        print_test("Test 1: Module Imports", "PASS")
        return True
    except Exception as e:
        print(f"  → Error: {e}")
        print_test("Test 1: Module Imports", "FAIL")
        import traceback
        traceback.print_exc()
        return False


def test_rag_agent_structure():
    """Test 2: RAG Agent has correct structure"""
    print_test("Test 2: RAGAgent Structure", "START")
    
    try:
        from agent.operational_agents.rag_agent.rag_agent_new import RAGAgent
        
        # Check __init__ signature
        init_sig = inspect.signature(RAGAgent.__init__)
        expected_params = ['self', 'redis_client', 'tenant_id', 'model']
        actual_params = list(init_sig.parameters.keys())
        
        print(f"  → __init__ parameters: {actual_params}")
        for param in expected_params:
            if param in actual_params:
                print(f"    ✓ {param}")
            else:
                raise ValueError(f"Missing parameter: {param}")
        
        # Check for tool creation methods
        tool_methods = [
            '_create_vector_search_companies_tool',
            '_create_vector_search_leads_tool',
            '_create_semantic_search_tool',
            '_create_crunchbase_lookup_tool',
            '_create_linkedin_lookup_tool',
            '_create_get_funding_data_tool',
            '_create_enrich_company_tool'
        ]
        
        print(f"\n  → Checking {len(tool_methods)} tool methods:")
        for method_name in tool_methods:
            if hasattr(RAGAgent, method_name):
                print(f"    ✓ {method_name}")
            else:
                raise ValueError(f"Missing tool method: {method_name}")
        
        # Check for execute and health_check methods
        print(f"\n  → Checking core methods:")
        assert hasattr(RAGAgent, 'execute'), "Missing execute method"
        print(f"    ✓ execute")
        
        assert hasattr(RAGAgent, 'health_check'), "Missing health_check method"
        print(f"    ✓ health_check")
        
        print_test("Test 2: RAGAgent Structure", "PASS")
        return True
    except Exception as e:
        print(f"  → Error: {e}")
        print_test("Test 2: RAGAgent Structure", "FAIL")
        import traceback
        traceback.print_exc()
        return False


def test_harness_structure():
    """Test 3: RAGAgentHarness has correct structure"""
    print_test("Test 3: RAGAgentHarness Structure", "START")
    
    try:
        from agent.operational_agents.rag_agent.rag_agent_harness import RAGAgentHarness
        
        # Check __init__ signature
        init_sig = inspect.signature(RAGAgentHarness.__init__)
        expected_params = ['self', 'redis_client', 'tenant_id', 'environment']
        actual_params = list(init_sig.parameters.keys())
        
        print(f"  → __init__ parameters: {actual_params}")
        for param in expected_params:
            if param in actual_params:
                print(f"    ✓ {param}")
            else:
                raise ValueError(f"Missing parameter: {param}")
        
        # Check for execute and health_check methods
        print(f"\n  → Checking core methods:")
        assert hasattr(RAGAgentHarness, 'execute'), "Missing execute method"
        print(f"    ✓ execute")
        
        assert hasattr(RAGAgentHarness, 'health_check'), "Missing health_check method"
        print(f"    ✓ health_check")
        
        print_test("Test 3: RAGAgentHarness Structure", "PASS")
        return True
    except Exception as e:
        print(f"  → Error: {e}")
        print_test("Test 3: RAGAgentHarness Structure", "FAIL")
        import traceback
        traceback.print_exc()
        return False


def test_consumer_structure():
    """Test 4: RAGConsumer has correct structure"""
    print_test("Test 4: RAGConsumer Structure", "START")
    
    try:
        from agent.operational_agents.rag_agent.consumer_new import RAGConsumer
        
        # Check __init__ signature
        init_sig = inspect.signature(RAGConsumer.__init__)
        expected_params = ['self', 'redis_client', 'tenant_id', 'environment']
        actual_params = list(init_sig.parameters.keys())
        
        print(f"  → __init__ parameters: {actual_params}")
        for param in expected_params:
            if param in actual_params:
                print(f"    ✓ {param}")
            else:
                raise ValueError(f"Missing parameter: {param}")
        
        # Check for key methods
        print(f"\n  → Checking core methods:")
        assert hasattr(RAGConsumer, 'process_task'), "Missing process_task method"
        print(f"    ✓ process_task")
        
        assert hasattr(RAGConsumer, 'run'), "Missing run method"
        print(f"    ✓ run")
        
        assert hasattr(RAGConsumer, '_ensure_consumer_group'), "Missing _ensure_consumer_group method"
        print(f"    ✓ _ensure_consumer_group")
        
        print_test("Test 4: RAGConsumer Structure", "PASS")
        return True
    except Exception as e:
        print(f"  → Error: {e}")
        print_test("Test 4: RAGConsumer Structure", "FAIL")
        import traceback
        traceback.print_exc()
        return False


def test_deep_agents_integration():
    """Test 5: Deep Agents import works"""
    print_test("Test 5: Deep Agents Integration", "START")
    
    try:
        from deepagents import create_deep_agent
        print("  → create_deep_agent imported: ✓")
        
        # Check it's callable
        assert callable(create_deep_agent), "create_deep_agent is not callable"
        print("  → create_deep_agent is callable: ✓")
        
        print_test("Test 5: Deep Agents Integration", "PASS")
        return True
    except Exception as e:
        print(f"  → Error: {e}")
        print_test("Test 5: Deep Agents Integration", "FAIL")
        import traceback
        traceback.print_exc()
        return False


def test_agent_harness_integration():
    """Test 6: Agent Harness import works"""
    print_test("Test 6: Agent Harness Integration", "START")
    
    try:
        from agent.harness import AgentHarness, HarnessConfig
        print("  → AgentHarness imported: ✓")
        print("  → HarnessConfig imported: ✓")
        
        # Check they're classes
        assert inspect.isclass(AgentHarness), "AgentHarness is not a class"
        assert inspect.isclass(HarnessConfig), "HarnessConfig is not a class"
        print("  → Classes validated: ✓")
        
        print_test("Test 6: Agent Harness Integration", "PASS")
        return True
    except Exception as e:
        print(f"  → Error: {e}")
        print_test("Test 6: Agent Harness Integration", "FAIL")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all structural tests"""
    print("\n" + "="*60)
    print("RAG AGENT STRUCTURE TEST - No Redis Required")
    print("="*60)
    
    results = []
    
    # Test 1: Imports
    results.append(("Imports", test_imports()))
    
    # Test 2: RAGAgent structure
    results.append(("RAGAgent Structure", test_rag_agent_structure()))
    
    # Test 3: RAGAgentHarness structure
    results.append(("RAGAgentHarness Structure", test_harness_structure()))
    
    # Test 4: RAGConsumer structure
    results.append(("RAGConsumer Structure", test_consumer_structure()))
    
    # Test 5: Deep Agents integration
    results.append(("Deep Agents Integration", test_deep_agents_integration()))
    
    # Test 6: Agent Harness integration
    results.append(("Agent Harness Integration", test_agent_harness_integration()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {test_name}")
    
    print(f"\n  {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! RAG Agent structure is correct.")
        print("\n📝 Next steps:")
        print("  1. Start Docker Desktop and Redis: docker-compose --profile local up -d redis")
        print("  2. Run full tests: python tests/test_rag_agent_new.py")
        print("  3. Test Redis Streams integration")
        print("  4. Implement actual tool logic (vector search, APIs)")
    else:
        print("\n❌ Some tests failed. Fix errors above.")
    
    print("="*60)


if __name__ == "__main__":
    run_all_tests()
