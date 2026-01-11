"""Smoke test: write a mock lead into Supabase via PersistenceAgent.

- Loads .env for SUPABASE_URL/KEY
- Uses factory to create a persistence agent with default write allowlist
- Generates one mock lead and writes to 'leads' table
- Prints the inserted row (id should be present if Supabase returns it)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.operational_agents.factory import create_persistence_agent
from agent.utils.mock_leads import generate_lead_profile


def main() -> None:
    # Basic validation envs exist
    assert os.getenv("SUPABASE_URL"), "SUPABASE_URL not set"
    assert os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_KEY"), "SUPABASE_KEY or SUPABASE_SERVICE_KEY not set"

    # Create persistence agent (supabase)
    agent = create_persistence_agent(kind="supabase")

    # Generate a mock lead and write
    lead = generate_lead_profile()
    # Ensure id isn't set client-side
    lead.pop("id", None)

    inserted = agent.write("leads", lead)
    print(json.dumps({"inserted": inserted}, indent=2))


if __name__ == "__main__":
    main()
