"""Golden fixtures for lead qualification scorer regression testing.

Each fixture represents a known scenario with expected outcome.
These are used for regression testing to catch drift in scoring behavior.

Format: JSON Lines (one JSON object per line)
"""

import json
from pathlib import Path
from typing import Any, Dict, List


# =============================================================================
# GOLDEN FIXTURES - DO NOT MODIFY WITHOUT REVIEW
# =============================================================================

GOLDEN_FIXTURES: List[Dict[str, Any]] = [
    # --- HIGH INTENT QUALIFIED LEADS ---
    {
        "name": "ideal_enterprise_prospect",
        "description": "Enterprise decision-maker with meeting request",
        "inputs": {
            "lead_data": {
                "email": "jane.vp@enterprise.com",
                "company_name": "Enterprise Corp",
                "job_title": "VP of Engineering",
                "phone_number": "+1-555-123-4567",
                "linkedin_url": "https://linkedin.com/in/janevp",
            },
            "email_classification": {"category": "business_inquiry", "confidence": 0.92},
            "conversation_history": [
                {"content": "Hi, I'd like to schedule a demo this week. Can you share pricing info?", "direction": "inbound"}
            ],
            "lead_source": "new",
            "email_direction": "inbound",
        },
        "expected": {
            "promote": True,
            "decision_in": ["qualified", "fast_track"],
            "min_score": 75,
            "max_score": 100,
        },
    },
    {
        "name": "campaign_reply_ceo",
        "description": "CEO replies to our campaign email",
        "inputs": {
            "lead_data": {
                "email": "ceo@startup.io",
                "company_name": "Hot Startup",
                "job_title": "CEO & Founder",
            },
            "email_classification": {"category": "personal", "confidence": 0.85},
            "conversation_history": [
                {"content": "Thanks for reaching out. Let's chat next week.", "direction": "inbound"}
            ],
            "lead_source": "leads",
            "email_direction": "inbound",
        },
        "expected": {
            "promote": True,
            "decision_in": ["qualified", "fast_track"],
            "min_score": 70,
            "max_score": 100,
        },
    },
    {
        "name": "budget_timeline_inquiry",
        "description": "Lead mentions budget and timeline",
        "inputs": {
            "lead_data": {
                "email": "procurement@bigco.com",
                "company_name": "Big Co",
                "job_title": "Procurement Manager",
            },
            "email_classification": {"category": "business_inquiry", "confidence": 0.88},
            "conversation_history": [
                {"content": "We have a budget of $100k for Q1. What's your timeline for implementation?", "direction": "inbound"}
            ],
            "lead_source": "new",
            "email_direction": "inbound",
        },
        "expected": {
            "promote": True,
            "decision_in": ["qualified", "fast_track"],
            "min_score": 70,
            "max_score": 100,
        },
    },
    
    # --- DISQUALIFIED LEADS ---
    {
        "name": "spam_email",
        "description": "Spam classified email",
        "inputs": {
            "lead_data": {"email": "spammer123@randomdomain.xyz"},
            "email_classification": {"category": "spam", "confidence": 0.98},
            "conversation_history": [],
            "lead_source": "new",
            "email_direction": "inbound",
        },
        "expected": {
            "promote": False,
            "decision_in": ["disqualified"],
            "min_score": 0,
            "max_score": 20,
        },
    },
    {
        "name": "unsubscribe_request",
        "description": "Lead requests unsubscribe",
        "inputs": {
            "lead_data": {"email": "tired@company.com"},
            "email_classification": {"category": "personal", "confidence": 0.7},
            "conversation_history": [
                {"content": "Please unsubscribe me from your mailing list. Stop emailing me.", "direction": "inbound"}
            ],
            "lead_source": "staging_leads",
            "email_direction": "inbound",
        },
        "expected": {
            "promote": False,
            "decision_in": ["disqualified", "nurture"],
            "min_score": 0,
            "max_score": 50,
        },
    },
    {
        "name": "bounce_email",
        "description": "Bounced email",
        "inputs": {
            "lead_data": {"email": "invalid@nonexistent.com"},
            "email_classification": {"category": "bounce", "confidence": 0.99},
            "conversation_history": [],
            "lead_source": "leads",
            "email_direction": "inbound",
        },
        "expected": {
            "promote": False,
            "decision_in": ["disqualified"],
            "min_score": 0,
            "max_score": 20,
        },
    },
    {
        "name": "not_interested_explicit",
        "description": "Lead explicitly says not interested",
        "inputs": {
            "lead_data": {"email": "notinterested@corp.com"},
            "email_classification": {"category": "personal", "confidence": 0.8},
            "conversation_history": [
                {"content": "No thanks, we're not interested at this time.", "direction": "inbound"}
            ],
            "lead_source": "staging_leads",
            "email_direction": "inbound",
        },
        "expected": {
            "promote": False,
            "decision_in": ["disqualified", "nurture"],
            "min_score": 0,
            "max_score": 50,
        },
    },
    
    # --- NURTURE LEADS (MIDDLE GROUND) ---
    {
        "name": "generic_freemail",
        "description": "Generic freemail with no clear signals",
        "inputs": {
            "lead_data": {"email": "random456@gmail.com"},
            "email_classification": {"category": "unknown", "confidence": 0.5},
            "conversation_history": [
                {"content": "Hi", "direction": "inbound"}
            ],
            "lead_source": "new",
            "email_direction": "inbound",
        },
        "expected": {
            "promote": False,
            "decision_in": ["nurture", "disqualified"],
            "min_score": 0,
            "max_score": 50,
        },
    },
    {
        "name": "newsletter_signup",
        "description": "Newsletter signup, low intent",
        "inputs": {
            "lead_data": {"email": "reader@blog.com"},
            "email_classification": {"category": "newsletter", "confidence": 0.9},
            "conversation_history": [],
            "lead_source": "new",
            "email_direction": "inbound",
        },
        "expected": {
            "promote": False,
            "decision_in": ["nurture", "disqualified"],
            "min_score": 0,
            "max_score": 40,
        },
    },
    {
        "name": "single_word_reply",
        "description": "Lead replies with just 'Thanks'",
        "inputs": {
            "lead_data": {"email": "brief@company.com", "company_name": "Some Co"},
            "email_classification": {"category": "personal", "confidence": 0.7},
            "conversation_history": [
                {"content": "Thanks", "direction": "inbound"}
            ],
            "lead_source": "staging_leads",
            "email_direction": "inbound",
        },
        "expected": {
            "promote": False,
            "decision_in": ["nurture"],
            "min_score": 20,
            "max_score": 60,
        },
    },
    
    # --- EDGE CASES ---
    {
        "name": "empty_inputs",
        "description": "Completely empty inputs",
        "inputs": {
            "lead_data": {},
            "email_classification": {},
            "conversation_history": [],
            "lead_source": "new",
            "email_direction": "inbound",
        },
        "expected": {
            "promote": False,
            "decision_in": ["nurture", "disqualified"],
            "min_score": 0,
            "max_score": 30,
        },
    },
    {
        "name": "unicode_content",
        "description": "Lead with unicode/emoji in message",
        "inputs": {
            "lead_data": {"email": "international@company.de", "company_name": "München GmbH"},
            "email_classification": {"category": "business_inquiry", "confidence": 0.8},
            "conversation_history": [
                {"content": "Hallo! 👋 Können wir einen Demo-Termin vereinbaren? 📅", "direction": "inbound"}
            ],
            "lead_source": "new",
            "email_direction": "inbound",
        },
        "expected": {
            "promote": True,
            "decision_in": ["qualified", "fast_track", "nurture"],
            "min_score": 40,
            "max_score": 100,
        },
    },
]


def get_fixtures() -> List[Dict[str, Any]]:
    """Return all golden fixtures."""
    return GOLDEN_FIXTURES


def save_fixtures_to_file(path: Path):
    """Save fixtures to JSONL file for external use."""
    with open(path, "w", encoding="utf-8") as f:
        for fixture in GOLDEN_FIXTURES:
            f.write(json.dumps(fixture) + "\n")


def load_fixtures_from_file(path: Path) -> List[Dict[str, Any]]:
    """Load fixtures from JSONL file."""
    fixtures = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                fixtures.append(json.loads(line))
    return fixtures
