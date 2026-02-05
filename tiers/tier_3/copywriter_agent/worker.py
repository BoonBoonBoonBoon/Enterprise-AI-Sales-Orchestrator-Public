"""Copywriter Worker (Streams): consumes copy tasks and emits generated content.

Supports enhanced envelope with context forwarding from RAG worker.
Expects payload with lead_data, campaign_context, instructions.

Usage:
    python -m agent.operational_agents.copywriter.worker
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict

repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

from services.redis import RedisStreamsClient, config as rconf
from core.envelope import from_redis_message, task, result, error, to_redis_fields, Status
from core.utils.rate_limiter import init_rate_limiter, get_rate_limiter
from core.security.prompt_hardening import (
    get_hardened_copywriter_prompt,
    sanitize_user_input,
    validate_llm_output_safe,
    scrub_ai_references,
)

# Optional persistence for lead context enrichment
from services.persistence.service import build_supabase_service, ReadOnlyPersistenceFacade
PERSISTENCE_AVAILABLE = True

# Optional OpenAI/Anthropic imports
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class CopyWorker:
    TASK_STREAM = rconf.STREAM_TASKS_COPY
    RESULT_STREAM = rconf.STREAM_RESULTS_COPY
    DLQ_STREAM = rconf.STREAM_DLQ_COPY
    GROUP = rconf.GROUP_COPY_WRITERS

    def __init__(self) -> None:
        self.redis = RedisStreamsClient()
        self.worker_id = str(os.getpid())
        
        # Initialize persistence service for lead context enrichment
        self.persistence = None
        if PERSISTENCE_AVAILABLE and os.getenv("ENABLE_LEAD_CONTEXT_ENRICHMENT", "1").lower() in ("1", "true", "yes"):
            try:
                service = build_supabase_service()
                self.persistence = ReadOnlyPersistenceFacade(service)
                print(f"[CopyWorker {self.worker_id}] Lead context enrichment enabled")
            except Exception as e:
                print(f"[CopyWorker {self.worker_id}] WARNING: Could not initialize persistence for context enrichment: {e}")
        
        # Initialize LLM client based on env var
        self.llm_provider = os.getenv("LLM_PROVIDER", "placeholder").lower()
        self.llm_client = None
        
        if self.llm_provider == "openai" and OPENAI_AVAILABLE:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.llm_client = OpenAI(api_key=api_key)
                print(f"[CopyWorker {self.worker_id}] OpenAI client initialized")
            else:
                print(f"[CopyWorker {self.worker_id}] WARNING: OPENAI_API_KEY not set, using placeholder")
                self.llm_provider = "placeholder"
        
        elif self.llm_provider == "anthropic" and ANTHROPIC_AVAILABLE:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.llm_client = Anthropic(api_key=api_key)
                print(f"[CopyWorker {self.worker_id}] Anthropic client initialized")
            else:
                print(f"[CopyWorker {self.worker_id}] WARNING: ANTHROPIC_API_KEY not set, using placeholder")
                self.llm_provider = "placeholder"
        
        else:
            if self.llm_provider != "placeholder":
                print(f"[CopyWorker {self.worker_id}] WARNING: LLM_PROVIDER={self.llm_provider} not available, using placeholder")
            self.llm_provider = "placeholder"
        
        # Initialize rate limiter
        self.rate_limiter = init_rate_limiter(redis_client=self.redis)
        
        try:
            self.redis.xgroup_create(self.TASK_STREAM, self.GROUP, id="$", mkstream=True)
        except Exception:
            pass
        if os.getenv("REDIS_DEBUG", "0").lower() in ("1", "true", "yes"):
            print(
                f"[CopyWorker {self.worker_id}] ns={rconf.NAMESPACE} tasks={rconf.full_key(self.TASK_STREAM)} "
                f"results={rconf.full_key(self.RESULT_STREAM)} dlq={rconf.full_key(self.DLQ_STREAM)} group={self.GROUP}"
            )

        self._stop = threading.Event()
        if rconf.OPS_HB_ENABLED:
            def _hb_loop():
                key = rconf.hb_key("copy", self.worker_id)
                while not self._stop.is_set():
                    try:
                        self.redis.client.setex(self.redis._chan(key), rconf.OPS_HB_TTL, str(time.time()))
                    except Exception:
                        pass
                    self._stop.wait(rconf.OPS_HB_INTERVAL)
            self._hb_thread = threading.Thread(target=_hb_loop, daemon=True)
            self._hb_thread.start()

    def _ack(self, msg_id: str) -> None:
        try:
            self.redis.xack(self.TASK_STREAM, self.GROUP, msg_id)
        except Exception:
            pass

    def _publish(self, envelope, stream: str) -> None:
        """Publish result envelope to stream."""
        self.redis.xadd(stream, to_redis_fields(envelope), maxlen=rconf.STREAM_MAXLEN)

    def _enrich_lead_data(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich lead data with additional context from database.
        
        If lead_id is provided and persistence is available, fetch full lead
        record including custom fields, interaction history, and enrichment data.
        """
        if not self.persistence:
            return lead_data
        
        lead_id = lead_data.get("id")
        if not lead_id:
            return lead_data
        
        try:
            # Fetch full lead record from database
            full_lead = self.persistence.read("leads", lead_id)
            if not full_lead:
                print(f"[CopyWorker {self.worker_id}] Lead {lead_id} not found in database")
                return lead_data
            
            # Merge database fields into lead_data (database fields take precedence)
            enriched = {**lead_data, **full_lead}
            
            # Optionally fetch recent interactions/emails for context
            try:
                recent_interactions = self.persistence.query(
                    "lead_interactions",
                    filters={"lead_id": lead_id},
                    order_by="created_at",
                    descending=True,
                    limit=5
                )
                if recent_interactions:
                    enriched["recent_interactions"] = recent_interactions
            except Exception as e:
                # Non-critical: continue without interaction history
                print(f"[CopyWorker {self.worker_id}] Could not fetch interactions for lead {lead_id}: {e}")
            
            print(f"[CopyWorker {self.worker_id}] Enriched lead {lead_id} with {len(full_lead)} fields")
            return enriched
            
        except Exception as e:
            print(f"[CopyWorker {self.worker_id}] Error enriching lead {lead_id}: {e}")
            return lead_data

    def _build_prompt(self, lead_data: Dict[str, Any], campaign_context: Dict[str, Any], instructions: Dict[str, Any]) -> str:
        """Build LLM prompt from lead data, campaign context, and instructions."""
        lead_name = lead_data.get("first_name", lead_data.get("name", "there")).title()
        company = lead_data.get("company_name", lead_data.get("company", "your company"))
        lead_title = lead_data.get("title", "")
        lead_email = lead_data.get("email", "")
        lead_industry = lead_data.get("industry", "")
        lead_location = lead_data.get("location", "")
        
        campaign_name = campaign_context.get("campaign_name", "Outreach")
        step = campaign_context.get("step", campaign_context.get("sequence_step", 1))
        previous_subject = campaign_context.get("previous_subject", "")
        previous_body_summary = campaign_context.get("previous_body_summary", "")
        days_since_last_contact = campaign_context.get("days_since_last_contact", 0)
        product_name = campaign_context.get("product_name", "")
        value_proposition = campaign_context.get("value_proposition", "")
        
        tone = instructions.get("tone", "professional")
        language = instructions.get("language", "en-US")
        max_length = instructions.get("max_length", instructions.get("word_count", 200))
        cta = instructions.get("cta", instructions.get("call_to_action", "schedule a call"))
        required_elements = instructions.get("required_elements", instructions.get("constraints", []))
        template_id = instructions.get("template_id", instructions.get("template", f"step{step}"))
        
        # Build comprehensive prompt with security hardening
        # Sanitize all user inputs
        lead_name = sanitize_user_input(lead_name)
        company = sanitize_user_input(company)
        lead_title = sanitize_user_input(lead_title) if lead_title else ""
        lead_email = sanitize_user_input(lead_email) if lead_email else ""
        lead_industry = sanitize_user_input(lead_industry) if lead_industry else ""
        lead_location = sanitize_user_input(lead_location) if lead_location else ""
        campaign_name = sanitize_user_input(campaign_name) if campaign_name else ""
        product_name = sanitize_user_input(product_name) if product_name else ""
        value_proposition = sanitize_user_input(value_proposition) if value_proposition else ""
        previous_subject = sanitize_user_input(previous_subject) if previous_subject else ""
        previous_body_summary = sanitize_user_input(previous_body_summary) if previous_body_summary else ""
        cta = sanitize_user_input(cta) if cta else "schedule a call"
        
        prompt = f"""Write a compelling B2B follow-up email.

LEAD DETAILS:
- Name: {lead_name}
- Company: {company}"""
        
        if lead_title:
            prompt += f"\n- Title: {lead_title}"
        if lead_email:
            prompt += f"\n- Email: {lead_email}"
        if lead_industry:
            prompt += f"\n- Industry: {lead_industry}"
        if lead_location:
            prompt += f"\n- Location: {lead_location}"
        
        # Add recent interactions context if available (sanitized)
        recent_interactions = lead_data.get("recent_interactions", [])
        if recent_interactions:
            prompt += f"\n\nRECENT INTERACTIONS ({len(recent_interactions)} total):"
            for i, interaction in enumerate(recent_interactions[:3], 1):
                interaction_type = sanitize_user_input(str(interaction.get("type", "email")))
                interaction_date = sanitize_user_input(str(interaction.get("created_at", "unknown")))
                interaction_summary = sanitize_user_input(str(interaction.get("summary", "No summary available")))
                prompt += f"\n{i}. {interaction_type.upper()} on {interaction_date}: {interaction_summary}"
        
        prompt += f"""

CAMPAIGN CONTEXT:
- Campaign: {campaign_name}
- Current Step: {step}"""
        
        if product_name:
            prompt += f"\n- Product: {product_name}"
        if value_proposition:
            prompt += f"\n- Value Proposition: {value_proposition}"
        if days_since_last_contact > 0:
            prompt += f"\n- Days Since Last Contact: {days_since_last_contact}"
        if previous_subject:
            prompt += f"\n- Previous Subject: \"{previous_subject}\""
        if previous_body_summary:
            prompt += f"\n- Previous Email Summary: {previous_body_summary}"
        
        prompt += f"""

WRITING INSTRUCTIONS:
- Tone: {tone}
- Language: {language}
- Max Length: {max_length} words
- Call to Action: {cta}
- Template ID: {template_id}"""
        
        if required_elements:
            prompt += f"\n- Required Elements: {', '.join(str(e) for e in required_elements)}"
        
        prompt += f"""

TASK:
Write a compelling follow-up email for {lead_name} at {company}. The email should:
1. Reference the previous conversation naturally (if applicable)
2. Add new value or context specific to their role/industry
3. Include a clear, soft call to action: {cta}
4. Match the {tone} tone
5. Be concise and respect the recipient's time ({max_length} words max)
6. Feel personal and human, NOT templated or robotic
7. NEVER use placeholder brackets like [Name] or [Company]

Return ONLY the email content in this format:
Subject: <subject line>

<email body>

No explanations or additional commentary."""
        
        # Apply security hardening for human identity
        return get_hardened_copywriter_prompt(
            base_prompt=prompt,
            include_human_identity=True,
            include_anti_injection=True
        )

    def _call_openai(self, prompt: str, instructions: Dict[str, Any]) -> Dict[str, Any]:
        """Call OpenAI API to generate email content."""
        model = instructions.get("model", "gpt-4o-mini")
        max_tokens = instructions.get("max_tokens", 500)
        temperature = instructions.get("temperature", 0.7)
        
        response = self.llm_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You write professional B2B emails. Write naturally like a real person. Never mention AI, bots, or language models. Never use placeholder brackets."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        content = response.choices[0].message.content.strip()
        
        # Parse subject and body
        lines = content.split("\n")
        subject = ""
        body_lines = []
        found_subject = False
        
        for line in lines:
            if line.startswith("Subject:"):
                subject = line.replace("Subject:", "").strip()
                found_subject = True
            elif found_subject and line.strip():
                body_lines.append(line)
        
        body = "\n".join(body_lines).strip()
        
        return {
            "subject": subject or "Follow-up",
            "body": body or content,
            "metadata": {
                "model": model,
                "tokens": response.usage.total_tokens,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens
            }
        }
    
    def _call_anthropic(self, prompt: str, instructions: Dict[str, Any]) -> Dict[str, Any]:
        """Call Anthropic API to generate email content."""
        model = instructions.get("model", "claude-3-5-sonnet-20241022")
        max_tokens = instructions.get("max_tokens", 500)
        temperature = instructions.get("temperature", 0.7)
        
        response = self.llm_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        content = response.content[0].text.strip()
        
        # Parse subject and body
        lines = content.split("\n")
        subject = ""
        body_lines = []
        found_subject = False
        
        for line in lines:
            if line.startswith("Subject:"):
                subject = line.replace("Subject:", "").strip()
                found_subject = True
            elif found_subject and line.strip():
                body_lines.append(line)
        
        body = "\n".join(body_lines).strip()
        
        return {
            "subject": subject or "Follow-up",
            "body": body or content,
            "metadata": {
                "model": model,
                "tokens": response.usage.input_tokens + response.usage.output_tokens,
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens
            }
        }

    def _generate(self, lead_data: Dict[str, Any], campaign_context: Dict[str, Any], instructions: Dict[str, Any]) -> Dict[str, Any]:
        """Generate email content using lead data, campaign context, and instructions."""
        # Enrich lead data from database if available
        enriched_lead = self._enrich_lead_data(lead_data)
        
        prompt = self._build_prompt(enriched_lead, campaign_context, instructions)
        
        # Call appropriate LLM provider
        if self.llm_provider == "openai" and self.llm_client:
            try:
                return self._call_openai(prompt, instructions)
            except Exception as e:
                print(f"[CopyWorker {self.worker_id}] OpenAI API error: {e}, falling back to placeholder")
        
        elif self.llm_provider == "anthropic" and self.llm_client:
            try:
                return self._call_anthropic(prompt, instructions)
            except Exception as e:
                print(f"[CopyWorker {self.worker_id}] Anthropic API error: {e}, falling back to placeholder")
        
        # Fallback: placeholder generation
        lead_name = lead_data.get("first_name", "there").title()
        company = lead_data.get("company_name", "your company")
        step = campaign_context.get("step", 1)
        tone = instructions.get("tone", "professional")
        subject_hint = instructions.get("subject_hint", "Following up")
        
        subject = f"{subject_hint} - Step {step}"
        body = (
            f"Hi {lead_name},\n\n"
            f"Following up on our earlier conversation.\n\n"
            f"I wanted to share how we can help {company} with [specific value prop].\n\n"
            f"Best regards,\n"
            f"[Your Name]"
        )
        
        return {
            "subject": subject,
            "body": body,
            "metadata": {
                "model": "placeholder",
                "tokens": 0,
                "tone": tone,
                "step": step,
                "prompt": prompt  # Include for debugging/audit
            }
        }

    def process(self, msg_id: str, fields: Dict[str, Any]) -> None:
        # Rate limiting: acquire token before processing
        worker_key = f"worker:{self.worker_id}"
        if not self.rate_limiter.acquire(worker_key, block=True, timeout=30.0):
            # Rate limit timeout - re-queue message
            print(f"[CopyWorker {self.worker_id}] Rate limit timeout for message {msg_id}, will retry")
            return  # Don't ACK, message will be retried
        
        # Parse task envelope
        task_envelope = from_redis_message(fields)
        lead_data = task_envelope.payload.get("lead_data", {})
        campaign_context = task_envelope.payload.get("campaign_context", {})
        instructions = task_envelope.payload.get("instructions", {})

        lock_key = rconf.idemp_key(self.TASK_STREAM, msg_id)
        try:
            acquired = self.redis.client.set(self.redis._chan(lock_key), "1", nx=True, ex=rconf.OPS_IDEMP_TTL)
            if not acquired:
                self._ack(msg_id)
                return
        except Exception:
            pass

        retries = 0
        while True:
            try:
                content = self._generate(lead_data, campaign_context, instructions)
                result_env = result(
                    original=task_envelope,
                    payload={
                        "content": content,
                        "lead_id": lead_data.get("id"),
                        "campaign_id": task_envelope.metadata.campaign_id
                    },
                    source="copy_worker"
                )
                result_env.mark_processed()
                self._publish(result_env, self.RESULT_STREAM)
                
                self._ack(msg_id)
                break
            except Exception as e:
                if retries < rconf.MAX_RETRIES:
                    retries += 1
                    if rconf.RETRY_BACKOFF_MS > 0:
                        time.sleep(rconf.RETRY_BACKOFF_MS / 1000.0)
                    continue
                
                error_env = error(
                    original=task_envelope,
                    error_msg=str(e),
                    source="copy_worker",
                    code=getattr(e, 'code', None)
                )
                error_env.increment_retry()
                
                if error_env.status == Status.DLQ and rconf.ENABLE_DLQ:
                    self._publish(error_env, self.DLQ_STREAM)
                else:
                    self._publish(error_env, self.RESULT_STREAM)
                
                self._ack(msg_id)
                break

    def start(self) -> None:
        print(
            f"[CopyWorker {self.worker_id}] listening on stream {rconf.full_key(self.TASK_STREAM)} in group {self.GROUP}..."
        )
        try:
            while True:
                res = self.redis.xreadgroup(
                    group=self.GROUP,
                    consumer=self.worker_id,
                    streams={self.TASK_STREAM: ">"},
                    count=1,
                    block=5000,
                )
                if not res:
                    continue
                for _stream, entries in res:
                    for msg_id, fields in entries:
                        self.process(msg_id, fields)
                        if os.getenv("WORKER_ONCE", "0").lower() in ("1", "true", "yes"):
                            print(f"[CopyWorker {self.worker_id}] WORKER_ONCE set, exiting after first task.")
                            self._stop.set()
                            return
        except KeyboardInterrupt:
            print("\nCopyWorker stopping...")
        finally:
            self._stop.set()
            try:
                self._hb_thread.join(timeout=1.0)  # type: ignore[attr-defined]
            except Exception:
                pass
            self.redis.close()


def main() -> int:
    CopyWorker().start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
