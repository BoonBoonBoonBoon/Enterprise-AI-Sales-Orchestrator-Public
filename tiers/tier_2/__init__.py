"""
Tier 2: Orchestrators - Business logic coordination layer.

Orchestrators are responsible for:
- Orchestrating complex workflows
- Coordinating multiple Tier 3 agents
- Managing business logic and sequencing
- Aggregating results from agents

Exported Orchestrators:
- LeadsOrchestrator: Lead management orchestration
- OutreachOrchestrator: Outreach campaign orchestration
- (Additional orchestrators can be added here)
"""

__all__ = [
    "leads_orchestrator",
    "outreach_orchestrator",
]
