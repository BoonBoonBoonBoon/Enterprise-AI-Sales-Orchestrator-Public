"""
Outreach Orchestrator - Tier 2 Deep Agent for Campaign Operations

This orchestrator manages outreach campaigns by coordinating:
- Copywriter agent (content generation)
- Booking agents (meeting scheduling)
- Channel sequencing (email, LinkedIn, phone)

Architecture:
- Layer 2: Deep Agent with TodoList, Filesystem, SubAgent middleware
- Layer 1: Wrapped in Agent Harness for production reliability
"""

import json
import os
import uuid
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path

import redis
from langchain.tools import tool
from deepagents import create_deep_agent
from core.envelope import task as create_task_envelope, to_redis_fields
from core.streams import assert_agents_stream

logger = logging.getLogger(__name__)


def _trace_log(actor: str, *, correlation_id: str, task_id: str, step: str, detail: str, **kwargs: Any) -> None:
    """Structured trace logging without extra infra."""
    try:
        payload = {
            "trace": True,
            "actor": actor,
            "correlation_id": correlation_id,
            "task_id": task_id,
            "step": step,
            "detail": detail,
            "timestamp": datetime.utcnow().isoformat(),
        }
        payload.update({k: v for k, v in kwargs.items() if v is not None})
        logger.info(json.dumps(payload))
    except Exception:
        pass


class OutreachOrchestrator:
    """
    Tier 2: Outreach Campaign Orchestrator (Deep Agent)
    
    Responsibilities:
    - Orchestrate multi-channel outreach campaigns
    - Generate personalized copy via Copywriter agent
    - Schedule meetings via Booking agents
    - Sequence touchpoints across channels (email, LinkedIn, phone)
    - Track campaign performance and optimize
    
    Tools vs Subagents:
    - Tools: Deterministic operations (validate campaign, schedule touchpoint, track metrics)
    - Subagents: Complex operations (copywriting, meeting booking, A/B testing)
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        tenant_id: str = "default",
        model: str = "gpt-4o-mini"
    ):
        """
        Initialize Outreach Orchestrator with Deep Agent.
        
        Args:
            redis_client: Redis client for task delegation
            tenant_id: Tenant context for multi-tenant isolation
            model: OpenAI model (gpt-4o-mini for cost efficiency)
        """
        self.redis = redis_client
        self.tenant_id = tenant_id
        self.model = model
        # Redis hash to persist auto-send metadata keyed by copywriter task_id
        self._auto_send_hash = f"{tenant_id}:outreach:auto_send"
        
        # Create Deep Agent with middleware
        self.agent = create_deep_agent(
            model=model,
            system_prompt=self._get_system_prompt(),
            tools=self._build_tools()
        )
        # TodoListMiddleware, FilesystemMiddleware, SubAgentMiddleware auto-configured
        
        logger.info(f"OutreachOrchestrator initialized (tenant={tenant_id}, model={model})")
    
    def _get_system_prompt(self) -> str:
        """System prompt defining Outreach Orchestrator role and decision framework"""
        return f"""You are the Outreach Orchestrator - a Tier 2 autonomous agent in a 3-tier event-driven system.

## SYSTEM ARCHITECTURE
- **Tier 1 (Manager)**: Assigns you goals via Redis Streams. You report results back.
- **Tier 2 (You)**: Autonomous orchestrator for outreach/campaign operations. You plan, execute, and complete tasks independently.
- **Tier 3 (Agents)**: Specialist workers you delegate to: Copywriter (content), Scheduler/Booking (meetings), Channel Sequencer (optimization).

## COMMUNICATION RULES (HARD CONSTRAINT)
- **Vertical only**: You may communicate UPWARD to Tier 1 (via your result payload) and DOWNWARD to Tier 3 agents (via your delegation tools).
- **No horizontal comms**: You MUST NOT coordinate with other Tier 2 orchestrators (e.g., Leads Orchestrator) directly.
- **Stream naming** (do not invent new patterns):
  - Manager: `{self.tenant_id}:manager:tasks` → `{self.tenant_id}:manager:results`
  - Orchestrators: `{self.tenant_id}:orchestrators:outbound:tasks` → `{self.tenant_id}:orchestrators:outbound:results`
  - Agents: `{self.tenant_id}:agents:<agent_name>:tasks` → `{self.tenant_id}:agents:<agent_name>:results`

## YOUR IDENTITY
You are an AUTONOMOUS EXECUTOR, not an assistant. You:
- NEVER ask for permission or confirmation
- NEVER say "Would you like me to..." or "Should I..."
- ALWAYS take action immediately based on the goal
- ALWAYS complete the full task before returning results

## YOUR TOOLS

**Campaign Operations (execute directly):**
- `validate_campaign_tool(campaign_data)` - Check campaign structure and required fields
- `create_touchpoint_tool(touchpoint_data)` - Create a single outreach touchpoint
- `schedule_touchpoint_tool(touchpoint_id, schedule)` - Schedule when a touchpoint fires
- `query_campaign_metrics_tool(campaign_id, filters)` - Get open rates, replies, conversions
- `update_campaign_status_tool(campaign_id, status)` - Pause, resume, or complete campaigns

**Tier 3 Delegation (for complex operations):**
- `delegate_to_copywriter_tool(copy_request)` - Generate personalized email/SMS/LinkedIn copy
- `delegate_to_scheduler_agent_tool(booking_request)` - Book meetings, manage calendars
- `delegate_to_channel_sequencer_agent_tool(sequence_request)` - Optimize multi-channel sequences

## EXECUTION PATTERN

1. **Analyze**: Parse the goal and context. What campaign action is needed?
2. **Plan**: For multi-step campaigns, break into touchpoints. For simple requests, skip planning.
3. **Execute**: Call tools immediately. Do NOT describe what you will do - just do it.
4. **Delegate**: If copy generation is needed, call `delegate_to_copywriter_tool` with full context.
5. **Complete**: Return a structured result with:
   - What was accomplished
   - Touchpoints created/scheduled
   - Copy generated (if applicable)
   - Next recommended actions

## CHANNEL STRATEGY
| Channel | When | Typical Timing |
|---------|------|----------------|
| Email | First touch, follow-ups, re-engagement | Day 0, Day 10 |
| LinkedIn | Professional context, warm intro | Day 3 (if email opened) |
| Phone | High-touch, booking-focused | Day 7 (if engaged but no reply) |

## OUTPUT REQUIREMENTS
- Return JSON-structured results when possible
- Do not ask the user questions - if multiple approaches exist, choose one and proceed
- Include `next_actions` list for downstream systems

## EXAMPLES

**Goal: "Draft a cold email for lead abc-123"**
→ Call `delegate_to_copywriter_tool({{"lead_id": "abc-123", "type": "cold_email", "tone": "professional"}})`
→ Return {{"copy_generated": true, "lead_id": "abc-123", "type": "cold_email", "status": "delegated"}}

**Goal: "Start a 3-touch sequence for campaign camp-456"**
→ Call `validate_campaign_tool({{"campaign_id": "camp-456"}})`
→ Call `create_touchpoint_tool(...)` for email (Day 0)
→ Call `create_touchpoint_tool(...)` for LinkedIn (Day 3)
→ Call `create_touchpoint_tool(...)` for phone (Day 7)
→ Call `schedule_touchpoint_tool(...)` for each
→ Return {{"campaign_id": "camp-456", "touchpoints_created": 3, "scheduled": true}}

**Goal: "Reply to inbound email from customer@example.com"**
→ Call `delegate_to_copywriter_tool({{"type": "reply", "context": {{...email_event...}}}})` 
→ Return {{"reply_drafted": true, "status": "delegated_to_copywriter"}}

## CONSTRAINTS
- Tenant isolation: All operations scoped to `{self.tenant_id}`
- No external API calls directly - delegate to appropriate agents
- Copywriter handles ALL content generation (emails, subject lines, LinkedIn messages)

You receive tasks from Manager (Tier 1). Execute autonomously and return results. Never wait for approval."""
    
    def _build_tools(self) -> List:
        """Build all tools (deterministic + delegation)"""
        return [
            # Deterministic tools (simple operations)
            self._create_validate_campaign_tool(),
            self._create_create_touchpoint_tool(),
            self._create_schedule_touchpoint_tool(),
            self._create_query_campaign_metrics_tool(),
            self._create_update_campaign_status_tool(),
            
            # Subagent delegation tools (complex operations)
            self._create_delegate_to_copywriter_tool(),
            self._create_delegate_to_scheduler_agent_tool(),
            self._create_delegate_to_channel_sequencer_agent_tool(),
        ]

    # ==================== DELEGATION HELPERS ====================

    def _enqueue_copywriter(self, copy_request: dict) -> dict:
        """Enqueue a copywriting request to the Copywriter agent stream."""
        task_id = f"copy-{uuid.uuid4()}"

        payload = {
            "tenant_id": self.tenant_id,
            "campaign_id": copy_request.get("campaign_id", ""),
            "lead_id": copy_request.get("lead_id", ""),
            # CopywriterAgent expects `type` (email/sms). Keep `channel` for downstream correlation.
            "type": copy_request.get("channel", "email"),
            "channel": copy_request.get("channel", "email"),
            "tone": copy_request.get("tone", "professional"),
            "goal": copy_request.get("goal", "book_meeting"),
            "context": copy_request.get("context", {}),
            "operation": "generate_copy",
            "delegated_by": "outreach_orchestrator",
            "timestamp": datetime.utcnow().isoformat(),
        }

        envelope = create_task_envelope(
            source="outreach_orchestrator",
            task_id=task_id,
            payload=payload,
            destination="copywriter",
            tenant_id=self.tenant_id,
        )

        stream = f"{self.tenant_id}:agents:copywriter:tasks"
        assert_agents_stream(stream)
        self.redis.xadd(
            stream,
            to_redis_fields(envelope),
        )

        logger.info(
            f"Enqueued copy generation: {task_id} for campaign {copy_request.get('campaign_id')}"
        )

        corr = copy_request.get("correlation_id") or copy_request.get("task_id") or task_id
        _trace_log(
            "outreach",
            correlation_id=corr,
            task_id=task_id,
            step="delegated",
            detail="delegate_to_copywriter",
            stream=stream,
        )

        return {
            "task_id": task_id,
            "status": "enqueued",
            "delegated_to": "copywriter_agent",
            "message": "Copywriter will generate personalized copy asynchronously",
        }

    def _enqueue_scheduler(self, booking_request: dict) -> dict:
        """Enqueue a meeting scheduling request to the booking stream."""
        task_id = f"scheduler-{uuid.uuid4()}"

        duration_minutes = booking_request.get("duration_minutes", 30)
        start_raw = (booking_request.get("preferred_times") or [None])[0]
        if start_raw:
            start_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
        else:
            start_dt = datetime.utcnow() + timedelta(minutes=60)
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        payload = {
            "tenant_id": self.tenant_id,
            "event_title": booking_request.get("meeting_type", "discovery_call"),
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat(),
            "attendees": booking_request.get("attendees", []),
            "provider": booking_request.get("provider", "google"),
            "description": booking_request.get("context", ""),
            "location": booking_request.get("location", booking_request.get("calendar_link")),
            "conference_link": booking_request.get("conference_link"),
            "lead_id": booking_request.get("lead_id"),
            "campaign_id": booking_request.get("campaign_id"),
            "delegated_by": "outreach_orchestrator",
            "operation": "schedule_meeting",
        }

        envelope = create_task_envelope(
            source="outreach_orchestrator",
            task_id=task_id,
            payload=payload,
            destination="booking",
            tenant_id=self.tenant_id,
        )

        stream = f"{self.tenant_id}:agents:booking:tasks"
        assert_agents_stream(stream)
        self.redis.xadd(
            stream,
            to_redis_fields(envelope),
        )

        logger.info(
            "Enqueued scheduler request",
            extra={"task_id": task_id, "lead_id": booking_request.get("lead_id")},
        )

        corr = booking_request.get("correlation_id") or booking_request.get("task_id") or task_id
        _trace_log(
            "outreach",
            correlation_id=corr,
            task_id=task_id,
            step="delegated",
            detail="delegate_to_booking",
            stream=stream,
        )

        return {
            "task_id": task_id,
            "status": "enqueued",
            "delegated_to": "booking",
            "message": "Booking stream will coordinate meeting scheduling asynchronously",
        }

    def _enqueue_sequencing(self, optimization_request: dict) -> dict:
        """Enqueue a sequencing request to the sequencing stream."""
        task_id = f"sequence-{uuid.uuid4()}"

        raw_steps = optimization_request.get("current_sequence") or optimization_request.get("steps") or []
        normalized_steps = []
        for step in raw_steps:
            delay_minutes = step.get("delay_minutes")
            if delay_minutes is None and "delay_days" in step:
                delay_minutes = int(step.get("delay_days", 0)) * 24 * 60
            normalized_steps.append(
                {
                    "channel": step.get("channel", "email"),
                    "to_email": step.get("to_email"),
                    "subject": step.get("subject"),
                    "body": step.get("body"),
                    "from_email": step.get("from_email"),
                    "template_id": step.get("template_id"),
                    "delay_minutes": delay_minutes or 0,
                    "metadata": step.get("metadata", {}),
                }
            )

        payload = {
            "tenant_id": self.tenant_id,
            "lead_id": optimization_request.get("lead_id"),
            "steps": normalized_steps,
            "context": {
                "campaign_id": optimization_request.get("campaign_id"),
                "optimization_goal": optimization_request.get("optimization_goal", "maximize_reply_rate"),
                "constraints": optimization_request.get("constraints", {}),
            },
            "operation": "build_sequence",
            "delegated_by": "outreach_orchestrator",
        }

        envelope = create_task_envelope(
            source="outreach_orchestrator",
            task_id=task_id,
            payload=payload,
            destination="sequencing",
            tenant_id=self.tenant_id,
        )

        stream = f"{self.tenant_id}:agents:sequencing:tasks"
        assert_agents_stream(stream)
        self.redis.xadd(
            stream,
            to_redis_fields(envelope),
        )

        logger.info(
            "Enqueued channel sequencing request",
            extra={"task_id": task_id, "campaign_id": optimization_request.get("campaign_id")},
        )

        corr = (
            optimization_request.get("correlation_id")
            or optimization_request.get("task_id")
            or task_id
        )
        _trace_log(
            "outreach",
            correlation_id=corr,
            task_id=task_id,
            step="delegated",
            detail="delegate_to_sequencer",
            stream=stream,
        )

        return {
            "task_id": task_id,
            "status": "enqueued",
            "delegated_to": "sequencing",
            "message": "Sequencing stream will optimize touchpoints asynchronously",
        }

    def _register_auto_send(self, *, copy_task_id: str, reply_packet: dict, copy_req: dict) -> None:
        """Persist auto-send routing details keyed by copywriter task_id."""
        try:
            inbound = (reply_packet or {}).get("inbound_email_event") or {}
            to_email = inbound.get("from")
            # IMPORTANT: Gmail SMTP authenticates as the sending mailbox (username).
            # Inbound events often have a synthetic/alias recipient (e.g. support@example.com).
            # If we use that as the SMTP username, Gmail rejects with 535 BadCredentials.
            configured_sender = (os.getenv("GMAIL_SENDER_EMAIL") or "").strip()
            inbound_to = (inbound.get("to") or "").strip()
            from_email = configured_sender or inbound_to or None
            subject_fallback = inbound.get("subject")

            payload = {
                "copy_task_id": copy_task_id,
                "tenant_id": self.tenant_id,
                "lead_id": copy_req.get("lead_id"),
                "campaign_id": copy_req.get("campaign_id"),
                "to_email": to_email,
                "from_email": from_email,
                "subject_fallback": subject_fallback,
                "reply_packet": reply_packet,
            }

            self.redis.client.hset(self._auto_send_hash, copy_task_id, json.dumps(payload))
            _trace_log(
                "outreach",
                correlation_id=copy_task_id,
                task_id=copy_task_id,
                step="register_auto_send",
                detail="stored copywriter auto-send context",
            )
        except Exception:
            logger.exception("Failed to register auto-send context; continuing without auto-send")
    
    # ==================== DETERMINISTIC TOOLS ====================
    
    def _create_validate_campaign_tool(self):
        """Tool for validating campaign structure and configuration"""
        
        @tool
        def validate_campaign_tool(campaign_config: dict) -> dict:
            """
            Validate campaign structure and configuration.
            
            This is a DETERMINISTIC operation - no AI reasoning needed.
            
            Args:
                campaign_config: Campaign configuration with leads, channels, timing
            
            Returns:
                {"valid": bool, "errors": list, "warnings": list}
            
            Example:
                campaign_config = {
                    "name": "Q4 Enterprise Outreach",
                    "leads": ["lead-123", "lead-456"],
                    "channels": ["email", "linkedin", "phone"],
                    "touchpoints": [
                        {"channel": "email", "delay_days": 0},
                        {"channel": "linkedin", "delay_days": 3},
                        {"channel": "phone", "delay_days": 7}
                    ]
                }
            """
            errors = []
            warnings = []
            
            # Check required fields
            required_fields = ["name", "leads", "channels", "touchpoints"]
            for field in required_fields:
                if field not in campaign_config:
                    errors.append(f"Missing required field: {field}")
            
            # Validate leads
            if "leads" in campaign_config:
                if not isinstance(campaign_config["leads"], list):
                    errors.append("'leads' must be a list")
                elif len(campaign_config["leads"]) == 0:
                    errors.append("Campaign must have at least one lead")
                elif len(campaign_config["leads"]) > 10000:
                    warnings.append(f"Large campaign ({len(campaign_config['leads'])} leads) - consider batching")
            
            # Validate channels
            valid_channels = {"email", "linkedin", "phone", "sms"}
            if "channels" in campaign_config:
                if not isinstance(campaign_config["channels"], list):
                    errors.append("'channels' must be a list")
                else:
                    for channel in campaign_config["channels"]:
                        if channel not in valid_channels:
                            errors.append(f"Invalid channel: {channel}")
            
            # Validate touchpoints
            if "touchpoints" in campaign_config:
                if not isinstance(campaign_config["touchpoints"], list):
                    errors.append("'touchpoints' must be a list")
                elif len(campaign_config["touchpoints"]) == 0:
                    warnings.append("Campaign has no touchpoints defined")
                else:
                    for i, tp in enumerate(campaign_config["touchpoints"]):
                        if "channel" not in tp:
                            errors.append(f"Touchpoint {i} missing 'channel'")
                        if "delay_days" not in tp:
                            errors.append(f"Touchpoint {i} missing 'delay_days'")
            
            # Check touchpoint timing (recommended best practices)
            if "touchpoints" in campaign_config and len(campaign_config["touchpoints"]) > 0:
                delays = [tp.get("delay_days", 0) for tp in campaign_config["touchpoints"]]
                if delays != sorted(delays):
                    warnings.append("Touchpoints should be ordered by delay_days")
                
                # Check for too-aggressive timing
                if len(delays) > 1:
                    gaps = [delays[i+1] - delays[i] for i in range(len(delays)-1)]
                    if any(gap < 2 for gap in gaps):
                        warnings.append("Touchpoints less than 2 days apart may feel spammy")
            
            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "checked_at": datetime.utcnow().isoformat() + "Z"
            }
        
        return validate_campaign_tool
    
    def _create_create_touchpoint_tool(self):
        """Tool for creating a touchpoint in a campaign"""
        
        @tool
        def create_touchpoint_tool(touchpoint_data: dict) -> dict:
            """
            Create a touchpoint in an outreach campaign.
            
            Args:
                touchpoint_data: Touchpoint configuration
            
            Returns:
                {"touchpoint_id": str, "status": str}
            
            Example:
                touchpoint_data = {
                    "campaign_id": "camp-123",
                    "lead_id": "lead-456",
                    "channel": "email",
                    "content": "Hi {{first_name}}, ...",
                    "subject": "Quick question about {{company}}",
                    "scheduled_for": "2025-11-10T10:00:00Z"
                }
            """
            # Validate required fields
            required = ["campaign_id", "lead_id", "channel", "content"]
            missing = [f for f in required if f not in touchpoint_data]
            if missing:
                return {
                    "status": "error",
                    "error": f"Missing required fields: {missing}"
                }
            
            # Create touchpoint
            touchpoint_id = f"touchpoint-{uuid.uuid4()}"
            
            # In real implementation, this would write to database
            logger.info(
                f"Created touchpoint {touchpoint_id}: "
                f"campaign={touchpoint_data['campaign_id']}, "
                f"lead={touchpoint_data['lead_id']}, "
                f"channel={touchpoint_data['channel']}"
            )
            
            return {
                "touchpoint_id": touchpoint_id,
                "campaign_id": touchpoint_data["campaign_id"],
                "lead_id": touchpoint_data["lead_id"],
                "channel": touchpoint_data["channel"],
                "status": "created",
                "created_at": datetime.utcnow().isoformat() + "Z"
            }
        
        return create_touchpoint_tool
    
    def _create_schedule_touchpoint_tool(self):
        """Tool for scheduling a touchpoint for delivery"""
        
        @tool
        def schedule_touchpoint_tool(
            touchpoint_id: str,
            scheduled_for: str,
            priority: str = "normal"
        ) -> dict:
            """
            Schedule a touchpoint for delivery at a specific time.
            
            Args:
                touchpoint_id: Touchpoint to schedule
                scheduled_for: ISO timestamp for delivery
                priority: Priority level (low, normal, high, urgent)
            
            Returns:
                {"status": str, "scheduled_for": str}
            
            Example:
                schedule_touchpoint_tool(
                    "touchpoint-123",
                    "2025-11-10T10:00:00Z",
                    "high"
                )
            """
            valid_priorities = {"low", "normal", "high", "urgent"}
            if priority not in valid_priorities:
                return {
                    "status": "error",
                    "error": f"Invalid priority: {priority}"
                }
            
            try:
                # Parse timestamp
                scheduled_dt = datetime.fromisoformat(scheduled_for.replace("Z", "+00:00"))
                
                # Check if in past
                if scheduled_dt < datetime.utcnow():
                    return {
                        "status": "error",
                        "error": "Cannot schedule touchpoint in the past"
                    }
                
                # In real implementation, this would queue to delivery system
                logger.info(
                    f"Scheduled touchpoint {touchpoint_id} for {scheduled_for}, "
                    f"priority={priority}"
                )
                
                return {
                    "touchpoint_id": touchpoint_id,
                    "status": "scheduled",
                    "scheduled_for": scheduled_for,
                    "priority": priority,
                    "scheduled_at": datetime.utcnow().isoformat() + "Z"
                }
                
            except Exception as e:
                return {
                    "status": "error",
                    "error": str(e)
                }
        
        return schedule_touchpoint_tool
    
    def _create_query_campaign_metrics_tool(self):
        """Tool for querying campaign performance metrics"""
        
        @tool
        def query_campaign_metrics_tool(campaign_id: str) -> dict:
            """
            Query performance metrics for a campaign.
            
            Args:
                campaign_id: Campaign to query
            
            Returns:
                Campaign metrics (sent, opened, clicked, replied, booked)
            
            Example:
                metrics = query_campaign_metrics_tool("camp-123")
                # Returns:
                {
                    "campaign_id": "camp-123",
                    "touchpoints_sent": 150,
                    "opened": 75,
                    "clicked": 20,
                    "replied": 10,
                    "meetings_booked": 3,
                    "open_rate": 0.50,
                    "click_rate": 0.133,
                    "reply_rate": 0.067,
                    "booking_rate": 0.02
                }
            """
            # In real implementation, this would query analytics database
            # For now, return mock metrics
            
            logger.info(f"Querying metrics for campaign {campaign_id}")
            
            return {
                "campaign_id": campaign_id,
                "touchpoints_sent": 0,
                "opened": 0,
                "clicked": 0,
                "replied": 0,
                "meetings_booked": 0,
                "open_rate": 0.0,
                "click_rate": 0.0,
                "reply_rate": 0.0,
                "booking_rate": 0.0,
                "last_updated": datetime.utcnow().isoformat() + "Z",
                "note": "Real metrics would come from analytics database"
            }
        
        return query_campaign_metrics_tool
    
    def _create_update_campaign_status_tool(self):
        """Tool for updating campaign status"""
        
        @tool
        def update_campaign_status_tool(
            campaign_id: str,
            status: str,
            reason: str = ""
        ) -> dict:
            """
            Update campaign status (active, paused, completed, cancelled).
            
            Args:
                campaign_id: Campaign to update
                status: New status
                reason: Reason for status change
            
            Returns:
                {"status": str, "updated_at": str}
            
            Example:
                update_campaign_status_tool(
                    "camp-123",
                    "paused",
                    "Low open rates - need to revise copy"
                )
            """
            valid_statuses = {"draft", "active", "paused", "completed", "cancelled"}
            if status not in valid_statuses:
                return {
                    "status": "error",
                    "error": f"Invalid status: {status}",
                    "valid_statuses": list(valid_statuses)
                }
            
            # In real implementation, this would update database
            logger.info(
                f"Updated campaign {campaign_id} status to {status}, "
                f"reason: {reason}"
            )
            
            return {
                "campaign_id": campaign_id,
                "status": status,
                "reason": reason,
                "updated_at": datetime.utcnow().isoformat() + "Z"
            }
        
        return update_campaign_status_tool
    
    # ==================== DELEGATION TOOLS ====================
    
    def _create_delegate_to_copywriter_tool(self):
        """Tool for delegating copy generation to Copywriter agent"""
        
        @tool
        def delegate_to_copywriter_tool(
            copy_request: dict
        ) -> dict:
            """
            Delegate copy generation to Copywriter agent.
            
            Args:
                copy_request: Copy generation request
            
            Returns:
                {"task_id": str, "status": "enqueued"}
            
            Example:
                copy_request = {
                    "campaign_id": "camp-123",
                    "lead_id": "lead-456",
                    "channel": "email",
                    "tone": "professional",
                    "goal": "book_meeting",
                    "context": {
                        "lead_name": "John Doe",
                        "company": "Acme Corp",
                        "industry": "SaaS"
                    }
                }
            """
            try:
                return self._enqueue_copywriter(copy_request)
            except Exception as e:
                logger.error(f"Copywriter delegation failed: {e}")
                return {
                    "status": "error",
                    "error": str(e)
                }
        
        return delegate_to_copywriter_tool
    
    def _create_delegate_to_scheduler_agent_tool(self):
        """Tool for delegating meeting scheduling to SchedulerAgent."""

        @tool
        def delegate_to_scheduler_agent_tool(booking_request: dict) -> dict:
            """Delegate meeting scheduling to SchedulerAgent via Redis stream."""
            try:
                return self._enqueue_scheduler(booking_request)
            except Exception as e:
                logger.error(f"Scheduler delegation failed: {e}")
                return {"status": "error", "error": str(e)}

        return delegate_to_scheduler_agent_tool
    
    def _create_delegate_to_channel_sequencer_agent_tool(self):
        """Tool for delegating channel sequencing to ChannelSequencerAgent."""

        @tool
        def delegate_to_channel_sequencer_agent_tool(optimization_request: dict) -> dict:
            """Delegate channel sequencing to the sequencing stream."""
            try:
                return self._enqueue_sequencing(optimization_request)
            except Exception as e:
                logger.error(f"Channel sequencing delegation failed: {e}")
                return {"status": "error", "error": str(e)}

        return delegate_to_channel_sequencer_agent_tool
    
    # ==================== EXECUTION ====================
    
    async def execute(self, task_data: Any) -> Dict[str, Any]:
        """
        Execute outreach orchestration task.
        
        Args:
            task_data: Task with "goal" and optional "data"
        
        Returns:
            Execution result
        """
        # Deterministic-first delegation path (E2E-friendly, avoids LLM dependency)
        if isinstance(task_data, dict):
            inner_payload = task_data.get("payload") if isinstance(task_data.get("payload"), dict) else {}
            delegations = inner_payload.get("delegations") if isinstance(inner_payload, dict) else None
            reply_packet = inner_payload.get("reply_packet") if isinstance(inner_payload, dict) else task_data.get("reply_packet")

            # If Manager chained a reply_packet, delegate directly to Copywriter.
            if isinstance(reply_packet, dict):
                auto_send = bool(inner_payload.get("auto_send") or task_data.get("auto_send") or True)
                copy_req = {
                    "channel": "email",
                    "type": "reply",
                    "tone": "concise",
                    "goal": "craft_reply",
                    "context": {
                        "reply_packet": reply_packet,
                        "upstream": task_data.get("upstream") or (inner_payload.get("upstream") if isinstance(inner_payload, dict) else None),
                    },
                }
                result = self._enqueue_copywriter(copy_req)
                if auto_send:
                    self._register_auto_send(copy_task_id=result["task_id"], reply_packet=reply_packet, copy_req=copy_req)
                return {
                    "status": "enqueued",
                    "delegations": {"copywriter": result},
                    "message": "Reply packet forwarded to Copywriter",
                    "auto_send": auto_send,
                }

            if isinstance(delegations, dict) and delegations:
                results: Dict[str, Any] = {}
                if isinstance(delegations.get("copywriter"), dict):
                    cw_req = delegations["copywriter"]
                    results["copywriter"] = self._enqueue_copywriter(cw_req)
                    if cw_req.get("auto_send"):
                        reply_packet = None
                        context = cw_req.get("context") if isinstance(cw_req.get("context"), dict) else {}
                        if isinstance(context.get("reply_packet"), dict):
                            reply_packet = context["reply_packet"]
                        if reply_packet:
                            self._register_auto_send(
                                copy_task_id=results["copywriter"]["task_id"],
                                reply_packet=reply_packet,
                                copy_req=cw_req,
                            )
                if isinstance(delegations.get("booking"), dict):
                    results["booking"] = self._enqueue_scheduler(delegations["booking"])
                if isinstance(delegations.get("sequencing"), dict):
                    results["sequencing"] = self._enqueue_sequencing(delegations["sequencing"])
                return {
                    "status": "enqueued",
                    "delegations": results,
                    "message": "Delegation requests enqueued deterministically",
                }

        # Deep-agent path: extract goal/context from Manager or direct task payloads
        goal = ""
        context: Dict[str, Any] = {}

        if isinstance(task_data, dict):
            goal = str(task_data.get("goal") or "")
            if isinstance(task_data.get("data"), dict):
                context = task_data.get("data") or {}

            # Manager router payload format: {subject, text, payload:{...}}
            if not goal and isinstance(task_data.get("payload"), dict):
                inner = task_data.get("payload") or {}
                goal = str(inner.get("goal") or inner.get("text") or inner.get("instruction") or inner.get("task") or "")
                if not context and isinstance(inner.get("data"), dict):
                    context = inner.get("data") or {}

            if not goal:
                subject = str(task_data.get("subject") or "")
                text = str(task_data.get("text") or "")
                goal = " ".join(filter(None, [subject, text])).strip()

        messages = [("user", goal or str(task_data))]
        if context:
            messages.insert(0, ("system", f"Additional context: {json.dumps(context)}"))

        result = await self.agent.ainvoke({"messages": messages})

        result_message = result.get("messages", [])[-1] if result.get("messages") else None
        result_content = result_message.content if hasattr(result_message, "content") else str(result_message)
        return {"status": "completed", "result": result_content}
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of orchestrator.
        
        Returns:
            Health status
        """
        return {
            "status": "healthy",
            "orchestrator": "OutreachOrchestrator",
            "tenant_id": self.tenant_id,
            "model": self.model,
            "tools_count": len(self._build_tools()),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
