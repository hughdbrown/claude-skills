"""Anthropic SDK integration: prompt construction, tool_use schemas, response parsing.

All AI calls go through this module. No other module imports the anthropic SDK.
Uses tool_use with forced tool_choice for reliable structured JSON output.
"""

from __future__ import annotations

import time
import logging
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

# ── Schemas ──────────────────────────────────────────────────────────

CLASSIFY_COMMITS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "themes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Short kebab-case theme name (e.g. rate-limiting, auth-refactor)",
                    },
                    "description": {
                        "type": "string",
                        "description": "One-sentence description of this theme",
                    },
                    "commit_shas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "SHAs belonging to this theme",
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence 0.0-1.0 for the weakest assignment in this group",
                    },
                },
                "required": ["name", "description", "commit_shas", "confidence"],
            },
        }
    },
    "required": ["themes"],
}

DEPENDENCY_ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "dependencies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "theme": {
                        "type": "string",
                        "description": "The theme that has a dependency",
                    },
                    "depends_on": {
                        "type": "string",
                        "description": "The theme it depends on",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why this dependency exists",
                    },
                },
                "required": ["theme", "depends_on", "reason"],
            },
        }
    },
    "required": ["dependencies"],
}

RESOLVE_CROSSCUTTING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "resolutions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "assigned_theme": {
                        "type": "string",
                        "description": "The theme name this file should be assigned to",
                    },
                    "strategy": {
                        "type": "string",
                        "enum": [
                            "earliest_pr",
                            "split_by_hunk",
                            "infrastructure",
                            "sequential_layering",
                        ],
                        "description": "Resolution strategy used",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Why this assignment was chosen",
                    },
                },
                "required": ["file_path", "assigned_theme", "strategy", "reasoning"],
            },
        }
    },
    "required": ["resolutions"],
}

GENERATE_TASKS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                        "description": "Imperative action (e.g. 'Add Redis rate limiter module')",
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed instructions with file paths and specific changes",
                    },
                    "acceptance": {
                        "type": "string",
                        "description": "How to verify completion",
                    },
                    "task_type": {
                        "type": "string",
                        "enum": [
                            "infrastructure",
                            "core",
                            "config",
                            "integration",
                            "test",
                            "docs",
                            "lint",
                            "verify",
                        ],
                    },
                    "source_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Files involved in this task",
                    },
                },
                "required": [
                    "subject",
                    "description",
                    "acceptance",
                    "task_type",
                    "source_files",
                ],
            },
        }
    },
    "required": ["tasks"],
}


# ── System prompts ───────────────────────────────────────────────────

CLASSIFY_SYSTEM = """\
You are analyzing a git branch to partition it into coherent, non-overlapping \
themes for separate pull requests. Each commit must belong to exactly one theme.

Use commit message prefixes (feat:, fix:, docs:, test:, refactor:, chore:, \
security:) as the primary signal. When the prefix is ambiguous, use the files \
changed to determine the theme.

Guidelines:
- Prefer fewer themes (3-6) over many small ones
- Related small changes should be grouped together
- Theme names must be kebab-case and descriptive (e.g. rate-limiting, auth-refactor)
- Every SHA listed must appear in exactly one theme — no omissions, no duplicates
- Formatting/linting commits should be grouped with the feature they support, \
  not in a separate theme (unless they are a standalone formatting pass)\
"""

DEPENDENCY_SYSTEM = """\
You are analyzing dependencies between theme groups in a git branch split.

A theme depends on another if:
1. It imports or calls functions/classes introduced by the other theme
2. It modifies files whose working state requires the other theme's changes
3. Its tests rely on fixtures or utilities introduced by the other theme
4. It extends a database migration introduced by the other theme

Only report real, code-level dependencies. Do not create dependencies based on:
- Coincidental file overlap (handled separately)
- Thematic similarity without code coupling
- Temporal ordering of commits

If two themes are fully independent, report zero dependencies between them.\
"""

CROSSCUTTING_SYSTEM = """\
You are resolving cross-cutting files — files touched by multiple themes in a \
git branch split. Each file must be assigned to exactly one PR/theme.

Strategies:
- earliest_pr: The file has a clear foundation change that later PRs build on. \
  Assign to the earliest PR in the dependency chain.
- split_by_hunk: The file has distinct, non-overlapping hunks for each theme. \
  (Use sparingly — only when hunks are truly independent.)
- infrastructure: The file is shared config or wiring (e.g. main.py, config.py). \
  Assign to the first PR or a dedicated infrastructure PR.
- sequential_layering: One theme adds content, another modifies it. Put the \
  addition in the earlier PR.

Decision guide for common file types:
- config.py / settings.py → earliest PR
- main.py / app wiring → earliest PR or infrastructure
- Makefile / docker-compose → PR whose feature it supports
- Shared test fixtures → earliest PR
- __init__.py / re-exports → PR that adds the module being exported
- Migration files → always with the schema change they implement

Prefer 'earliest_pr' when in doubt. Avoid 'split_by_hunk' unless the hunks \
are truly independent.\
"""

TASKS_SYSTEM = """\
You are generating an implementation task list for a single pull request that \
is part of a branch split. Each task should be specific and actionable.

Task ordering:
1. Infrastructure / new modules (create new files)
2. Core implementation (main logic changes)
3. Configuration (settings, env vars)
4. Integration / wiring (connecting components)
5. Tests
6. Documentation
7. Linting / formatting
8. Commit and verify

Each task must include:
- A clear imperative subject
- Specific file paths and what to change
- Acceptance criteria (how to verify the task is done)
- The source files involved

Keep tasks focused — each task should be completable in one sitting.\
"""


# ── Core API call ────────────────────────────────────────────────────


class AIError(Exception):
    """Raised when Claude returns an unexpected or unparseable response."""

    pass


def create_client() -> anthropic.Anthropic:
    """Create an Anthropic client. Raises if ANTHROPIC_API_KEY is not set."""
    return anthropic.Anthropic()


def call_claude_structured(
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
                wait = 2 ** (attempt + 1)
                logger.warning(f"Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
        except anthropic.APIConnectionError:
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                logger.warning(f"API connection error, waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise AIError("Exhausted retries")


# ── High-level AI functions ──────────────────────────────────────────


def classify_commits(
    client: anthropic.Anthropic,
    model: str,
    commits_text: str,
) -> dict[str, Any]:
    """Classify commits into themes. Returns the parsed tool response."""
    return call_claude_structured(
        client=client,
        model=model,
        system_prompt=CLASSIFY_SYSTEM,
        user_content=commits_text,
        tool_name="classify_commits",
        tool_description="Classify git commits into coherent themes for separate PRs",
        schema=CLASSIFY_COMMITS_SCHEMA,
    )


def analyze_dependencies(
    client: anthropic.Anthropic,
    model: str,
    analysis_text: str,
) -> dict[str, Any]:
    """Analyze dependencies between themes. Returns parsed tool response."""
    return call_claude_structured(
        client=client,
        model=model,
        system_prompt=DEPENDENCY_SYSTEM,
        user_content=analysis_text,
        tool_name="analyze_dependencies",
        tool_description="Identify dependency edges between theme groups",
        schema=DEPENDENCY_ANALYSIS_SCHEMA,
    )


def resolve_crosscutting(
    client: anthropic.Anthropic,
    model: str,
    resolution_text: str,
) -> dict[str, Any]:
    """Resolve cross-cutting file assignments. Returns parsed tool response."""
    return call_claude_structured(
        client=client,
        model=model,
        system_prompt=CROSSCUTTING_SYSTEM,
        user_content=resolution_text,
        tool_name="resolve_crosscutting",
        tool_description="Assign each cross-cutting file to exactly one PR/theme",
        schema=RESOLVE_CROSSCUTTING_SCHEMA,
    )


def generate_tasks(
    client: anthropic.Anthropic,
    model: str,
    task_text: str,
) -> dict[str, Any]:
    """Generate tasks for a single PR. Returns parsed tool response."""
    return call_claude_structured(
        client=client,
        model=model,
        system_prompt=TASKS_SYSTEM,
        user_content=task_text,
        tool_name="generate_tasks",
        tool_description="Generate an ordered task list for implementing a PR",
        schema=GENERATE_TASKS_SCHEMA,
    )


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token."""
    return len(text) // 4


def batch_if_needed(
    items: list[str], max_chars: int = 150_000
) -> list[list[str]]:
    """Split items into batches that fit within the character limit."""
    batches: list[list[str]] = []
    current_batch: list[str] = []
    current_size = 0
    for item in items:
        item_size = len(item)
        if current_size + item_size > max_chars and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_size = 0
        current_batch.append(item)
        current_size += item_size
    if current_batch:
        batches.append(current_batch)
    return batches
