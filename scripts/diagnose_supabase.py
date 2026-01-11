import os
import json
import requests
from dotenv import load_dotenv

"""LEGACY SCRIPT (diagnostic) - will be folded into ingest_cli.py (--mode diagnose)
Keep for now; prefer unified CLI when ready.
"""

# A direct, minimal “DB health” probe.
# It bypasses all your application logic and talks straight to Supabase REST.
# Purpose: isolate infrastructure issues 
# (permissions, NOT NULL violations, header problems) without any masking by the app code.



# DEV WARNING:
# The client_id and campaign_id injected below are for LOCAL / DEV TESTING ONLY.
# DO NOT HARD-CODE TENANT / CUSTOMER IDENTIFIERS IN PRODUCTION CODE.
# In production these should come from a secure request payload, an auth token,
# or a configuration lookup keyed by the authenticated tenant.
# This script enforces a guard: if ENV=production it will abort.

DEV_CLIENT_ID = "90fd5909-89fb-4a7f-afa9-d17810496768"  # DEV ONLY
DEV_CAMPAIGN_ID = "9646f98a-e987-4a8c-b786-9b82ea985d38"  # DEV ONLY

if os.environ.get("ENV", "").lower() == "production":
    raise RuntimeError("Hardcoded DEV identifiers detected in diagnose_supabase.py – aborting in production environment.")

load_dotenv()


def main():
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY')
    if not url or not key:
        print('SUPABASE_URL or SUPABASE_KEY not set in environment')
        return

    table = 'leads'
    endpoint = url.rstrip('/') + f'/rest/v1/{table}'
    headers = {
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation',
    }

    payload = [{
        'email': 'diag+test@example.com',
        'client_id': DEV_CLIENT_ID,
        'campaign_id': DEV_CAMPAIGN_ID,
        'first_name': 'Diag',  # added to satisfy NOT NULL
        'last_name': 'Tester',  # added to satisfy potential NOT NULL
        'company_name': 'DiagCo'  # newly added to satisfy NOT NULL for company_name
        ,'job_title': 'Tester'
        ,'phone_number': '+10000000000'
        ,'current_status': 'new'
        ,'sequence_step': 0
        ,'sequence_active': True
        ,'next_action_date': '2025-09-24T00:00:00Z'
        ,'last_contact_date': '2025-09-23T00:00:00Z'
        ,'booking_status': 'unbooked'
        ,'re_engagement_date': '2025-10-01T00:00:00Z'
    }]

    print('POST', endpoint)
    r = requests.post(endpoint, headers=headers, data=json.dumps(payload))
    print('status', r.status_code)
    try:
        print('body', r.json())
    except Exception:
        print('body (text)', r.text)


if __name__ == '__main__':
    main()
