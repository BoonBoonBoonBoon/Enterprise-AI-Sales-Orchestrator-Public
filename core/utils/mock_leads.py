"""Utilities to generate mock Lead profiles for testing and demos.

No 'id' field is generated (assumed to be DB-generated UUID).
Client IDs are assigned from a provided list (FKs), campaign_id can be fixed.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional


DEFAULT_CLIENT_IDS: List[str] = [
    # Provided client_id values (FKs)
    "3111512b-dc2b-4c3f-8153-2bc0b3e0761f",
    "90fd5909-89fb-4a7f-afa9-d17810496768",
    "592c9b4c-77be-4303-ad46-1ffb1ede127e",
    "4ecd445c-1ff8-44a3-8a0c-404e7c69f031",
]


DEFAULT_CAMPAIGN_ID = "9646f98a-e987-4a8c-b786-9b82ea985d38"


FIRST_NAMES = [
    "John",
    "Jane",
    "Alex",
    "Sam",
    "Chris",
    "Taylor",
    "Jordan",
    "Casey",
]


LAST_NAMES = [
    "Smith",
    "Johnson",
    "Brown",
    "Davis",
    "Miller",
    "Wilson",
    "Taylor",
    "Anderson",
]


JOB_TITLES = [
    "Director",
    "CEO",
    "Founder",
    "Head of Operations",
    "Operations Manager",
    "Sales Director",
    "Managing Director",
]


COMPANY_SUFFIX = ["Ltd", "Limited", "Group", "Holdings", "Services", "Consulting"]


def _iso(dt: datetime) -> str:
    """Return ISO-8601 with timezone offset +00:00 and seconds precision."""
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _rand_phone_uk() -> str:
    # Simple UK-style mobile: 07 + 9 random digits
    return "07" + "".join(str(random.randint(0, 9)) for _ in range(9))


def _rand_company_name(first: str, last: str) -> str:
    base = f"{last} {first[0]}"
    return f"{base} {random.choice(COMPANY_SUFFIX)}"


def _rand_email(first: str, last: str, company: str) -> str:
    handle = f"{first}.{last}".lower().replace(" ", "")
    domain = company.split()[0].lower().replace(" ", "")
    return f"{handle}@{domain}.com"


def generate_lead_profile(
    client_ids: Optional[List[str]] = None,
    campaign_id: str = DEFAULT_CAMPAIGN_ID,
) -> Dict:
    """Generate a single mock lead profile dict without 'id'.

    - client_id is randomly chosen from provided client_ids list.
    - campaign_id defaults to the fixed campaign provided.
    - nullable fields are set to None by default.
    - datetime fields are ISO-8601 with UTC offset.
    """
    client_ids = client_ids or DEFAULT_CLIENT_IDS
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    company = _rand_company_name(first, last)
    email = _rand_email(first, last, company)
    now = datetime.now(timezone.utc)
    past = now - timedelta(days=random.randint(1, 90))
    future = now + timedelta(days=random.randint(1, 90))
    # Ensure non-null re_engagement_date to satisfy NOT NULL schemas
    reengage = now + timedelta(days=random.randint(30, 180)) if random.random() < 0.5 else (now + timedelta(days=90))

    profile = {
        # No 'id' here (assumed DB-generated)
        "client_id": random.choice(client_ids),
        "campaign_id": campaign_id,
        "email": email,
        "first_name": first.lower(),
        "last_name": last.lower(),
        "company_name": company,
        "job_title": random.choice(JOB_TITLES),
        "phone_number": _rand_phone_uk(),
        # Many schemas require a non-null status; default to 'new'
        "current_status": "new",
        "sequence_step": random.randint(1, 5),
        "sequence_active": random.choice([True, False]),
        "next_action_date": _iso(future),
        "last_contact_date": _iso(past),
        "sent_timestamps": None,
        "reply_timestamps": None,
    # Many schemas require a non-null booking status; default to 'not_booked'
    "booking_status": "not_booked",
    "re_engagement_date": _iso(reengage),
        "generated_copy_subject": None,
        "generated_copy_body": None,
        "created_at": _iso(now),
        "updated_at": _iso(now),
        "crm_id": None,
        "last_reply_sentiment": None,
        "lead_score": None,
        "qualification_status": None,
    }
    return profile


def generate_leads(
    count: int,
    client_ids: Optional[List[str]] = None,
    campaign_id: str = DEFAULT_CAMPAIGN_ID,
) -> List[Dict]:
    return [generate_lead_profile(client_ids=client_ids, campaign_id=campaign_id) for _ in range(max(1, int(count)))]


__all__ = [
    "generate_lead_profile",
    "generate_leads",
    "DEFAULT_CLIENT_IDS",
    "DEFAULT_CAMPAIGN_ID",
]
