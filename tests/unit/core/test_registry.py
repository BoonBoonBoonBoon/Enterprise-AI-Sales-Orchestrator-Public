import unittest

from agent.tools.registry import discover_local_tools
from agent.operational_agents.registry import discover_local_agents


class RegistryDiscoveryTests(unittest.TestCase):
    def test_tools_discovery(self):
        tools = discover_local_tools()
        # Expect supabase_tools to be discoverable
        self.assertIn('supabase_tools', tools)

    def test_agents_discovery(self):
        agents = discover_local_agents()
        # Expect rag_agent to be discoverable
        self.assertIn('rag_agent', agents)


if __name__ == '__main__':
    unittest.main()
