import json
import os
import random
import argparse
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import requests


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    env: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


@dataclass
class SupabaseRest:
    url: str
    service_key: str

    @property
    def rest_base(self) -> str:
        return self.url.rstrip("/") + "/rest/v1"

    def _headers(self, prefer: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    def select(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        r = requests.get(
            f"{self.rest_base}/{table}",
            headers=self._headers(),
            params={"select": "*", **params},
            timeout=30,
        )
        if not r.ok:
            raise requests.HTTPError(
                f"{r.status_code} {r.reason} for GET {table}: {r.text}", response=r
            )
        return r.json()

    def insert(self, table: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        r = requests.post(
            f"{self.rest_base}/{table}",
            headers=self._headers(prefer="return=representation"),
            data=json.dumps(rows),
            timeout=60,
        )
        if not r.ok:
            raise requests.HTTPError(
                f"{r.status_code} {r.reason} for INSERT {table}: {r.text}", response=r
            )
        return r.json()

    def upsert(self, table: str, rows: list[dict[str, Any]], on_conflict: str) -> list[dict[str, Any]]:
        r = requests.post(
            f"{self.rest_base}/{table}",
            headers=self._headers(prefer="return=representation,resolution=merge-duplicates"),
            params={"on_conflict": on_conflict},
            data=json.dumps(rows),
            timeout=60,
        )
        if not r.ok:
            raise requests.HTTPError(
                f"{r.status_code} {r.reason} for UPSERT {table}: {r.text}", response=r
            )
        return r.json()


def ensure_sequence_and_campaign(
    supabase: SupabaseRest,
    client_id: str,
    campaign_id: str,
) -> tuple[str, str]:
    # Create a sequence + campaign when allowed by policies.
    # Some deployments lock these down; if inserts are forbidden, we'll proceed assuming
    # CAMPAIGN_ID_PLACEHOLDER already exists.
    seq_id = str(uuid.uuid4())
    try:
        supabase.insert(
            "sequences",
            [
                {
                    "id": seq_id,
                    "client_id": client_id,
                    "sequence_name": "Demo Sequence",
                    "steps": [],
                    "created_at": _iso(_now()),
                    "updated_at": _iso(_now()),
                }
            ],
        )
    except requests.HTTPError as e:
        print(f"WARN: could not insert sequences (continuing): {e}")

    try:
        supabase.upsert(
            "campaigns",
            [
                {
                    "id": campaign_id,
                    "client_id": client_id,
                    "campaign_name": "Demo Campaign",
                    "campaign_type": "outbound_email",
                    "status": "active",
                    "sequence_id": seq_id,
                    "created_at": _iso(_now()),
                    "updated_at": _iso(_now()),
                }
            ],
            on_conflict="id",
        )
    except requests.HTTPError as e:
        print(f"WARN: could not upsert campaigns (continuing): {e}")

    return seq_id, campaign_id


def ensure_membership(
    supabase: SupabaseRest,
    *,
    user_id: str,
    client_id: str,
    role: str = "admin",
) -> None:
    try:
        supabase.upsert(
            "user_client_memberships",
            [{"user_id": user_id, "client_id": client_id, "role": role}],
            on_conflict="user_id,client_id",
        )
        print(f"Ensured membership user_id={user_id} -> client_id={client_id} ({role})")
    except requests.HTTPError as e:
        print(f"WARN: could not upsert user_client_memberships (continuing): {e}")


def seed_staging_leads(
    supabase: SupabaseRest,
    *,
    client_id: str,
    campaign_id: str,
    count: int,
) -> list[str]:
    industries = ["SaaS", "Marketing", "Finance", "Healthcare", "Ecommerce"]
    sizes = ["1-10", "11-50", "51-200", "201-500"]
    locations = ["London, UK", "Austin, TX", "NYC, NY", "Toronto, CA", "Berlin, DE"]

    rows: list[dict[str, Any]] = []
    staging_ids: list[str] = []
    for i in range(count):
        lead_id = str(uuid.uuid4())
        staging_ids.append(lead_id)
        first = random.choice(["Alex", "Jordan", "Taylor", "Sam", "Morgan", "Casey", "Jamie"]) + f"{i}"
        last = random.choice(["Smith", "Johnson", "Lee", "Brown", "Garcia", "Patel", "Wong"])
        company = random.choice(["Northwind", "Contoso", "Bluebird", "Greenfield", "Pinecone", "Orbit"]) + f" Labs {i}"
        industry = random.choice(industries)
        rows.append(
            {
                "id": lead_id,
                "client_id": client_id,
                "campaign_id": campaign_id,
                "source": random.choice(["website", "inbound_email", "linkedin", "import"]),
                "email": f"{first.lower()}.{last.lower()}@example.com",
                "first_name": first,
                "last_name": last,
                "company_name": company,
                "job_title": random.choice(["Founder", "Head of Growth", "VP Sales", "Marketing Lead", "Ops Manager"]),
                "phone_number": f"+1-555-01{i:02d}",
                "linkedin_url": f"https://linkedin.com/in/{first.lower()}-{last.lower()}-{i}",
                "website_url": f"https://{company.lower().replace(' ', '').replace('.', '')}.com",
                "location": random.choice(locations),
                "industry": industry,
                "company_size": random.choice(sizes),
                "revenue_range": random.choice(["<1M", "1-5M", "5-20M", "20M+"] ),
                "raw_data": {"seed": True, "kind": "staging_demo"},
                "enrichment_status": random.choice(["pending", "complete", "partial"]),
                "qualification_status": random.choice(["unqualified", "needs_review", "qualified"]),
                "promotion_ready": random.choice([False, False, True]),
                "created_at": _iso(_now() - timedelta(days=random.randint(0, 10))),
                "updated_at": _iso(_now()),
                "archived_at": None,
            }
        )

    _insert_chunked(supabase, "staging_leads", rows)
    return staging_ids


def seed_staging_threads(
    supabase: SupabaseRest,
    *,
    staging_lead_ids: list[str],
    leads_with_threads: int,
    messages_per_thread: int,
) -> None:
    # Create threads for a subset of staging leads.
    convo_rows: list[dict[str, Any]] = []
    convo_ids: list[str] = []
    for idx, staging_lead_id in enumerate(staging_lead_ids[: max(0, leads_with_threads)]):
        convo_id = str(uuid.uuid4())
        convo_ids.append(convo_id)
        convo_rows.append(
            {
                "id": convo_id,
                "staging_lead_id": staging_lead_id,
                "status": "active",
                "metadata": {"seed": True},
                "subject": f"Quick question about your {random.choice(['pipeline', 'team', 'stack', 'workflow'])}",
                "thread_id": f"stg-thread-{idx}",
                "channel": "email",
                "created_at": _iso(_now() - timedelta(days=idx + 1)),
                "updated_at": _iso(_now()),
                "archived_at": None,
            }
        )

    if convo_rows:
        _insert_chunked(supabase, "staging_conversations", convo_rows)

    msg_rows: list[dict[str, Any]] = []
    for idx, convo_id in enumerate(convo_ids):
        msg_count = max(1, messages_per_thread)
        base_time = _now() - timedelta(days=idx + 1)
        for j in range(msg_count):
            msg_rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "staging_conversation_id": convo_id,
                    "sender": "lead" if j % 2 == 0 else "agent",
                    "receiver": "agent" if j % 2 == 0 else "lead",
                    "content": (
                        "Hi — saw your site and had a question about pricing." if j == 0 else
                        "Happy to share. What size team are you?" if j == 1 else
                        "We’re ~20 people. Interested in a short call?"
                    ),
                    "sent_at": _iso(base_time + timedelta(hours=j * 3)),
                    "metadata": {"seed": True, "idx": j},
                    "created_at": _iso(_now()),
                    "updated_at": _iso(_now()),
                    "archived_at": None,
                    "message_id": f"stg-msg-{idx}-{j}",
                }
            )

    if msg_rows:
        _insert_chunked(supabase, "staging_messages", msg_rows)


def seed_leads(
    supabase: SupabaseRest,
    *,
    client_id: str,
    campaign_id: str,
    count: int,
) -> list[str]:
    statuses = ["new", "contacted", "replied", "booked"]
    companies = ["Northwind", "Contoso", "Globex", "Initech", "Umbrella", "Soylent"]

    rows: list[dict[str, Any]] = []
    lead_ids: list[str] = []
    for i in range(count):
        lead_id = str(uuid.uuid4())
        lead_ids.append(lead_id)
        first = random.choice(["Avery", "Riley", "Quinn", "Parker", "Reese", "Rowan"]) + f"{i}"
        last = random.choice(["Ng", "Kim", "Davis", "Miller", "Wilson", "Clark"])
        company = f"{random.choice(companies)} Demo {i}"
        now = _now()
        rows.append(
            {
                "id": lead_id,
                "client_id": client_id,
                "campaign_id": campaign_id,
                "email": f"{first.lower()}.{last.lower()}@{company.lower().replace(' ', '')}.com",
                "first_name": first,
                "last_name": last,
                "company_name": company,
                "job_title": random.choice(["Founder", "CEO", "VP Sales", "Head of Ops"]),
                "phone_number": f"+1-555-20{i:02d}",
                "current_status": random.choice(statuses),
                "sequence_step": int(random.choice([1, 2, 3])),
                "sequence_active": random.choice([True, True, False]),
                "next_action_date": _iso(now + timedelta(days=random.randint(1, 5))),
                "last_contact_date": _iso(now - timedelta(days=random.randint(1, 7))),
                "booking_status": random.choice(["none", "pending", "booked"]),
                "re_engagement_date": _iso(now + timedelta(days=random.randint(7, 21))),
                "created_at": _iso(now - timedelta(days=random.randint(3, 14))),
                "updated_at": _iso(now),
                "last_reply_sentiment": random.choice([None, "positive", "neutral", "negative"]),
                "lead_score": random.choice([45, 52, 68, 77, 83, 91]),
                "qualification_status": random.choice([None, "qualified", "hot"]),
            }
        )

    _insert_chunked(supabase, "leads", rows)
    return lead_ids


def seed_conversations_and_messages(
    supabase: SupabaseRest,
    *,
    client_id: str,
    lead_ids: list[str],
    conversations_per_lead: int,
    messages_per_conversation: int,
) -> None:
    convo_rows: list[dict[str, Any]] = []
    convo_ids: list[str] = []

    for i, lead_id in enumerate(lead_ids):
        for c in range(max(1, conversations_per_lead)):
            convo_id = str(uuid.uuid4())
            convo_ids.append(convo_id)
            convo_rows.append(
                {
                    "id": convo_id,
                    "client_id": client_id,
                    "lead_id": lead_id,
                    "channel": "email",
                    "status": random.choice(["open", "active", "closed"]),
                    "summary": random.choice(
                        [
                            "Lead asked about pricing and timeline.",
                            "Discussed use case; awaiting follow-up.",
                            "Positive reply; suggested quick call.",
                            "No response yet; scheduled next touch.",
                        ]
                    ),
                    "thread_id": f"thread-{i}-{c}",
                    "subject": random.choice(
                        [
                            "Quick intro",
                            "Following up",
                            "Re: your website",
                            "Next steps",
                        ]
                    ),
                    "created_at": _iso(_now() - timedelta(days=10 - i)),
                    "updated_at": _iso(_now() - timedelta(days=5 - i)),
                }
            )

    if convo_rows:
        _insert_chunked(supabase, "conversations", convo_rows)

    msg_rows: list[dict[str, Any]] = []
    for idx, convo_id in enumerate(convo_ids):
        base_time = _now() - timedelta(days=3) + timedelta(hours=idx)
        for j in range(max(1, messages_per_conversation)):
            sender_type = "agent" if j % 2 == 0 else "lead"
            msg_rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "conversation_id": convo_id,
                    "sender_type": sender_type,
                    "text_content": (
                        "Hey — would you be open to a quick 10-min call this week?" if j == 0 else
                        "Possibly. Can you share pricing?" if j == 1 else
                        "Sure — ballpark depends on volume; what size team?" if j == 2 else
                        "We’re about 25 people. Thursday works."
                    ),
                    "metadata": {},
                    "sent_at": _iso(base_time + timedelta(hours=j * 2)),
                    "created_at": _iso(_now()),
                    "message_id": f"msg-{idx}-{j}",
                }
            )

    if msg_rows:
        _insert_chunked(supabase, "messages", msg_rows)


def _chunks(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _insert_chunked(supabase: SupabaseRest, table: str, rows: list[dict[str, Any]], chunk_size: int = 500) -> None:
    for chunk in _chunks(rows, chunk_size):
        supabase.insert(table, chunk)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo data for a specific Supabase client_id")
    parser.add_argument("--client-id", dest="client_id", default=None)
    parser.add_argument("--campaign-id", dest="campaign_id", default=None)
    parser.add_argument("--seed", dest="seed", type=int, default=42)
    parser.add_argument("--staging-count", dest="staging_count", type=int, default=12)
    parser.add_argument("--qualified-count", dest="qualified_count", type=int, default=7)
    # Defaults enforce the minimum requested: >=1 conversation and >=1 message per prospect.
    # Staging defaults to threads for ALL staging leads.
    parser.add_argument(
        "--staging-leads-with-threads",
        dest="staging_with_threads",
        type=int,
        default=None,
        help="How many staging leads get a staging_conversation+messages. Default: all staging leads.",
    )
    parser.add_argument(
        "--messages-per-staging-thread",
        dest="messages_per_staging_thread",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--conversations-per-qualified-lead",
        dest="conversations_per_lead",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--messages-per-qualified-conversation",
        dest="messages_per_conversation",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--user-id",
        dest="user_id",
        default=None,
        help="Optional: Supabase auth user UUID to upsert into user_client_memberships for this client",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]

    env = dict(os.environ)
    env.update(load_env_file(repo_root / ".env"))
    env.update(load_env_file(repo_root / "apps" / "portal-customer" / ".env.local"))

    supabase_url = env.get("SUPABASE_URL") or env.get("NEXT_PUBLIC_SUPABASE_URL")
    service_key = env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_KEY")

    if not supabase_url or not service_key:
        raise SystemExit(
            "Missing SUPABASE_URL/NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY in env."
        )

    client_id = args.client_id or env.get("DEMO_CLIENT_ID") or "8b51af73-ecae-44e9-8e0d-cb7671a95845"
    client_name = env.get("DEMO_CLIENT_NAME") or "gmail.com"

    campaign_id = (
        args.campaign_id
        or env.get("CAMPAIGN_ID_PLACEHOLDER")
        or "9646f98a-e987-4a8c-b786-9b82ea985d38"
    )

    supabase = SupabaseRest(url=supabase_url, service_key=service_key)

    random.seed(args.seed)

    print(f"Seeding data for client_id={client_id}")
    # NOTE: We intentionally do NOT touch the clients table here.
    # Many deployments restrict it via RLS; your client row already exists.
    print(f"Using existing client row name={client_name}")

    ensure_sequence_and_campaign(supabase, client_id=client_id, campaign_id=campaign_id)

    if args.user_id:
        ensure_membership(supabase, user_id=args.user_id, client_id=client_id)

    staging_count = max(0, args.staging_count)
    qualified_count = max(0, args.qualified_count)

    staging_ids = seed_staging_leads(
        supabase,
        client_id=client_id,
        campaign_id=campaign_id,
        count=staging_count,
    )

    # Default: every staging lead gets at least one thread + one message.
    staging_with_threads = (
        len(staging_ids)
        if args.staging_with_threads is None
        else max(0, args.staging_with_threads)
    )
    seed_staging_threads(
        supabase,
        staging_lead_ids=staging_ids,
        leads_with_threads=staging_with_threads,
        messages_per_thread=max(1, args.messages_per_staging_thread),
    )

    lead_ids = seed_leads(
        supabase,
        client_id=client_id,
        campaign_id=campaign_id,
        count=qualified_count,
    )
    seed_conversations_and_messages(
        supabase,
        client_id=client_id,
        lead_ids=lead_ids,
        conversations_per_lead=max(1, args.conversations_per_lead),
        messages_per_conversation=max(1, args.messages_per_conversation),
    )

    print("Done.")
    print(f"Inserted staging_leads: {len(staging_ids)}")
    print(f"Inserted leads: {len(lead_ids)}")
    print("Inserted conversations/messages and staging threads.")


if __name__ == "__main__":
    main()
