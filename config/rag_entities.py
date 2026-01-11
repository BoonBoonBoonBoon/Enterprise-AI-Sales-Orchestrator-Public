"""
RAG Entity Schemas and Validation Rules

Defines entity schemas matching actual Supabase database structure.
Each entity includes:
- Field definitions with types
- Required fields list
- Optional fields list
- Validation rules
- Text fields for embedding (vector search)
"""

from typing import Dict, List, Set, Any, Optional
from enum import Enum
from dataclasses import dataclass


class EntityType(str, Enum):
    """Supported entity types for RAG operations"""
    LEAD = "lead"
    CONVERSATION = "conversation"
    MESSAGE = "message"
    CLIENT = "client"
    CAMPAIGN = "campaign"
    SEQUENCE = "sequence"
    AGENT_TASK = "agent_task"
    AGENT_SUBTASK = "agent_subtask"
    AUDIT_LOG = "audit_log"
    STAGING_LEAD = "staging_lead"


@dataclass
class FieldDefinition:
    """Field definition with type and constraints"""
    name: str
    field_type: str  # uuid, text, jsonb, timestamptz, int8, bool
    required: bool
    default: Optional[Any] = None
    max_length: Optional[int] = None
    enum_values: Optional[List[str]] = None


class EntitySchema:
    """Base class for entity schemas"""
    entity_type: EntityType
    table_name: str
    fields: List[FieldDefinition]
    required_fields: Set[str]
    text_fields_for_embedding: List[str]  # Fields to embed for vector search
    
    @classmethod
    def get_required_fields(cls) -> Set[str]:
        """Get set of required field names"""
        return {f.name for f in cls.fields if f.required}
    
    @classmethod
    def get_text_fields(cls) -> List[str]:
        """Get fields to use for embedding generation"""
        return cls.text_fields_for_embedding


# ============ LEAD SCHEMA ============

class LeadSchema(EntitySchema):
    """Lead entity schema (primary enrichment target)"""
    entity_type = EntityType.LEAD
    table_name = "leads"
    
    fields = [
        FieldDefinition("id", "uuid", required=True),
        FieldDefinition("client_id", "uuid", required=True),
        FieldDefinition("campaign_id", "uuid", required=False),
        FieldDefinition("email", "text", required=True),
        FieldDefinition("first_name", "text", required=True),
        FieldDefinition("last_name", "text", required=True),
        FieldDefinition("company_name", "text", required=False),
        FieldDefinition("job_title", "text", required=False),
        FieldDefinition("phone_number", "text", required=False),
        FieldDefinition("current_status", "text", required=False),
        FieldDefinition("sequence_step", "int8", required=False),
        FieldDefinition("sequence_active", "bool", required=False),
        FieldDefinition("next_action_date", "timestamptz", required=False),
        FieldDefinition("last_contact_date", "timestamptz", required=False),
        FieldDefinition("sent_timestamps", "jsonb", required=False),
        FieldDefinition("reply_timestamps", "jsonb", required=False),
        FieldDefinition("booking_status", "text", required=False),
        FieldDefinition("re_engagement_date", "timestamptz", required=False),
        FieldDefinition("generated_copy_subject", "text", required=False),
        FieldDefinition("generated_copy_body", "text", required=False),
        FieldDefinition("created_at", "timestamptz", required=False),
        FieldDefinition("updated_at", "timestamptz", required=False),
        FieldDefinition("crm_id", "text", required=False),
        FieldDefinition("last_reply_sentiment", "text", required=False),
        FieldDefinition("lead_score", "int8", required=False),
        FieldDefinition("qualification_status", "text", required=False),
        # RAG enrichment fields
        FieldDefinition("enrichment_status", "text", required=False, 
                       enum_values=["pending", "in_progress", "completed", "failed"]),
        FieldDefinition("raw_data", "jsonb", required=False),  # Enriched data storage
    ]
    
    required_fields = {"id", "client_id", "email", "first_name", "last_name"}
    
    # Fields to embed for vector similarity search
    text_fields_for_embedding = [
        "company_name",  # Primary signal
        "job_title",     # Role context
        "current_status",  # Lead status
        "qualification_status"  # Enrichment result
    ]


# ============ STAGING LEAD SCHEMA ============

class StagingLeadSchema(EntitySchema):
    """Staging leads (pre-enrichment/validation)"""
    entity_type = EntityType.STAGING_LEAD
    table_name = "staging_leads"
    
    fields = [
        FieldDefinition("id", "uuid", required=True),
        FieldDefinition("client_id", "uuid", required=True),
        FieldDefinition("campaign_id", "uuid", required=False),
        FieldDefinition("source", "text", required=False),
        FieldDefinition("email", "text", required=False),
        FieldDefinition("first_name", "text", required=False),
        FieldDefinition("last_name", "text", required=False),
        FieldDefinition("company_name", "text", required=False),
        FieldDefinition("job_title", "text", required=False),
        FieldDefinition("phone_number", "text", required=False),
        FieldDefinition("linkedin_url", "text", required=False),
        FieldDefinition("website_url", "text", required=False),
        FieldDefinition("location", "text", required=False),
        FieldDefinition("industry", "text", required=False),
        FieldDefinition("company_size", "text", required=False),
        FieldDefinition("revenue_range", "text", required=False),
        FieldDefinition("raw_data", "jsonb", required=False),
        FieldDefinition("duplicate_check_hash", "text", required=False),
        FieldDefinition("error_log", "text", required=False),
        FieldDefinition("enrichment_status", "text", required=False),
        FieldDefinition("qualification_status", "text", required=False),
        FieldDefinition("promotion_ready", "bool", required=False),
        FieldDefinition("created_at", "timestamptz", required=False),
        FieldDefinition("updated_at", "timestamptz", required=False),
    ]
    
    required_fields = {"id", "client_id"}
    
    text_fields_for_embedding = [
        "company_name",
        "industry",
        "job_title",
        "location"
    ]


# ============ CONVERSATION SCHEMA ============

class ConversationSchema(EntitySchema):
    """Conversation entity schema"""
    entity_type = EntityType.CONVERSATION
    table_name = "conversations"
    
    fields = [
        FieldDefinition("id", "uuid", required=True),
        FieldDefinition("client_id", "uuid", required=True),
        FieldDefinition("lead_id", "uuid", required=False),
        FieldDefinition("channel", "text", required=True),
        FieldDefinition("status", "text", required=False),
        FieldDefinition("summary", "text", required=False),  # AI-generated summary
        FieldDefinition("created_at", "timestamptz", required=False),
        FieldDefinition("updated_at", "timestamptz", required=False),
    ]
    
    required_fields = {"id", "client_id", "channel"}
    
    # Embed conversation summary for semantic search
    text_fields_for_embedding = ["summary", "channel"]


# ============ MESSAGE SCHEMA ============

class MessageSchema(EntitySchema):
    """Message entity schema"""
    entity_type = EntityType.MESSAGE
    table_name = "messages"
    
    fields = [
        FieldDefinition("id", "uuid", required=True),
        FieldDefinition("conversation_id", "uuid", required=True),
        FieldDefinition("sender_type", "text", required=True),  # agent, lead, system
        FieldDefinition("text_content", "text", required=False),
        FieldDefinition("metadata", "text", required=False),
        FieldDefinition("sent_at", "text", required=False),
        FieldDefinition("created_at", "timestamptz", required=False),
    ]
    
    required_fields = {"id", "conversation_id", "sender_type"}
    
    # Embed message content for semantic search
    text_fields_for_embedding = ["text_content"]


# ============ CLIENT SCHEMA ============

class ClientSchema(EntitySchema):
    """Client entity schema"""
    entity_type = EntityType.CLIENT
    table_name = "clients"
    
    fields = [
        FieldDefinition("id", "uuid", required=True),
        FieldDefinition("name", "text", required=True),
        FieldDefinition("created_at", "timestamptz", required=False),
        FieldDefinition("updated_at", "timestamptz", required=False),
    ]
    
    required_fields = {"id", "name"}
    
    text_fields_for_embedding = ["name"]


# ============ CAMPAIGN SCHEMA ============

class CampaignSchema(EntitySchema):
    """Campaign entity schema"""
    entity_type = EntityType.CAMPAIGN
    table_name = "campaigns"
    
    fields = [
        FieldDefinition("id", "uuid", required=True),
        FieldDefinition("client_id", "uuid", required=True),
        FieldDefinition("campaign_name", "text", required=True),
        FieldDefinition("campaign_type", "text", required=False),
        FieldDefinition("status", "text", required=False),
        FieldDefinition("sequence_id", "uuid", required=False),
        FieldDefinition("created_at", "timestamptz", required=False),
        FieldDefinition("updated_at", "timestamptz", required=False),
    ]
    
    required_fields = {"id", "client_id", "campaign_name"}
    
    text_fields_for_embedding = ["campaign_name", "campaign_type"]


# ============ SEQUENCE SCHEMA ============

class SequenceSchema(EntitySchema):
    """Sequence entity schema"""
    entity_type = EntityType.SEQUENCE
    table_name = "sequences"
    
    fields = [
        FieldDefinition("id", "uuid", required=True),
        FieldDefinition("client_id", "uuid", required=True),
        FieldDefinition("sequence_name", "text", required=True),
        FieldDefinition("steps", "jsonb", required=False),
        FieldDefinition("created_at", "timestamptz", required=False),
        FieldDefinition("updated_at", "timestamptz", required=False),
    ]
    
    required_fields = {"id", "client_id", "sequence_name"}
    
    text_fields_for_embedding = ["sequence_name"]


# ============ AGENT TASK SCHEMA ============

class AgentTaskSchema(EntitySchema):
    """Agent task entity schema"""
    entity_type = EntityType.AGENT_TASK
    table_name = "agent_tasks"
    
    fields = [
        FieldDefinition("task_id", "uuid", required=True),
        FieldDefinition("client_id", "uuid", required=True),
        FieldDefinition("status", "text", required=False),
        FieldDefinition("input", "jsonb", required=False),
        FieldDefinition("output", "jsonb", required=False),
        FieldDefinition("error", "text", required=False),
        FieldDefinition("created_at", "timestamptz", required=False),
        FieldDefinition("updated_at", "timestamptz", required=False),
        FieldDefinition("workflow_id", "text", required=False),
        FieldDefinition("metadata", "jsonb", required=False),
    ]
    
    required_fields = {"task_id", "client_id"}
    
    text_fields_for_embedding = []  # Tasks not typically embedded


# ============ AGENT SUBTASK SCHEMA ============

class AgentSubtaskSchema(EntitySchema):
    """Agent subtask entity schema"""
    entity_type = EntityType.AGENT_SUBTASK
    table_name = "agent_subtasks"
    
    fields = [
        FieldDefinition("sub_task_id", "uuid", required=True),
        FieldDefinition("parent_task_id", "uuid", required=False),
        FieldDefinition("agent_name", "text", required=False),
        FieldDefinition("status", "text", required=False),
        FieldDefinition("input", "jsonb", required=False),
        FieldDefinition("output", "jsonb", required=False),
        FieldDefinition("error", "text", required=False),
        FieldDefinition("created_at", "timestamptz", required=False),
        FieldDefinition("updated_at", "timestamptz", required=False),
    ]
    
    required_fields = {"sub_task_id"}
    
    text_fields_for_embedding = []


# ============ AUDIT LOG SCHEMA ============

class AuditLogSchema(EntitySchema):
    """Audit log entity schema"""
    entity_type = EntityType.AUDIT_LOG
    table_name = "audit_log"
    
    fields = [
        FieldDefinition("id", "uuid", required=True),
        FieldDefinition("client_id", "uuid", required=True),
        FieldDefinition("user_or_agent", "text", required=False),
        FieldDefinition("action", "text", required=False),
        FieldDefinition("target_table", "text", required=False),
        FieldDefinition("target_id", "uuid", required=False),
        FieldDefinition("metadata", "jsonb", required=False),
        FieldDefinition("created_at", "timestamptz", required=False),
    ]
    
    required_fields = {"id", "client_id"}
    
    text_fields_for_embedding = []


# ============ SCHEMA REGISTRY ============

ENTITY_SCHEMAS: Dict[EntityType, type[EntitySchema]] = {
    EntityType.LEAD: LeadSchema,
    EntityType.STAGING_LEAD: StagingLeadSchema,
    EntityType.CONVERSATION: ConversationSchema,
    EntityType.MESSAGE: MessageSchema,
    EntityType.CLIENT: ClientSchema,
    EntityType.CAMPAIGN: CampaignSchema,
    EntityType.SEQUENCE: SequenceSchema,
    EntityType.AGENT_TASK: AgentTaskSchema,
    EntityType.AGENT_SUBTASK: AgentSubtaskSchema,
    EntityType.AUDIT_LOG: AuditLogSchema,
}


def get_schema(entity_type: EntityType) -> type[EntitySchema]:
    """Get schema class for entity type"""
    if entity_type not in ENTITY_SCHEMAS:
        raise ValueError(f"Unknown entity type: {entity_type}")
    return ENTITY_SCHEMAS[entity_type]


def get_required_fields(entity_type: EntityType) -> Set[str]:
    """Get required fields for entity type"""
    schema = get_schema(entity_type)
    return schema.required_fields


def get_text_fields(entity_type: EntityType) -> List[str]:
    """Get text fields for embedding for entity type"""
    schema = get_schema(entity_type)
    return schema.text_fields_for_embedding


def get_table_name(entity_type: EntityType) -> str:
    """Get table name for entity type"""
    schema = get_schema(entity_type)
    return schema.table_name


__all__ = [
    "EntityType",
    "FieldDefinition",
    "EntitySchema",
    "LeadSchema",
    "StagingLeadSchema",
    "ConversationSchema",
    "MessageSchema",
    "ClientSchema",
    "CampaignSchema",
    "SequenceSchema",
    "AgentTaskSchema",
    "AgentSubtaskSchema",
    "AuditLogSchema",
    "ENTITY_SCHEMAS",
    "get_schema",
    "get_required_fields",
    "get_text_fields",
    "get_table_name",
]
