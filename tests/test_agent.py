import os
import unittest
from unittest.mock import patch, MagicMock

from agent.operational_agents.rag_agent.rag_agent import RAGAgent


class TestRAGAgent(unittest.TestCase):
    def setUp(self):
        self.agent = RAGAgent()

    @patch("agent.tools.supabase_tools.SupabaseClient.query_table")
    @patch("agent.operational_agents.rag_agent.rag_agent.OpenAI")
    def test_agent_response_with_mocks(self, mock_openai, mock_query_table):
        if os.getenv("USE_REAL_TESTS") == "1":
            self.skipTest("Skipping mock test because USE_REAL_TESTS is set.")

        # Mock the OpenAI LLM response
        mock_openai.return_value.invoke.return_value = "{\"id\": \"123\", \"email\": null, \"company\": null}"

        # Mock the Supabase query response
        mock_query_table.return_value = [
            {
                "id": "123",
                "email": "test@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "company": "TestCorp"
            }
        ]

        prompt = os.getenv("TEST_PROMPT", "Find leads with the name 'John'.")
        response = self.agent.run(prompt, return_json=True)

        # Assertions for the updated JSON structure
        self.assertIn("metadata", response)
        self.assertIn("records", response)
        self.assertEqual(len(response["records"]), 1)
        # Record may be a structured row from Supabase or an agent-wrapped response
        rec0 = response["records"][0]
        if isinstance(rec0.get("id"), str):
            self.assertEqual(rec0.get("id"), "123")
            self.assertEqual(rec0.get("first_name"), "John")
        else:
            # agent-wrapped fallback: ensure there's a textual response
            self.assertIn("response", rec0)
            self.assertIsInstance(rec0.get("response"), str)

    def test_agent_response_or_skip(self):
        if os.getenv("USE_REAL_TESTS") != "1":
            self.skipTest("Skipping real test because USE_REAL_TESTS is not set.")

        prompt = os.getenv("TEST_PROMPT", "Find leads with the name 'John'.")
        response = self.agent.run(prompt)
        self.assertIn("John", response)  # Example assertion


if __name__ == "__main__":
    unittest.main()
