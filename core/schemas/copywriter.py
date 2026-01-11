"""Type-safe schemas for Copywriter agent task and result payloads."""
from __future__ import annotations

from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field, validator
from enum import Enum


class CopyTone(str, Enum):
    """Supported copy tones"""
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    FRIENDLY = "friendly"
    FORMAL = "formal"
    ENTHUSIASTIC = "enthusiastic"
    PERSUASIVE = "persuasive"


class CopyTemplate(str, Enum):
    """Supported copy templates"""
    COLD_EMAIL = "cold_email"
    FOLLOWUP_EMAIL = "followup_email"
    SMS = "sms"
    LINKEDIN_MESSAGE = "linkedin_message"
    CUSTOM = "custom"


class LeadData(BaseModel):
    """Lead information for copy generation"""
    id: str = Field(..., description="Lead ID")
    email: Optional[str] = Field(None, description="Lead email")
    name: Optional[str] = Field(None, description="Lead name")
    company: Optional[str] = Field(None, description="Lead company")
    title: Optional[str] = Field(None, description="Lead job title")
    industry: Optional[str] = Field(None, description="Company industry")
    custom_fields: Dict[str, Any] = Field(default_factory=dict, description="Additional lead data")
    
    @validator('email')
    def validate_email_format(cls, v):
        """Basic email validation"""
        if v and '@' not in v:
            raise ValueError(f"Invalid email format: {v}")
        return v
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "id": "lead-123",
                    "email": "john@example.com",
                    "name": "John Doe",
                    "company": "Acme Corp",
                    "title": "VP of Engineering",
                    "industry": "Software"
                }
            ]
        }


class CampaignContext(BaseModel):
    """Campaign metadata for copy generation"""
    campaign_id: str = Field(..., description="Campaign identifier")
    variant: Optional[str] = Field(None, description="A/B test variant (A, B, etc.)")
    sequence_step: int = Field(default=1, ge=1, description="Step in email sequence")
    product_name: Optional[str] = Field(None, description="Product/service name")
    value_proposition: Optional[str] = Field(None, description="Key value prop")
    call_to_action: Optional[str] = Field(None, description="Desired CTA")
    custom_variables: Dict[str, str] = Field(default_factory=dict, description="Template variables")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "campaign_id": "camp-123",
                    "variant": "A",
                    "sequence_step": 1,
                    "product_name": "AI Platform",
                    "value_proposition": "Automate 80% of customer support",
                    "call_to_action": "Schedule a demo"
                }
            ]
        }


class CopyInstructions(BaseModel):
    """Instructions for copy generation"""
    template: CopyTemplate = Field(..., description="Copy template to use")
    tone: CopyTone = Field(default=CopyTone.PROFESSIONAL, description="Desired tone")
    word_count: Optional[int] = Field(None, ge=10, le=5000, description="Target word count")
    include_subject: bool = Field(default=True, description="Generate subject line (for emails)")
    personalization_level: int = Field(default=2, ge=1, le=5, description="1=generic, 5=highly personalized")
    constraints: List[str] = Field(default_factory=list, description="Content constraints (no pricing, etc.)")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "template": "followup_email",
                    "tone": "professional",
                    "word_count": 150,
                    "include_subject": True,
                    "personalization_level": 4,
                    "constraints": ["no pricing", "mention recent funding"]
                }
            ]
        }


class CopywriterTaskPayload(BaseModel):
    """Payload for copywriter tasks"""
    lead_data: LeadData = Field(..., description="Lead information")
    campaign_context: CampaignContext = Field(..., description="Campaign metadata")
    instructions: CopyInstructions = Field(..., description="Copy generation instructions")
    previous_interactions: List[Dict[str, Any]] = Field(default_factory=list, description="Past emails/messages")
    timeout_ms: int = Field(default=60000, ge=1000, le=300000, description="Generation timeout")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "lead_data": {
                        "id": "lead-123",
                        "email": "john@example.com",
                        "name": "John Doe",
                        "company": "Acme Corp",
                        "title": "VP of Engineering"
                    },
                    "campaign_context": {
                        "campaign_id": "camp-123",
                        "variant": "A",
                        "sequence_step": 1,
                        "product_name": "AI Platform"
                    },
                    "instructions": {
                        "template": "cold_email",
                        "tone": "professional",
                        "word_count": 150
                    }
                }
            ]
        }


class GeneratedCopy(BaseModel):
    """Generated copy output"""
    subject: Optional[str] = Field(None, description="Email subject line")
    body: str = Field(..., min_length=10, description="Main copy content")
    preview_text: Optional[str] = Field(None, description="Email preview text")
    word_count: int = Field(..., ge=0, description="Actual word count")
    personalization_tokens: List[str] = Field(default_factory=list, description="Tokens used ({{name}}, etc.)")
    
    @validator('body')
    def validate_body_not_empty(cls, v):
        """Ensure body has actual content"""
        if not v or v.strip() == "":
            raise ValueError("Copy body cannot be empty")
        return v


class CopywriterResultPayload(BaseModel):
    """Payload for copywriter results"""
    generated_copy: GeneratedCopy = Field(..., description="Generated copy content")
    lead_id: str = Field(..., description="Lead ID this copy is for")
    campaign_id: str = Field(..., description="Campaign ID")
    variant: Optional[str] = Field(None, description="A/B test variant")
    generation_time_ms: Optional[float] = Field(None, description="Time taken to generate")
    model_used: Optional[str] = Field(None, description="LLM model used (gpt-4, claude-3, etc.)")
    tokens_used: Optional[int] = Field(None, description="API tokens consumed")
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Quality score (0-1)")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "generated_copy": {
                        "subject": "Quick question about Acme Corp's engineering workflow",
                        "body": "Hi John,\n\nI noticed Acme Corp recently...",
                        "word_count": 147,
                        "personalization_tokens": ["{{name}}", "{{company}}"]
                    },
                    "lead_id": "lead-123",
                    "campaign_id": "camp-123",
                    "variant": "A",
                    "generation_time_ms": 3200.5,
                    "model_used": "gpt-4",
                    "tokens_used": 450
                }
            ]
        }
