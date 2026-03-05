"""Anthropic SDK integration for conflict resolution analysis.

All AI calls go through this module. No other module imports the anthropic SDK.
Uses tool_use with forced tool_choice for reliable structured output.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import anthropic

from mergefix.models import ConflictBlock, MergeContext, Resolution, Strategy

logger = logging.getLogger(__name__)


# ── Schema ────────────────────────────────────────────────────────────

RESOLUTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "strategy": {
            "type": "string",
            "enum": ["take_ours", "take_theirs", "take_both", "custom"],
            "description": (
                "The resolution strategy: "
                "take_ours (keep current branch), "
                "take_theirs (keep incoming branch), "
                "take_both (incorporate both sides), "
                "custom (manually crafted resolution)"
            ),
        },
        "resolved_content": {
            "type": "string",
            "description": (
                "The resolved content that replaces the entire conflict block "
                "(including markers). Must be valid code/text — no conflict markers."
            ),
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": (
                "Confidence in the resolution (0.0 to 1.0). "
                "Use >= 0.9 for obvious cases, 0.7-0.9 for likely correct, "
                "< 0.7 for uncertain."
            ),
        },
        "reasoning": {
            "type": "string",
            "description": (
                "Brief explanation of why this resolution is correct. "
                "Reference specific code elements."
            ),
        },
    },
    "required": ["strategy", "resolved_content", "confidence", "reasoning"],
}

RESOLUTION_SYSTEM = """\
You are an expert at resolving git merge conflicts. You analyze conflict blocks \
and determine the correct resolution.

Rules:
1. NEVER include conflict markers (<<<<<<, =======, >>>>>>>) in resolved_content.
2. The resolved_content must be syntactically valid for the file's language.
3. Preserve indentation and formatting conventions from the surrounding code.
4. When both sides add non-overlapping content (imports, list items, etc.), use take_both.
5. When one side is clearly a superset or improvement, take that side.
6. When changes genuinely overlap, produce a custom merge that combines intent from both.
7. For whitespace-only or formatting conflicts, prefer the incoming (theirs) version.
8. Consider the common ancestor (base) when available — it shows what each side changed.

During a REBASE, note that the labels are swapped:
- "ours" = the branch being rebased onto (upstream changes)
- "theirs" = the commit being replayed (your changes)

Set confidence based on how certain you are:
- 0.95-1.0: Trivial resolution (one side is empty, pure additions, obvious choice)
- 0.85-0.95: Clear resolution with good context
- 0.7-0.85: Reasonable resolution but some ambiguity
- < 0.7: Uncertain — human review recommended\
"""


# ── Core API call ────────────────────────────────────────────────────


class AIError(Exception):
    """Raised when Claude returns an unexpected response."""

    pass


def create_client() -> anthropic.Anthropic:
    """Create an Anthropic client. Raises if ANTHROPIC_API_KEY is not set."""
    return anthropic.Anthropic()


def _call_structured(
    client: anthropic.Anthropic,
    model: str,
    system_prompt: str,
    user_content: str,
    tool_name: str,
    tool_description: str,
    schema: dict[str, Any],
    max_tokens: int = 4096,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Send a message with a forced tool call, return parsed result."""
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
                f"No tool_use block in response (attempt {attempt + 1})"
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


# ── High-level AI functions ──────────────────────────────────────────


def resolve_conflict(
    client: anthropic.Anthropic,
    model: str,
    block: ConflictBlock,
    context: MergeContext,
) -> Resolution:
    """Analyze a conflict block and return a Resolution.

    Sends the conflict with surrounding context to Claude and parses
    the structured response.
    """
    user_content = _build_conflict_prompt(block, context)
    logger.debug(
        "AI call: resolve conflict in '%s' block %d/%d",
        block.file_path,
        block.block_index + 1,
        block.total_blocks,
    )

    result: dict[str, Any] = _call_structured(
        client=client,
        model=model,
        system_prompt=RESOLUTION_SYSTEM,
        user_content=user_content,
        tool_name="resolve_conflict",
        tool_description="Resolve a git merge conflict block",
        schema=RESOLUTION_SCHEMA,
    )

    strategy_str: str = result.get("strategy", "custom")
    try:
        strategy = Strategy(strategy_str)
    except ValueError:
        strategy = Strategy.CUSTOM

    return Resolution(
        strategy=strategy,
        resolved_content=result.get("resolved_content", ""),
        confidence=float(result.get("confidence", 0.5)),
        reasoning=result.get("reasoning", ""),
    )


def _build_conflict_prompt(
    block: ConflictBlock,
    context: MergeContext,
) -> str:
    """Build the user prompt for a single conflict block."""
    parts: list[str] = []

    # Operation context
    parts.append(f"Operation: {context.operation.value}")
    parts.append(f"Current branch: {context.current_branch}")
    if context.incoming_ref:
        parts.append(f"Incoming: {context.incoming_ref}")

    if context.current_commits:
        parts.append("\nRecent commits on current branch:")
        for c in context.current_commits[:5]:
            parts.append(f"  {c}")

    if context.incoming_commits:
        parts.append("\nRecent commits on incoming branch:")
        for c in context.incoming_commits[:5]:
            parts.append(f"  {c}")

    # File info
    parts.append(f"\nFile: {block.file_path}")
    parts.append(
        f"Conflict block {block.block_index + 1} of {block.total_blocks}"
    )

    # Context before
    if block.context_before:
        parts.append("\n--- Context before conflict ---")
        parts.append(block.context_before)

    # The conflict itself
    parts.append(f"\n--- OURS ({block.ours_label}) ---")
    parts.append(block.ours if block.ours else "(empty)")

    if block.base is not None:
        parts.append("\n--- BASE (common ancestor) ---")
        parts.append(block.base if block.base else "(empty)")

    parts.append(f"\n--- THEIRS ({block.theirs_label}) ---")
    parts.append(block.theirs if block.theirs else "(empty)")

    # Context after
    if block.context_after:
        parts.append("\n--- Context after conflict ---")
        parts.append(block.context_after)

    return "\n".join(parts)
