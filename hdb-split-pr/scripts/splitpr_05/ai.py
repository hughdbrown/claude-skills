"""Anthropic SDK integration for PR description generation.

All AI calls go through this module. No other module imports the anthropic SDK.
Uses tool_use with forced tool_choice for reliable structured output.
"""

from __future__ import annotations

import logging
from typing import Any

import anthropic

from splitpr_common.ai import (  # noqa: F401
    AIError,
    call_structured,
    create_client,
)
from splitpr_05.models import PR, Task

logger = logging.getLogger(__name__)


# ── Schema ────────────────────────────────────────────────────────────

PR_BODY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "body": {
            "type": "string",
            "description": "The full PR body in GitHub-flavored markdown",
        },
    },
    "required": ["body"],
}

PR_BODY_SYSTEM = """\
You are generating a GitHub pull request description for a PR that is part \
of a branch split. The PR was extracted from a larger feature branch.

Format the description with these sections:
## Summary
1-3 bullet points describing what this PR does.

## Context
PR N of M from the `<original-branch>` split.
**Merge order:** where this PR fits.
**Depends on:** dependency PR links, or "None".

## Changes
Key files and what changed (bulleted list, 5-10 items max).

## Test plan
- [ ] All existing tests pass
- [ ] Specific verification items

Generated with [Claude Code](https://claude.com/claude-code)

Keep it professional, concise, and focused on helping reviewers.\
"""


# ── High-level AI functions ──────────────────────────────────────────


def generate_pr_body(
    client: anthropic.Anthropic,
    model: str,
    pr: PR,
    tasks: list[Task],
    files: list[str],
    dep_branches: list[str],
    total_prs: int,
    pr_index: int,
    source_branch: str,
) -> str:
    """Generate a GitHub PR body using AI.

    Returns the markdown body string.
    """
    # Build context for the AI
    parts: list[str] = []
    parts.append(f"PR Title: {pr.title}")
    parts.append(f"Branch: {pr.branch_name}")
    parts.append(f"Base: {pr.base_branch}")
    parts.append(f"Source branch: {source_branch}")
    parts.append(f"This is PR {pr_index} of {total_prs} in the split.")

    if dep_branches:
        parts.append(f"Depends on: {', '.join(dep_branches)}")
    else:
        parts.append("Depends on: None")

    parts.append(f"\nFiles ({len(files)}):")
    for f in files[:20]:
        parts.append(f"  - {f}")
    if len(files) > 20:
        parts.append(f"  ... and {len(files) - 20} more")

    if tasks:
        parts.append(f"\nTasks ({len(tasks)}):")
        for task in tasks:
            parts.append(f"  {task.ordinal}. [{task.task_type}] {task.subject}")
            if task.description:
                # Truncate long descriptions
                desc = task.description[:200]
                if len(task.description) > 200:
                    desc += "..."
                parts.append(f"     {desc}")

    user_content: str = "\n".join(parts)

    logger.debug("AI call: generate PR body for '%s'", pr.title)

    result: dict[str, Any] = call_structured(
        client=client,
        model=model,
        system_prompt=PR_BODY_SYSTEM,
        user_content=user_content,
        tool_name="generate_pr_body",
        tool_description="Generate a GitHub PR description in markdown",
        schema=PR_BODY_SCHEMA,
    )
    return result.get("body", "")


def generate_pr_body_template(
    pr: PR,
    tasks: list[Task],
    files: list[str],
    dep_branches: list[str],
    total_prs: int,
    pr_index: int,
    source_branch: str,
) -> str:
    """Generate a PR body from a template (no AI needed).

    Used as a fallback when ANTHROPIC_API_KEY is not set.
    """
    parts: list[str] = []

    parts.append("## Summary")
    parts.append(f"- {pr.title}")
    parts.append(
        f"- {pr.file_count} files changed, "
        f"{'+' if pr.net_lines >= 0 else ''}{pr.net_lines} net lines"
    )
    parts.append("")

    parts.append("## Context")
    parts.append(
        f"PR {pr_index} of {total_prs} from the `{source_branch}` split."
    )
    parts.append(f"**Merge order:** {pr.merge_order}")
    if dep_branches:
        dep_links: str = ", ".join(f"`{b}`" for b in dep_branches)
        parts.append(f"**Depends on:** {dep_links}")
    else:
        parts.append("**Depends on:** None")
    parts.append("")

    parts.append("## Changes")
    for f in files[:15]:
        parts.append(f"- `{f}`")
    if len(files) > 15:
        parts.append(f"- ... and {len(files) - 15} more files")
    parts.append("")

    if tasks:
        parts.append("## Tasks")
        for task in tasks:
            parts.append(f"- [{task.task_type}] {task.subject}")
        parts.append("")

    parts.append("## Test plan")
    parts.append("- [ ] All existing tests pass")
    parts.append("- [ ] Branch diff contains only assigned files")
    parts.append("")
    parts.append("Generated with [Claude Code](https://claude.com/claude-code)")

    return "\n".join(parts)
