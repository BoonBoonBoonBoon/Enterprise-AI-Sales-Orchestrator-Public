from tiers.tier_3.copywriter_agent.copywriter import generate_email, generate_text


def test_generate_email_contains_subject_and_body():
    ctx = {"recipient_name": "Alice", "company_name": "ACME", "call_to_action": "Please confirm"}
    out = generate_email(ctx)
    assert "subject" in out and "body" in out
    assert "Alice" in out["subject"]
    assert "ACME" in out["body"]


def test_generate_text_short():
    ctx = {"recipient_name": "Bob", "company_name": "BetaCorp"}
    txt = generate_text(ctx)
    assert "Bob" in txt and "BetaCorp" in txt
