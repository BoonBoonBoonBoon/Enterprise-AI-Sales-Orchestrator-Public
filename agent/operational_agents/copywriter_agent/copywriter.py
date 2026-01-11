from typing import Dict, Any


class CopywriterAgent:
    """Simple deterministic copywriter for tests and local runs.

    It accepts a context dict and produces formatted strings for email and text.
    Production systems would replace this with an LLM-backed implementation.
    """

    def __init__(self, template_config: Dict[str, Any] | None = None):
        self.template_config = template_config or {}

    def write_email(self, context: Dict[str, Any]) -> Dict[str, str]:
        """Return a dict with `subject` and `body` keys."""
        name = context.get("name", "there")
        company = context.get("company")
        subject = f"Hello {name} - important update"
        body_lines = [f"Hi {name},"]
        if company:
            body_lines.append(f"We noticed activity from {company}.")
        if context.get("action"):
            body_lines.append(f"Please take action: {context['action']}")
        body_lines.append("Thanks,\nYour Team")
        return {"subject": subject, "body": "\n\n".join(body_lines)}

    def write_text(self, context: Dict[str, Any]) -> str:
        """Return a short SMS-like text string."""
        name = context.get("name", "there")
        action = context.get("action", "check this out")
        return f"{name}: {action} - reply STOP to opt out"


# convenience helpers

def generate_email(context: Dict[str, Any]) -> Dict[str, str]:
    return CopywriterAgent().write_email(context)


def generate_text(context: Dict[str, Any]) -> str:
    return CopywriterAgent().write_text(context)
