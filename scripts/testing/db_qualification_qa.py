"""Database state inspection for qualification QA.

Checks:
1. leads table - qualified leads
2. staging_leads table - pre-qualified leads
3. conversations table - lead conversations
4. staging_conversations table - staging conversations
5. Record counts and recent activity
6. Data flow verification (staging → leads promotions)

Usage:
  python scripts/testing/db_qualification_qa.py
  python scripts/testing/db_qualification_qa.py --full

Environment:
  SUPABASE_URL
  SUPABASE_SERVICE_KEY (or SUPABASE_KEY fallback)
"""
from __future__ import annotations

import os
import sys
import json
import pathlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


def _load_env_file():
    """Lightweight .env loader."""
    env_path = pathlib.Path('.env')
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.strip().startswith('#'):
            continue
        if '=' not in line:
            continue
        key, val = line.split('=', 1)
        key = key.strip()
        val = val.strip()
        if key and key not in os.environ:
            os.environ[key] = val


def get_supabase_client():
    """Get Supabase client with proper auth."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_KEY environment variables")
        sys.exit(1)
    
    try:
        from supabase import create_client
        return create_client(url, key)
    except ImportError:
        print("❌ Missing supabase package. Run: pip install supabase")
        sys.exit(1)


def count_table(client, table: str) -> int:
    """Count rows in a table."""
    try:
        result = client.table(table).select("id", count="exact").execute()
        return result.count if hasattr(result, 'count') else len(result.data)
    except Exception as e:
        print(f"  ⚠️  Error counting {table}: {e}")
        return -1


def get_recent_records(client, table: str, limit: int = 5) -> List[Dict]:
    """Get most recent records from a table."""
    try:
        result = client.table(table).select("*").order("created_at", desc=True).limit(limit).execute()
        return result.data or []
    except Exception as e:
        print(f"  ⚠️  Error fetching {table}: {e}")
        return []


def get_promoted_leads(client, since_hours: int = 24) -> List[Dict]:
    """Get leads that were promoted from staging recently."""
    try:
        cutoff = (datetime.utcnow() - timedelta(hours=since_hours)).isoformat()
        result = client.table("leads").select("*").gte("created_at", cutoff).execute()
        return result.data or []
    except Exception as e:
        print(f"  ⚠️  Error fetching promoted leads: {e}")
        return []


def get_staging_with_conversations(client, limit: int = 5) -> List[Dict]:
    """Get staging leads that have conversations."""
    try:
        # First get staging leads
        leads = client.table("staging_leads").select("*").limit(limit).execute()
        if not leads.data:
            return []
        
        # Then get conversations for each
        result = []
        for lead in leads.data:
            convos = client.table("staging_conversations").select("*").eq(
                "staging_lead_id", lead["id"]
            ).limit(5).execute()
            lead["_conversations"] = convos.data or []
            result.append(lead)
        return result
    except Exception as e:
        print(f"  ⚠️  Error fetching staging with conversations: {e}")
        return []


def check_data_integrity(client) -> Dict[str, Any]:
    """Check for data integrity issues."""
    issues = []
    
    try:
        # Check for leads without campaigns
        orphan_leads = client.table("leads").select("id,email").is_("campaign_id", "null").execute()
        if orphan_leads.data:
            issues.append(f"Leads without campaign_id: {len(orphan_leads.data)}")
        
        # Check for conversations without leads
        # This is a bit tricky since we need to check FK integrity
        
        # Check for staging leads that might be stale (> 7 days old, no activity)
        week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
        stale = client.table("staging_leads").select("id,email,created_at").lt(
            "created_at", week_ago
        ).execute()
        if stale.data:
            issues.append(f"Stale staging leads (>7 days): {len(stale.data)}")
            
    except Exception as e:
        issues.append(f"Integrity check error: {e}")
    
    return {
        "issues": issues,
        "clean": len(issues) == 0
    }


def summarize_field(records: List[Dict], field: str) -> str:
    """Summarize a field's values across records."""
    values = [r.get(field) for r in records if r.get(field)]
    if not values:
        return "none"
    if len(values) <= 3:
        return ", ".join(str(v)[:50] for v in values)
    return f"{len(values)} values (first: {str(values[0])[:30]}...)"


def main():
    """Main entry point."""
    _load_env_file()
    
    full_mode = "--full" in sys.argv
    
    print("\n" + "=" * 60)
    print("🔍 QUALIFICATION QA - DATABASE STATE INSPECTION")
    print("=" * 60)
    
    client = get_supabase_client()
    print("✅ Supabase client connected\n")
    
    # Table counts
    print("📊 TABLE COUNTS:")
    print("-" * 40)
    tables = [
        "leads", "staging_leads", 
        "conversations", "staging_conversations",
        "messages", "staging_messages",
        "campaigns", "clients"
    ]
    counts = {}
    for table in tables:
        count = count_table(client, table)
        counts[table] = count
        status = "✅" if count >= 0 else "❌"
        print(f"  {status} {table}: {count}")
    
    print("\n📈 RECENT ACTIVITY:")
    print("-" * 40)
    
    # Recent leads
    print("\n  🟢 Recent LEADS (qualified):")
    recent_leads = get_recent_records(client, "leads", 5)
    if recent_leads:
        for lead in recent_leads:
            email = lead.get("email", "N/A")[:40]
            created = lead.get("created_at", "N/A")[:19]
            company = lead.get("company_name") or lead.get("company") or "N/A"
            print(f"     • {email} | {company[:20]} | {created}")
    else:
        print("     (no leads found)")
    
    # Recent staging leads
    print("\n  🟡 Recent STAGING_LEADS (pre-qualification):")
    recent_staging = get_recent_records(client, "staging_leads", 5)
    if recent_staging:
        for lead in recent_staging:
            email = lead.get("email", "N/A")[:40]
            created = lead.get("created_at", "N/A")[:19]
            status = lead.get("status", "N/A")
            print(f"     • {email} | status={status} | {created}")
    else:
        print("     (no staging leads found)")
    
    # Recent conversations
    print("\n  💬 Recent CONVERSATIONS:")
    recent_convos = get_recent_records(client, "conversations", 5)
    if recent_convos:
        for convo in recent_convos:
            lead_id = str(convo.get("lead_id", "N/A"))[:8]
            created = convo.get("created_at", "N/A")[:19]
            print(f"     • lead_id={lead_id}... | {created}")
    else:
        print("     (no conversations found)")
    
    # Data flow check
    print("\n🔄 DATA FLOW VERIFICATION:")
    print("-" * 40)
    
    # Check staging → leads promotion in last 24h
    promoted = get_promoted_leads(client, since_hours=24)
    print(f"  Leads created in last 24h: {len(promoted)}")
    
    # Check for staging leads with qualification scores
    try:
        scored = client.table("staging_leads").select("*").neq(
            "qualification_score", None
        ).limit(10).execute()
        print(f"  Staging leads with qualification scores: {len(scored.data or [])}")
        if scored.data:
            for lead in scored.data[:3]:
                email = lead.get("email", "N/A")[:30]
                score = lead.get("qualification_score", "N/A")
                decision = lead.get("qualification_decision", "N/A")
                print(f"     • {email} | score={score} | decision={decision}")
    except Exception as e:
        print(f"  ⚠️  Could not check qualification scores: {e}")
    
    # Integrity check
    print("\n🔐 DATA INTEGRITY:")
    print("-" * 40)
    integrity = check_data_integrity(client)
    if integrity["clean"]:
        print("  ✅ No integrity issues detected")
    else:
        for issue in integrity["issues"]:
            print(f"  ⚠️  {issue}")
    
    if full_mode:
        print("\n📝 FULL DETAIL MODE:")
        print("-" * 40)
        
        # Show staging leads with conversations
        print("\n  Staging leads with conversations:")
        staging_with_convos = get_staging_with_conversations(client, 3)
        for lead in staging_with_convos:
            email = lead.get("email", "N/A")
            print(f"\n     📧 {email}")
            for convo in lead.get("_conversations", []):
                convo_id = str(convo.get("id", ""))[:8]
                print(f"        └── Conversation: {convo_id}...")
    
    print("\n" + "=" * 60)
    print("✅ Database inspection complete")
    print("=" * 60 + "\n")
    
    # Return counts as JSON for programmatic use
    return json.dumps({
        "counts": counts,
        "recent_leads": len(recent_leads),
        "recent_staging": len(recent_staging),
        "promoted_24h": len(promoted),
        "integrity": integrity
    }, indent=2)


if __name__ == "__main__":
    result = main()
    print(result)
