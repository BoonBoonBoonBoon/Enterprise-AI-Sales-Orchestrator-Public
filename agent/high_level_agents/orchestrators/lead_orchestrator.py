from typing import Any, Dict
from agent.high_level_agents.orchestrators.base_orchestrator import BaseOrchestrator


class LeadOrchestrator(BaseOrchestrator):
    """Domain orchestrator for lead-related flows.

    Responsibilities:
    - Accept prompts or envelopes related to lead discovery and enrichment.
    - Use registry to call operational agents (data_coordinator, rag_agent).
    - Return canonical envelope.
    """

    def run(self, request: Any) -> Dict[str, Any]:
        # fast-path: if the request is already an envelope, return it
        if self.validate_envelope(request):
            return request

        # minimal example: call rag_agent then return its envelope
        rag = self.get_agent('rag_agent')
        if rag:
            return rag({'prompt': request})

        raise RuntimeError('rag_agent not available in registry')


# TODOs for LeadOrchestrator
# - Validate input envelope and support fast-path when records exist (already present)
# - Implement domain-specific post-processing (normalize names, merge duplicates)
# - Enforce provenance enrichment: ensure every returned record has provenance
# - Add unit tests: happy-path (mock rag_agent), envelope passthrough, error handling
# - Consider caching layer for repeated lookups to reduce DB/LLM calls
