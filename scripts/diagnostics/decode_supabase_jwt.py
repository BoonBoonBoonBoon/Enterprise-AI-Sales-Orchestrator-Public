from dotenv import load_dotenv
import os, json, base64

load_dotenv()
token = os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY') or ''
if not token or token.count('.') < 2:
    print('no token or not a jwt')
    raise SystemExit(0)

payload = token.split('.')[1]
padded = payload + '=' * ((4 - len(payload) % 4) % 4)
decoded = base64.urlsafe_b64decode(padded)
print(json.dumps(json.loads(decoded), indent=2))
