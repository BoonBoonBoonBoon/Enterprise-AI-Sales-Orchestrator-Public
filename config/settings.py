import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
INBOX_PROVIDER = os.getenv("INBOX_PROVIDER", "gmail")
INBOX_POLL_INTERVAL_S = int(os.getenv("INBOX_POLL_INTERVAL_S", "60"))
INBOX_DEDUP_TTL_SECONDS = int(os.getenv("INBOX_DEDUP_TTL_SECONDS", "86400"))
GMAIL_READ_CREDENTIALS_PATH = os.getenv("GMAIL_READ_CREDENTIALS_PATH")
GMAIL_INBOX_USER = os.getenv("GMAIL_INBOX_USER") or os.getenv("GMAIL_SENDER_EMAIL")
IMAP_HOST = os.getenv("IMAP_HOST")
IMAP_USERNAME = os.getenv("IMAP_USERNAME")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")
IMAP_MAILBOX = os.getenv("IMAP_MAILBOX", "INBOX")
INBOX_WEBHOOK_SECRET = os.getenv("INBOX_WEBHOOK_SECRET")
INBOX_WEBHOOK_HOST = os.getenv("INBOX_WEBHOOK_HOST", "0.0.0.0")
INBOX_WEBHOOK_PORT = int(os.getenv("INBOX_WEBHOOK_PORT", "8080"))

def validate_keys(raise_on_missing: bool = False):
	missing = []
	if not SUPABASE_URL:
		missing.append('SUPABASE_URL')
	if not SUPABASE_KEY:
		missing.append('SUPABASE_KEY')
	if not OPENAI_API_KEY:
		missing.append('OPENAI_API_KEY')
	if missing and raise_on_missing:
		raise EnvironmentError(f"Missing required env vars: {', '.join(missing)}")
	return missing
