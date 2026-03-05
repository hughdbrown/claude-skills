"""Click CLI definition and top-level orchestration.

This is the only module that knows about all other modules.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import click

from splitpr_05 import __version__
from splitpr_05 import db
from splitpr_05 import git_ops

logger = logging.getLogger("splitpr_05")


@click.command()
@click.option(
    "--database", "-d",
    required=True,
    type=click.Path(exists=True),
    help="Path to the splitpr_00 SQLite database.",
)
@click.option(
    "--dry-run", "-n",
    is_flag=True,
    default=False,
    help="Print operations without executing them.",
)
@click.option(
    "--model", "-m",
    default="claude-sonnet-4-20250514",
    help="Anthropic model for generating PR descriptions.",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Print detailed progress.",
)
@click.version_option(version=__version__)
def cli(
    database: str,
    dry_run: bool,
    model: str,
    verbose: bool,
) -> None:
    """Execute a split PR plan from a splitpr_00 database.

    Reads the plan (PRs, file assignments, tasks) from DATABASE and
    creates git branches, applies changes, pushes to the remote, and
    creates GitHub pull requests.

    Use --dry-run to preview what would happen without making changes.
    """
    _setup_logging(verbose)

    # ── Validate environment ─────────────────────────────────────────
    if not git_ops.is_git_repo():
        raise click.UsageError("Not inside a git repository.")

    db_path = Path(database)
    if not db_path.exists():
        raise click.UsageError(f"Database not found: {database}")

    # ── Connect to database ──────────────────────────────────────────
    conn = db.connect(db_path)

    # Validate the database has plan data
    try:
        prs = db.get_all_prs(conn)
    except Exception:
        conn.close()
        raise click.UsageError(
            f"Database '{database}' does not have the expected schema. "
            "Was it created by splitpr_00?"
        )
    if not prs:
        conn.close()
        raise click.UsageError(
            "No PRs found in the database. "
            "Run splitpr_00 first to create a plan."
        )

    meta = db.get_all_metadata(conn)
    source_branch = meta.get("source_branch", "")
    base_branch = meta.get("base_branch", "")

    if not source_branch or not base_branch:
        conn.close()
        raise click.UsageError(
            "Database is missing source_branch or base_branch metadata. "
            "Was it created by splitpr_00?"
        )

    # ── Display plan summary ─────────────────────────────────────────
    _display_plan_summary(conn, meta, prs, dry_run)

    # ── Set up AI client ─────────────────────────────────────────────
    from splitpr_05 import ai as ai_module

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    client = None
    if api_key:
        client = ai_module.create_client()
        logger.info("Anthropic client initialized (model: %s).", model)
    else:
        logger.warning(
            "ANTHROPIC_API_KEY not set. PR descriptions will use templates."
        )

    # ── Execute ──────────────────────────────────────────────────────
    from splitpr_05.executor import execute_plan

    try:
        pr_urls = execute_plan(
            conn=conn,
            client=client,
            model=model,
            dry_run=dry_run,
            verbose=verbose,
        )
    except Exception:
        conn.close()
        raise
    finally:
        conn.close()


def _setup_logging(verbose: bool) -> None:
    """Configure logging for the CLI."""
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(levelname)-7s %(message)s")
    )
    root_logger = logging.getLogger("splitpr_05")
    root_logger.setLevel(level)
    root_logger.addHandler(handler)

    for name in (
        "splitpr_05.executor",
        "splitpr_05.git_ops",
        "splitpr_05.ai",
        "splitpr_05.db",
    ):
        child = logging.getLogger(name)
        child.setLevel(level)
        child.addHandler(handler)


def _display_plan_summary(
    conn,
    meta: dict[str, str],
    prs: list,
    dry_run: bool,
) -> None:
    """Display a summary of the plan about to be executed."""
    prefix = "[DRY RUN] " if dry_run else ""

    click.echo("")
    click.echo("=" * 60)
    click.echo(f"{prefix}SPLIT PR EXECUTION PLAN")
    click.echo("=" * 60)
    click.echo(f"Source branch:  {meta.get('source_branch', '?')}")
    click.echo(f"Base branch:    {meta.get('base_branch', '?')}")
    click.echo(f"Total commits:  {meta.get('total_commits', '?')}")
    click.echo(f"Total files:    {meta.get('total_files', '?')}")
    click.echo(f"PRs to create:  {len(prs)}")
    click.echo("")

    for pr in prs:
        deps = db.get_pr_dependencies(conn, pr.pr_id)
        files = db.get_files_for_pr(conn, pr.pr_id)
        dep_str = (
            ", ".join(str(d["depends_on"]) for d in deps) if deps else "none"
        )
        click.echo(
            f"  [{pr.merge_order}] {pr.branch_name} "
            f"({len(files)} files, "
            f"{'+' if pr.net_lines >= 0 else ''}{pr.net_lines} lines) "
            f"base: {pr.base_branch} deps: {dep_str}"
        )

    click.echo("")
