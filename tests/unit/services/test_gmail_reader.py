import base64

from services.email.gmail_reader import _decode_mime_header, _extract_email, GmailReader


def _build_raw_email() -> str:
    raw = (
        "From: =?utf-8?B?Sm9obiBEb2U=?= <john@example.com>\r\n"
        "To: jane@example.com\r\n"
        "Subject: =?utf-8?B?SGVsbG8gV29ybGQ=?=\r\n"
        "Message-ID: <msg-1@example.com>\r\n"
        "Date: Tue, 23 Jan 2026 10:00:00 +0000\r\n"
        "List-Unsubscribe: <mailto:unsubscribe@example.com>\r\n"
        "Precedence: bulk\r\n"
        "X-Auto-Response-Suppress: OOF\r\n"
        "X-Mailer: TestMailer\r\n"
        "Reply-To: reply@example.com\r\n"
        "\r\n"
        "Hello from Gmail.\r\n"
    )
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")


def test_decode_mime_header():
    assert _decode_mime_header("=?utf-8?B?SGVsbG8=?=") == "Hello"


def test_extract_email():
    name, email = _extract_email("John Doe <john@example.com>")
    assert name == "John Doe"
    assert email == "john@example.com"


def test_parse_raw_message_extracts_fields():
    raw = _build_raw_email()
    payload = {
        "id": "gmail-1",
        "threadId": "thread-1",
        "labelIds": ["INBOX"],
        "raw": raw,
    }

    parsed = GmailReader.parse_raw_message(payload)

    assert parsed["message_id"] == "<msg-1@example.com>"
    assert parsed["thread_id"] == "thread-1"
    assert parsed["from_email"] == "john@example.com"
    assert parsed["to_email"] == "jane@example.com"
    assert parsed["subject"] == "Hello World"
    assert "Hello from Gmail" in parsed["body_text"]
    assert parsed["list_unsubscribe"] == "<mailto:unsubscribe@example.com>"
    assert parsed["precedence"] == "bulk"
    assert parsed["auto_response_suppress"] == "OOF"
    assert parsed["x_mailer"] == "TestMailer"
    assert parsed["reply_to"] == "reply@example.com"