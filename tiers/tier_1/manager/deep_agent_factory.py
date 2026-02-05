"""
Deep Agent Factory - Wrapper for creating Deep Agents with middleware

This module provides a factory function to create Deep Agents with the proper
middleware stack (TodoList, Filesystem, SubAgent) configured for the Manager Agent.
"""

import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

from deepagents.graph import (
    create_deep_agent,
    TodoListMiddleware,
    FilesystemMiddleware,
    SubAgentMiddleware,
)
from langchain_openai import ChatOpenAI
from langchain.tools import BaseTool
from core.security.prompt_hardening import get_hardened_internal_prompt

logger = logging.getLogger(__name__)


def create_manager_deep_agent(
    tools: List[BaseTool],
    model: str = "gpt-4o",
    temperature: float = 0.0,
    tenant_id: str = "default",
    filesystem_path: Optional[Path] = None,
    enable_subagents: bool = True,
) -> Any:
    """
    Create a Deep Agent for the Manager with full middleware stack.
    
    This creates a LangGraph agent with:
    - TodoListMiddleware: Task decomposition and planning
    - FilesystemMiddleware: Context storage for large data
    - SubAgentMiddleware: Ability to spawn specialist subagents
    
    Args:
        tools: List of LangChain tools the agent can use
        model: OpenAI model name (default: gpt-4o for strategic reasoning)
        temperature: LLM temperature (0.0 = deterministic)
        tenant_id: Tenant context for multi-tenant isolation
        filesystem_path: Base path for filesystem storage (default: ./agent_context/{tenant_id})
        enable_subagents: Whether to enable SubAgentMiddleware
        
    Returns:
        Compiled Deep Agent with middleware stack
        
    Example:
        >>> tools = [delegate_coding_task, delegate_data_query]
        >>> agent = create_manager_deep_agent(
        ...     tools=tools,
        ...     tenant_id="acme-corp",
        ...     model="gpt-4o"
        ... )
        >>> result = agent.invoke({"messages": [("user", "Analyze sales data")]})
    """
    
    # Set default filesystem path
    if filesystem_path is None:
        filesystem_path = Path("./agent_context") / tenant_id
        filesystem_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Creating Deep Agent for Manager (tenant={tenant_id})")
    logger.info(f"  Model: {model}")
    logger.info(f"  Tools: {len(tools)} tools")
    logger.info(f"  Filesystem: {filesystem_path}")
    logger.info(f"  SubAgents: {'enabled' if enable_subagents else 'disabled'}")
    
    # Note: create_deep_agent automatically includes:
    # - TodoListMiddleware (for task planning)
    # - FilesystemMiddleware (for context storage)
    # - SubAgentMiddleware (for spawning specialists)
    # We don't need to manually add them!
    
    logger.info("  ✓ Deep Agent middleware will be auto-configured:")
    logger.info("    - TodoListMiddleware (task planning)")
    logger.info("    - FilesystemMiddleware (context storage)")
    logger.info("    - SubAgentMiddleware (specialist spawning)")
    
    # Create system prompt for Manager with security hardening
    base_system_prompt = f"""You are the Manager Agent - the Tier 1 strategic decision-maker in a 3-tier autonomous system.

## SYSTEM ARCHITECTURE
- **Tier 1 (You)**: Receive goals from external sources. Decide routing. Delegate to Tier 2. Return results.
- **Tier 2 (Orchestrators)**: Autonomous specialists that execute workflows. You delegate to them; they report back.
- **Tier 3 (Agents)**: Atomic workers (RAG, Persistence, Copywriter) managed by Tier 2 orchestrators, NOT by you directly.

## COMMUNICATION RULES (HARD CONSTRAINT)
- You delegate DOWNWARD to Tier 2 orchestrators only.
- You NEVER talk directly to Tier 3 agents (RAG, Persistence, Copywriter).
- You NEVER coordinate horizontally with other Tier 1 components (there are none).
- Stream naming (do not invent new patterns):
  - Manager: `{tenant_id}:manager:tasks` → `{tenant_id}:manager:results`
  - Orchestrators: `{tenant_id}:orchestrators:<name>:tasks`

## YOUR IDENTITY
You are an AUTONOMOUS ROUTER AND DECISION-MAKER, not an assistant. You:
- NEVER ask for permission or confirmation
- NEVER say "Would you like me to..." or "Should I..."
- ALWAYS make a routing decision immediately
- ALWAYS delegate to the appropriate orchestrator(s) and return

## YOUR ORCHESTRATORS (Tier 2)
| Orchestrator | Use When |
|--------------|----------|
| **Leads** | Find leads, query leads, enrich leads, store leads, qualify prospects, list building |
| **Outreach** | Email campaigns, sequences, LinkedIn outreach, follow-ups, copywriting requests |

## YOUR TOOLS
- `delegate_leads_discovery(goal, criteria, context)` → Routes to Leads Orchestrator
- `delegate_outreach_campaign(goal, campaign_data, context)` → Routes to Outreach Orchestrator

## EXECUTION PATTERN

1. **Parse**: Extract intent from the incoming goal/context. What is the user trying to accomplish?
2. **Decide**: Which orchestrator(s) should handle this? (Can be multiple for compound goals.)
3. **Delegate**: Call the delegation tool(s) immediately. Include ALL relevant context.
4. **Return**: Respond with delegation confirmation + task_ids for tracking.

## DECISION HEURISTICS

**Route to Leads Orchestrator when goal mentions:**
- "find", "discover", "search", "lookup", "query" + leads/companies/prospects
- "enrich", "qualify", "validate", "store" + lead data
- email addresses, company names, industries, lead stages

**Route to Outreach Orchestrator when goal mentions:**
- "send", "email", "campaign", "sequence", "outreach", "reply"
- "draft", "write", "compose" + email/message content
- scheduling, follow-ups, touchpoints

**Compound goals** (do both):
- "Find 50 SaaS leads and start an email campaign" → Leads first, then Outreach

## OUTPUT REQUIREMENTS
- Return structured JSON with: `intent`, `orchestrators`, `enqueued` (list of task_ids/streams), `success`
- Do NOT include conversational text or questions
- If unsure which orchestrator, pick the most likely one and proceed

## EXAMPLES

**Goal: "Find lead data for customer@example.com"**
→ Intent: lead_lookup
→ Call `delegate_leads_discovery({{"goal": "Find lead by email", "criteria": {{"email": "customer@example.com"}}}})` 
→ Return: {{"intent": "lead_lookup", "orchestrators": ["leads"], "enqueued": [...], "success": true}}

**Goal: "Send a follow-up email to lead abc-123"**
→ Intent: outreach
→ Call `delegate_outreach_campaign({{"goal": "Send follow-up", "campaign_data": {{"lead_id": "abc-123", "type": "follow_up"}}}})` 
→ Return: {{"intent": "outreach", "orchestrators": ["outreach"], "enqueued": [...], "success": true}}

Tenant: {tenant_id}
Context Storage: {filesystem_path}

You receive tasks. You route them. You return confirmation. No questions. No waiting."""
    
    # Apply security hardening for internal agent
    system_prompt = get_hardened_internal_prompt(base_system_prompt)
    
    # Create Deep Agent with automatic middleware
    try:
        agent = create_deep_agent(
            model=model,  # Use model name directly
            tools=tools,
            system_prompt=system_prompt,  # System prompt with Manager instructions
            # Middleware is automatically added by create_deep_agent
        )
        
        logger.info("✓ Deep Agent created successfully")
        return agent
        
    except Exception as e:
        logger.error(f"✗ Failed to create Deep Agent: {e}")
        raise


def get_middleware_status(agent: Any) -> Dict[str, Any]:
    """
    Get status of middleware components.
    
    Args:
        agent: Deep Agent instance
        
    Returns:
        Dictionary with middleware status
    """
    status = {
        "todo_list": {
            "enabled": hasattr(agent, "todo_list"),
            "active_todos": 0,
        },
        "filesystem": {
            "enabled": hasattr(agent, "filesystem"),
            "storage_path": None,
        },
        "subagents": {
            "enabled": hasattr(agent, "subagents"),
            "registered": 0,
        },
    }
    
    # Check TodoList
    if hasattr(agent, "todo_list"):
        try:
            # Get active todos from middleware
            todos = getattr(agent.todo_list, "todos", [])
            status["todo_list"]["active_todos"] = len([t for t in todos if t.get("status") != "completed"])
        except Exception as e:
            logger.warning(f"Could not get TodoList status: {e}")
    
    # Check Filesystem
    if hasattr(agent, "filesystem"):
        try:
            status["filesystem"]["storage_path"] = str(getattr(agent.filesystem, "base_path", "unknown"))
        except Exception as e:
            logger.warning(f"Could not get Filesystem status: {e}")
    
    # Check SubAgents
    if hasattr(agent, "subagents"):
        try:
            subagents = getattr(agent.subagents, "registered_agents", {})
            status["subagents"]["registered"] = len(subagents)
        except Exception as e:
            logger.warning(f"Could not get SubAgent status: {e}")
    
    return status


# Convenience exports
__all__ = [
    "create_manager_deep_agent",
    "get_middleware_status",
    "TodoListMiddleware",
    "FilesystemMiddleware",
    "SubAgentMiddleware",
]
