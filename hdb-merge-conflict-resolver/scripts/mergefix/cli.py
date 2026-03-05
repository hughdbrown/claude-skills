"""Click CLI definition and top-level orchestration.

This is the only module that knows about all other modules.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import click

from mergefix import __version__
from mergefix import db
from mergefix import git_ops
from mergefix.models import Resolution, Strategy

logger = logging.getLogger("mergefix")


@click.command()
@click.option(
    "--database",
    "-d",
    default=None,
    type=click.Path(),
    help="Path to SQLite database for logging resolutions. Defaults to .git/mergefix.db.",
)
@click.option(
    "--dry-run",
    "-n",
    is_flag=True,
    default=False,
    help="Show proposed resolutions without applying them.",
)
@click.option(
    "--model",
    "-m",
    default="claude-sonnet-4-20250514",
    help="Anthropic model for conflict analysis.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Print detailed progress and reasoning.",
)
@click.version_option(version=__version__)
def cli(
    database: str | None,
    dry_run: bool,
    model: str,
    verbose: bool,
) -> None:
    """Resolve git merge conflicts using AI-assisted analysis.

    Discovers conflicted files, analyzes each conflict block with Claude,
    and applies the chosen resolution strategy (take_ours, take_theirs,
    take_both, or custom).

    Use --dry-run to preview resolutions without modifying any files.
    """
    _setup_logging(verbose)

    # ── Validate environment ─────────────────────────────────────────
    if not git_ops.is_git_repo():
        raise click.UsageError("Not inside a git repository.")

    conflicted = git_ops.get_conflicted_files()
    if not conflicted:
        click.echo("No merge conflicts found. Nothing to resolve.")
        sys.exit(0)

    # ── Database setup ───────────────────────────────────────────────
    if database is None:
        git_dir = git_ops.get_git_dir()
        db_path = Path(git_dir) / "mergefix.db"
    else:
        db_path = Path(database)

    conn = db.connect(db_path)
    db.initialize(conn)

    # ── AI client ────────────────────────────────────────────────────
    from mergefix import ai as ai_module

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    client = None
    if api_key:
        client = ai_module.create_client()
        logger.info("Anthropic client initialized (model: %s).", model)
    else:
        logger.warning(
            "ANTHROPIC_API_KEY not set. "
            "Resolutions will default to take_theirs."
        )

    # ── Resolve ──────────────────────────────────────────────────────
    from mergefix.resolver import resolve_all

    try:
        all_resolutions = resolve_all(
            conn=conn,
            client=client,
            model=model,
            dry_run=dry_run,
            verbose=verbose,
        )
    finally:
        _print_summary(conn, all_resolutions, dry_run)
        conn.close()


def _setup_logging(verbose: bool) -> None:
    """Configure logging for the CLI."""
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(levelname)-7s %(message)s")
    )
    root_logger = logging.getLogger("mergefix")
    root_logger.setLevel(level)
    root_logger.addHandler(handler)

    for name in (
        "mergefix.resolver",
        "mergefix.git_ops",
        "mergefix.ai",
        "mergefix.db",
    ):
        child = logging.getLogger(name)
        child.setLevel(level)
        child.addHandler(handler)


def _print_summary(
    conn,
    all_resolutions: dict[str, list[Resolution]],
    dry_run: bool,
) -> None:
    """Print a summary of all resolutions."""
    prefix = "[DRY RUN] " if dry_run else ""

    strategy_counts = db.get_resolution_summary(conn)
    confidence_counts = db.get_confidence_summary(conn)
    flagged_count = db.count_flagged(conn)
    applied_count = db.count_applied(conn)
    skipped = db.get_skipped_files(conn)

    total = sum(strategy_counts.values())
    if total == 0 and not skipped:
        return

    click.echo("")
    click.echo("=" * 60)
    click.echo(f"{prefix}MERGE CONFLICT RESOLUTION SUMMARY")
    click.echo("=" * 60)

    if total > 0:
        total_files = len(all_resolutions)
        click.echo(
            f"Total conflicts: {total} across {total_files} file"
            f"{'s' if total_files != 1 else ''}"
        )
        click.echo("")

        click.echo("Resolutions:")
        for strategy in Strategy:
            count = strategy_counts.get(strategy.value, 0)
            pct = (count / total * 100) if total > 0 else 0
            click.echo(f"  {strategy.value:15s} {count:3d} ({pct:.0f}%)")
        click.echo("")

        click.echo("Confidence:")
        for band in ("high", "medium", "low"):
            count = confidence_counts.get(band, 0)
            label = {
                "high": "High (>= 0.9)",
                "medium": "Medium (0.7-0.9)",
                "low": "Low (< 0.7)",
            }[band]
            click.echo(f"  {label:20s} {count}")
        click.echo("")

        click.echo("Status:")
        if dry_run:
            click.echo(f"  Proposed: {total}")
        else:
            click.echo(f"  Applied: {applied_count}")
            click.echo(f"  Flagged for review: {flagged_count}")

    if skipped:
        click.echo("")
        click.echo(f"Skipped files: {len(skipped)}")
        for s in skipped:
            click.echo(f"  {s['file_path']}: {s['reason']}")

    click.echo("")
    if not dry_run and total > 0:
        click.echo("Resolved files staged. Run 'git commit' to complete the merge.")
    click.echo("")
