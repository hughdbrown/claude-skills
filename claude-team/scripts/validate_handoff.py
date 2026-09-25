#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["click>=8.1"]
# ///
"""Reject worker handoffs that claim success without evidence.

    validate_handoff.py handoffs/TASK-042.md
    validate_handoff.py handoffs/TASK-042.md --task tasks/TASK-042-list-endpoint.md --repo ../proj-task-042
    validate_handoff.py handoffs/TASK-042.md --no-git     # structure only

Checks:
  * all required sections exist and are non-empty
  * Status is one of the allowed values
  * a Completed handoff has a commit SHA that exists in --repo
  * Verification contains command output, and mentions every command the
    task card required (when --task is given)
  * Files Changed matches the files the commit actually touched
  * no "FAIL" / "error" in Verification while Status says Completed

It does not judge code quality — that is the coordinator's review. It only makes
sure the review starts from evidence instead of a completion claim.
Exit status: 0 valid, 1 problems found.
"""

from __future__ import annotations

import re
from pathlib import Path

import click

from taskcard import BACKTICK_RE, SHA_RE, fenced_blocks, git, load_task, sections, strip_comments

REQUIRED = ["Status", "Summary", "Files Changed", "Verification", "Known Limitations", "Commit"]
STATUSES = {"completed", "blocked", "failed", "needs escalation"}
FAILURE_RE = re.compile(r"\b(FAIL(ED|URE)?|error(s)?:|panicked|Traceback)\b")


@click.command()
@click.argument("handoff", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--task", "task_card", type=click.Path(exists=True, dir_okay=False, path_type=Path), help="Task card to cross-check against.")
@click.option(
    "--repo",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    show_default=True,
    help="Repo or worktree holding the commit.",
)
@click.option("--no-git", is_flag=True, help="Skip commit existence and file cross-checks (structure only).")
def main(handoff: Path, task_card: Path | None, repo: Path, no_git: bool) -> None:
    """Validate a worker HANDOFF file."""
    problems: list[str] = []
    warnings: list[str] = []
    secs = {k: strip_comments(v) for k, v in sections(handoff.read_text()).items()}

    for name in REQUIRED:
        if not secs.get(name):
            problems.append(f"missing or empty section: ## {name}")

    status = secs.get("Status", "").splitlines()[0].strip().lower() if secs.get("Status") else ""
    if status and status not in STATUSES:
        problems.append(f"Status {status!r} is not one of {sorted(STATUSES)}")
    completed = status == "completed"

    verification = secs.get("Verification", "")
    blocks = fenced_blocks(verification)
    if completed and not blocks:
        problems.append("Verification has no fenced command output — a claim is not evidence")
    if completed and FAILURE_RE.search(verification):
        problems.append("Status is Completed but Verification output mentions a failure")

    listed = sorted(set(BACKTICK_RE.findall(secs.get("Files Changed", ""))))

    sha = None
    if m := SHA_RE.search(secs.get("Commit", "")):
        sha = m.group(0)
    if completed and not sha:
        problems.append("Completed handoff has no commit SHA")

    actual: list[str] | None = None
    if sha and not no_git:
        try:
            git(repo, "cat-file", "-e", f"{sha}^{{commit}}")
            out = git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", sha)
            actual = sorted({line for line in out.splitlines() if line})
        except RuntimeError:
            problems.append(f"commit {sha} not found in {repo}")

    if actual is not None:
        missing = sorted(set(actual) - set(listed))
        phantom = sorted(set(listed) - set(actual))
        if missing:
            problems.append(f"commit touches files not listed in Files Changed: {missing}")
        if phantom:
            warnings.append(f"Files Changed lists files the commit does not touch: {phantom}")

    if task_card:
        card = load_task(task_card)
        text = "\n".join(blocks)
        for cmd in card.verify:
            if cmd not in text:
                problems.append(f"required verification command not shown in output: {cmd}")

    click.echo(f"{handoff}: status={status or '?'} commit={sha or '-'} files={len(listed)}")
    for w in warnings:
        click.echo(f"  WARN  {w}")
    for p in problems:
        click.echo(f"  FAIL  {p}")
    if problems:
        raise SystemExit(1)
    click.echo("  OK: handoff has the evidence needed for review")


if __name__ == "__main__":
    main()
