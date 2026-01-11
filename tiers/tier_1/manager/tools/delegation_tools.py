"""
Delegation Tools for Manager Agent

Tools that enable Manager to delegate tasks to specialist orchestrators.
Each tool enqueues tasks to Redis Streams for async processing.
"""

import json
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
import redis
import logging

from tiers.tier_1.manager.policy.router import stream_for
from core.envelope import task as create_task_envelope, to_redis_fields

logger = logging.getLogger(__name__)


class DelegationTools:
    """
    Collection of delegation tools for Manager Agent.
    Each tool corresponds to a specialist orchestrator.
    """
    
    def __init__(self, redis_client: redis.Redis, tenant_id: str = "default"):
        """
        Initialize delegation tools.
        
        Args:
            redis_client: Redis client for task enqueueing
            tenant_id: Tenant context for multi-tenant isolation
        """
        self.redis = redis_client
        self.tenant_id = tenant_id
        
        # NOTE: Manager is top-level entry point (no task stream needed)
        # Manager delegates DOWN to orchestrator-specific streams:
        #   - {tenant}:orchestrators:leads:tasks
        #   - {tenant}:orchestrators:outbound:tasks
        #   - {tenant}:orchestrators:control:tasks
        #   - {tenant}:orchestrators:{name}:tasks (future safe default)
    
    def delegate_to_coding_orchestrator(
        self,
        task: str,
        requirements: Optional[Dict[str, Any]] = None,
        priority: str = "medium"
    ) -> Dict[str, Any]:
        """
        Delegate coding/automation task to Coding Orchestrator.
        
        Use cases:
        - Script generation
        - Code refactoring
        - Automation workflows
        - Data processing pipelines
        
        Args:
            task: Description of coding task
            requirements: Technical requirements (language, framework, constraints)
            priority: Task priority (low, medium, high, urgent)
            
        Returns:
            Task metadata with task_id and stream info
        """
        task_id = str(uuid.uuid4())
        
        task_data = {
            "task": task,
            "requirements": requirements or {},
            "priority": priority,
            "tenant_id": self.tenant_id,
            "timestamp": datetime.now().isoformat(),
            "delegated_by": "manager_agent",
            "orchestrator": "coding",
        }
        
        # Create typed envelope
        envelope = create_task_envelope(
            source="manager_agent",
            task_id=task_id,
            payload=task_data,
            destination="coding_orchestrator",
            tenant_id=self.tenant_id
        )
        
        # Enqueue to Redis Stream (orchestrators namespace only)
        stream_name = stream_for(self.tenant_id, "coding")
        stream_id = self.redis.xadd(
            stream_name,
            to_redis_fields(envelope)
        )
        
        logger.info(f"Delegated coding task {task_id} to stream {stream_name}")
        
        return {
            "success": True,
            "task_id": task_id,
            "stream": stream_name,
            "stream_id": stream_id.decode() if isinstance(stream_id, bytes) else stream_id,
            "orchestrator": "coding",
            "message": f"Task delegated to Coding Orchestrator (task_id: {task_id})",
        }
    
    def delegate_to_data_orchestrator(
        self,
        query: str,
        dataset: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        priority: str = "medium"
    ) -> Dict[str, Any]:
        """
        Delegate data query/analysis task to Data Orchestrator.
        
        Use cases:
        - Lead searches
        - Campaign analytics
        - Report generation
        - Data exports
        
        Args:
            query: Natural language query or SQL-like expression
            dataset: Target dataset (leads, campaigns, interactions)
            filters: Additional filters (date ranges, status, etc.)
            priority: Task priority (low, medium, high, urgent)
            
        Returns:
            Task metadata with task_id and stream info
        """
        task_id = str(uuid.uuid4())
        
        task_data = {
            "query": query,
            "dataset": dataset,
            "filters": filters or {},
            "priority": priority,
            "tenant_id": self.tenant_id,
            "timestamp": datetime.now().isoformat(),
            "delegated_by": "manager_agent",
            "orchestrator": "data",
        }
        
        # Create typed envelope
        envelope = create_task_envelope(
            source="manager_agent",
            task_id=task_id,
            payload=task_data,
            destination="data_orchestrator",
            tenant_id=self.tenant_id
        )
        
        # Enqueue to Redis Stream (orchestrators namespace only)
        stream_name = stream_for(self.tenant_id, "data")
        stream_id = self.redis.xadd(
            stream_name,
            to_redis_fields(envelope)
        )
        
        logger.info(f"Delegated data task {task_id} to stream {stream_name}")
        
        return {
            "success": True,
            "task_id": task_id,
            "stream": stream_name,
            "stream_id": stream_id.decode() if isinstance(stream_id, bytes) else stream_id,
            "orchestrator": "data",
            "message": f"Task delegated to Data Orchestrator (task_id: {task_id})",
        }
    
    def delegate_to_api_orchestrator(
        self,
        endpoint: str,
        operation: str,
        parameters: Optional[Dict[str, Any]] = None,
        priority: str = "medium"
    ) -> Dict[str, Any]:
        """
        Delegate API integration task to API Orchestrator.
        
        Use cases:
        - CRM sync (HubSpot, Salesforce, etc.)
        - Webhook processing
        - Third-party API calls
        - OAuth flows
        
        Args:
            endpoint: API endpoint or integration name
            operation: Operation type (GET, POST, PUT, DELETE, SYNC)
            parameters: Request parameters or body
            priority: Task priority (low, medium, high, urgent)
            
        Returns:
            Task metadata with task_id and stream info
        """
        task_id = str(uuid.uuid4())
        
        task_data = {
            "endpoint": endpoint,
            "operation": operation,
            "parameters": parameters or {},
            "priority": priority,
            "tenant_id": self.tenant_id,
            "timestamp": datetime.now().isoformat(),
            "delegated_by": "manager_agent",
            "orchestrator": "api",
        }
        
        # Create typed envelope
        envelope = create_task_envelope(
            source="manager_agent",
            task_id=task_id,
            payload=task_data,
            destination="api_orchestrator",
            tenant_id=self.tenant_id
        )
        
        # Enqueue to Redis Stream (orchestrators namespace only)
        stream_name = stream_for(self.tenant_id, "api")
        stream_id = self.redis.xadd(
            stream_name,
            to_redis_fields(envelope)
        )
        
        logger.info(f"Delegated API task {task_id} to stream {stream_name}")
        
        return {
            "success": True,
            "task_id": task_id,
            "stream": stream_name,
            "stream_id": stream_id.decode() if isinstance(stream_id, bytes) else stream_id,
            "orchestrator": "api",
            "message": f"Task delegated to API Orchestrator (task_id: {task_id})",
        }
    
    def delegate_to_copywriter_orchestrator(
        self,
        lead_id: str,
        campaign_id: str,
        context: Optional[Dict[str, Any]] = None,
        priority: str = "medium"
    ) -> Dict[str, Any]:
        """
        Deprecated: Manager must route copywriting via Outreach/Outbound orchestrator.

        We keep this method to avoid breaking callers but refuse direct delegation
        to Tier 3 copywriter agents to enforce vertical-only comms.
        """
        raise ValueError(
            "Copywriter delegation is now routed via the outbound orchestrator; "
            "please call delegate_to_outreach_orchestrator instead."
        )
    
    def delegate_to_leads_orchestrator(
        self,
        goal: str,
        criteria: Optional[Dict[str, Any]] = None,
        priority: str = "medium"
    ) -> Dict[str, Any]:
        """
        Delegate lead discovery/qualification to Leads Orchestrator.
        
        Use cases:
        - Lead discovery from sources
        - Lead qualification scoring
        - Lead enrichment
        - List building
        
        Args:
            goal: Lead discovery goal (e.g., "Find 50 AI startups in SF")
            criteria: Search criteria (industry, location, size, etc.)
            priority: Task priority (low, medium, high, urgent)
            
        Returns:
            Task metadata with task_id and stream info
        """
        task_id = str(uuid.uuid4())
        
        task_data = {
            "goal": goal,
            "data": {
                "criteria": criteria or {},
                "requested_by": "manager_agent",
            },
            "priority": priority,
            "tenant_id": self.tenant_id,
            "timestamp": datetime.now().isoformat(),
            "delegated_by": "manager_agent",
            "orchestrator": "leads",
        }
        
        # Create typed envelope
        envelope = create_task_envelope(
            source="manager_agent",
            task_id=task_id,
            payload=task_data,
            destination="leads_orchestrator",
            tenant_id=self.tenant_id
        )
        
        # Enqueue to Leads stream
        leads_stream = stream_for(self.tenant_id, "leads")
        stream_id = self.redis.xadd(
            leads_stream,
            to_redis_fields(envelope)
        )
        
        logger.info(f"Delegated leads task {task_id} to stream {leads_stream}")
        
        return {
            "success": True,
            "task_id": task_id,
            "stream": leads_stream,
            "stream_id": stream_id.decode() if isinstance(stream_id, bytes) else stream_id,
            "orchestrator": "leads",
            "message": f"Task delegated to Leads Orchestrator (task_id: {task_id})",
        }
    
    def delegate_to_outreach_orchestrator(
        self,
        goal: str,
        campaign_data: Optional[Dict[str, Any]] = None,
        priority: str = "medium"
    ) -> Dict[str, Any]:
        """
        Delegate campaign orchestration to Outreach Orchestrator.
        
        Use cases:
        - Multi-channel campaign launch
        - Touchpoint sequencing
        - A/B test campaigns
        - Follow-up automation
        
        Args:
            goal: Campaign goal (e.g., "Launch Q4 enterprise outreach")
            campaign_data: Campaign details (leads, channels, touchpoints, etc.)
            priority: Task priority (low, medium, high, urgent)
            
        Returns:
            Task metadata with task_id and stream info
        """
        task_id = str(uuid.uuid4())
        
        task_data = {
            "goal": goal,
            "data": campaign_data or {},
            "priority": priority,
            "tenant_id": self.tenant_id,
            "timestamp": datetime.now().isoformat(),
            "delegated_by": "manager_agent",
            "orchestrator": "outreach",
        }
        
        # Create typed envelope
        envelope = create_task_envelope(
            source="manager_agent",
            task_id=task_id,
            payload=task_data,
            destination="outreach_orchestrator",
            tenant_id=self.tenant_id
        )
        
        # Enqueue to Outreach stream
        outreach_stream = stream_for(self.tenant_id, "outbound")
        stream_id = self.redis.xadd(
            outreach_stream,
            to_redis_fields(envelope)
        )
        
        logger.info(f"Delegated outreach task {task_id} to stream {outreach_stream}")
        
        return {
            "success": True,
            "task_id": task_id,
            "stream": outreach_stream,
            "stream_id": stream_id.decode() if isinstance(stream_id, bytes) else stream_id,
            "orchestrator": "outreach",
            "message": f"Task delegated to Outreach Orchestrator (task_id: {task_id})",
        }
    
    def check_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Check status of delegated task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task status and result (if completed)
        """
        # Query Redis for task status
        status_key = f"{self.tenant_id}:task:status:{task_id}"
        result_key = f"{self.tenant_id}:task:result:{task_id}"
        
        status = self.redis.get(status_key)
        result = self.redis.get(result_key)
        
        if not status:
            return {
                "success": False,
                "task_id": task_id,
                "error": "Task not found or expired",
            }
        
        status_data = {
            "success": True,
            "task_id": task_id,
            "status": status.decode() if isinstance(status, bytes) else status,
        }
        
        if result:
            try:
                result_data = json.loads(result.decode() if isinstance(result, bytes) else result)
                status_data["result"] = result_data
            except json.JSONDecodeError:
                status_data["result"] = result.decode() if isinstance(result, bytes) else result
        
        return status_data


# LangChain Tool Wrappers
# These can be imported and used directly with LangChain agents

from langchain.tools import tool


@tool
def delegate_coding_task(task: str, requirements: str = "") -> str:
    """
    Delegate coding/automation task to Coding Orchestrator.
    
    Use for: script generation, code refactoring, automation workflows.
    
    Args:
        task: Description of coding task
        requirements: JSON string with technical requirements
        
    Returns:
        Task delegation confirmation with task_id
    """
    # This will be initialized in ManagerAgent with proper Redis client
    # Placeholder implementation
    return f"Coding task would be delegated: {task}"


@tool
def delegate_data_query(query: str, dataset: str = "leads") -> str:
    """
    Delegate data query/analysis to Data Orchestrator.
    
    Use for: lead searches, campaign analytics, report generation.
    
    Args:
        query: Natural language query
        dataset: Target dataset (leads, campaigns, interactions)
        
    Returns:
        Task delegation confirmation with task_id
    """
    return f"Data query would be delegated: {query} on {dataset}"


@tool
def delegate_api_request(endpoint: str, operation: str, parameters: str = "{}") -> str:
    """
    Delegate API integration task to API Orchestrator.
    
    Use for: CRM sync, webhook processing, third-party API calls.
    
    Args:
        endpoint: API endpoint or integration name
        operation: Operation type (GET, POST, PUT, DELETE, SYNC)
        parameters: JSON string with request parameters
        
    Returns:
        Task delegation confirmation with task_id
    """
    return f"API request would be delegated: {operation} {endpoint}"


@tool
def delegate_email_generation(lead_id: str, campaign_id: str, context: str = "{}") -> str:
    """
    Delegate email generation to Copywriter Orchestrator.
    
    Use for: outreach emails, follow-up sequences, campaign personalization.
    
    Args:
        lead_id: Target lead identifier
        campaign_id: Campaign context
        context: JSON string with additional context
        
    Returns:
        Task delegation confirmation with task_id
    """
    return f"Email generation would be delegated for lead {lead_id} in campaign {campaign_id}"
