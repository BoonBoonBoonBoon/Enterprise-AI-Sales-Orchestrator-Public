"""
Copywriter Agent - Async Implementation

Copywriting agent for email and SMS generation with:
- Agent Harness for retry, observability, and checkpointing
- Redis Streams consumer pattern
- Hierarchical stream naming: {tenant}:agents:copywriter:tasks/results
"""

import logging
import os
import asyncio
from typing import Dict, Any, Optional

try:
    from openai import OpenAI  # OpenAI SDK (>=1.0.0)
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore
try:
    import anthropic  # Anthropic SDK
except ImportError:  # pragma: no cover - optional dependency
    anthropic = None  # type: ignore

logger = logging.getLogger(__name__)


class CopywriterAgent:
    """
    Copywriter Agent for email and SMS generation.
    
    Provides copywriting for:
    - Email campaigns (subject + body)
    - SMS messages
    - Personalized content generation
    """
    
    def __init__(
        self,
        llm_config: Optional[Dict[str, Any]] = None,
        default_tone: str = "professional"
    ):
        """
        Initialize Copywriter Agent.
        
        Args:
            llm_config: Optional LLM configuration (for future integration)
            default_tone: Default writing tone (professional, casual, formal)
        """
        self.llm_config = llm_config or {}
        self.default_tone = default_tone
    
    async def execute(self, task_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute copywriting task.
        
        Args:
            task_data: Task data with copywriting request
            context: Optional execution context
        
        Returns:
            Generated copy
        """
        try:
            copy_type = task_data.get("type", "email")
            ctx = task_data.get("context", {})
            tone = task_data.get("tone", self.default_tone)
            
            logger.info(f"Executing copywriting task: {copy_type}")
            
            if copy_type == "email":
                return await self._generate_email(ctx, tone, task_data.get("length", "medium"))
            elif copy_type == "sms":
                return await self._generate_sms(ctx, tone, task_data.get("max_length", 160))
            else:
                return {
                    "status": "error",
                    "error": f"Unknown copy type: {copy_type}"
                }
                
        except Exception as e:
            logger.error(f"Copywriting task execution failed: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _generate_email(self, context: dict, tone: str, length: str) -> Dict[str, Any]:
        """Generate email copy. Attempts LLM; falls back to template."""
        prompt = self._build_email_prompt(context, tone, length)
        llm_resp = await self._call_llm(prompt, kind="email")
        if llm_resp:
            return {
                "status": "success",
                "copy": {
                    "subject": llm_resp.get("subject", "Follow up"),
                    "body": llm_resp.get("body", llm_resp.get("text", "")),
                    "type": "email",
                    "metadata": llm_resp.get("metadata", {})
                }
            }

        # Fallback template logic
        recipient = context.get("recipient_name", "there")
        company = context.get("company_name", "your company")
        value_prop = context.get("value_prop", "our solution")
        cta = context.get("call_to_action", "Let me know if you'd like a quick demo.")
        subject = f"{recipient}, {value_prop} - Partnership Opportunity"
        body = (
            f"Hi {recipient},\n\n"
            f"I noticed your work at {company}. We've developed {value_prop} that could help streamline your workflow.\n\n"
            f"{cta}\n\n"
            "Best regards"
        )
        return {
            "status": "success",
            "copy": {
                "subject": subject,
                "body": body,
                "type": "email",
                "metadata": {"provider": "template_fallback"}
            }
        }
    
    async def _generate_sms(self, context: dict, tone: str, max_length: int) -> Dict[str, Any]:
        """Generate SMS copy. Attempts LLM; falls back to template."""
        prompt = self._build_sms_prompt(context, tone, max_length)
        llm_resp = await self._call_llm(prompt, kind="sms")
        if llm_resp:
            text = llm_resp.get("text") or llm_resp.get("body") or ""
            text = text[:max_length]
            return {
                "status": "success",
                "copy": {
                    "text": text,
                    "type": "sms",
                    "metadata": llm_resp.get("metadata", {})
                }
            }

        # Fallback template logic
        recipient = context.get("recipient_name", "there")
        company = context.get("company_name", "")
        key_info = context.get("key_info", "our latest update")
        text = f"Hi {recipient}, {key_info} from {company}. Reply YES for details."[:max_length]
        return {
            "status": "success",
            "copy": {
                "text": text,
                "type": "sms",
                "metadata": {"provider": "template_fallback"}
            }
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check agent health.
        
        Returns:
            Health status dictionary
        """
        try:
            return {
                "status": "healthy",
                "agent": "copywriter",
                "default_tone": self.default_tone
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "agent": "copywriter",
                "error": str(e)
            }
    
    # Legacy compatibility methods
    def write_email(self, context: Dict[str, Any]) -> Dict[str, str]:
        """
        Legacy email generation method (synchronous).
        
        For production use, prefer async execute() method.
        """
        # Simple template-based fallback
        recipient = context.get("recipient_name", "there")
        company = context.get("company_name", "your company")
        
        return {
            "subject": f"Partnership Opportunity with {company}",
            "body": f"Hi {recipient},\n\nI noticed your work at {company}...\n\nBest regards"
        }
    
    def write_text(self, context: Dict[str, Any]) -> str:
        """
        Legacy SMS generation method (synchronous).
        
        For production use, prefer async execute() method.
        """
        recipient = context.get("recipient_name", "")
        company = context.get("company_name", "")
        
        return f"Hi {recipient}, special offer from {company}! Reply YES for details."

    # ------------------------ LLM Helpers ------------------------ #
    def _build_email_prompt(self, context: Dict[str, Any], tone: str, length: str) -> str:
        return (
            "You are a B2B copywriter. Write a concise outreach email."\
            f" Tone: {tone}. Desired length: {length}. "
            f"Recipient: {context.get('recipient_name','there')}. "
            f"Company: {context.get('company_name','their company')}. "
            f"Value Proposition: {context.get('value_prop','a helpful solution')}. "
            f"Call To Action: {context.get('call_to_action','schedule a short demo')}."\
            " Return JSON with keys subject and body."
        )

    def _build_sms_prompt(self, context: Dict[str, Any], tone: str, max_length: int) -> str:
        return (
            "You write short opt-in compliant B2B SMS messages."\
            f" Tone: {tone}. Max length: {max_length} characters. "
            f"Recipient: {context.get('recipient_name','there')}. "
            f"Company: {context.get('company_name','our company')}. "
            f"Key Info: {context.get('key_info','an update')}."\
            " Return JSON with key text."
        )

    async def _call_llm(self, prompt: str, kind: str) -> Optional[Dict[str, Any]]:  # pragma: no cover - network
        provider = (self.llm_config.get("provider") or os.getenv("LLM_PROVIDER") or "openai").lower()
        model = self.llm_config.get("model") or os.getenv("LLM_MODEL") or ("gpt-4o-mini" if provider == "openai" else "claude-3-5-sonnet-20241022")
        temperature = float(self.llm_config.get("temperature") or os.getenv("LLM_TEMPERATURE") or 0.7)

        try:
            if provider == "openai" and OpenAI:
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    return None
                client = OpenAI(api_key=api_key)
                # Use JSON schema style if available else parse manually
                completion = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": "Return JSON only."}, {"role": "user", "content": prompt}],
                    temperature=temperature
                )
                content = completion.choices[0].message.content.strip()
                parsed = self._safe_json_parse(content)
                return {
                    **(parsed or {"body": content}),
                    "metadata": {
                        "provider": "openai",
                        "model": model,
                        "temperature": temperature
                    }
                }
            if provider == "anthropic" and anthropic:
                api_key = os.getenv("ANTHROPIC_API_KEY")
                if not api_key:
                    return None
                client = anthropic.Anthropic(api_key=api_key)
                msg = client.messages.create(
                    model=model,
                    max_tokens=800,
                    temperature=temperature,
                    messages=[{"role": "user", "content": prompt}]
                )
                content = "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")
                parsed = self._safe_json_parse(content)
                return {
                    **(parsed or {"body": content}),
                    "metadata": {
                        "provider": "anthropic",
                        "model": model,
                        "temperature": temperature
                    }
                }
        except Exception as e:  # Network or parsing failure
            logger.warning(f"LLM call failed ({provider}): {e}")
            return None
        return None

    def _safe_json_parse(self, text: str) -> Optional[Dict[str, Any]]:
        import json
        try:
            return json.loads(text)
        except Exception:
            return None


def generate_email(context: Dict[str, Any]) -> Dict[str, str]:
    return CopywriterAgent().write_email(context)


def generate_text(context: Dict[str, Any]) -> str:
    return CopywriterAgent().write_text(context)


__all__ = ["CopywriterAgent", "generate_email", "generate_text"]
