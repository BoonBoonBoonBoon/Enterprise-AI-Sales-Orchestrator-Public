import types

import pytest

from core.schemas.persistence import TableStep, StepOperation, CompoundPayload, ConditionalCheck
from tiers.tier_3.persistence_agent import compound_handler


class DummyAdapter:
    def __init__(self):
        self.rows = {}

    def write(self, table, record):
        record = dict(record)
        record.setdefault("id", f"{table}_1")
        self.rows.setdefault(table, []).append(record)
        return record

    def batch_write(self, table, records):
        out = []
        for rec in records:
            out.append(self.write(table, rec))
        return out

    def upsert(self, table, record, on_conflict=None):
        record = dict(record)
        record.setdefault("id", f"{table}_1")
        self.rows.setdefault(table, [])
        if on_conflict:
            for idx, existing in enumerate(self.rows[table]):
                if all(existing.get(k) == record.get(k) for k in on_conflict):
                    merged = {**existing, **record}
                    self.rows[table][idx] = merged
                    return merged
        self.rows[table].append(record)
        return record

    def delete(self, table, record_id):
        self.rows[table] = [r for r in self.rows.get(table, []) if r.get("id") != record_id]

    def query(self, table, filters, limit=1000, order_by=None, descending=False):
        results = []
        for row in self.rows.get(table, []):
            if all(row.get(k) == v for k, v in filters.items()):
                results.append(row)
        return results[:limit]

    def get_columns(self, table):
        return None


def test_resolve_references_nested():
    outputs = {"lead": {"id": "L1"}, "conversation": {"id": "C1"}}
    data = {"lead_id": "$ref:lead.id", "conversation_id": "$ref:conversation.id"}

    resolved = compound_handler.resolve_references(data, outputs)

    assert resolved["lead_id"] == "L1"
    assert resolved["conversation_id"] == "C1"


def test_execute_step_create_and_update():
    adapter = DummyAdapter()

    create_step = TableStep(
        step_name="lead",
        table="leads",
        operation=StepOperation.CREATE,
        data={"email": "a@example.com"},
    )
    create_result = compound_handler.execute_step(create_step, adapter, {})
    assert create_result.status == "success"
    assert create_result.output["email"] == "a@example.com"

    update_step = TableStep(
        step_name="update_lead",
        table="leads",
        operation=StepOperation.UPDATE,
        where={"id": create_result.output["id"]},
        data={"stage": "engaged"},
    )
    update_result = compound_handler.execute_step(update_step, adapter, {"lead": create_result.output})
    assert update_result.status == "success"


def test_execute_step_delete_with_where():
    adapter = DummyAdapter()
    record = adapter.write("leads", {"id": "L9", "email": "x@example.com"})

    delete_step = TableStep(
        step_name="delete",
        table="leads",
        operation=StepOperation.DELETE,
        where={"id": record["id"]},
    )
    delete_result = compound_handler.execute_step(delete_step, adapter, {})

    assert delete_result.status == "success"
    assert adapter.query("leads", {"id": "L9"}) == []


def test_execute_compound_rolls_back_on_failure(monkeypatch):
    adapter = DummyAdapter()

    class FailingAdapter(DummyAdapter):
        def write(self, table, record):
            if table == "messages":
                raise RuntimeError("boom")
            return super().write(table, record)

    failing = FailingAdapter()

    payload = CompoundPayload(
        rollback_on_failure=True,
        continue_on_skip=False,
        steps=[
            TableStep(step_name="lead", table="leads", operation=StepOperation.CREATE, data={"email": "a"}),
            TableStep(step_name="message", table="messages", operation=StepOperation.CREATE, data={"content": "x"}),
        ],
    )

    result = compound_handler.execute_compound(payload, failing)

    assert result.success is False
    assert result.rollback_performed is True
    assert failing.query("leads", {"email": "a"}) == []


def test_execute_step_condition_skip():
    adapter = DummyAdapter()
    outputs = {"lead": {"id": "L1", "status": "active"}}

    step = TableStep(
        step_name="conditional",
        table="leads",
        operation=StepOperation.UPDATE,
        where={"id": "$ref:lead.id"},
        data={"stage": "engaged"},
        condition=ConditionalCheck(field="$ref:lead.status", operator="equals", value="inactive"),
    )

    result = compound_handler.execute_step(step, adapter, outputs)

    assert result.status == "skipped"


def test_retry_upsert_transient(monkeypatch):
    calls = {"count": 0}

    class FlakyAdapter(DummyAdapter):
        def upsert(self, table, record, on_conflict=None):
            calls["count"] += 1
            if calls["count"] < 2:
                raise RuntimeError("42P10 transient")
            return super().upsert(table, record, on_conflict)

    monkeypatch.setattr(compound_handler.time, "sleep", lambda *_: None)

    adapter = FlakyAdapter()
    result = compound_handler._retry_upsert(adapter, "leads", {"id": "L1"}, on_conflict=["id"], max_attempts=2)

    assert result["id"] == "L1"
    assert calls["count"] == 2