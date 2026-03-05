"""Click CLI definition and top-level phase orchestration.

This is the only module that knows about all phases.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import click

from splitpr_00 import __version__
from splitpr_00 import db
from splitpr_00 import git_ops

logger = logging.getLogger("splitpr_00")

_SMALL_COMMIT_THRESHOLD = 5
_SMALL_FILE_THRESHOLD = 10


@click.command()
@click.option(
    "--base", "-b",
    default=None,
    help="Base branch to diff against. Auto-detects master/main if omitted.",
)
@click.option(
    "--db-path", "-d",
    default="splitpr_00.db",
    type=click.Path(),
    help="Path to SQLite database file.",
)
@click.option(
    "--report", "-r",
    default="splitpr_00-report.md",
    type=click.Path(),
    help="Path to markdown report output.",
)
@click.option(
    "--model", "-m",
    default="claude-sonnet-4-20250514",
    help="Anthropic model to use.",
)
@click.option(
    "--phase",
    type=click.IntRange(1, 5),
    default=None,
    help="Run only up to this phase (1-5). Default: run all.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Force analysis even on small branches.",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Print detailed progress and AI responses.",
)
@click.version_option(version=__version__)
def cli(
    base: str | None,
    db_path: str,
    report: str,
    model: str,
    phase: int | None,
    force: bool,
    verbose: bool,
) -> None:
    """Decompose an oversize git branch into focused PRs.

    Analyzes the current branch against BASE, categorizes commits by theme,
    builds a dependency DAG, assigns every changed file to exactly one PR,
    and generates a detailed task list with recovery commands.

    Output: SQLite database (--db-path) and markdown report (--report).
    """
    _setup_logging(verbose)
    max_phase = phase or 5

    # ── Validate environment ─────────────────────────────────────────
    if not git_ops.is_git_repo():
        raise click.UsageError("Not inside a git repository.")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise click.UsageError(
            "ANTHROPIC_API_KEY environment variable is required."
        )

    # ── Detect branches ──────────────────────────────────────────────
    try:
        base_branch = git_ops.detect_base_branch(base)
    except git_ops.GitError as e:
        raise click.UsageError(str(e))

    source_branch = git_ops.get_current_branch()
    if source_branch == "HEAD":
        raise click.UsageError(
            "Detached HEAD. Check out a branch or use --base to specify context."
        )

    try:
        merge_base = git_ops.get_merge_base(base_branch)
    except git_ops.GitError as e:
        raise click.UsageError(
            f"Cannot find merge base between '{base_branch}' and HEAD: {e}"
        )

    logger.info(f"Source: {source_branch} | Base: {base_branch} | Merge base: {merge_base[:12]}")

    # ── Small branch check ───────────────────────────────────────────
    if not force:
        commits = git_ops.list_commits(merge_base)
        changed_files = git_ops.get_changed_files(base_branch)
        if (
            len(commits) < _SMALL_COMMIT_THRESHOLD
            and len(changed_files) < _SMALL_FILE_THRESHOLD
        ):
            click.echo(
                f"Branch has only {len(commits)} commits and "
                f"{len(changed_files)} changed files — small enough for a "
                f"single PR. Use --force to analyze anyway."
            )
            sys.exit(0)

    # ── Create database ──────────────────────────────────────────────
    conn = db.connect(db_path)
    db.initialize(conn)

    # Deferred imports to avoid circular dependencies and keep startup fast
    from splitpr_00 import ai as ai_module
    from splitpr_00.inventory import run_inventory
    from splitpr_00.dependencies import run_dependency_analysis
    from splitpr_00.partition import run_partition
    from splitpr_00.tasks import run_task_generation
    from splitpr_00.report import generate_report

    client = ai_module.create_client()

    try:
        # ── Phase 1: Inventory ───────────────────────────────────────
        if max_phase >= 1:
            logger.info("=" * 60)
            logger.info("Phase 1: Inventory")
            logger.info("=" * 60)
            run_inventory(
                conn, client, model, base_branch, source_branch,
                merge_base, verbose,
            )

        # ── Phase 2: Dependency Analysis ─────────────────────────────
        if max_phase >= 2:
            logger.info("=" * 60)
            logger.info("Phase 2: Dependency Analysis")
            logger.info("=" * 60)
            run_dependency_analysis(conn, client, model, verbose)

        # ── Phase 3: Partition ───────────────────────────────────────
        if max_phase >= 3:
            logger.info("=" * 60)
            logger.info("Phase 3: Partition")
            logger.info("=" * 60)
            run_partition(conn, client, model, verbose)

        # ── Phase 4: Task Generation ─────────────────────────────────
        if max_phase >= 4:
            logger.info("=" * 60)
            logger.info("Phase 4: Task Generation")
            logger.info("=" * 60)
            run_task_generation(conn, client, model, verbose)

        # ── Phase 5: Report ──────────────────────────────────────────
        if max_phase >= 5:
            logger.info("=" * 60)
            logger.info("Phase 5: Report")
            logger.info("=" * 60)
            generate_report(conn, Path(report))

        # ── Final summary ────────────────────────────────────────────
        _print_summary(conn, db_path, report, max_phase)

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
    logger.setLevel(level)
    logger.addHandler(handler)
    # Also configure child loggers
    for name in ("splitpr_00.inventory", "splitpr_00.dependencies",
                 "splitpr_00.partition", "splitpr_00.tasks", "splitpr_00.report",
                 "splitpr_00.ai"):
        child = logging.getLogger(name)
        child.setLevel(level)
        child.addHandler(handler)


def _print_summary(
    conn,
    db_path: str,
    report_path: str,
    max_phase: int,
) -> None:
    """Print a final summary to stdout."""
    meta = db.get_all_metadata(conn)
    prs = db.get_all_prs(conn) if max_phase >= 2 else []
    tasks = db.get_all_tasks(conn) if max_phase >= 4 else []

    click.echo("")
    click.echo("=" * 60)
    click.echo("SPLIT PR ANALYSIS COMPLETE")
    click.echo("=" * 60)
    click.echo(f"Source branch:  {meta.get('source_branch', '?')}")
    click.echo(f"Base branch:    {meta.get('base_branch', '?')}")
    click.echo(f"Commits:        {meta.get('total_commits', '?')}")
    click.echo(f"Files changed:  {meta.get('total_files', '?')}")
    click.echo(f"Net lines:      +{meta.get('total_insertions', '?')}/-{meta.get('total_deletions', '?')}")

    if prs:
        click.echo(f"PRs planned:    {len(prs)}")
        for pr in prs:
            deps = db.get_pr_dependencies(conn, pr.pr_id)
            dep_str = ", ".join(str(d["depends_on"]) for d in deps) if deps else "none"
            click.echo(
                f"  [{pr.merge_order}] {pr.branch_name} "
                f"({pr.file_count} files, {'+' if pr.net_lines >= 0 else ''}{pr.net_lines} lines) "
                f"deps: {dep_str}"
            )

    if tasks:
        click.echo(f"Total tasks:    {len(tasks)}")

    click.echo(f"\nDatabase:       {db_path}")
    if max_phase >= 5:
        click.echo(f"Report:         {report_path}")
    click.echo("")
