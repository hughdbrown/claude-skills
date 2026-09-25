#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["click>=8.1"]
# ///
"""Scaffold the next numbered task card from templates/TASK.md.

    new_task.py "Add pending invitation list endpoint" --model sonnet \
        --allow src/api/invitations.ts --allow src/api/invitations.test.ts \
        --forbid "Database migrations" --forbid src/auth/ \
        --verify "pnpm test src/api/invitations.test.ts" --verify "pnpm typecheck"

Paths passed to --allow/--forbid are wrapped in backticks so check_scope.py can
enforce them; anything containing a space is kept as descriptive prose.
The Contract, Requirements, and Acceptance Criteria sections are left for the
coordinator to fill in — those are the judgment calls a script cannot make.
"""

from __future__ import annotations

import re
from pathlib import Path
from string import Template

import click

from taskcard import TASK_ID_RE, TEMPLATES

MODEL_NAMES = {
    "opus": "Claude Opus 5.5",
    "sonnet": "Claude Sonnet 5",
    "haiku": "Claude Haiku 4.5",
}


def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48]


def next_number(tasks_dir: Path) -> int:
    numbers = [int(m.group(1)) for p in tasks_dir.glob("TASK-*.md") if (m := TASK_ID_RE.search(p.name))]
    return max(numbers, default=0) + 1


def bullets(items: tuple[str, ...], empty: str) -> str:
    if not items:
        return f"- {empty}"
    return "\n".join(f"- {item}" if " " in item and "/" not in item else f"- `{item}`" for item in items)


@click.command()
@click.argument("title")
@click.option("--model", type=click.Choice(sorted(MODEL_NAMES)), default="sonnet", show_default=True)
@click.option("--goal", default="", help="One-sentence goal; defaults to a placeholder.")
@click.option("--allow", multiple=True, help="Allowed file, dir/ or glob (repeatable).")
@click.option("--forbid", multiple=True, help="Forbidden path or prose area (repeatable).")
@click.option("--verify", multiple=True, help="Verification command (repeatable).")
@click.option("--depends-on", multiple=True, help="TASK-### this task waits for (repeatable).")
@click.option("--read-only", is_flag=True, help="Recon/review task: no files may be modified.")
@click.option("--tasks-dir", type=click.Path(path_type=Path), default=Path("tasks"), show_default=True)
@click.option("--handoffs-dir", type=click.Path(path_type=Path), default=Path("handoffs"), show_default=True)
@click.option("--number", type=int, help="Force a task number instead of the next free one.")
def main(
    title: str,
    model: str,
    goal: str,
    allow: tuple[str, ...],
    forbid: tuple[str, ...],
    verify: tuple[str, ...],
    depends_on: tuple[str, ...],
    read_only: bool,
    tasks_dir: Path,
    handoffs_dir: Path,
    number: int | None,
) -> None:
    """Create tasks/TASK-###-<slug>.md and print its path."""
    tasks_dir.mkdir(parents=True, exist_ok=True)
    num = number if number is not None else next_number(tasks_dir)
    task_id = f"TASK-{num:03d}"
    path = tasks_dir / f"{task_id}-{slugify(title)}.md"
    if path.exists():
        raise click.ClickException(f"{path} already exists")
    if read_only and allow:
        raise click.ClickException("--read-only and --allow are contradictory")

    template = Template((TEMPLATES / "TASK.md").read_text())
    card = template.safe_substitute(
        task_id=task_id,
        title=title,
        goal=goal or "<!-- one sentence: the observable outcome -->",
        model_name=MODEL_NAMES[model],
        depends_on=", ".join(d.upper() for d in depends_on) or "None",
        allowed="- None — read-only task; do not modify any file" if read_only else bullets(allow, "<!-- `path/to/file` -->"),
        forbidden=bullets(forbid, "Everything not listed above"),
        verify="\n".join(verify) or "# commands that prove the task is done",
        handoff_path=(handoffs_dir / f"{task_id}.md").as_posix(),
    )
    path.write_text(card)
    click.echo(path)


if __name__ == "__main__":
    main()
