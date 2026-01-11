from datetime import datetime, timedelta

from tiers.tier_3.rag_agent.query_strategy import cascading_lead_lookup


class FakeAdapter:
    def __init__(self):
        now = datetime.utcnow()
        self.tables = {
            "staging_leads": [
                {"id": "sl1", "email": "staging@example.com", "created_at": now},
            ],
            "staging_conversations": [
                {"id": "sc1", "staging_lead_id": "sl1", "created_at": now + timedelta(seconds=1)},
                {"id": "sc2", "staging_lead_id": "sl1", "created_at": now},
            ],
            "staging_messages": [
                {"id": "sm1", "staging_conversation_id": "sc1", "created_at": now, "text_content": "Hi"},
                {"id": "sm2", "staging_conversation_id": "sc1", "created_at": now + timedelta(seconds=1), "text_content": "Hello"},
            ],
            "leads": [
                {"id": "l1", "email": "lead@example.com", "created_at": now},
            ],
            "conversations": [],
            "messages": [],
        }

    def query(self, table, filters=None, limit=None, order_by=None, descending=False):
        records = list(self.tables.get(table, []))
        if filters:
            records = [r for r in records if all(r.get(k) == v for k, v in filters.items())]
        if order_by:
            records.sort(key=lambda r: r.get(order_by), reverse=descending)
        if limit:
            records = records[:limit]
        return {"data": records}

    def read(self, table, id_value, id_column="id"):
        for rec in self.tables.get(table, []):
            if rec.get(id_column) == id_value:
                return {"data": rec}
        return {"data": None}


def test_staging_lead_uses_staging_conversations_and_messages():
    adapter = FakeAdapter()

    result = cascading_lead_lookup(
        adapter,
        email="staging@example.com",
        conversation_limit=2,
        message_limit=5,
    )

    assert result["status"] == "success"
    assert result["lead_source"] == "staging_leads"

    conversations = result["conversations"]
    assert conversations and conversations[0]["id"] == "sc1"  # newest by created_at

    messages = result["messages"]
    assert messages and {m["id"] for m in messages} == {"sm1", "sm2"}

    tables_queried = [step["table"] for step in result["query_trace"]["steps"]]
    assert "staging_conversations" in tables_queried
    assert "staging_messages" in tables_queried
