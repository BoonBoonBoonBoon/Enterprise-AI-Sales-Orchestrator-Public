"""
Lookup a lead by email using the unified persistence factory.

Usage:
  python scripts/get_lead_by_email.py "someone@example.com"

Requires Supabase environment variables when kind='supabase':
  - SUPABASE_URL
  - SUPABASE_SERVICE_KEY (preferred) or SUPABASE_KEY

Set PERSIST_ALLOWED_TABLES or config allowlists to include 'leads' if needed.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict
from pathlib import Path

try:
    # Ensure repo root on sys.path so `import agent` works even when invoked from elsewhere
    REPO_ROOT = Path(__file__).resolve().parents[1]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
except Exception:
    pass

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    # Optional dependency; if not present, rely on OS env
    pass

from agent.operational_agents.factory import create_persistence_agent


def main() -> int:
    if len(sys.argv) < 2:
        print("Error: email argument is required. Example: python scripts/get_lead_by_email.py jk@jk.com", file=sys.stderr)
        return 2

    email = sys.argv[1].strip()
    kind = os.environ.get("PERSIST_KIND", "supabase")  # allow override to 'memory' if desired

    try:
        agent = create_persistence_agent(kind=kind)
    except Exception as e:
        print(f"Failed to construct persistence agent (kind={kind}): {e}", file=sys.stderr)
        return 1

    try:
        rows = agent.query(
            "leads",
            filters={"email": email},
            limit=1,
        )
    except Exception as e:
        print(f"Query failed: {e}", file=sys.stderr)
        return 1

    if not rows:
        print(json.dumps({"found": False, "email": email}))
        return 0

    print(json.dumps({"found": True, "row": rows[0]}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
