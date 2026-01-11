import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

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
