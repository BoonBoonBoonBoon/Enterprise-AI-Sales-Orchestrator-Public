from typing import Any, Dict, Optional
from datetime import datetime, timezone
from agent.orchestration_agents.registry import Registry
from agent.orchestration_agents.base_orchestrator import BaseOrchestrator


class CampaignManager:
    """High-level control plane that schedules triggers, manages campaigns,
    and issues orchestration commands. This class subsumes a lightweight
    dispatcher: schedule/run/cancel flows and gate delivery.
    """

    def __init__(self, registry: Optional[Registry] = None, allow_delivery: bool = False, queue: Any = None):
        self.registry = registry or Registry()
        self.allow_delivery = allow_delivery
        self.runs = {}
        self.queue = queue  # optional async handoff; must implement enqueue(topic, message)

    def ingest_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Ingest an external event and decide whether to trigger workflows.

        Expected event keys: {'flow': 'lead_sync', 'context': {...}}
        Returns a run descriptor with run_id and status.
        """
        flow = event.get('flow')
        context = event.get('context', {})
        if not flow:
            return {'status': 'error', 'error': 'missing flow'}

        orchestrator = self.registry.get(flow)
        if not orchestrator:
            return {'status': 'error', 'error': f'unknown flow: {flow}'}

        run_id = f"{flow}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        self.runs[run_id] = {'status': 'running', 'flow': flow, 'started_at': datetime.now(timezone.utc).isoformat()}

        # If a queue is present, enqueue instead of immediate run (async path)
        if self.queue is not None:
            job = {
                'job_id': run_id,  # reuse run_id for simplicity
                'run_id': run_id,
                'orchestrator': flow,
                'payload': context,
                'meta': {'topic': 'orchestrate'}
            }
            try:
                self.queue.enqueue('orchestrate', job)
                self.runs[run_id]['status'] = 'queued'
                return {'status': 'queued', 'run_id': run_id, 'job_id': run_id}
            except Exception as e:
                self.runs[run_id]['status'] = 'failed'
                self.runs[run_id]['error'] = str(e)
                return {'status': 'error', 'run_id': run_id, 'error': str(e)}

        # Synchronous execution path
        try:
            result = orchestrator.run(context)
            self.runs[run_id]['status'] = 'finished'
            self.runs[run_id]['completed_at'] = datetime.now(timezone.utc).isoformat()
            if self.allow_delivery:
                pass  # placeholder for delivery integration
            return {'status': 'ok', 'run_id': run_id, 'result': result}
        except Exception as e:
            self.runs[run_id]['status'] = 'failed'
            self.runs[run_id]['error'] = str(e)
            return {'status': 'error', 'run_id': run_id, 'error': str(e)}

    def list_runs(self):
        return dict(self.runs)

    def register_flow(self, name: str, orchestrator: BaseOrchestrator):
        self.registry.register(name, orchestrator)


CONTROL_CLASS = CampaignManager
