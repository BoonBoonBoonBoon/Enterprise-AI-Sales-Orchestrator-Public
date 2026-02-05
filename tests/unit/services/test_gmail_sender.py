import pytest


def _load_module():
    import services.email.gmail_sender as gmail_sender

    return gmail_sender


def test_send_email_dry_run_skips_smtp(monkeypatch):
    monkeypatch.setenv("GMAIL_SENDER_EMAIL", "sender@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "secret")

    gmail_sender = _load_module()
    monkeypatch.setattr(gmail_sender, "DRY_RUN", True)

    class DummySMTP:
        def __init__(self, *args, **kwargs):
            raise AssertionError("SMTP should not be called in DRY_RUN mode")

    monkeypatch.setattr(gmail_sender.smtplib, "SMTP", DummySMTP)

    message_id = gmail_sender.send_email_via_gmail(
        to_email="recipient@example.com",
        subject="Test",
        body="Hello world",
    )

    assert message_id


def test_send_email_missing_config_raises(monkeypatch):
    monkeypatch.delenv("GMAIL_SENDER_EMAIL", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)

    gmail_sender = _load_module()

    with pytest.raises(gmail_sender.GmailConfigError):
        gmail_sender.send_email_via_gmail(
            to_email="recipient@example.com",
            subject="Test",
            body="Hello world",
        )


def test_send_email_with_attachment_path(monkeypatch, tmp_path):
    monkeypatch.setenv("GMAIL_SENDER_EMAIL", "sender@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "secret")

    attachment = tmp_path / "note.txt"
    attachment.write_text("hello", encoding="utf-8")

    gmail_sender = _load_module()
    monkeypatch.setattr(gmail_sender, "DRY_RUN", True)

    message_id = gmail_sender.send_email_via_gmail(
        to_email="recipient@example.com",
        subject="Attachment",
        body="See attached",
        attachments=[attachment],
    )

    assert message_id