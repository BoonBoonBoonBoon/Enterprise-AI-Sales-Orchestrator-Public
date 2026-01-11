"""Quick RAGAgent demo to print input filters/envelope and output envelope.

Usage (PowerShell):
  $env:RAG_DEBUG_IO=1; .\.venv\Scripts\python.exe scripts\rag_demo.py --email alice@example.com

You can supply --email / --company / --id. Falls back to a simple prompt run
if no filters given.
"""
from __future__ import annotations
import argparse
import os
from agent.operational_agents.rag_agent.rag_agent import RAGAgent
from agent.tools.persistence.service import ReadOnlyPersistenceFacade


def build_facade() -> ReadOnlyPersistenceFacade | None:
    """Instantiate a read-only persistence facade if environment is configured.

    Falls back to None (legacy Supabase path) if creation fails.
    """
    try:
        from agent.tools.persistence.service import PersistenceService, InMemoryAdapter
        # For demo, use in-memory adapter with a small sample dataset
        sample_rows = [
            {"id": "1", "email": "alice@example.com", "company_name": "Acme", "client_id": "c1"},
            {"id": "2", "email": "bob@example.com", "company_name": "Beta LLC", "client_id": "c1"},
            {"id": "3", "email": "carol@example.com", "company_name": "Acme Incorporated", "client_id": "c2"},
        ]
        mem = InMemoryAdapter()
        service = PersistenceService(adapter=mem, allowed_tables=["leads"])  # legacy single allowlist
        for row in sample_rows:
            service.write("leads", row)
        return ReadOnlyPersistenceFacade(service)
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email")
    parser.add_argument("--company")
    parser.add_argument("--id")
    parser.add_argument("--prompt", help="Free text prompt (when no filters)")
    args = parser.parse_args()

    # Ensure debug output enabled
    os.environ.setdefault("RAG_DEBUG_IO", "1")

    facade = build_facade()
    agent = RAGAgent(read_only_persistence=facade)

    if args.email or args.company or args.id:
        filters = {k: v for k, v in {"email": args.email, "company": args.company, "id": args.id}.items() if v}
        print("\n=== INPUT FILTERS ===")
        print(filters)
        env = agent.query_leads_tool({"filters": filters, "limit": 50})
        print("\n=== OUTPUT ENVELOPE ===")
        print(env)
    else:
        prompt = args.prompt or "Find leads at Acme"
        print(f"\n=== PROMPT ===\n{prompt}")
        env = agent.run(prompt, return_json=True)
        print("\n=== OUTPUT ENVELOPE ===")
        print(env)


if __name__ == "__main__":  # pragma: no cover
    main()
