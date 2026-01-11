"""Copywriter LLM Integration Demo

Demonstrates how to use the copywriter worker with real LLM providers
(OpenAI, Anthropic) or placeholder mode.

Prerequisites:
    - Redis running
    - For OpenAI: Set OPENAI_API_KEY environment variable
    - For Anthropic: Set ANTHROPIC_API_KEY environment variable
    - For persistence: Set SUPABASE_URL and SUPABASE_KEY

Usage:
    # With OpenAI (default)
    python examples/copywriter_llm_demo.py --provider openai
    
    # With Anthropic
    python examples/copywriter_llm_demo.py --provider anthropic
    
    # Placeholder mode (no API calls)
    python examples/copywriter_llm_demo.py --provider placeholder
    
    # With custom model
    python examples/copywriter_llm_demo.py --provider openai --model gpt-4
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from agent.tools.redis.client import RedisPubSub
from agent.tools.redis import config as rconf
from agent.utils.typed_envelope import task, from_redis_message


def send_copywriter_task(
    lead_data: dict,
    campaign_context: dict,
    instructions: dict,
    provider: str = "openai",
    model: str | None = None
) -> str:
    """Send a copywriter task to Redis and return the message ID."""
    
    # Build task envelope
    envelope = task(
        payload={
            "lead_data": lead_data,
            "campaign_context": campaign_context,
            "instructions": instructions
        },
        source="demo_script",
        stream_override="copy:tasks",
        campaign_id=campaign_context.get("campaign_id", "demo-campaign"),
        lead_id=lead_data.get("id", "demo-lead")
    )
    
    # Add LLM configuration to envelope
    if model:
        envelope.payload["instructions"]["model"] = model
    
    # Publish to copy:tasks stream
    redis = RedisPubSub()
    fields = {
        "metadata": json.dumps(envelope.metadata.model_dump()),
        "payload": json.dumps(envelope.payload),
        "status": envelope.status.value,
        "history": json.dumps([h.model_dump() for h in envelope.history])
    }
    
    msg_id = redis.xadd(rconf.STREAM_TASKS_COPY, fields)
    print(f"✓ Sent task to {rconf.full_key(rconf.STREAM_TASKS_COPY)}")
    print(f"  Message ID: {msg_id}")
    print(f"  Lead: {lead_data.get('name', 'Unknown')}")
    print(f"  Provider: {provider}")
    if model:
        print(f"  Model: {model}")
    
    redis.close()
    return msg_id


def wait_for_result(msg_id: str, timeout: int = 60) -> dict | None:
    """Wait for result from copy:results stream."""
    redis = RedisPubSub()
    start_time = time.time()
    
    print(f"\n⏳ Waiting for result (timeout: {timeout}s)...")
    
    while (time.time() - start_time) < timeout:
        # Read from results stream
        results = redis.xread({rconf.STREAM_RESULTS_COPY: "0"}, count=100)
        
        for stream, messages in results:
            for result_id, fields in messages:
                envelope = from_redis_message(fields)
                
                # Check if this is our result (by trace_id or lead_id)
                if envelope.metadata.lead_id == "demo-lead":
                    print(f"✓ Received result!")
                    redis.close()
                    return envelope.payload
        
        time.sleep(1)
    
    print(f"✗ Timeout waiting for result")
    redis.close()
    return None


def print_generated_copy(payload: dict):
    """Pretty print the generated copy."""
    content = payload.get("content", {})
    
    print("\n" + "="*80)
    print("GENERATED EMAIL COPY")
    print("="*80)
    
    # Subject
    subject = content.get("subject", "")
    print(f"\nSubject: {subject}")
    print("-"*80)
    
    # Body
    body = content.get("body", "")
    print(f"\n{body}")
    print("-"*80)
    
    # Metadata
    metadata = content.get("metadata", {})
    if metadata:
        print(f"\nMetadata:")
        print(f"  Model: {metadata.get('model', 'unknown')}")
        print(f"  Tokens: {metadata.get('tokens', 0)}")
        print(f"  Prompt Tokens: {metadata.get('prompt_tokens', 0)}")
        print(f"  Completion Tokens: {metadata.get('completion_tokens', 0)}")
    
    print("="*80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Copywriter LLM Integration Demo")
    parser.add_argument(
        "--provider",
        choices=["openai", "anthropic", "placeholder"],
        default="openai",
        help="LLM provider to use (default: openai)"
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Specific model to use (e.g., gpt-4, claude-3-5-sonnet-20241022)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout in seconds to wait for result (default: 60)"
    )
    
    args = parser.parse_args()
    
    # Set environment variable for worker to use
    os.environ["LLM_PROVIDER"] = args.provider
    
    # Check API keys
    if args.provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        print("⚠️  WARNING: OPENAI_API_KEY not set. Worker will fall back to placeholder mode.")
        print("   Set OPENAI_API_KEY to use real OpenAI API.\n")
    elif args.provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  WARNING: ANTHROPIC_API_KEY not set. Worker will fall back to placeholder mode.")
        print("   Set ANTHROPIC_API_KEY to use real Anthropic API.\n")
    
    # Sample lead data
    lead_data = {
        "id": "demo-lead",
        "first_name": "Sarah",
        "name": "Sarah Chen",
        "company_name": "TechStartup Inc",
        "company": "TechStartup Inc",
        "title": "VP of Engineering",
        "email": "sarah.chen@techstartup.com",
        "industry": "Software",
        "location": "San Francisco, CA"
    }
    
    # Sample campaign context
    campaign_context = {
        "campaign_id": "demo-campaign",
        "campaign_name": "Engineering Leaders Q4 Outreach",
        "sequence_step": 2,
        "step": 2,
        "product_name": "AI-Powered Code Review Platform",
        "value_proposition": "Reduce code review time by 60% with AI-powered suggestions",
        "call_to_action": "schedule a 15-minute demo",
        "days_since_last_contact": 3,
        "previous_subject": "Improving code quality at TechStartup Inc",
        "previous_body_summary": "Introduced our AI code review platform and mentioned how it helps teams like theirs"
    }
    
    # Sample instructions
    instructions = {
        "template": "followup_email",
        "tone": "professional",
        "language": "en-US",
        "max_length": 150,
        "word_count": 150,
        "cta": "schedule a quick demo",
        "call_to_action": "schedule a quick demo",
        "temperature": 0.7,
        "max_tokens": 500
    }
    
    # Add model if specified
    if args.model:
        instructions["model"] = args.model
    
    print(f"\n{'='*80}")
    print(f"COPYWRITER LLM DEMO - {args.provider.upper()}")
    print(f"{'='*80}\n")
    
    # Send task
    msg_id = send_copywriter_task(
        lead_data=lead_data,
        campaign_context=campaign_context,
        instructions=instructions,
        provider=args.provider,
        model=args.model
    )
    
    # Wait for result
    result = wait_for_result(msg_id, timeout=args.timeout)
    
    if result:
        print_generated_copy(result)
        return 0
    else:
        print("\n✗ Failed to receive result within timeout period")
        print("  Make sure the copywriter worker is running:")
        print("  python -m agent.operational_agents.copywriter.worker")
        return 1


if __name__ == "__main__":
    sys.exit(main())
