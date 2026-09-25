#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["click>=8.1"]
# ///
"""Turn a task card into a ready-to-send worker prompt plus Agent tool settings.

    render_worker_prompt.py tasks/TASK-042-list-endpoint.md
    render_worker_prompt.py tasks/TASK-042-list-endpoint.md --json

The prompt embeds the card verbatim, so the worker gets the task-specific
context and nothing else — no feature discussion, no other workers' output.
The model comes from the card's "Assigned Model" section; code-writing tasks
get `isolation: "worktree"`, read-only tasks do not.
"""

from __future__ import annotations

import json
from pathlib import Path
from string import Template

import click

from taskcard import TEMPLATES, load_task

TEMPLATE_FOR = {"sonnet": "worker-sonnet.md", "haiku": "worker-haiku.md", "opus": "worker-sonnet.md"}


def is_read_only(allowed: list[str]) -> bool:
    return not allowed or all("none" in a.lower() and "`" not in a for a in allowed)


@click.command()
@click.argument("task_card", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--agents-md", default="AGENTS.md", show_default=True)
@click.option("--handoffs-dir", default="handoffs", show_default=True)
@click.option("--workdir", default=".", show_default=True, help="Directory the worker should treat as the repo root.")
@click.option("--json", "as_json", is_flag=True, help="Emit {description, model, isolation, prompt} as JSON.")
def main(task_card: Path, agents_md: str, handoffs_dir: str, workdir: str, as_json: bool) -> None:
    """Print the worker prompt for TASK_CARD."""
    card = load_task(task_card)
    if card.model is None:
        raise click.ClickException(f"{task_card}: no recognizable model under '## Assigned Model'")
    read_only = is_read_only(card.allowed)
    template = Template((TEMPLATES / TEMPLATE_FOR[card.model]).read_text())
    prompt = template.safe_substitute(
        workdir=workdir,
        agents_md=agents_md,
        task_id=card.task_id,
        task_card=task_card.as_posix(),
        handoff_path=f"{handoffs_dir}/{card.task_id}.md",
        card=card.text.strip(),
    )
    settings = {
        "description": f"{card.task_id} {card.title}"[:60],
        "subagent_type": "Explore" if read_only and card.model == "haiku" else "general-purpose",
        "model": card.model,
        "prompt": prompt,
    }
    if not read_only:
        settings["isolation"] = "worktree"
    if as_json:
        click.echo(json.dumps(settings, indent=2))
        return
    meta = {k: v for k, v in settings.items() if k != "prompt"}
    click.echo(f"# Agent settings: {json.dumps(meta)}")
    if card.depends_on:
        click.echo(f"# Waits for: {', '.join(card.depends_on)}")
    click.echo(prompt)


if __name__ == "__main__":
    main()
