"""
Persistence Agent - Tier 3 Operational Agent

Deep Agent implementation for database persistence (WRITE ONLY):
- Schema-specific write operations for 4 core tables
- Validation before writes
- Batch operations with rollback support
- Audit logging for compliance

Architecture:
- Layer 2: Deep Agent with TodoList, Filesystem, SubAgent middleware
- Layer 1: Wrapped in Agent Harness for production reliability
- Direct Supabase access (WRITE ONLY - no reads)
"""

import logging
import json
import os
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from email.utils import parseaddr
from langchain.tools import tool
from deepagents import create_deep_agent
import redis

# Import Supabase adapter for database writes
try:
    from services.persistence.adapters.supabase_adapter import SupabaseAdapter
except ImportError:
    SupabaseAdapter = None

from services.persistence.service import PersistenceService
from config.persistence_config import get_write_allowlist
from core.schemas.persistence import CompoundPayload
from core.security.prompt_hardening import get_hardened_internal_prompt
from tiers.tier_3.persistence_agent.compound_handler import (
    execute_compound,
    build_inbound_email_compound,
)

logger = logging.getLogger(__name__)

# Backwards compatibility: expose constant for external imports while delegating
DEFAULT_PERSISTENCE_ALLOWED_TABLES = get_write_allowlist()


class PersistenceAgent:
    """
    Tier 3: Persistence Agent (Deep Agent)
    
    Responsibilities:
    - Write data to Supabase (WRITE ONLY)
    - Create/update staging_leads, leads, conversations, messages
    - Batch operations with atomicity
    - Audit logging for all writes
    
    Tools:
    - Schema-specific write tools (12 tools across 4 tables)
    - Validation tools
    - Batch operations
    
    CRITICAL: This agent does NOT read from database (use RAG Agent for reads).
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        tenant_id: str = "default",
        model: str = "gpt-4o-mini",
        service: Optional[PersistenceService] = None
    ):
        """
        Initialize Persistence Agent with Deep Agent.
        
        Args:
            redis_client: Redis client for caching
            tenant_id: Tenant context for multi-tenant isolation
            model: OpenAI model (gpt-4o-mini for cost efficiency)
            service: Optional legacy PersistenceService (deprecated)
        """
        self.redis = redis_client
        self.tenant_id = tenant_id
        self.model = model
        self.service = service  # Legacy compatibility
        self.use_langgraph = os.getenv("LANGGRAPH_WORKFLOWS_ENABLED", "1").lower() in ("1", "true", "yes")
        self._graph_runner = None
        
        # Convert tenant_id string to UUID for database client_id field
        # Use UUID5 for deterministic mapping: "agentic-dev" → same UUID always
        self.client_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, tenant_id))

        # Placeholder campaign for inbound/unsolicited leads (override with CAMPAIGN_ID_PLACEHOLDER)
        self.campaign_placeholder = os.environ.get(
            "CAMPAIGN_ID_PLACEHOLDER",
            "9646f98a-e987-4a8c-b786-9b82ea985d38",
        )

        # Optional mailbox→campaign routing for inbound/outbound association.
        # Format: {"inbox@agency.com": "<campaign-uuid>", ...}
        self.mailbox_campaign_id_map: Dict[str, str] = {}
        raw_mailbox_map = os.environ.get("MAILBOX_CAMPAIGN_ID_MAP")
        if raw_mailbox_map:
            try:
                parsed = json.loads(raw_mailbox_map)
                if isinstance(parsed, dict):
                    self.mailbox_campaign_id_map = {
                        str(k).strip().lower(): str(v).strip()
                        for k, v in parsed.items()
                        if k and v
                    }
                else:
                    logger.warning("MAILBOX_CAMPAIGN_ID_MAP must be a JSON object")
            except Exception as exc:
                logger.warning(f"Invalid MAILBOX_CAMPAIGN_ID_MAP JSON: {exc}")
        
        # Initialize Supabase adapter for database writes (WRITE ONLY)
        self.supabase = None
        if SupabaseAdapter:
            try:
                supabase_url = os.environ.get("SUPABASE_URL")
                # Prefer service_role key for bypassing RLS, fallback to custom JWT
                # Note: SUPABASE_KEY is typically the service_role key in this project
                supabase_key = (
                    os.environ.get("SUPABASE_SERVICE_KEY") 
                    or os.environ.get("SUPABASE_KEY") 
                    or os.environ.get("SUPABASE_PERSISTENCE_JWT")
                )
                supabase_anon_key = os.environ.get("SUPABASE_ANON_KEY")
                
                if not supabase_url or not supabase_key:
                    logger.warning("SUPABASE_URL/SUPABASE_KEY not configured - write tools disabled")
                else:
                    # If using custom JWT (not service_role), pass anon_key for proper authentication
                    using_custom_jwt = (
                        os.environ.get("SUPABASE_PERSISTENCE_JWT") 
                        and supabase_key == os.environ.get("SUPABASE_PERSISTENCE_JWT")
                        and supabase_anon_key
                    )
                    if using_custom_jwt:
                        self.supabase = SupabaseAdapter(supabase_url, supabase_key, anon_key=supabase_anon_key)
                        logger.info("Supabase adapter initialized (WRITE ONLY mode with custom JWT)")
                    else:
                        self.supabase = SupabaseAdapter(supabase_url, supabase_key)
                        logger.info("Supabase adapter initialized (WRITE ONLY mode with service_role)")
            except Exception as e:
                logger.warning(f"Supabase adapter init failed: {e}")
        
        # Create Deep Agent with middleware
        self.agent = create_deep_agent(
            model=model,
            system_prompt=self._get_system_prompt(),
            tools=self._build_tools()
        )
        # TodoListMiddleware, FilesystemMiddleware, SubAgentMiddleware auto-configured
        
        logger.info(f"PersistenceAgent initialized (tenant={tenant_id}, model={model})")
    
    def _get_system_prompt(self) -> str:
        """System prompt defining Persistence Agent role and write operations"""
        base_prompt = f"""You are the Persistence Agent - Database write specialist.

**Your Role:**
Write data to Supabase for leads, conversations, and messages. WRITE ONLY - no reads.

**Available Tables (4 core tables):**

1. **staging_leads** (22 fields) - Pre-qualification queue
   - Create new staging leads from imports
   - Update validation status and completeness scores
   - Promote to leads table after validation

2. **leads** (27 fields) - Qualified leads with enrichment
   - Create leads from promoted staging leads
   - Update enrichment data (raw_data JSONB)
   - Update qualification scores and status
   - Link to campaigns

3. **conversations** (7 fields) - Email threads
   - Create new conversations for leads
   - Update conversation status
   - Close/archive conversations

4. **messages** (7 fields) - Individual emails
   - Create messages in conversations
   - Update sentiment scores
   - Track send status

**Write Strategy:**

1. **Validation Before Write**: Always validate payloads before writing
   - Check required fields
   - Validate UUIDs
   - Check foreign key relationships

2. **Atomic Operations**: Use transactions for multi-table writes
   - Create conversation + first message together
   - Promote staging_lead → lead with audit log

3. **Audit Logging**: Log all write operations
   - Who, what, when, why
   - Changes to critical fields
   - Data provenance

4. **Error Handling**: Return clear errors for:
   - Missing required fields
   - Foreign key violations
   - Duplicate records
   - Schema validation failures

**Tools Available (12 write tools):**

Staging Leads (3):
- create_staging_lead
- update_staging_lead
- promote_staging_lead_to_lead

Leads (4):
- create_lead
- update_lead
- update_lead_enrichment_data
- link_lead_to_campaign

Conversations (2):
- create_conversation
            Promote validated staging lead to leads table.

            Steps:
            1) Read staging lead
            2) Create lead
            3) Copy staging conversations/messages into production tables
            4) Soft-delete staging rows via archived_at + enrichment_status=promoted

Messages (2):
- create_message
- update_message_sentiment

Batch (1):
- batch_create_staging_leads
**Output Format - MINIMAL PAYLOADS:**
Return ONLY essential fields:
- status: "success" | "error"
- id: UUID of created/updated record
- operation: "create" | "update" | "delete"
- affected_rows: int
- error: string (only if error)

**Guidelines:**
- Validate before writing
- Use batch operations for >10 records
- Log all writes to audit trail
- Return minimal payloads
- Handle foreign key errors gracefully
- No reads - delegate to RAG Agent

Tenant: {self.tenant_id}
Current task: {{input}}
"""
        return get_hardened_internal_prompt(base_prompt)
    
    def _build_tools(self) -> List:
        """Build Persistence write tools - schema-specific operations for 4 core tables"""
        tools = []

        if self.supabase:
            tools.extend(
                [
                    self._create_create_staging_lead_tool(),
                    self._create_update_staging_lead_tool(),
                    self._create_promote_staging_lead_tool(),
                ]
            )

            tools.extend(
                [
                    self._create_create_lead_tool(),
                    self._create_update_lead_tool(),
                    self._create_update_lead_enrichment_tool(),
                    self._create_link_lead_to_campaign_tool(),
                ]
            )

            tools.extend(
                [
                    self._create_create_conversation_tool(),
                    self._create_update_conversation_status_tool(),
                ]
            )

            tools.extend(
                [
                    self._create_create_message_tool(),
                    self._create_update_message_sentiment_tool(),
                ]
            )

            tools.extend([
                self._create_batch_create_staging_leads_tool(),
            ])
        else:
            logger.warning("Supabase adapter not available - write tools disabled")

        return tools
    
    # ==================== STAGING LEADS WRITE TOOLS (3) ====================
    
    def _create_create_staging_lead_tool(self):
        """Create new staging lead"""
        supabase = self.supabase
        
        @tool
        def create_staging_lead(
            email: str,
            first_name: str = None,
            last_name: str = None,
            company: str = None,
            title: str = None,
            source: str = "manual",
            **kwargs
        ) -> Dict[str, Any]:
            """
            Create new staging lead for pre-qualification.
            
            Args:
                email: Email address (required, unique)
                first_name: First name (optional)
                last_name: Last name (optional)
                company: Company name (optional)
                title: Job title (optional)
                source: Lead source (default: 'manual')
                **kwargs: Additional fields
            
            Returns:
                {"status": "success", "id": "uuid", "operation": "create"}
            """
            try:
                # Set required defaults for NOT NULL fields
                if not kwargs.get("campaign_id"):
                    kwargs["campaign_id"] = "00000000-0000-0000-0000-000000000000"  # Null UUID for optional campaign
                
                record = {
                    "id": str(uuid.uuid4()),
                    "client_id": self.client_uuid,
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "company_name": company,
                    "job_title": title,
                    "source": source,
                    "enrichment_status": "pending",
                    "created_at": datetime.utcnow().isoformat(),
                    **kwargs
                }
                
                result = supabase.write(table="staging_leads", record=record)
                
                return {
                    "status": "success",
                    "id": record["id"],
                    "operation": "create",
                    "affected_rows": 1
                }
            except Exception as e:
                logger.error(f"Create staging lead failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return create_staging_lead
    
    def _create_update_staging_lead_tool(self):
        """Update existing staging lead"""
        supabase = self.supabase
        
        @tool
        def update_staging_lead(
            lead_id: str,
            enrichment_status: str = None,
            **updates
        ) -> Dict[str, Any]:
            """
            Update staging lead fields.
            
            Args:
                lead_id: Staging lead UUID
                enrichment_status: New status ('pending', 'completed', 'failed')
                **updates: Additional fields to update
            
            Returns:
                {"status": "success", "id": "uuid", "operation": "update"}
            """
            try:
                update_data = {"updated_at": datetime.utcnow().isoformat()}
                
                if enrichment_status:
                    update_data["enrichment_status"] = enrichment_status
                update_data.update(updates)
                
                # Update record
                result = supabase.upsert(
                    table="staging_leads",
                    record={"id": lead_id, **update_data},
                    on_conflict=["id"]
                )
                
                return {
                    "status": "success",
                    "id": lead_id,
                    "operation": "update",
                    "affected_rows": 1
                }
            except Exception as e:
                logger.error(f"Update staging lead failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return update_staging_lead
    
    def _create_promote_staging_lead_tool(self):
        """Promote staging lead to leads table"""
        supabase = self.supabase
        
        @tool
        def promote_staging_lead_to_lead(
            staging_lead_id: str,
            lead_score: int = 50,
            campaign_id: str = None
        ) -> Dict[str, Any]:
            """
            Promote validated staging lead to leads table.
            
            Args:
                staging_lead_id: Staging lead UUID
                lead_score: Initial lead score (0-100)
                campaign_id: Optional campaign UUID to link
            
            Returns:
                {"status": "success", "lead_id": "uuid", "operation": "promote"}
            """
            try:
                staging = supabase.read(table="staging_leads", id_value=staging_lead_id)

                if not staging.get("data"):
                    return {"status": "error", "error": "Staging lead not found"}

                staging_data = staging["data"]

                lead_id = str(uuid.uuid4())

                now_iso = datetime.utcnow().isoformat()

                resolved_client_id = staging_data.get("client_id") or self.client_uuid
                resolved_campaign_id = (
                    campaign_id
                    or staging_data.get("campaign_id")
                    or "00000000-0000-0000-0000-000000000000"
                )

                lead_record = {
                    "id": lead_id,
                    "client_id": resolved_client_id,
                    "email": staging_data.get("email"),
                    "first_name": staging_data.get("first_name"),
                    "last_name": staging_data.get("last_name"),
                    "company_name": staging_data.get("company_name"),
                    "job_title": staging_data.get("job_title"),
                    "phone_number": staging_data.get("phone_number", ""),
                    # Required defaults for NOT NULL leads columns (see integration tests)
                    "sequence_step": int(staging_data.get("sequence_step") or 1),
                    "sequence_active": bool(staging_data.get("sequence_active", True)),
                    "booking_status": staging_data.get("booking_status") or "not_booked",
                    "last_contact_date": staging_data.get("last_contact_date") or now_iso,
                    "next_action_date": staging_data.get("next_action_date") or now_iso,
                    "re_engagement_date": staging_data.get("re_engagement_date") or now_iso,
                    "current_status": staging_data.get("current_status") or "new",
                    "lead_score": lead_score,
                    "campaign_id": resolved_campaign_id,
                    "qualification_status": staging_data.get("qualification_status"),
                    "source": staging_data.get("source"),
                    "created_at": now_iso,
                }

                supabase.write(table="leads", record=lead_record)

                conversations_created = 0
                messages_created = 0

                staging_conversations = supabase.query(
                    table="staging_conversations",
                    filters={"staging_lead_id": staging_lead_id},
                    order_by="created_at",
                    descending=False,
                    limit=500,
                ).get("data", [])

                for staging_conv in staging_conversations:
                    new_conv_id = str(uuid.uuid4())
                    conv_record = {
                        "id": new_conv_id,
                        "client_id": resolved_client_id,
                        "lead_id": lead_id,
                        "thread_id": staging_conv.get("thread_id"),
                        "subject": staging_conv.get("subject"),
                        "channel": staging_conv.get("channel", "email"),
                        "status": staging_conv.get("status", "active"),
                        "metadata": staging_conv.get("metadata", {}),
                        "created_at": staging_conv.get("created_at") or now_iso,
                    }
                    supabase.write(table="conversations", record=conv_record)
                    conversations_created += 1

                    staging_messages = supabase.query(
                        table="staging_messages",
                        filters={"staging_conversation_id": staging_conv.get("id")},
                        order_by="created_at",
                        descending=False,
                        limit=500,
                    ).get("data", [])

                    for staging_msg in staging_messages:
                        msg_id = str(uuid.uuid4())
                        meta = staging_msg.get("metadata") if isinstance(staging_msg.get("metadata"), dict) else {}
                        if staging_msg.get("receiver"):
                            meta = {**meta, "receiver": staging_msg.get("receiver")}
                        supabase.write(
                            table="messages",
                            record={
                                "id": msg_id,
                                "conversation_id": new_conv_id,
                                "sender_type": staging_msg.get("sender_type") or staging_msg.get("sender") or "unknown",
                                "text_content": staging_msg.get("text_content") or staging_msg.get("content") or "",
                                "metadata": meta,
                                "sent_at": staging_msg.get("sent_at") or staging_msg.get("created_at"),
                                "created_at": staging_msg.get("created_at") or now_iso,
                            },
                        )
                        messages_created += 1

                supabase.upsert(
                    table="staging_leads",
                    record={
                        "id": staging_lead_id,
                        "enrichment_status": "promoted",
                        "archived_at": now_iso,
                        "updated_at": now_iso,
                    },
                    on_conflict=["id"],
                )

                return {
                    "status": "success",
                    "lead_id": lead_id,
                    "staging_lead_id": staging_lead_id,
                    "operation": "promote",
                    "affected_rows": 2 + conversations_created + messages_created,
                    "conversations_created": conversations_created,
                    "messages_created": messages_created,
                }
            except Exception as e:
                logger.error(f"Promote staging lead failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return promote_staging_lead_to_lead
    
    # ==================== LEADS WRITE TOOLS (4) ====================
    
    def _create_create_lead_tool(self):
        """Create new lead"""
        supabase = self.supabase
        
        @tool
        def create_lead(
            email: str,
            first_name: str = None,
            last_name: str = None,
            company: str = None,
            title: str = None,
            status: str = "active",
            lead_score: int = 50,
            campaign_id: str = None,
            **kwargs
        ) -> Dict[str, Any]:
            """
            Create new lead directly (bypass staging).
            
            Args:
                email: Email address (required, unique)
                first_name: First name
                last_name: Last name
                company: Company name
                title: Job title
                status: Lead status ('active', 'contacted', 'converted')
                lead_score: Score 0-100
                campaign_id: Campaign UUID
                **kwargs: Additional fields
            
            Returns:
                {"status": "success", "id": "uuid", "operation": "create"}
            """
            try:
                # Set required defaults for NOT NULL fields
                if not campaign_id:
                    campaign_id = "00000000-0000-0000-0000-000000000000"
                if "phone_number" not in kwargs:
                    kwargs["phone_number"] = ""  # Empty string for optional phone
                if "sequence_step" not in kwargs:
                    kwargs["sequence_step"] = 0  # Default to step 0
                
                record = {
                    "id": str(uuid.uuid4()),
                    "client_id": self.client_uuid,
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "company_name": company,
                    "job_title": title,
                    "current_status": status,
                    "lead_score": lead_score,
                    "campaign_id": campaign_id,
                    "created_at": datetime.utcnow().isoformat(),
                    **kwargs
                }
                
                result = supabase.write(table="leads", record=record)
                
                return {
                    "status": "success",
                    "id": record["id"],
                    "operation": "create",
                    "affected_rows": 1
                }
            except Exception as e:
                logger.error(f"Create lead failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return create_lead
    
    def _create_update_lead_tool(self):
        """Update existing lead"""
        supabase = self.supabase
        
        @tool
        def update_lead(
            lead_id: str,
            status: str = None,
            lead_score: int = None,
            **updates
        ) -> Dict[str, Any]:
            """
            Update lead fields.
            
            Args:
                lead_id: Lead UUID
                status: New status
                lead_score: New score (0-100)
                **updates: Additional fields
            
            Returns:
                {"status": "success", "id": "uuid", "operation": "update"}
            """
            try:
                update_data = {"updated_at": datetime.utcnow().isoformat()}
                
                if status:
                    update_data["current_status"] = status
                if lead_score is not None:
                    update_data["lead_score"] = lead_score
                update_data.update(updates)
                
                result = supabase.upsert(
                    table="leads",
                    record={"id": lead_id, **update_data},
                    on_conflict=["id"]
                )
                
                return {
                    "status": "success",
                    "id": lead_id,
                    "operation": "update",
                    "affected_rows": 1
                }
            except Exception as e:
                logger.error(f"Update lead failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return update_lead
    
    def _create_update_lead_enrichment_tool(self):
        """Update lead enrichment data (JSONB)"""
        supabase = self.supabase
        
        @tool
        def update_lead_enrichment_data(
            lead_id: str,
            enrichment_data: dict
        ) -> Dict[str, Any]:
            """
            Update lead's raw_data JSONB field with enrichment.
            
            Args:
                lead_id: Lead UUID
                enrichment_data: Dict with enrichment fields (industry, funding, etc.)
            
            Returns:
                {"status": "success", "id": "uuid", "operation": "enrich"}
            """
            try:
                # Read current raw_data
                current = supabase.read(table="leads", id_value=lead_id)
                
                if not current.get("data"):
                    return {"status": "error", "error": "Lead not found"}
                
                # Merge enrichment data
                raw_data = current["data"].get("raw_data", {})
                raw_data.update(enrichment_data)
                raw_data["enriched_at"] = datetime.utcnow().isoformat()
                
                # Update
                result = supabase.upsert(
                    table="leads",
                    record={
                        "id": lead_id,
                        "raw_data": raw_data,
                        "updated_at": datetime.utcnow().isoformat()
                    },
                    on_conflict=["id"]
                )
                
                return {
                    "status": "success",
                    "id": lead_id,
                    "operation": "enrich",
                    "enrichment_keys": list(enrichment_data.keys()),
                    "affected_rows": 1
                }
            except Exception as e:
                logger.error(f"Update enrichment failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return update_lead_enrichment_data
    
    def _create_link_lead_to_campaign_tool(self):
        """Link lead to campaign"""
        supabase = self.supabase
        
        @tool
        def link_lead_to_campaign(
            lead_id: str,
            campaign_id: str
        ) -> Dict[str, Any]:
            """
            Link lead to a campaign.
            
            Args:
                lead_id: Lead UUID
                campaign_id: Campaign UUID
            
            Returns:
                {"status": "success", "operation": "link"}
            """
            try:
                result = supabase.upsert(
                    table="leads",
                    record={
                        "id": lead_id,
                        "campaign_id": campaign_id,
                        "updated_at": datetime.utcnow().isoformat()
                    },
                    on_conflict=["id"]
                )
                
                return {
                    "status": "success",
                    "lead_id": lead_id,
                    "campaign_id": campaign_id,
                    "operation": "link",
                    "affected_rows": 1
                }
            except Exception as e:
                logger.error(f"Link to campaign failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return link_lead_to_campaign
    
    # ==================== CONVERSATIONS WRITE TOOLS (2) ====================
    
    def _create_create_conversation_tool(self):
        """Create new conversation"""
        supabase = self.supabase
        
        @tool
        def create_conversation(
            lead_id: str,
            channel: str = "email",
            status: str = "active",
            **kwargs
        ) -> Dict[str, Any]:
            """
            Create new conversation (email thread).
            
            Args:
                lead_id: Lead UUID
                channel: Communication channel ('email', 'sms', 'linkedin')
                status: Status ('active', 'closed', 'archived')
                **kwargs: Additional fields
            
            Returns:
                {"status": "success", "id": "uuid", "operation": "create"}
            """
            try:
                record = {
                    "id": str(uuid.uuid4()),
                    "client_id": self.client_uuid,
                    "lead_id": lead_id,
                    "channel": channel,
                    "status": status,
                    "created_at": datetime.utcnow().isoformat(),
                    **kwargs
                }
                
                result = supabase.write(table="conversations", record=record)
                
                return {
                    "status": "success",
                    "id": record["id"],
                    "lead_id": lead_id,
                    "operation": "create",
                    "affected_rows": 1
                }
            except Exception as e:
                logger.error(f"Create conversation failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return create_conversation
    
    def _create_update_conversation_status_tool(self):
        """Update conversation status"""
        supabase = self.supabase
        
        @tool
        def update_conversation_status(
            conversation_id: str,
            status: str
        ) -> Dict[str, Any]:
            """
            Update conversation status.
            
            Args:
                conversation_id: Conversation UUID
                status: New status ('active', 'closed', 'archived')
            
            Returns:
                {"status": "success", "id": "uuid", "operation": "update"}
            """
            try:
                result = supabase.upsert(
                    table="conversations",
                    record={
                        "id": conversation_id,
                        "status": status,
                        "updated_at": datetime.utcnow().isoformat()
                    },
                    on_conflict=["id"]
                )
                
                return {
                    "status": "success",
                    "id": conversation_id,
                    "operation": "update",
                    "affected_rows": 1
                }
            except Exception as e:
                logger.error(f"Update conversation status failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return update_conversation_status
    
    # ==================== MESSAGES WRITE TOOLS (2) ====================
    
    def _create_create_message_tool(self):
        """Create new message"""
        supabase = self.supabase
        
        @tool
        def create_message(
            conversation_id: str,
            sender_type: str,
            text_content: str,
            **kwargs
        ) -> Dict[str, Any]:
            """
            Create new message in conversation.
            
            Args:
                conversation_id: Conversation UUID
                sender_type: Who sent it ('agent', 'lead', 'system')
                text_content: Message content
                **kwargs: Additional fields (metadata, sent_at)
            
            Returns:
                {"status": "success", "id": "uuid", "operation": "create"}
            """
            try:
                # Let Supabase auto-generate ID (FK to conversations)
                record = {
                    "conversation_id": conversation_id,
                    "sender_type": sender_type,
                    "text_content": text_content,
                    "created_at": datetime.utcnow().isoformat(),
                    **kwargs
                }
                
                result = supabase.write(table="messages", record=record)
                
                return {
                    "status": "success",
                    "id": result.get("id") if isinstance(result, dict) else None,
                    "conversation_id": conversation_id,
                    "operation": "create",
                    "affected_rows": 1
                }
            except Exception as e:
                logger.error(f"Create message failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return create_message
    
    def _create_update_message_sentiment_tool(self):
        """Update message sentiment score"""
        supabase = self.supabase
        
        @tool
        def update_message_sentiment(
            message_id: str,
            sentiment_score: float
        ) -> Dict[str, Any]:
            """
            Update message sentiment score.
            
            Args:
                message_id: Message UUID
                sentiment_score: Sentiment (-1.0 to 1.0)
            
            Returns:
                {"status": "success", "id": "uuid", "operation": "update"}
            """
            try:
                result = supabase.upsert(
                    table="messages",
                    record={
                        "id": message_id,
                        "sentiment_score": sentiment_score,
                        "updated_at": datetime.utcnow().isoformat()
                    },
                    on_conflict=["id"]
                )
                
                return {
                    "status": "success",
                    "id": message_id,
                    "operation": "update",
                    "affected_rows": 1
                }
            except Exception as e:
                logger.error(f"Update sentiment failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return update_message_sentiment
    
    # ==================== BATCH OPERATIONS (1) ====================
    
    def _create_batch_create_staging_leads_tool(self):
        """Batch create staging leads"""
        supabase = self.supabase
        
        @tool
        def batch_create_staging_leads(
            leads: list
        ) -> Dict[str, Any]:
            """
            Batch create multiple staging leads.
            
            Args:
                leads: List of dicts with lead data
            
            Returns:
                {"status": "success", "created_count": int, "operation": "batch_create"}
            """
            try:
                records = []
                for lead in leads:
                    records.append({
                        "id": str(uuid.uuid4()),
                        "client_id": self.client_uuid,
                        "email": lead.get("email"),
                        "first_name": lead.get("first_name"),
                        "last_name": lead.get("last_name"),
                        "company_name": lead.get("company_name"),
                        "job_title": lead.get("job_title"),
                        "source": lead.get("source", "import"),
                        "enrichment_status": "pending",
                        "created_at": datetime.utcnow().isoformat()
                    })
                
                result = supabase.batch_write(table="staging_leads", records=records)
                
                return {
                    "status": "success",
                    "created_count": len(records),
                    "operation": "batch_create",
                    "affected_rows": len(records)
                }
            except Exception as e:
                logger.error(f"Batch create failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return batch_create_staging_leads
    
    # ==================== EXECUTION METHODS ====================
    
    def _get_graph_runner(self):
        if self._graph_runner is not None:
            return self._graph_runner
        from core.langgraph import LangGraphRunner

        async def _execute_graph(state):
            task_data_or_goal = state.get("task_data_or_goal")
            context = state.get("context") or {}
            return await self._execute_core(task_data_or_goal, context)

        async def _guardrails(state):
            output = state.get("output") or {}
            if output.get("status") == "error":
                return output
            return output

        self._graph_runner = LangGraphRunner(
            name="persistence",
            execute_fn=_execute_graph,
            required_input_keys=["task_data_or_goal"],
            guardrails_fn=_guardrails,
        )
        return self._graph_runner

    async def execute(self, task_data_or_goal, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self.use_langgraph:
            runner = self._get_graph_runner()
            graph_result = await runner.run(
                state_input={
                    "task_data_or_goal": task_data_or_goal,
                    "context": context or {},
                    "task_id": task_data_or_goal.get("task_id") if isinstance(task_data_or_goal, dict) else None,
                    "correlation_id": task_data_or_goal.get("correlation_id") if isinstance(task_data_or_goal, dict) else None,
                },
                execution_id=str(task_data_or_goal.get("task_id") if isinstance(task_data_or_goal, dict) else ""),
            )
            if graph_result.get("status") == "success":
                return graph_result.get("output", {})
            return {
                "status": "error",
                "error": graph_result.get("error", "langgraph_failed"),
                "trace": graph_result.get("trace", []),
            }
        return await self._execute_core(task_data_or_goal, context)

    async def _execute_core(self, task_data_or_goal, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a persistence write task.
        
        Args:
            task_data_or_goal: User's goal/request (string) or task data dict
            context: Optional context (lead_data, campaign_data, etc.)
        
        Returns:
            Minimal result payload with write confirmation
        """
        start_time = datetime.now()
        execution_id = f"exec_{start_time.timestamp()}"
        
        # Extract goal and record from task_data
        if isinstance(task_data_or_goal, dict):
            goal = task_data_or_goal.get("goal", "")
            record = task_data_or_goal.get("record") or task_data_or_goal.get("data")
            if task_data_or_goal.get("operation") in {"compound_write", "compound"}:
                return self._handle_compound(task_data_or_goal)
            
            # Legacy compatibility: operation-based execution
            if "operation" in task_data_or_goal and self.service:
                return await self._legacy_execute(task_data_or_goal, context)
        else:
            goal = str(task_data_or_goal)
            record = None
        
        # ============ DEEP AGENT EXECUTION ============
        try:
            # Prepare messages for Deep Agent
            messages = [
                ("system", self._get_system_prompt()),
                ("user", f"Goal: {goal}\n\nData: {record if record else context or 'None'}")
            ]
            
            # Execute through Deep Agent
            result = await self.agent.ainvoke({"messages": messages})
            
            # Extract and minimize response
            if isinstance(result, dict):
                output = result.get("output", result)
            else:
                output = result
            
            # Return minimal payload
            return self._minimal_success_response(
                execution_id=execution_id,
                result=output,
                duration=(datetime.now() - start_time).total_seconds()
            )
            
        except Exception as e:
            logger.error(f"Persistence execution failed: {e}", exc_info=True)
            return self._minimal_error_response(
                execution_id=execution_id,
                error=str(e),
                duration=(datetime.now() - start_time).total_seconds()
            )
    
    def _handle_compound(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a compound payload using the available adapter.
        
        NOTE: For compound operations we prefer the raw Supabase adapter over the
        PersistenceService wrapper. This is because compound operations are transactional
        and we need actual database failures to propagate (not be silently caught by
        hybrid adapter fallbacks). If the raw adapter is unavailable, we fall back to
        the service but compound integrity may be compromised on partial failures.
        """
        # Prefer raw Supabase adapter for compound operations to avoid silent fallback
        adapter = self.supabase or self.service
        if not adapter:
            return {
                "status": "error",
                "error": "No persistence adapter available for compound operations",
            }

        def _inject_scoping_fields(steps: Any) -> None:
            """Inject tenant-scoped client_id and placeholder campaign_id when missing.

            Notes:
            - Only applies to CREATE/UPSERT to avoid overwriting on UPDATE.
            - Skips staging_conversations/staging_messages because those tables (by migration) do not carry client_id.
            - campaign_id falls back to CAMPAIGN_ID_PLACEHOLDER (default: 9646f98a-e987-4a8c-b786-9b82ea985d38)
              until a real campaign context is supplied. Replace once an actual campaign is available.
            """

            if not isinstance(steps, list):
                return

            def _infer_campaign_id_from_steps(steps_list: List[dict]) -> Optional[str]:
                """Infer campaign_id from message metadata (mailbox routing).

                Looks for a matching mailbox address in `MAILBOX_CAMPAIGN_ID_MAP`.
                Priority:
                - inbound: metadata.to
                - outbound: metadata.from
                """

                if not self.mailbox_campaign_id_map:
                    return None

                target_tables = {"messages", "staging_messages"}

                def _extract_email(value: Any) -> Optional[str]:
                    if not value:
                        return None
                    if isinstance(value, list):
                        # Take first usable entry
                        for item in value:
                            email_val = _extract_email(item)
                            if email_val:
                                return email_val
                        return None
                    if not isinstance(value, str):
                        return None
                    addr = parseaddr(value)[1] or value
                    addr = addr.strip().lower()
                    return addr or None

                for step in steps_list:
                    if not isinstance(step, dict):
                        continue
                    table = step.get("table")
                    if table not in target_tables:
                        continue

                    data = step.get("data")
                    records: List[dict] = []
                    if isinstance(data, dict):
                        records = [data]
                    elif isinstance(data, list):
                        records = [r for r in data if isinstance(r, dict)]

                    for record in records:
                        meta = record.get("metadata")
                        if not isinstance(meta, dict):
                            continue

                        inbound_to = _extract_email(meta.get("to") or meta.get("inbox") or meta.get("mailbox"))
                        outbound_from = _extract_email(meta.get("from") or meta.get("sender") or meta.get("from_email"))

                        for candidate in (inbound_to, outbound_from):
                            if candidate and candidate in self.mailbox_campaign_id_map:
                                return self.mailbox_campaign_id_map[candidate]

                return None

            inferred_campaign_id = _infer_campaign_id_from_steps(steps)

            # Tables that require client_id injection
            client_id_tables = {
                "staging_leads",
                "leads",
                "conversations",
                "messages",
            }
            # Tables that receive placeholder campaign_id when absent
            campaign_id_tables = {
                "staging_leads",
                "leads",
            }

            for step in steps:
                if not isinstance(step, dict):
                    continue
                table = step.get("table")
                operation = (step.get("operation") or "").lower()
                if operation not in ("create", "upsert"):
                    continue

                data = step.get("data")

                def inject_into_record(record: dict) -> None:
                    """Inject client_id and placeholder campaign_id into a single record dict."""
                    # Inject client_id for tenant scoping
                    if table in client_id_tables:
                        if "client_id" not in record or record.get("client_id") in (None, ""):
                            record["client_id"] = self.client_uuid
                    # Inject campaign placeholder when absent
                    if table in campaign_id_tables:
                        if "campaign_id" not in record or record.get("campaign_id") in (None, ""):
                            record["campaign_id"] = inferred_campaign_id or self.campaign_placeholder

                if isinstance(data, dict):
                    inject_into_record(data)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            inject_into_record(item)

        def _inject_correlation_id(steps: Any, correlation_id: Optional[str]) -> None:
            """Add correlation_id into messages/staging_messages metadata if missing."""

            if not correlation_id or not isinstance(steps, list):
                return

            target_tables = {"messages", "staging_messages"}

            for step in steps:
                if not isinstance(step, dict):
                    continue
                table = step.get("table")
                if table not in target_tables:
                    continue

                data = step.get("data")

                def ensure_metadata(record: dict) -> None:
                    meta = record.get("metadata")
                    if meta is None:
                        meta = {}
                    if isinstance(meta, dict) and "correlation_id" not in meta:
                        meta["correlation_id"] = correlation_id
                    record["metadata"] = meta

                if isinstance(data, dict):
                    ensure_metadata(data)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            ensure_metadata(item)

        try:
            # Normalize legacy key
            if "operations" in task_data and "steps" not in task_data:
                task_data = {**task_data, "steps": task_data.get("operations")}

            # Ensure tenant scoping for compound writes (injects client_id + campaign_id)
            _inject_scoping_fields(task_data.get("steps"))
            _inject_correlation_id(task_data.get("steps"), task_data.get("correlation_id"))

            payload = CompoundPayload(**task_data)
        except Exception as exc:
            return {"status": "error", "error": f"Invalid compound payload: {exc}"}

        result = execute_compound(payload, adapter)
        return result.model_dump()

    async def _legacy_execute(self, task_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Legacy service-based execution for backward compatibility."""
        try:
            operation = task_data.get("operation", "write")
            table = task_data.get("table", "")
            
            logger.info(f"Executing legacy persistence {operation} on {table}")
            
            allow_read_ops = os.getenv("PERSISTENCE_ALLOW_READ_OPERATIONS", "1").lower() in ("1", "true", "yes")

            if not allow_read_ops and operation in ("read", "query"):
                return {
                    "status": "error",
                    "error": "read/query operations are disabled in PersistenceAgent; use RAGAgent",
                }

            if operation in ("compound_write", "compound"):
                return self._handle_compound(task_data)
            if operation == "write":
                record = task_data.get("record", {})
                result = self.service.write(table, record)
            elif operation == "batch_write":
                records = task_data.get("records", [])
                result = self.service.batch_write(table, records)
            elif operation == "upsert":
                record = task_data.get("record", {})
                on_conflict = task_data.get("on_conflict")
                result = self.service.upsert(table, record, on_conflict=on_conflict)
            elif operation == "read":
                id_value = task_data.get("id_value")
                id_column = task_data.get("id_column", "id")
                result = self.service.read(table, id_value, id_column)
            elif operation == "query":
                filters = task_data.get("filters") or task_data.get("where") or {}
                limit = task_data.get("limit")
                order_by = task_data.get("order_by")
                descending = bool(task_data.get("descending", False))
                select = task_data.get("select")
                result = self.service.query(
                    table,
                    filters=filters if isinstance(filters, dict) else {},
                    limit=int(limit) if isinstance(limit, int) or (isinstance(limit, str) and str(limit).isdigit()) else None,
                    order_by=str(order_by) if order_by else None,
                    descending=descending,
                    select=select if isinstance(select, list) else None,
                )
            elif operation == "promote_staging_lead":
                # Promote staging lead to qualified leads table
                staging_lead_id = task_data.get("staging_lead_id")
                lead_score = task_data.get("lead_score", 50)
                campaign_id = task_data.get("campaign_id")
                qualification_status = task_data.get("qualification_status", "qualified")
                
                if not staging_lead_id:
                    return {
                        "status": "error",
                        "error": "staging_lead_id is required for promote_staging_lead operation"
                    }
                
                # Get the promote tool and call it
                promote_tool = self._create_promote_staging_lead_tool()
                result = promote_tool.invoke({
                    "staging_lead_id": staging_lead_id,
                    "lead_score": lead_score,
                    "campaign_id": campaign_id,
                })
                
                # If promotion was successful, update qualification status
                if result.get("status") == "success" and self.supabase:
                    try:
                        self.supabase.upsert(
                            "staging_leads",
                            {
                                "id": staging_lead_id,
                                "qualification_status": qualification_status,
                                "enrichment_status": "promoted",
                            },
                            on_conflict=["id"],
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update staging lead qualification status: {e}")
            else:
                return {
                    "status": "error",
                    "error": f"Unknown operation: {operation}"
                }
            
            return {
                "status": "success",
                "result": result,
                "operation": operation
            }
                
        except Exception as e:
            logger.error(f"Legacy persistence task execution failed: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _minimal_success_response(self, execution_id: str, result: Any, duration: float) -> Dict[str, Any]:
        """Create minimal success response to reduce stream payload size"""
        # Extract only essential fields from result
        if isinstance(result, dict):
            affected_rows = result.get("affected_rows", result.get("created_count", 1))
            record_id = result.get("id") or result.get("lead_id")
            operation = result.get("operation", "write")
        else:
            affected_rows = 1
            record_id = None
            operation = "write"
        
        return {
            "status": "completed",
            "task_id": execution_id,
            "id": record_id,
            "operation": operation,
            "affected_rows": affected_rows,
            "duration_ms": int(duration * 1000)
        }
    
    def _minimal_error_response(
        self, 
        execution_id: str, 
        error: str, 
        duration: float
    ) -> Dict[str, Any]:
        """Create minimal error response"""
        return {
            "status": "error",
            "task_id": execution_id,
            "error": error[:200],  # Truncate long errors
            "duration_ms": int(duration * 1000)
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check agent health.
        
        Returns:
            Health status dictionary
        """
        try:
            health = {
                "status": "healthy",
                "agent": "persistence",
                "timestamp": datetime.utcnow().isoformat(),
                "components": {}
            }
            
            # Check Redis
            try:
                self.redis.ping()
                health["components"]["redis"] = "healthy"
            except:
                health["components"]["redis"] = "unhealthy"
                health["status"] = "degraded"
            
            # Check Supabase
            if self.supabase:
                health["components"]["supabase"] = "healthy"
                health["write_tools"] = 12
            else:
                health["components"]["supabase"] = "not_configured"
                health["write_tools"] = 0
            
            return health
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "agent": "persistence",
                "error": str(e)
            }
    
    # Legacy compatibility methods
    def write(self, table: str, record: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy write method for backward compatibility."""
        return self.service.write(table, record)
    
    def batch_write(self, table: str, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Legacy batch write method for backward compatibility."""
        return self.service.batch_write(table, records)
    
    def upsert(
        self, table: str, record: Dict[str, Any], on_conflict: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Legacy upsert method for backward compatibility."""
        return self.service.upsert(table, record, on_conflict=on_conflict)
    
    # ----------------------------- Read Operations ------------------------- #
    def read(
        self, table: str, id_value: Any, id_column: str = "id"
    ) -> Optional[Dict[str, Any]]:
        return self.service.read(table, id_value, id_column)

    def query(
        self,
        table: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        order_by: Optional[str] = None,
        descending: bool = False,
        select: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        return self.service.query(
            table,
            filters=filters,
            limit=limit,
            order_by=order_by,
            descending=descending,
            select=select,
        )

    def get_columns(self, table: str) -> Optional[List[str]]:
        return self.service.get_columns(table)


def create_persistence_agent(*args, **kwargs):  # pragma: no cover - retained for compatibility
    """Deprecated direct factory.

    Prefer `agent.operational_agents.factory.create_persistence_agent` for unified
    construction logic. This shim delegates to the new factory to avoid breaking imports.
    """
    from agent.operational_agents.factory import create_persistence_agent as _f

    return _f(*args, **kwargs)


__all__ = [
    "PersistenceAgent",
    "create_persistence_agent",
    "DEFAULT_PERSISTENCE_ALLOWED_TABLES",
]
