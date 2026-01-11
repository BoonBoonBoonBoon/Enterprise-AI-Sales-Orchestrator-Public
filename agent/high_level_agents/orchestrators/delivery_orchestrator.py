from typing import Any, Dict
from agent.high_level_agents.orchestrators.base_orchestrator import BaseOrchestrator


class DeliveryOrchestrator(BaseOrchestrator):
    """Orchestrator responsible for delivery flows.

    It should perform delivery gating and call the delivery operational agent
    when allowed.
    """

    def run(self, request: Any) -> Dict[str, Any]:
        if self.validate_envelope(request):
            env = request
        else:
            # placeholder behavior: fetch from rag_agent or raise
            rag = self.get_agent('rag_agent')
            if not rag:
                raise RuntimeError('rag_agent not available')
            env = rag({'prompt': request})

        # delivery gating should be enforced by CampaignManager; here we just
        # call the delivery tool if present
        delivery = self.get_agent('delivery')
        if delivery:
            return delivery(env)

        # if delivery not available, return envelope for audit
        return env


# TODOs for DeliveryOrchestrator
# - Enforce delivery policy: verify CampaignManager allow_delivery flag before calling delivery agent
# - Implement retry/backoff for delivery failures and idempotency key support
# - Add auditing hooks to persist delivery attempts and responses
# - Unit tests: delivery gating, successful delivery, delivery failure handling
