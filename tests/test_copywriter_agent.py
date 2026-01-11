from agent.operational_agents.copywriter import generate_email, generate_text


def test_generate_email_contains_subject_and_body():
    ctx = {"name": "Alice", "company": "ACME", "action": "confirm"}
    out = generate_email(ctx)
    assert "subject" in out and "body" in out
    assert "Alice" in out["subject"]
    assert "ACME" in out["body"]


def test_generate_text_short():
    ctx = {"name": "Bob", "action": "verify"}
    txt = generate_text(ctx)
    assert "Bob" in txt and "verify" in txt
