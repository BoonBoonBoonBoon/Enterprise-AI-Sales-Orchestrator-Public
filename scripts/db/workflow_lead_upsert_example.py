"""Example script showing how a workflow/agent uses the new PersistenceAgent
instead of CampaignManager to persist a lead.

Usage:
    python scripts/workflow_lead_upsert_example.py

Requires SUPABASE_URL and SUPABASE_SERVICE_KEY (or SUPABASE_KEY) in environment.
Optional PERSIST_ALLOWED_TABLES to restrict tables (comma-separated).
"""
import os
import sys
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ensure repo root in path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.operational_agents.persistence_agent.persistence_agent import create_persistence_agent

lead_record = {
    'email': 'workflow+example@example.com',
    'client_id': '90fd5909-89fb-4a7f-afa9-d17810496768',
    'campaign_id': '9646f98a-e987-4a8c-b786-9b82ea985d38',
    'first_name': 'Flow',
    'last_name': 'Example',
    'company_name': 'FlowCo',
    'job_title': 'Ops Engineer',
    'phone_number': '+10000000000',
    'current_status': 'new',
    'sequence_step': 0,
    'sequence_active': True,
    'next_action_date': datetime.utcnow().date().isoformat() + 'T00:00:00Z',
    'last_contact_date': datetime.utcnow().date().isoformat() + 'T00:00:00Z',
    'booking_status': 'unbooked',
    're_engagement_date': '2030-01-01T00:00:00Z'
}


def main():
    try:
        agent = create_persistence_agent()
    except Exception as e:
        print('Failed to build persistence agent:', e)
        return
    try:
        res = agent.upsert('leads', lead_record, on_conflict=['email'])
        print(json.dumps(res, indent=2, default=str))
    except Exception as e:
        print('Upsert failed:', e)

if __name__ == '__main__':
    main()
