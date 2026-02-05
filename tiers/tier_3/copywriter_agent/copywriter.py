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
import re
from typing import Dict, Any, Optional

from core.security.prompt_hardening import (
    get_hardened_copywriter_prompt,
    sanitize_user_input,
    validate_llm_output_safe,
    validate_output_comprehensive,
    scrub_ai_references,
    scrub_output_aggressive,
    detect_injection_attempt,
    detect_ai_vocabulary,
)

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
        self.use_langgraph = os.getenv("LANGGRAPH_WORKFLOWS_ENABLED", "1").lower() in ("1", "true", "yes")
        self._graph_runner = None

    def _get_graph_runner(self):
        if self._graph_runner is not None:
            return self._graph_runner
        from core.langgraph import LangGraphRunner

        async def _execute_graph(state):
            task_data = state.get("task_data") or {}
            context = state.get("context") or {}
            return await self._execute_core(task_data, context)

        async def _guardrails(state):
            output = state.get("output") or {}
            if output.get("status") != "success":
                return output
            copy = output.get("copy") or {}
            subject = str(copy.get("subject") or "").strip()
            body = str(copy.get("body") or "").strip()
            if not subject or not body:
                return {"status": "error", "error": "empty_copy_output"}
            return output

        self._graph_runner = LangGraphRunner(
            name="copywriter",
            execute_fn=_execute_graph,
            required_input_keys=["task_data"],
            guardrails_fn=_guardrails,
        )
        return self._graph_runner

    def _replace_placeholder_with_value(
        self,
        text: str,
        *,
        recipient_name: Optional[str] = None,
        recipient_company: Optional[str] = None,
        recipient_role: Optional[str] = None,
        sender_name: Optional[str] = None,
        sender_company: Optional[str] = None,
        sender_email: Optional[str] = None,
    ) -> str:
        """Replace common LLM placeholders with actual values before sanitization.
        
        This handles cases where the LLM ignores instructions and emits placeholders
        like [Recipient's Name], [Your Company], etc.
        """
        if not text:
            return ""
        
        result = text
        
        # Recipient placeholders → actual recipient data
        recipient_patterns = [
            r"\[Recipient'?s?\s*Name\]",
            r"\[Name\]",
            r"\[First\s*Name\]",
            r"\[Contact\s*Name\]",
        ]
        for pattern in recipient_patterns:
            if recipient_name and recipient_name.lower() != "there":
                result = re.sub(pattern, recipient_name, result, flags=re.IGNORECASE)
            else:
                # Replace with empty or generic greeting handled later
                result = re.sub(pattern, "", result, flags=re.IGNORECASE)
        
        # Recipient company
        company_patterns = [
            r"\[Recipient'?s?\s*Company\]",
            r"\[Company\s*Name\]",
            r"\[Their\s*Company\]",
        ]
        for pattern in company_patterns:
            if recipient_company:
                result = re.sub(pattern, recipient_company, result, flags=re.IGNORECASE)
            else:
                result = re.sub(pattern, "", result, flags=re.IGNORECASE)
        
        # Sender placeholders → actual sender data
        sender_name_patterns = [
            r"\[Your\s*Name\]",
            r"\[Sender'?s?\s*Name\]",
            r"\[My\s*Name\]",
        ]
        for pattern in sender_name_patterns:
            if sender_name:
                result = re.sub(pattern, sender_name, result, flags=re.IGNORECASE)
            else:
                result = re.sub(pattern, "", result, flags=re.IGNORECASE)
        
        sender_company_patterns = [
            r"\[Your\s*Company\]",
            r"\[Our\s*Company\]",
            r"\[Company\]",
            r"\[Sender'?s?\s*Company\]",
        ]
        for pattern in sender_company_patterns:
            if sender_company:
                result = re.sub(pattern, sender_company, result, flags=re.IGNORECASE)
            else:
                result = re.sub(pattern, "", result, flags=re.IGNORECASE)
        
        # Other common placeholders to remove
        other_patterns = [
            r"\[Your\s*Position\]",
            r"\[Your\s*Title\]",
            r"\[Your\s*Role\]",
            r"\[Your\s*Contact\s*Info(?:rmation)?\]",
            r"\[Contact\s*Info(?:rmation)?\]",
            r"\[Email\]",
            r"\[Phone\]",
            r"\[Phone\s*Number\]",
        ]
        for pattern in other_patterns:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)
        
        return result

    def _strip_square_bracket_text(self, text: str) -> str:
        """Remove any remaining '[...]' fragments from model output.

        The copywriter prompt forbids square brackets, but LLMs can still
        occasionally emit template placeholders (e.g. [Your Name]). This is a
        last-resort sanitizer to keep outbound copy clean.
        """
        if not text:
            return ""
        # Remove bracketed placeholders and any leftover double spaces.
        cleaned = re.sub(r"\[[^\]]*\]", "", text)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        # Normalize blank lines (avoid huge gaps after removals)
        lines = [ln.rstrip() for ln in cleaned.splitlines()]
        cleaned = "\n".join(lines).strip()
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned

    def _sanitize_email_copy(
        self,
        subject: str,
        body: str,
        *,
        recipient_name: Optional[str] = None,
        recipient_company: Optional[str] = None,
        recipient_role: Optional[str] = None,
        sender_name: Optional[str] = None,
        sender_company: Optional[str] = None,
        sender_email: Optional[str] = None,
    ) -> Dict[str, str]:
        """Sanitize email copy by replacing placeholders with actual values.
        
        First attempts intelligent replacement, then strips any remaining brackets.
        """
        # Step 1: Replace known placeholders with actual values
        subject_replaced = self._replace_placeholder_with_value(
            subject,
            recipient_name=recipient_name,
            recipient_company=recipient_company,
            recipient_role=recipient_role,
            sender_name=sender_name,
            sender_company=sender_company,
            sender_email=sender_email,
        )
        body_replaced = self._replace_placeholder_with_value(
            body,
            recipient_name=recipient_name,
            recipient_company=recipient_company,
            recipient_role=recipient_role,
            sender_name=sender_name,
            sender_company=sender_company,
            sender_email=sender_email,
        )
        
        # Step 2: Strip any remaining unknown brackets
        subject_clean = self._strip_square_bracket_text(subject_replaced)
        body_clean = self._strip_square_bracket_text(body_replaced)
        
        # Step 3: Fix greeting if recipient name was missing
        # "Hi ," → "Hi there," or just "Hi,"
        body_clean = re.sub(r"^(Hi|Hello|Hey)\s*,", r"\1 there,", body_clean, flags=re.IGNORECASE)
        # Remove duplicate "there there" if it happened
        body_clean = re.sub(r"there\s+there", "there", body_clean, flags=re.IGNORECASE)
        
        return {
            "subject": subject_clean.strip() or "Re:",
            "body": body_clean.strip(),
        }
    
    async def execute(self, task_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self.use_langgraph:
            runner = self._get_graph_runner()
            graph_result = await runner.run(
                state_input={
                    "task_data": task_data,
                    "context": context or {},
                    "task_id": task_data.get("task_id"),
                    "correlation_id": task_data.get("correlation_id"),
                },
                execution_id=str(task_data.get("task_id") or task_data.get("correlation_id") or ""),
            )
            if graph_result.get("status") == "success":
                return graph_result.get("output", {})
            return {
                "status": "error",
                "error": graph_result.get("error", "langgraph_failed"),
                "trace": graph_result.get("trace", []),
            }
        return await self._execute_core(task_data, context)

    async def _execute_core(self, task_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
        # Reply mode: if a reply_packet is present, generate a reply-style email.
        if isinstance(context.get("reply_packet"), dict):
            return await self._generate_reply_email(context, tone, length)

        # Extract context for sanitization
        recipient_name = context.get("recipient_name", "there")
        recipient_company = context.get("company_name")
        sender_config = self._get_sender_config(context)

        prompt = self._build_email_prompt(context, tone, length)
        llm_resp = await self._call_llm(prompt, kind="email")
        if llm_resp:
            sanitized = self._sanitize_email_copy(
                str(llm_resp.get("subject", "Follow up")),
                str(llm_resp.get("body", llm_resp.get("text", ""))),
                recipient_name=recipient_name,
                recipient_company=recipient_company,
                sender_name=sender_config.get("sender_name"),
                sender_company=sender_config.get("sender_company"),
                sender_email=sender_config.get("sender_email"),
            )
            return {
                "status": "success",
                "copy": {
                    "subject": sanitized["subject"],
                    "body": sanitized["body"],
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

    async def _generate_reply_email(self, context: dict, tone: str, length: str) -> Dict[str, Any]:
        """Generate a reply to an inbound email event using a ReplyPacket-shaped context.
        
        SECURITY: This method handles external user input (inbound emails) which may
        contain injection attempts. All inbound content is:
        1. Checked for injection patterns (logged but not blocked - we still reply professionally)
        2. Sanitized before being included in prompts
        3. The LLM output is validated and scrubbed before return
        """
        reply_packet = context.get("reply_packet") or {}
        inbound = (reply_packet.get("inbound_email_event") or {}) if isinstance(reply_packet, dict) else {}
        facts = (reply_packet.get("facts") or {}) if isinstance(reply_packet, dict) else {}
        conversation = (reply_packet.get("conversation") or {}) if isinstance(reply_packet, dict) else {}
        lead_resolution = (reply_packet.get("lead_resolution") or {}) if isinstance(reply_packet, dict) else {}
        # Check upstream for additional lead/RAG data
        upstream = context.get("upstream") or {}
        leads_result = upstream.get("leads_result") or {} if isinstance(upstream, dict) else {}

        # === SECURITY: Check inbound email for injection attempts ===
        inbound_text = str(inbound.get("text") or inbound.get("body") or inbound.get("snippet") or "")
        inbound_subject = str(inbound.get("subject") or "")
        
        is_injection, matched_pattern = detect_injection_attempt(inbound_text + " " + inbound_subject)
        if is_injection:
            logger.warning(
                f"[COPYWRITER:SECURITY] Injection attempt detected in inbound email! "
                f"Pattern: {matched_pattern}, From: {inbound.get('from')}"
            )
            # We still generate a professional reply, but the prompt hardening will
            # instruct the LLM to treat this as potentially malicious content

        # --- DEBUG: Log received data for troubleshooting ---
        self._log_reply_context_debug(
            reply_packet=reply_packet,
            inbound=inbound,
            facts=facts,
            lead_resolution=lead_resolution,
            conversation=conversation,
            upstream=upstream,
        )

        # --- Extract recipient info from multiple sources ---
        recipient_name = self._extract_recipient_name(inbound, facts, lead_resolution, leads_result)
        recipient_company = self._extract_company(facts, lead_resolution, leads_result)
        recipient_role = self._extract_role(facts, lead_resolution, leads_result)
        recent_messages = conversation.get("recent_messages") or [] if isinstance(conversation, dict) else []
        
        # --- DEBUG: Log extracted values ---
        logger.info(
            "[COPYWRITER:DEBUG] Extracted recipient info: name=%s, company=%s, role=%s, msg_count=%d",
            recipient_name,
            recipient_company,
            recipient_role,
            len(recent_messages),
        )

        # --- Extract sender/company branding info ---
        sender_config = self._get_sender_config(context)
        logger.info(
            "[COPYWRITER:DEBUG] Sender config: name=%s, company=%s, email=%s",
            sender_config.get("sender_name"),
            sender_config.get("sender_company"),
            sender_config.get("sender_email"),
        )

        prompt = self._build_reply_email_prompt(
            inbound=inbound,
            recipient_name=recipient_name,
            recipient_company=recipient_company,
            recipient_role=recipient_role,
            intent=facts.get("intent") if isinstance(facts, dict) else None,
            conversation_summary=conversation.get("summary") if isinstance(conversation, dict) else None,
            recent_messages=recent_messages,
            tone=tone,
            length=length,
            sender_config=sender_config,
        )
        llm_resp = await self._call_llm(prompt, kind="email")
        if llm_resp:
            subject = llm_resp.get("subject") or "Re: " + str(inbound.get("subject") or "")
            body = llm_resp.get("body") or llm_resp.get("text") or ""
            sanitized = self._sanitize_email_copy(
                str(subject),
                str(body),
                recipient_name=recipient_name,
                recipient_company=recipient_company,
                recipient_role=recipient_role,
                sender_name=sender_config.get("sender_name"),
                sender_company=sender_config.get("sender_company"),
                sender_email=sender_config.get("sender_email"),
            )
            return {
                "status": "success",
                "copy": {
                    "subject": sanitized["subject"],
                    "body": sanitized["body"],
                    "type": "email",
                    "metadata": llm_resp.get("metadata", {}),
                },
            }

        # Fallback reply template (deterministic but inbound-aware)
        inbound_subject = (inbound.get("subject") or "").strip()
        inbound_text = (
            (inbound.get("text") or inbound.get("body") or inbound.get("snippet") or "")
            .strip()
        )
        inbound_text_short = inbound_text[:400]
        subject = inbound_subject
        if subject:
            if not subject.lower().startswith("re:"):
                subject = f"Re: {subject}"
        else:
            subject = "Re:"
        opener = f"Hi {recipient_name}," if recipient_name and recipient_name != "there" else "Hi,"
        company_line = f" (regarding {recipient_company})" if recipient_company else ""
        
        # Build signature from sender_config
        sender_name = sender_config.get("sender_name", "")
        sender_company = sender_config.get("sender_company", "")
        if sender_name and sender_company:
            signature = f"Best regards,\n{sender_name}\n{sender_company}"
        elif sender_name:
            signature = f"Best regards,\n{sender_name}"
        elif sender_company:
            signature = f"Best regards,\n{sender_company} Team"
        else:
            signature = "Best regards"
        
        body = (
            f"{opener}\n\n"
            f"Thanks for reaching out{company_line}. "
            f"I want to make sure I understand correctly."
            f"\n\n"
            f"You said:\n\"{inbound_text_short}\"\n\n"
            f"Could you confirm the key details (timeline + best next step) so I can help?\n\n"
            f"{signature}"
        )
        return {
            "status": "success",
            "copy": {
                "subject": subject,
                "body": body,
                "type": "email",
                "metadata": {"provider": "template_fallback", "mode": "reply"},
            },
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

    def _log_reply_context_debug(
        self,
        *,
        reply_packet: dict,
        inbound: dict,
        facts: dict,
        lead_resolution: dict,
        conversation: dict,
        upstream: dict,
    ) -> None:
        """Log comprehensive debug info about the reply context received by Copywriter.
        
        This helps diagnose data propagation issues in the Manager→Leads→RAG→Copywriter chain.
        """
        try:
            # Log summary of what we received
            logger.info("[COPYWRITER:DEBUG] === REPLY CONTEXT RECEIVED ===")
            
            # Inbound email event
            logger.info(
                "[COPYWRITER:DEBUG] Inbound: from=%s, from_name=%s, subject=%s",
                inbound.get("from"),
                inbound.get("from_name"),
                (inbound.get("subject") or "")[:50],
            )
            
            # Facts from reply_packet
            logger.info(
                "[COPYWRITER:DEBUG] Facts: first_name=%s, last_name=%s, company=%s, role=%s, email=%s",
                facts.get("first_name"),
                facts.get("last_name"),
                facts.get("company"),
                facts.get("role"),
                facts.get("email"),
            )
            
            # Lead resolution
            lead_data = lead_resolution.get("lead_data") or {}
            logger.info(
                "[COPYWRITER:DEBUG] LeadResolution: status=%s, lead_id=%s, source=%s",
                lead_resolution.get("status"),
                lead_resolution.get("lead_id"),
                lead_resolution.get("source"),
            )
            if lead_data:
                logger.info(
                    "[COPYWRITER:DEBUG] LeadData: first_name=%s, last_name=%s, company_name=%s, job_title=%s, email=%s",
                    lead_data.get("first_name"),
                    lead_data.get("last_name"),
                    lead_data.get("company_name"),
                    lead_data.get("job_title"),
                    lead_data.get("email"),
                )
            else:
                logger.warning("[COPYWRITER:DEBUG] LeadData is empty or missing!")
            
            # Conversation history
            recent_messages = conversation.get("recent_messages") or []
            logger.info(
                "[COPYWRITER:DEBUG] Conversation: id=%s, summary=%s, message_count=%d",
                conversation.get("conversation_id"),
                (conversation.get("summary") or "")[:50] if conversation.get("summary") else None,
                len(recent_messages),
            )
            
            # Upstream data (if any)
            if upstream:
                leads_result = upstream.get("leads_result") or {}
                logger.info(
                    "[COPYWRITER:DEBUG] Upstream leads_result present: %s",
                    bool(leads_result),
                )
            
            logger.info("[COPYWRITER:DEBUG] === END REPLY CONTEXT ===")
            
        except Exception as e:
            # Debug logging must never break the main flow
            logger.warning(f"[COPYWRITER:DEBUG] Failed to log context: {e}")
    
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
            "subject": f"{recipient}, Partnership Opportunity with {company}",
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

    # ------------------------ Data Extraction Helpers ------------------------ #
    def _extract_recipient_name(self, inbound: dict, facts: dict, lead_resolution: dict, leads_result: dict) -> str:
        """Extract recipient name from multiple sources, with email-parsing fallback."""
        # 1. Check inbound from_name
        if inbound.get("from_name"):
            return str(inbound["from_name"]).strip()
        # 2. Check facts
        if isinstance(facts, dict):
            for key in ("name", "first_name", "contact_name", "recipient_name"):
                if facts.get(key):
                    return str(facts[key]).strip()
        # 3. Check lead_resolution for lead data
        if isinstance(lead_resolution, dict):
            lead_data = lead_resolution.get("lead_data") or lead_resolution.get("lead") or {}
            if isinstance(lead_data, dict):
                for key in ("first_name", "name", "full_name"):
                    if lead_data.get(key):
                        return str(lead_data[key]).strip()
        # 4. Check upstream leads_result
        if isinstance(leads_result, dict):
            lead_info = leads_result.get("lead") or leads_result.get("lead_data") or {}
            if isinstance(lead_info, dict):
                for key in ("first_name", "name", "full_name"):
                    if lead_info.get(key):
                        return str(lead_info[key]).strip()
        # 5. Parse email address as last resort
        email = inbound.get("from") or ""
        if email and "@" in email:
            local_part = email.split("@")[0]
            # Remove common prefixes/suffixes and numbers
            import re
            clean = re.sub(r"[._\-]+", " ", local_part)  # Replace separators with spaces
            clean = re.sub(r"\d+", "", clean)  # Remove numbers
            clean = clean.strip()
            if clean and len(clean) >= 2:
                # Capitalize words
                return " ".join(word.capitalize() for word in clean.split())
        return "there"  # Generic fallback

    def _extract_company(self, facts: dict, lead_resolution: dict, leads_result: dict) -> Optional[str]:
        """Extract company name from multiple sources."""
        # 1. Check facts
        if isinstance(facts, dict):
            for key in ("company", "company_name", "organization"):
                if facts.get(key):
                    return str(facts[key]).strip()
        # 2. Check lead_resolution
        if isinstance(lead_resolution, dict):
            lead_data = lead_resolution.get("lead_data") or lead_resolution.get("lead") or {}
            if isinstance(lead_data, dict):
                for key in ("company", "company_name", "organization"):
                    if lead_data.get(key):
                        return str(lead_data[key]).strip()
        # 3. Check upstream leads_result
        if isinstance(leads_result, dict):
            lead_info = leads_result.get("lead") or leads_result.get("lead_data") or {}
            if isinstance(lead_info, dict):
                for key in ("company", "company_name", "organization"):
                    if lead_info.get(key):
                        return str(lead_info[key]).strip()
        return None

    def _extract_role(self, facts: dict, lead_resolution: dict, leads_result: dict) -> Optional[str]:
        """Extract role/title from multiple sources."""
        # 1. Check facts
        if isinstance(facts, dict):
            for key in ("role", "title", "job_title", "position"):
                if facts.get(key):
                    return str(facts[key]).strip()
        # 2. Check lead_resolution
        if isinstance(lead_resolution, dict):
            lead_data = lead_resolution.get("lead_data") or lead_resolution.get("lead") or {}
            if isinstance(lead_data, dict):
                for key in ("role", "title", "job_title", "position"):
                    if lead_data.get(key):
                        return str(lead_data[key]).strip()
        # 3. Check upstream leads_result
        if isinstance(leads_result, dict):
            lead_info = leads_result.get("lead") or leads_result.get("lead_data") or {}
            if isinstance(lead_info, dict):
                for key in ("role", "title", "job_title", "position"):
                    if lead_info.get(key):
                        return str(lead_info[key]).strip()
        return None

    def _get_sender_config(self, context: dict) -> Dict[str, str]:
        """
        Get sender/company branding info from context, task payload, or environment.
        
        Priority order:
        1. Explicit sender_config in context
        2. Top-level from_name/from_email in context
        3. Environment variables (SENDER_NAME, SENDER_COMPANY, SENDER_EMAIL)
        4. Default fallbacks (empty = omit from signature)
        """
        sender_config = context.get("sender_config") or {}
        
        # Try explicit sender_config first
        sender_name = sender_config.get("sender_name") or sender_config.get("from_name")
        sender_company = sender_config.get("sender_company") or sender_config.get("company_name")
        sender_email = sender_config.get("sender_email") or sender_config.get("from_email")
        
        # Fallback to top-level context
        if not sender_name:
            sender_name = context.get("from_name") or context.get("sender_name")
        if not sender_company:
            sender_company = context.get("sender_company") or context.get("our_company")
        if not sender_email:
            sender_email = context.get("from_email") or context.get("sender_email")
        
        # Fallback to environment variables
        if not sender_name:
            sender_name = os.getenv("SENDER_NAME", "")
        if not sender_company:
            sender_company = os.getenv("SENDER_COMPANY", "")
        if not sender_email:
            sender_email = os.getenv("SENDER_EMAIL", "")
        
        return {
            "sender_name": sender_name.strip() if sender_name else "",
            "sender_company": sender_company.strip() if sender_company else "",
            "sender_email": sender_email.strip() if sender_email else "",
        }

    # ------------------------ LLM Helpers ------------------------ #
    def _build_email_prompt(self, context: Dict[str, Any], tone: str, length: str) -> str:
        # Sanitize all user-provided content
        recipient = sanitize_user_input(str(context.get('recipient_name', 'there')))
        company = sanitize_user_input(str(context.get('company_name', 'their company')))
        value_prop = sanitize_user_input(str(context.get('value_prop', 'a helpful solution')))
        cta = sanitize_user_input(str(context.get('call_to_action', 'schedule a short demo')))
        
        base_prompt = (
            f"Write a concise B2B outreach email. Tone: {tone}. Length: {length}.\n"
            f"Recipient: {recipient}. Company: {company}.\n"
            f"Value Proposition: {value_prop}. Call To Action: {cta}.\n\n"
            "Return JSON only with keys 'subject' and 'body'.\n"
            "Write as a real sales professional would - natural, personable, human."
        )
        return get_hardened_copywriter_prompt(
            base_prompt=base_prompt,
            include_human_identity=True,
            include_anti_injection=True
        )

    def _build_reply_email_prompt(
        self,
        *,
        inbound: Dict[str, Any],
        recipient_name: str,
        recipient_company: Optional[str],
        recipient_role: Optional[str],
        intent: Optional[str],
        conversation_summary: Optional[str],
        recent_messages: list,
        tone: str,
        length: str,
        sender_config: Optional[Dict[str, str]] = None,
    ) -> str:
        # Sanitize all inbound content to prevent injection
        inbound_from = sanitize_user_input(str(inbound.get("from") or ""))
        inbound_subject = sanitize_user_input(str(inbound.get("subject") or ""))
        inbound_text = sanitize_user_input(
            str(inbound.get("text") or inbound.get("body") or inbound.get("snippet") or "")
        )
        recipient_name = sanitize_user_input(str(recipient_name or ""))
        recipient_company = sanitize_user_input(str(recipient_company or ""))
        recipient_role = sanitize_user_input(str(recipient_role or ""))
        intent = sanitize_user_input(str(intent or ""))
        conversation_summary = sanitize_user_input(str(conversation_summary or ""))

        # Build recent conversation context if available (sanitized)
        conv_context = ""
        if recent_messages:
            conv_context = "Recent conversation history:\n"
            for msg in recent_messages[-5:]:  # Last 5 messages
                sender = msg.get("sender_type") or msg.get("direction") or "unknown"
                text = sanitize_user_input((msg.get("body") or msg.get("content") or "")[:200])
                conv_context += f"  - [{sender}]: {text}\n"

        # Extract sender info with fallbacks
        sender_config = sender_config or {}
        sender_name = sender_config.get("sender_name", "")
        sender_company = sender_config.get("sender_company", "")
        
        # Build signature instruction based on available sender info
        if sender_name and sender_company:
            signature_instruction = f"Sign off exactly as: 'Best regards,\n{sender_name}\n{sender_company}'"
        elif sender_name:
            signature_instruction = f"Sign off exactly as: 'Best regards,\n{sender_name}'"
        elif sender_company:
            signature_instruction = f"Sign off exactly as: 'Best regards,\n{sender_company} Team'"
        else:
            signature_instruction = "Sign off with 'Best regards' only (signature will be added later)."

        base_prompt = (
            f"Write a helpful B2B email reply. Tone: {tone}. Length: {length}.\n\n"
            "=== FORMATTING RULES (MUST FOLLOW) ===\n"
            "1. NEVER use placeholder brackets like [Name], [Company], [Your Name], etc.\n"
            "2. NEVER output ANY text in square brackets - STRICTLY FORBIDDEN.\n"
            "3. Use the ACTUAL recipient name below. If unknown, use 'Hi there'.\n"
            "4. Do NOT invent facts, company names, or contact info not provided.\n"
            f"5. {signature_instruction}\n\n"
            f"=== RECIPIENT ===\n"
            f"Name: {recipient_name or 'there'}\n"
            f"Email: {inbound_from}\n"
            f"Company: {recipient_company or 'their company'}\n"
            f"Role: {recipient_role or 'Unknown'}\n\n"
            f"=== YOUR IDENTITY ===\n"
            f"Name: {sender_name or '(will be added in signature)'}\n"
            f"Company: {sender_company or '(will be added in signature)'}\n\n"
            f"=== THEIR EMAIL ===\n"
            f"Subject: {inbound_subject}\n"
            f"Body: {inbound_text}\n\n"
            f"{conv_context}"
            f"Detected intent: {intent or 'General inquiry'}\n"
            f"Summary: {conversation_summary or 'No prior context'}\n\n"
            "Return JSON only: {{\"subject\": \"...\", \"body\": \"...\"}}\n"
            "Subject should be 'Re: <original subject>' when replying."
        )
        
        return get_hardened_copywriter_prompt(
            base_prompt=base_prompt,
            include_human_identity=True,
            include_anti_injection=True
        )

    def _build_sms_prompt(self, context: Dict[str, Any], tone: str, max_length: int) -> str:
        # Sanitize user inputs
        recipient = sanitize_user_input(str(context.get('recipient_name', 'there')))
        company = sanitize_user_input(str(context.get('company_name', 'our company')))
        key_info = sanitize_user_input(str(context.get('key_info', 'an update')))
        
        base_prompt = (
            f"Write a short opt-in compliant B2B SMS message.\n"
            f"Tone: {tone}. Max length: {max_length} characters.\n"
            f"Recipient: {recipient}. Company: {company}.\n"
            f"Key Info: {key_info}.\n\n"
            "Write naturally like a real person texting. No robotic language.\n"
            "Return JSON with key 'text'."
        )
        return get_hardened_copywriter_prompt(
            base_prompt=base_prompt,
            include_human_identity=True,
            include_anti_injection=True
        )

    async def _call_llm(self, prompt: str, kind: str) -> Optional[Dict[str, Any]]:  # pragma: no cover - network
        provider = (self.llm_config.get("provider") or os.getenv("LLM_PROVIDER") or "openai").lower()
        model = self.llm_config.get("model") or os.getenv("LLM_MODEL") or ("gpt-4o-mini" if provider == "openai" else "claude-3-5-sonnet-20241022")
        temperature = float(self.llm_config.get("temperature") or os.getenv("LLM_TEMPERATURE") or 0.7)

        def _validate_and_scrub(result: Dict[str, Any]) -> Dict[str, Any]:
            """
            PRODUCTION-GRADE validation and scrubbing pipeline.
            
            Multi-pass sanitization to ensure no AI signatures leak to external world:
            1. Comprehensive validation check
            2. Aggressive AI reference scrubbing
            3. AI vocabulary detection and warning
            4. Final validation pass
            """
            body = result.get("body", "")
            subject = result.get("subject", "")
            metadata = result.setdefault("metadata", {})
            
            # === BODY PROCESSING ===
            
            # Step 1: Comprehensive validation
            body_validation = validate_output_comprehensive(body)
            if not body_validation["safe"]:
                logger.warning(
                    f"[COPYWRITER:SECURITY] Body failed validation: severity={body_validation['severity']}, "
                    f"issues={body_validation['issues']}"
                )
                
                # Step 2: Aggressive scrubbing for unsafe content
                body = scrub_output_aggressive(body)
                metadata["body_scrubbed"] = True
                metadata["body_scrub_reason"] = body_validation["issues"]
            
            # Step 3: Check AI vocabulary count even if passed validation
            ai_vocab = detect_ai_vocabulary(body)
            if ai_vocab:
                logger.info(
                    f"[COPYWRITER:SECURITY] AI vocabulary detected ({len(ai_vocab)}): {ai_vocab[:5]}"
                )
                # Light scrubbing for vocabulary even if it passed other checks
                body = scrub_ai_references(body)
                metadata["ai_vocabulary_count"] = len(ai_vocab)
                
                # If still high after scrubbing, log warning
                ai_vocab_after = detect_ai_vocabulary(body)
                if len(ai_vocab_after) > 3:
                    logger.warning(
                        f"[COPYWRITER:SECURITY] High AI vocabulary persists after scrubbing: {ai_vocab_after[:5]}"
                    )
                    metadata["ai_vocabulary_warning"] = True
            
            # Step 4: Final safety check
            final_safe, final_issues = validate_llm_output_safe(body)
            if final_issues:
                body = scrub_output_aggressive(body)
                metadata["final_scrub"] = True
                metadata["final_issues"] = final_issues
            
            result["body"] = body
            
            # === SUBJECT PROCESSING ===
            
            # Validate subject
            subj_validation = validate_output_comprehensive(subject)
            if not subj_validation["safe"]:
                logger.warning(
                    f"[COPYWRITER:SECURITY] Subject failed validation: {subj_validation['issues']}"
                )
                subject = scrub_output_aggressive(subject)
                metadata["subject_scrubbed"] = True
            
            result["subject"] = subject
            
            return result

        try:
            if provider == "openai" and OpenAI:
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    logger.warning("OPENAI_API_KEY not set; using template fallback")
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
                result = {
                    **(parsed or {"body": content}),
                    "metadata": {
                        "provider": "openai",
                        "model": model,
                        "temperature": temperature
                    }
                }
                return _validate_and_scrub(result)
            
            if provider == "anthropic" and anthropic:
                api_key = os.getenv("ANTHROPIC_API_KEY")
                if not api_key:
                    logger.warning("ANTHROPIC_API_KEY not set; using template fallback")
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
                result = {
                    **(parsed or {"body": content}),
                    "metadata": {
                        "provider": "anthropic",
                        "model": model,
                        "temperature": temperature
                    }
                }
                return _validate_and_scrub(result)
        except Exception as e:  # Network or parsing failure
            logger.warning(f"LLM call failed ({provider}): {e}")
            return None
        if provider == "openai" and not OpenAI:
            logger.warning("OpenAI SDK not installed/importable; using template fallback")
        if provider == "anthropic" and not anthropic:
            logger.warning("Anthropic SDK not installed/importable; using template fallback")
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
