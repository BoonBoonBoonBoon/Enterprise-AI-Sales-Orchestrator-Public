"""Run a handful of live queries against the RAGAgent and print JSON envelopes.

Environment
-----------
- SUPABASE_URL, SUPABASE_KEY (or SUPABASE_SERVICE_KEY)
- OPENAI_API_KEY

Usage (PowerShell):
  $env:USE_REAL_TESTS=1; python scripts/run_live_queries.py

This demo now constructs the agent via the factory to guarantee a read-only
persistence façade is wired in (no writes possible from this flow).
"""
import json
import sys
from pathlib import Path

# ensure repo root is on sys.path
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from agent.operational_agents.factory import create_rag_agent

queries = [
    # Exact id observed earlier in runs
    "Find the lead with id 75991643-a653-43eb-8220-0ed9f03bc25f",
    # client_id observed earlier
    "Find the lead with client_id 3111512b-dc2b-4c3f-8153-2bc0b3e0761f",
    # email observed earlier
    "Find the lead with email jk@jk.com",
    # company observed earlier (note original data had a typo)
    "Find leads at company 'JK consturction'",
    # name search
    "Find leads with the name 'John'",
    # broad company example
    "Find leads at company 'Acme'"
]

agent = create_rag_agent(kind='supabase')

for q in queries:
    print("\n--- Prompt:\n", q)
    try:
        res = agent.run(q, return_json=True, include_raw=False)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    except Exception as e:
        print("Error running prompt:", e)
