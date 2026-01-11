"""
Three-Tier Architecture Organization.

The agentic system is organized into three distinct tiers:

tier_1: Manager
  - Strategic decision making
  - Request delegation to orchestrators
  - System-wide coordination

tier_2: Orchestrators
  - Business logic orchestration
  - Coordination of multiple agents
  - Workflow management

tier_3: Operational Agents
  - Specialized operational tasks
  - Individual agent implementations
  - Task execution and result reporting
"""

__all__ = [
    "tier_1",
    "tier_2", 
    "tier_3",
]
