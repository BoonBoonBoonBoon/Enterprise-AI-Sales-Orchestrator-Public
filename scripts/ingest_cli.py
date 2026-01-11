import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Unified CLI for lead ingestion & diagnostics.
# Modes:
#   --mode diagnose : direct REST insert (Supabase PostgREST) to enumerate / test schema.
#   --mode ingest   : application path via CampaignManager.ingest_event.
# Includes dev guards; do not hardcode IDs in production.

DEV_CLIENT_ID = "90fd5909-89fb-4a7f-afa9-d17810496768"  # DEV ONLY
DEV_CAMPAIGN_ID = "9646f98a-e987-4a8c-b786-9b82ea985d38"  # DEV ONLY

if os.environ.get("ENV", "").lower() == "production":
    raise RuntimeError("Hardcoded DEV identifiers detected in ingest_cli.py – aborting in production environment.")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv()

REQUIRED_NOT_NULL = [
    'email','client_id','campaign_id','first_name','last_name','company_name','job_title',
    'phone_number','current_status','sequence_step','sequence_active','next_action_date',
    'last_contact_date','booking_status','re_engagement_date'
]

def build_full_mock(unique_suffix: str = ""):
    base_email = f'test+{unique_suffix}@example.com' if unique_suffix else 'test+unified@example.com'
    return {
        'email': base_email,
        'client_id': DEV_CLIENT_ID,
        'campaign_id': DEV_CAMPAIGN_ID,
        'first_name': 'Test',
        'last_name': 'User',
        'company_name': 'ExampleCo',
        'job_title': 'QA Engineer',
        'phone_number': '+15555550123',
        'current_status': 'new',
        'sequence_step': 0,
        'sequence_active': True,
        'next_action_date': datetime.utcnow().date().isoformat() + 'T00:00:00Z',
        'last_contact_date': datetime.utcnow().date().isoformat() + 'T00:00:00Z',
        'booking_status': 'unbooked',
        're_engagement_date': '2030-01-01T00:00:00Z'
    }


def mode_diagnose(args):
    import requests
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY')
    if not url or not key:
        print('Missing SUPABASE_URL or SUPABASE_KEY/SUPABASE_SERVICE_KEY')
        return 1
    payload = [build_full_mock(unique_suffix='diag')]
    endpoint = url.rstrip('/') + '/rest/v1/leads'
    headers = {
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation',
    }
    print('POST', endpoint)
    r = requests.post(endpoint, headers=headers, data=json.dumps(payload))
    print('status', r.status_code)
    try:
        print('body', r.json())
    except Exception:
        print('body(text)', r.text)
    return 0 if r.status_code in (200,201) else 2


def mode_ingest(args):
    from agent.high_level_agents.control_layer.campaign_manager import CampaignManager
    from agent.high_level_agents.orchestrators.base_orchestrator import BaseOrchestrator

    class NoOpOrch(BaseOrchestrator):
        def run(self, request):
            return {'metadata': {'source': 'noop'}, 'records': []}

    cm = CampaignManager()
    cm.register_flow('lead_sync', NoOpOrch())

    os.environ['INGEST_TO_DB'] = 'true'

    context = build_full_mock(unique_suffix='ingest')

    event = {'flow': 'lead_sync', 'context': context}
    res = cm.ingest_event(event)
    print(json.dumps(res, indent=2, default=str))
    # surface mismatch of required columns (if DB error didn't happen due to future schema changes)
    missing = [c for c in REQUIRED_NOT_NULL if c not in context]
    if missing:
        print('WARNING: context missing columns now required by schema:', missing)
    return 0 if res.get('status') in ('ok','queued') else 3


def main():
    parser = argparse.ArgumentParser(description='Unified ingestion/diagnostic CLI')
    parser.add_argument('--mode', choices=['diagnose','ingest'], required=True)
    args = parser.parse_args()

    if args.mode == 'diagnose':
        rc = mode_diagnose(args)
    else:
        rc = mode_ingest(args)
    sys.exit(rc)

if __name__ == '__main__':
    main()
