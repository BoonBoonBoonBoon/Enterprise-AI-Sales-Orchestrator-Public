import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

"""LEGACY SCRIPT (will be unified into ingest_cli.py soon)
Use `python scripts/ingest_cli.py --mode ingest` once available.
Retained temporarily for reference and comparison.
"""
 
# An end‑to‑end application flow test. 
# It runs through CampaignManager.ingest_event, mapping,
# required‑field validation, DBWriteAgent adapter, orchestrator dispatch, etc.
# Purpose: confirm your internal pipeline wiring and mapping logic.


# DEV WARNING:
# The client_id and campaign_id below are hardcoded for LOCAL DEVELOPMENT ONLY.
# NEVER ship hardcoded tenant/customer identifiers to production.
# In production these must be derived from authenticated context or payload.
DEV_CLIENT_ID = "90fd5909-89fb-4a7f-afa9-d17810496768"  # DEV ONLY
DEV_CAMPAIGN_ID = "9646f98a-e987-4a8c-b786-9b82ea985d38"  # DEV ONLY

if os.environ.get("ENV", "").lower() == "production":
    raise RuntimeError("Hardcoded DEV identifiers detected in mock_ingest.py – aborting in production environment.")

# ensure repo root is on sys.path so `import agent` works when running this script
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    load_dotenv()

    # Enable ingestion to DB for this test
    os.environ['INGEST_TO_DB'] = 'true'

    # Sample mock lead
    mock = {
        'email': 'test+ingest@example.com',
        'first_name': 'Test',
        'last_name': 'User',
        'company': 'ExampleCo',
        'job_title': 'QA Engineer',
        'phone': '+15555550123',
        'sequence_active': True,
        'sequence_step': 1,
        'current_status': 'new',
        'crm_id': 'crm-12345',
        'client_id': DEV_CLIENT_ID,
        'campaign_id': DEV_CAMPAIGN_ID
    }

    try:
        from agent.high_level_agents.control_layer.campaign_manager import CampaignManager
    except Exception as e:
        print('Failed to import CampaignManager:', e)
        return

    cm = CampaignManager()
    # register a minimal no-op orchestrator for the 'lead_sync' flow so ingest_event can dispatch
    from agent.high_level_agents.orchestrators.base_orchestrator import BaseOrchestrator

    class NoOpOrch(BaseOrchestrator):
        def run(self, request):
            return {'metadata': {'source': 'noop'}, 'records': []}

    cm.register_flow('lead_sync', NoOpOrch())

    print('Sending mock ingest event to CampaignManager...')
    res = cm.ingest_event({'flow': 'lead_sync', 'context': mock})
    print('Result:')
    print(json.dumps(res, indent=2, default=str))


if __name__ == '__main__':
    main()
