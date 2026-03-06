"""Shared Anthropic SDK integration: structured tool_use call with retries.

Both splitpr_00 and splitpr_05 use the same mechanism for calling Claude
with forced tool_choice.  Package-specific schemas, system prompts, and
high-level wrapper functions stay in each package's own ai module.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import anthropic

logger = logging.getLogger(__name__)


class AIError(Exception):
    """Raised when Claude returns an unexpected or unparseable response."""

    pass


def create_client() -> anthropic.Anthropic:
    """Create an Anthropic client. Raises if ANTHROPIC_API_KEY is not set."""
    return anthropic.Anthropic()


def call_structured(
    client: anthropic.Anthropic,
    model: str,
    system_prompt: str,
    user_content: str,
    tool_name: str,
    tool_description: str,
    schema: dict[str, Any],
    max_tokens: int = 8192,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Send a message to Claude with a forced tool call, return the parsed result.

    Uses tool_choice to guarantee structured JSON output matching the schema.
    Retries on rate limits and API errors with exponential backoff.
    """
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
                tools=[
                    {
                        "name": tool_name,
                        "description": tool_description,
                        "input_schema": schema,
                    }
                ],
                tool_choice={"type": "tool", "name": tool_name},
            )
            for block in response.content:
                if block.type == "tool_use":
                    return block.input
            raise AIError(
                f"No tool_use block in response (attempt {attempt + 1}): "
                f"{[b.type for b in response.content]}"
            )
        except anthropic.RateLimitError:
            if attempt < max_retries - 1:
                wait: int = 2 ** (attempt + 1)
                logger.warning("Rate limited, waiting %ds...", wait)
                time.sleep(wait)
            else:
                raise
        except anthropic.APIConnectionError:
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                logger.warning("API connection error, waiting %ds...", wait)
                time.sleep(wait)
            else:
                raise
    raise AIError("Exhausted retries")
