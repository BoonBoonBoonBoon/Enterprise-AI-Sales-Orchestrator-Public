"""
Direct Supabase write smoke test.

- Upserts a staging_leads row with a generated email and client_id.
- Reads it back to verify visibility (depending on RLS policies).

Exit code 0 on success; non-zero on failure.
"""
from __future__ import annotations

import os
import sys
import uuid
from typing import Any, Dict

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.persistence.adapters.supabase_adapter import SupabaseAdapter


def _require(env_var: str) -> str:
    val = os.getenv(env_var)
    if not val:
        raise RuntimeError(f"Missing required env var: {env_var}")
    return val


def main() -> int:
    try:
        supabase_url = _require("SUPABASE_URL")
        # Prefer custom persistence JWT; fall back to service key.
        supabase_key = os.getenv("SUPABASE_PERSISTENCE_JWT") or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
        if not supabase_key:
            raise RuntimeError("Missing SUPABASE_PERSISTENCE_JWT or SUPABASE_SERVICE_KEY/SUPABASE_KEY")
        anon_key = os.getenv("SUPABASE_ANON_KEY")

        adapter = SupabaseAdapter(supabase_url, supabase_key, anon_key=anon_key)

        tenant_id = os.getenv("TENANT_ID", "agentic-dev")
        client_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, tenant_id))
        email = f"supabase_direct_{uuid.uuid4().hex[:8]}@example.com"

        record: Dict[str, Any] = {
            "email": email,
            "client_id": client_uuid,
            # Add optional metadata defaults here if your schema requires.
        }

        print(f"[WRITE] staging_leads -> {record}")
        res = adapter.upsert("staging_leads", record, on_conflict=["email"])
        print(f"[WRITE RESULT] {res}")

        print("[READ] staging_leads by email")
        row = adapter.query("staging_leads", {"email": email}, limit=1)
        print(f"[READ RESULT] {row}")
        print("OK")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
