#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["click>=8.1"]
# ///
"""Check that a worker's changes stay inside its task card's file boundary.

    check_scope.py tasks/TASK-042-list-endpoint.md --commit abc1234
    check_scope.py tasks/TASK-042-list-endpoint.md --range main...agent/task-042
    check_scope.py tasks/TASK-042-list-endpoint.md --worktree ../proj-task-042 --base main

Every changed path must match an "Allowed files" pattern and must not match a
backticked "Do not modify" pattern. Prose entries under "Do not modify" (e.g.
"Database migrations") cannot be checked mechanically; they are printed so the
reviewer checks them by eye. Exit status: 0 in scope, 1 violations, 2 usage error.
"""

from __future__ import annotations

from pathlib import Path

import click

from taskcard import git, load_task, matches


def changed_files(repo: Path, commit: str | None, rev_range: str | None, base: str | None) -> list[str]:
    if commit:
        out = git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", commit)
    elif rev_range:
        out = git(repo, "diff", "--name-only", rev_range)
    else:
        # Worktree mode: committed changes since base plus anything uncommitted.
        committed = git(repo, "diff", "--name-only", f"{base}...HEAD")
        uncommitted = git(repo, "status", "--porcelain", "--untracked-files=all")
        extra = [line[3:].split(" -> ")[-1] for line in uncommitted.splitlines() if line.strip()]
        out = committed + "\n".join(extra)
    return sorted({line.strip() for line in out.splitlines() if line.strip()})


@click.command()
@click.argument("task_card", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--commit", help="Check the files touched by one commit.")
@click.option("--range", "rev_range", help="Check a git revision range, e.g. main...agent/task-042.")
@click.option("--worktree", type=click.Path(exists=True, file_okay=False, path_type=Path), help="Worker worktree to inspect.")
@click.option("--base", default="main", show_default=True, help="Base branch for --worktree mode.")
@click.option("--repo", type=click.Path(exists=True, file_okay=False, path_type=Path), default=Path("."), show_default=True)
def main(task_card: Path, commit: str | None, rev_range: str | None, worktree: Path | None, base: str, repo: Path) -> None:
    """Report out-of-scope file changes for TASK_CARD."""
    modes = sum(x is not None for x in (commit, rev_range, worktree))
    if modes != 1:
        raise click.UsageError("give exactly one of --commit, --range, --worktree")
    card = load_task(task_card)
    allowed, forbidden = card.allowed_patterns, card.forbidden_patterns
    try:
        files = changed_files(worktree or repo, commit, rev_range, base if worktree else None)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    violations: list[str] = []
    for path in files:
        hit_forbidden = next((p for p in forbidden if matches(path, p)), None)
        if hit_forbidden:
            violations.append(f"FORBIDDEN  {path}  (matches `{hit_forbidden}`)")
        elif not any(matches(path, p) for p in allowed):
            violations.append(f"UNLISTED   {path}")

    click.echo(f"{card.task_id}: {len(files)} changed file(s), {len(allowed)} allowed pattern(s)")
    for path in files:
        click.echo(f"  {path}")
    if card.descriptive_forbidden:
        click.echo("Check by eye (prose 'Do not modify' entries):")
        for item in card.descriptive_forbidden:
            click.echo(f"  - {item}")
    if not files:
        click.echo("WARNING: no changed files — was the commit/range right?")
    if violations:
        click.echo("SCOPE VIOLATIONS:")
        for v in violations:
            click.echo(f"  {v}")
        raise SystemExit(1)
    click.echo("OK: all changes within scope")


if __name__ == "__main__":
    main()
