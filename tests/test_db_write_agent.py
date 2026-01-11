from agent.operational_agents.db_write_agent.db_write_agent import create_in_memory_agent


def test_db_write_agent_writes_record():
    agent = create_in_memory_agent()
    rec = {"name": "Alice", "email": "alice@example.com"}
    stored = agent.write("leads", rec)
    assert "id" in stored
    assert stored["name"] == "Alice"


def test_db_write_agent_batch_write():
    agent = create_in_memory_agent()
    records = [{"name": "A"}, {"name": "B"}]
    out = agent.batch_write("leads", records)
    assert len(out) == 2
    assert out[0]["id"] != out[1]["id"]
