"""Copywriter operational agent.

This agent is responsible for generating textual content (emails, SMS, etc.)
from structured data. It does not perform delivery.
"""

from .copywriter import CopywriterAgent, generate_email, generate_text

__all__ = ["CopywriterAgent", "generate_email", "generate_text"]
