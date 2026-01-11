import uuid
from datetime import datetime, timedelta

from tiers.tier_3.persistence_agent.persistence_agent import PersistenceAgent


class FakeSupabase:
    def __init__(self):
        now = datetime.utcnow()
        self.tables = {
            "staging_leads": [
                {
                    "id": "sl1",
                    "email": "staging@example.com",
                    "first_name": "Pat",
                    "last_name": "Smith",
                    "company_name": "Acme",
                    "job_title": "CTO",
                    "phone_number": "",
                    "source": "inbound",
                    "created_at": now,
                }
            ],
            "staging_conversations": [
                {"id": "sc1", "staging_lead_id": "sl1", "status": "active", "metadata": {"thread": "t1"}, "created_at": now},
            ],
            "staging_messages": [
                {
                    "id": "sm1",
                    "staging_conversation_id": "sc1",
                    "sender": "lead",
                    "content": "Hi there",
                    "metadata": {"message_id": "m1"},
                    "created_at": now + timedelta(seconds=1),
                }
            ],
            "leads": [],
            "conversations": [],
            "messages": [],
        }

    def read(self, table, id_value, id_column="id"):
        for rec in self.tables.get(table, []):
            if rec.get(id_column) == id_value:
                return {"data": rec}
        return {"data": None}

    def write(self, table, record):
        self.tables.setdefault(table, []).append(record)
        return {"data": record}

    def upsert(self, table, record, on_conflict=None):
        on_conflict = on_conflict or ["id"]
        table_list = self.tables.setdefault(table, [])
        for idx, rec in enumerate(table_list):
            if all(rec.get(col) == record.get(col) for col in on_conflict):
                table_list[idx] = {**rec, **record}
                return {"data": table_list[idx]}
        table_list.append(record)
        return {"data": record}

    def query(self, table, filters=None, limit=None, order_by=None, descending=False):
        filters = filters or {}
        records = [r for r in self.tables.get(table, []) if all(r.get(k) == v for k, v in filters.items())]
        if order_by:
            records.sort(key=lambda r: r.get(order_by), reverse=descending)
        if limit:
            records = records[:limit]
        return {"data": records}


class Dummy:
    pass


def build_agent_with_fake_supabase():
    agent = PersistenceAgent.__new__(PersistenceAgent)
    agent.supabase = FakeSupabase()
    agent.client_uuid = "client-uuid"
    return agent


def test_promote_copies_conversations_and_messages():
    agent = build_agent_with_fake_supabase()
    tool = agent._create_promote_staging_lead_tool()

    result = tool.func(staging_lead_id="sl1")

    assert result["status"] == "success"
    assert result["conversations_created"] == 1
    assert result["messages_created"] == 1

    leads = agent.supabase.tables["leads"]
    assert len(leads) == 1

    conversations = agent.supabase.tables["conversations"]
    assert len(conversations) == 1
    assert conversations[0]["lead_id"] == leads[0]["id"]

    messages = agent.supabase.tables["messages"]
    assert len(messages) == 1
    assert messages[0]["conversation_id"] == conversations[0]["id"]

    staging_lead = agent.supabase.tables["staging_leads"][0]
    assert staging_lead.get("archived_at") is not None
    assert staging_lead.get("enrichment_status") == "promoted"
