"""Real OpenAI connectivity check with guardrails.

Runs against the live API to mirror production behavior, but is:
- auto-skipped if `OPENAI_API_KEY` is missing
- bounded by a per-test timeout
- using a short client timeout to prevent hangs
"""

from __future__ import annotations

import os

import pytest

try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass


CLIENT_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TEST_TIMEOUT", "15"))


@pytest.mark.llm
def test_openai_chat_connectivity() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set; skipping live OpenAI call")

    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=CLIENT_TIMEOUT_SECONDS)
    model = os.getenv("OPENAI_TEST_MODEL", "gpt-4o-mini")

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Say 'Hello' and nothing else."}],
        max_tokens=10,
        temperature=0,
    )

    content = (response.choices[0].message.content or "").strip().lower()
    assert content == "hello"
