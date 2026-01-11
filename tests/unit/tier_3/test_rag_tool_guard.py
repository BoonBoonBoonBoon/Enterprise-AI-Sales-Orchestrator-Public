import unittest
from unittest.mock import MagicMock, patch
import json
from agent.operational_agents.rag_agent.rag_agent import RAGAgent


class TestRagToolGuard(unittest.TestCase):
    def test_rag_tool_returns_records_without_calling_coordinator(self):
        agent = RAGAgent()
        # replace coordinator.tool with a mock that would raise if called
        agent.coordinator.tool = MagicMock(side_effect=AssertionError("coordinator should not be called"))

        sample_records = [{"id": "r1", "email": "a@b.com"}]
        envelope = {
            "metadata": {"source": "test", "retrieved_at": "now", "total_count": 1},
            "records": sample_records,
        }

        # Call rag_tool with an envelope (as dict)
        out = agent.rag_tool(envelope)
        self.assertEqual(out.get('records'), sample_records)

        # Call rag_tool with JSON string
        out2 = agent.rag_tool(json.dumps(envelope))
        self.assertEqual(out2.get('records'), sample_records)


if __name__ == '__main__':
    unittest.main()
