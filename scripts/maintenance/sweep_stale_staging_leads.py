"""Sweep stale staging leads.

Purpose
- Find staging leads that are still unarchived and stuck in pending states
  past a threshold.
- Dry-run by default; only writes when --apply is provided.

This is intentionally a standalone maintenance script (no Redis required).

Usage
- python -m scripts.maintenance.sweep_stale_staging_leads --days 14
- python -m scripts.maintenance.sweep_stale_staging_leads --days 14 --apply

Requires
- SUPABASE_URL
- SUPABASE_SERVICE_KEY (preferred) or SUPABASE_KEY

Notes
- Uses enrichment_status="failed" when archiving due to staleness, because
  "failed" is already an established status in code/docs.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List


def _get_supabase_client():
    try:
        from supabase import create_client
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("supabase package not installed") from exc

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY/SUPABASE_KEY")

    return create_client(url, key)


def find_stale_staging_leads(
    supabase_client,
    *,
    older_than_days: int,
    limit: int,
) -> List[Dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=int(older_than_days))
    cutoff_iso = cutoff.isoformat()

    # Keep filters intentionally conservative.
    query = (
        supabase_client.table("staging_leads")
        .select("id,email,created_at,qualification_status,enrichment_status,promotion_ready,archived_at")
        .is_("archived_at", "null")
        .eq("enrichment_status", "pending")
        .eq("qualification_status", "pending")
        .eq("promotion_ready", False)
        .lt("created_at", cutoff_iso)
        .limit(int(limit))
    )

    resp = query.execute()
    return list(resp.data or [])


def archive_staging_lead_as_failed(
    supabase_client,
    *,
    staging_lead_id: str,
) -> Dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    resp = (
        supabase_client.table("staging_leads")
        .update({"archived_at": now_iso, "enrichment_status": "failed", "qualification_status": "nurture"})
        .eq("id", staging_lead_id)
        .execute()
    )
    return {"updated": len(resp.data or []), "id": staging_lead_id}


def main() -> int:
    parser = argparse.ArgumentParser(description="Sweep stale staging leads")
    parser.add_argument("--days", type=int, default=int(os.getenv("STAGING_STALE_DAYS", "14")))
    parser.add_argument("--limit", type=int, default=int(os.getenv("STAGING_SWEEP_LIMIT", "500")))
    parser.add_argument("--apply", action="store_true", help="Apply updates (otherwise dry-run)")

    args = parser.parse_args()

    supabase_client = _get_supabase_client()
    stale = find_stale_staging_leads(
        supabase_client,
        older_than_days=args.days,
        limit=args.limit,
    )

    print(f"Found {len(stale)} stale staging leads (>{args.days} days)")

    if not args.apply:
        for row in stale[:25]:
            print(f"DRYRUN id={row.get('id')} email={row.get('email')} created_at={row.get('created_at')}")
        if len(stale) > 25:
            print(f"...and {len(stale) - 25} more")
        return 0

    updated = 0
    for row in stale:
        result = archive_staging_lead_as_failed(supabase_client, staging_lead_id=row.get("id"))
        updated += int(result.get("updated", 0))

    print(f"Updated {updated} staging leads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
