"""
Workflow Progress Tracking Utilities

Enhanced workflow state tracking with multi-step progress, percentages, and step transitions.
Builds on top of existing workflow_state infrastructure in Redis.

Features:
- Multi-step progress tracking (RAG → Copy → Persist)
- Completion percentages
- Step transition timestamps
- Error tracking per step
- Exposed via health API and ops CLI

Usage:
    from core.utils.workflow_progress import WorkflowProgressTracker
    
    tracker = WorkflowProgressTracker(redis_client)
    
    # Start workflow
    tracker.start_workflow("workflow-123", steps=["rag", "copy", "persist"])
    
    # Update step progress
    tracker.update_step("workflow-123", "rag", status="in_progress")
    tracker.update_step("workflow-123", "rag", status="completed", result_count=10)
    
    # Get current progress
    progress = tracker.get_progress("workflow-123")
    # Returns: {"status": "in_progress", "progress": 33, "steps": {...}}
"""

import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum

from services.redis import config as rconf


class StepStatus(str, Enum):
    """Status values for workflow steps."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowStatus(str, Enum):
    """Overall workflow status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some steps completed, others failed


class WorkflowProgressTracker:
    """
    Enhanced workflow progress tracking with multi-step support.
    
    Data Model:
        workflow:state:{correlation_id} -> Hash with:
            - correlation_id: str
            - status: WorkflowStatus
            - progress: int (0-100)
            - total_steps: int
            - completed_steps: int
            - failed_steps: int
            - created_at: ISO timestamp
            - updated_at: ISO timestamp
            - steps: JSON string of step details
    
    Step Details:
        {
            "rag": {
                "status": "completed",
                "started_at": "2025-10-26T10:00:00Z",
                "completed_at": "2025-10-26T10:00:05Z",
                "duration_ms": 5000,
                "result_count": 10,
                "error": null
            },
            "copy": {
                "status": "in_progress",
                "started_at": "2025-10-26T10:00:06Z",
                "completed_at": null,
                "duration_ms": null,
                "error": null
            },
            ...
        }
    """
    
    def __init__(self, redis_client):
        """
        Initialize tracker with Redis client.
        
        Args:
            redis_client: Redis client instance (from RedisPubSub().client)
        """
        self.redis = redis_client
        self.enabled = rconf.WORKFLOW_STATE_ENABLED
    
    def _get_key(self, correlation_id: str) -> str:
        """Get Redis key for workflow state."""
        return rconf.full_key(rconf.workflow_state_key(correlation_id))
    
    def start_workflow(
        self,
        correlation_id: str,
        steps: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize a new workflow with defined steps.
        
        Args:
            correlation_id: Unique workflow identifier
            steps: List of step names (e.g., ["rag", "copy", "persist"])
            metadata: Optional metadata (tenant_id, campaign_id, etc.)
        
        Example:
            tracker.start_workflow("wf-123", steps=["rag", "copy", "persist"],
                                 metadata={"campaign_id": "camp-456"})
        """
        if not self.enabled:
            return
        
        # Initialize steps dictionary
        steps_data = {}
        for step_name in steps:
            steps_data[step_name] = {
                "status": StepStatus.PENDING,
                "started_at": None,
                "completed_at": None,
                "duration_ms": None,
                "result_count": None,
                "error": None
            }
        
        # Create workflow state
        now = datetime.utcnow().isoformat()
        state = {
            "correlation_id": correlation_id,
            "status": WorkflowStatus.PENDING,
            "progress": 0,
            "total_steps": len(steps),
            "completed_steps": 0,
            "failed_steps": 0,
            "created_at": now,
            "updated_at": now,
            "steps": json.dumps(steps_data)
        }
        
        # Add metadata
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    state[key] = str(value)
        
        # Store in Redis
        key = self._get_key(correlation_id)
        self.redis.hset(key, mapping=state)
        self.redis.expire(key, rconf.WORKFLOW_STATE_TTL)
    
    def update_step(
        self,
        correlation_id: str,
        step_name: str,
        status: str,
        result_count: Optional[int] = None,
        error: Optional[str] = None
    ) -> None:
        """
        Update progress of a specific workflow step.
        
        Args:
            correlation_id: Workflow identifier
            step_name: Name of the step to update (e.g., "rag", "copy")
            status: New status (pending|in_progress|completed|failed|skipped)
            result_count: Optional result count for this step
            error: Optional error message if step failed
        
        Example:
            # Start RAG step
            tracker.update_step("wf-123", "rag", status="in_progress")
            
            # Complete RAG step
            tracker.update_step("wf-123", "rag", status="completed", result_count=10)
            
            # Fail with error
            tracker.update_step("wf-123", "rag", status="failed", 
                              error="Database connection timeout")
        """
        if not self.enabled:
            return
        
        key = self._get_key(correlation_id)
        
        # Get current state
        state = self.redis.hgetall(key)
        if not state:
            return  # Workflow doesn't exist
        
        # Parse steps
        steps_data = json.loads(state.get("steps", "{}"))
        if step_name not in steps_data:
            return  # Step doesn't exist
        
        step_data = steps_data[step_name]
        now = datetime.utcnow().isoformat()
        
        # Update step status
        old_status = step_data["status"]
        step_data["status"] = status
        
        # Track timestamps
        if status == StepStatus.IN_PROGRESS and not step_data["started_at"]:
            step_data["started_at"] = now
        
        if status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED):
            if not step_data["completed_at"]:
                step_data["completed_at"] = now
            
            # Calculate duration
            if step_data["started_at"]:
                start_time = datetime.fromisoformat(step_data["started_at"])
                end_time = datetime.fromisoformat(now)
                duration_ms = int((end_time - start_time).total_seconds() * 1000)
                step_data["duration_ms"] = duration_ms
        
        # Store result count
        if result_count is not None:
            step_data["result_count"] = result_count
        
        # Store error
        if error:
            step_data["error"] = error
        
        steps_data[step_name] = step_data
        
        # Calculate overall progress
        completed_count = sum(1 for s in steps_data.values() 
                            if s["status"] == StepStatus.COMPLETED)
        failed_count = sum(1 for s in steps_data.values() 
                          if s["status"] == StepStatus.FAILED)
        total_steps = len(steps_data)
        
        # Calculate progress percentage
        if total_steps > 0:
            progress = int((completed_count / total_steps) * 100)
        else:
            progress = 0
        
        # Determine overall status
        if failed_count > 0 and completed_count > 0:
            overall_status = WorkflowStatus.PARTIAL
        elif failed_count > 0 and completed_count == 0:
            overall_status = WorkflowStatus.FAILED
        elif completed_count == total_steps:
            overall_status = WorkflowStatus.COMPLETED
        elif any(s["status"] == StepStatus.IN_PROGRESS for s in steps_data.values()):
            overall_status = WorkflowStatus.IN_PROGRESS
        else:
            overall_status = WorkflowStatus.PENDING
        
        # Update state
        updated_state = {
            "status": overall_status,
            "progress": progress,
            "completed_steps": completed_count,
            "failed_steps": failed_count,
            "updated_at": now,
            "steps": json.dumps(steps_data)
        }
        
        self.redis.hset(key, mapping=updated_state)
    
    def get_progress(self, correlation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current workflow progress.
        
        Args:
            correlation_id: Workflow identifier
        
        Returns:
            Dictionary with workflow state, or None if not found
        
        Example:
            progress = tracker.get_progress("wf-123")
            # Returns:
            # {
            #     "correlation_id": "wf-123",
            #     "status": "in_progress",
            #     "progress": 66,
            #     "total_steps": 3,
            #     "completed_steps": 2,
            #     "failed_steps": 0,
            #     "created_at": "...",
            #     "updated_at": "...",
            #     "steps": {
            #         "rag": {"status": "completed", ...},
            #         "copy": {"status": "completed", ...},
            #         "persist": {"status": "in_progress", ...}
            #     }
            # }
        """
        if not self.enabled:
            return None
        
        key = self._get_key(correlation_id)
        state = self.redis.hgetall(key)
        
        if not state:
            return None
        
        # Parse steps
        steps_data = json.loads(state.get("steps", "{}"))
        
        # Build response
        return {
            "correlation_id": state.get("correlation_id"),
            "status": state.get("status"),
            "progress": int(state.get("progress", 0)),
            "total_steps": int(state.get("total_steps", 0)),
            "completed_steps": int(state.get("completed_steps", 0)),
            "failed_steps": int(state.get("failed_steps", 0)),
            "created_at": state.get("created_at"),
            "updated_at": state.get("updated_at"),
            "steps": steps_data,
            # Include any additional metadata
            **{k: v for k, v in state.items() 
               if k not in ("steps", "correlation_id", "status", "progress", 
                           "total_steps", "completed_steps", "failed_steps",
                           "created_at", "updated_at")}
        }
    
    def list_active_workflows(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        List all active workflows (not completed/failed).
        
        Args:
            limit: Maximum number of workflows to return
        
        Returns:
            List of workflow progress dictionaries
        """
        if not self.enabled:
            return []
        
        # Scan for workflow state keys
        pattern = rconf.full_key("workflow:state:*")
        workflows = []
        
        for key in self.redis.scan_iter(match=pattern, count=limit):
            correlation_id = key.decode().split(":")[-1]
            progress = self.get_progress(correlation_id)
            
            if progress and progress["status"] in (WorkflowStatus.PENDING, WorkflowStatus.IN_PROGRESS):
                workflows.append(progress)
            
            if len(workflows) >= limit:
                break
        
        return workflows
    
    def get_step_metrics(self, step_name: str, limit: int = 100) -> Dict[str, Any]:
        """
        Get aggregated metrics for a specific step across all workflows.
        
        Args:
            step_name: Name of step to analyze (e.g., "rag", "copy")
            limit: Maximum workflows to analyze
        
        Returns:
            Dictionary with metrics:
            - total_count: Total workflows with this step
            - completed_count: Successfully completed
            - failed_count: Failed
            - avg_duration_ms: Average duration
            - p95_duration_ms: 95th percentile duration
        """
        if not self.enabled:
            return {}
        
        durations = []
        total = 0
        completed = 0
        failed = 0
        
        # Scan workflow states
        pattern = rconf.full_key("workflow:state:*")
        for key in self.redis.scan_iter(match=pattern, count=limit):
            state = self.redis.hgetall(key)
            if not state:
                continue
            
            steps_data = json.loads(state.get("steps", "{}"))
            if step_name not in steps_data:
                continue
            
            step_data = steps_data[step_name]
            total += 1
            
            if step_data["status"] == StepStatus.COMPLETED:
                completed += 1
                if step_data["duration_ms"]:
                    durations.append(step_data["duration_ms"])
            elif step_data["status"] == StepStatus.FAILED:
                failed += 1
        
        # Calculate metrics
        avg_duration = int(sum(durations) / len(durations)) if durations else None
        p95_duration = int(sorted(durations)[int(len(durations) * 0.95)]) if durations else None
        
        return {
            "step_name": step_name,
            "total_count": total,
            "completed_count": completed,
            "failed_count": failed,
            "success_rate": round(completed / total * 100, 2) if total > 0 else 0,
            "avg_duration_ms": avg_duration,
            "p95_duration_ms": p95_duration
        }
