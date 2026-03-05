"""Execution engine — create branches, apply changes, push, and create PRs.

Reads the plan from the splitpr_00 database and executes it.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

import anthropic

from splitpr_05 import ai
from splitpr_05 import db
from splitpr_05 import git_ops
from splitpr_05.models import PR, Task

logger = logging.getLogger(__name__)


class ExecutionError(Exception):
    """Raised when a step in the execution fails unrecoverably."""

    pass


def execute_plan(
    conn: sqlite3.Connection,
    client: anthropic.Anthropic | None,
    model: str,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[int, str]:
    """Execute the full split-PR plan from the database.

    Returns a mapping of pr_id -> PR URL for created PRs.
    """
    meta: dict[str, str] = db.get_all_metadata(conn)
    prs: list[PR] = db.get_all_prs(conn)
    source_branch: str = meta.get("source_branch", "")
    base_branch: str = meta.get("base_branch", "")
    file_statuses: dict[str, str] = db.get_file_statuses(conn)

    if not prs:
        logger.warning("No PRs found in the plan. Nothing to execute.")
        return {}

    _validate_preconditions(source_branch, base_branch, meta, dry_run)

    original_branch: str = git_ops.get_current_branch()
    total_prs: int = len(prs)
    pr_urls: dict[int, str] = {}
    created_branches: list[str] = []

    logger.info("Executing plan: %d PRs from branch '%s'", total_prs, source_branch)

    if dry_run:
        logger.info("[DRY RUN] No actual changes will be made.")

    # ── Log repository context ───────────────────────────────────────
    _log_repo_context()

    has_gh: bool = git_ops.gh_available()
    if not has_gh:
        logger.warning(
            "gh CLI not available or not authenticated. "
            "PRs will not be created on GitHub."
        )

    try:
        for pr_index, pr in enumerate(prs, start=1):
            url: str | None = _execute_single_pr(
                conn=conn,
                client=client,
                model=model,
                pr=pr,
                pr_index=pr_index,
                total_prs=total_prs,
                source_branch=source_branch,
                file_statuses=file_statuses,
                dry_run=dry_run,
                verbose=verbose,
                has_gh=has_gh,
            )
            created_branches.append(pr.branch_name)
            if url:
                pr_urls[pr.pr_id] = url

    except Exception:
        logger.error(
            "Execution failed. Restoring original branch '%s'.",
            original_branch,
        )
        if not dry_run:
            try:
                git_ops.checkout_branch(original_branch)
            except git_ops.GitError:
                logger.error(
                    "Could not restore original branch '%s'.",
                    original_branch,
                )
        raise

    # Restore original branch
    logger.info("Restoring original branch '%s'...", original_branch)
    git_ops.checkout_branch(original_branch, dry_run)

    _print_summary(prs, pr_urls, created_branches, dry_run)
    return pr_urls


def _validate_preconditions(
    source_branch: str,
    base_branch: str,
    meta: dict[str, str],
    dry_run: bool,
) -> None:
    """Validate that the repository is in a good state for execution."""
    if not git_ops.is_git_repo():
        raise ExecutionError("Not inside a git repository.")

    if not source_branch:
        raise ExecutionError(
            "No source_branch in database metadata. "
            "Was the plan created correctly?"
        )

    if not base_branch:
        raise ExecutionError(
            "No base_branch in database metadata. "
            "Was the plan created correctly?"
        )

    # ── Repo identity check ──────────────────────────────────────────
    expected_repo: str = meta.get("repo_toplevel", "")
    if expected_repo:
        actual_repo: str = git_ops.get_repo_toplevel()
        if actual_repo != expected_repo:
            raise ExecutionError(
                f"Repository mismatch.\n"
                f"  Database was built against: {expected_repo}\n"
                f"  Current repository:         {actual_repo}\n"
                f"Run splitpr_05 from the same repo that splitpr_00 analyzed."
            )
    else:
        logger.warning(
            "Database does not contain repo_toplevel metadata. "
            "Skipping repo identity check. "
            "(Re-run splitpr_00 to record it.)"
        )

    # ── HEAD revision check ──────────────────────────────────────────
    expected_rev: str = meta.get("head_rev", "")
    if expected_rev:
        actual_rev: str = git_ops.get_head_rev()
        if actual_rev != expected_rev:
            raise ExecutionError(
                f"HEAD revision mismatch.\n"
                f"  Database was built at: {expected_rev}\n"
                f"  Current HEAD:          {actual_rev}\n"
                f"The branch has changed since the plan was created. "
                f"Re-run splitpr_00 to generate a fresh plan."
            )
    else:
        logger.warning(
            "Database does not contain head_rev metadata. "
            "Skipping HEAD revision check. "
            "(Re-run splitpr_00 to record it.)"
        )

    if not dry_run and git_ops.has_uncommitted_changes():
        raise ExecutionError(
            "Working tree has uncommitted changes. "
            "Please commit or stash them before executing."
        )


def _execute_single_pr(
    conn: sqlite3.Connection,
    client: anthropic.Anthropic | None,
    model: str,
    pr: PR,
    pr_index: int,
    total_prs: int,
    source_branch: str,
    file_statuses: dict[str, str],
    dry_run: bool,
    verbose: bool,
    has_gh: bool,
) -> str | None:
    """Execute a single PR: create branch, apply changes, push, create PR.

    Returns the GitHub PR URL if created, otherwise None.
    """
    logger.info(
        "=" * 60 + "\n"
        "PR %d/%d: %s\n"
        "Branch: %s\n"
        "Base: %s",
        pr_index, total_prs, pr.title,
        pr.branch_name, pr.base_branch,
    )

    files: list[str] = db.get_files_for_pr(conn, pr.pr_id)
    tasks: list[Task] = db.get_tasks_for_pr(conn, pr.pr_id)
    cherry_picks: list[dict[str, Any]] = db.get_cherry_picks_for_pr_ordered(
        conn, pr.pr_id
    )
    deps: list[dict[str, Any]] = db.get_pr_dependencies(conn, pr.pr_id)

    dep_branches: list[str] = _get_dep_branches(conn, deps)

    if not files:
        logger.warning("PR %d has no files assigned, skipping.", pr.pr_id)
        return None

    # ── 1. Check if branch already exists ────────────────────────────
    if not dry_run and git_ops.branch_exists(pr.branch_name):
        logger.warning(
            "Branch '%s' already exists. Skipping creation. "
            "Delete it manually to recreate.",
            pr.branch_name,
        )
        return None

    # ── 2. Create branch from base ───────────────────────────────────
    logger.info("Creating branch '%s' from '%s'...", pr.branch_name, pr.base_branch)
    git_ops.create_branch(pr.branch_name, pr.base_branch, dry_run)

    # ── 3. Apply changes ─────────────────────────────────────────────
    _apply_changes(
        pr=pr,
        files=files,
        file_statuses=file_statuses,
        cherry_picks=cherry_picks,
        source_branch=source_branch,
        dry_run=dry_run,
        verbose=verbose,
    )

    # ── 4. Push to remote ────────────────────────────────────────────
    remote_url: str | None = git_ops.get_remote_url("origin")
    logger.info(
        "Pushing '%s' to origin (%s)...",
        pr.branch_name,
        remote_url or "URL unknown",
    )
    git_ops.push_branch(pr.branch_name, "origin", dry_run)

    # ── 5. Create GitHub PR ──────────────────────────────────────────
    pr_url: str | None = None
    if has_gh:
        gh_info: dict[str, str] | None = git_ops.get_gh_repo_info()
        target_repo: str = (
            gh_info.get("nameWithOwner", "unknown") if gh_info else "unknown"
        )
        logger.info(
            "Creating PR on %s: '%s' (base: %s)...",
            target_repo,
            pr.title,
            pr.base_branch,
        )
        pr_url = _create_pr(
            conn=conn,
            client=client,
            model=model,
            pr=pr,
            tasks=tasks,
            files=files,
            dep_branches=dep_branches,
            total_prs=total_prs,
            pr_index=pr_index,
            source_branch=source_branch,
            dry_run=dry_run,
        )
        if pr_url:
            logger.info("PR created: %s", pr_url)
    else:
        logger.info("Skipping PR creation (gh CLI not available).")

    return pr_url


def _apply_changes(
    pr: PR,
    files: list[str],
    file_statuses: dict[str, str],
    cherry_picks: list[dict[str, Any]],
    source_branch: str,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Apply changes for a PR using cherry-pick or file-level checkout."""
    # Decide extraction method
    all_clean: bool = (
        bool(cherry_picks)
        and all(cp.get("is_clean") for cp in cherry_picks)
    )

    if all_clean:
        logger.info(
            "Using cherry-pick method (%d clean commits)...",
            len(cherry_picks),
        )
        shas: list[str] = [cp["sha"] for cp in cherry_picks]
        success: bool = git_ops.cherry_pick(shas, dry_run)

        if not success and not dry_run:
            logger.warning(
                "Cherry-pick failed, falling back to file-level checkout."
            )
            git_ops.cherry_pick_abort()
            _apply_file_checkout(
                files, file_statuses, source_branch, pr.title, dry_run
            )
        elif not success and dry_run:
            logger.info(
                "[DRY RUN] Would fall back to file-level checkout if "
                "cherry-pick failed."
            )
    else:
        if cherry_picks:
            logger.info(
                "Using file-level checkout (%d commits, not all clean)...",
                len(cherry_picks),
            )
        else:
            logger.info("Using file-level checkout (%d files)...", len(files))
        _apply_file_checkout(
            files, file_statuses, source_branch, pr.title, dry_run
        )

    if verbose:
        logger.info("Applied changes for %d files.", len(files))


def _apply_file_checkout(
    files: list[str],
    file_statuses: dict[str, str],
    source_branch: str,
    pr_title: str,
    dry_run: bool,
) -> None:
    """Apply changes via file-level checkout from the source branch.

    Handles different file statuses:
    - A (added) / M (modified) / R (renamed): checkout from source branch
    - D (deleted): git rm the file
    """
    # Separate files by status
    checkout_files: list[str] = []
    delete_files: list[str] = []

    for file_path in files:
        status: str = file_statuses.get(file_path, "M")
        if status == "D":
            delete_files.append(file_path)
        else:
            checkout_files.append(file_path)

    if checkout_files:
        logger.info("Checking out %d files from '%s'...", len(checkout_files), source_branch)
        git_ops.checkout_files_from_branch(source_branch, checkout_files, dry_run)

    if delete_files:
        logger.info("Removing %d deleted files...", len(delete_files))
        git_ops.rm_files(delete_files, dry_run)

    # Commit the changes
    commit_msg: str = (
        f"{pr_title}\n\n"
        f"File-level extraction from {source_branch}.\n"
        f"Files: {len(files)}"
    )
    logger.info("Committing changes...")
    git_ops.commit(commit_msg, dry_run)


def _create_pr(
    conn: sqlite3.Connection,
    client: anthropic.Anthropic | None,
    model: str,
    pr: PR,
    tasks: list[Task],
    files: list[str],
    dep_branches: list[str],
    total_prs: int,
    pr_index: int,
    source_branch: str,
    dry_run: bool,
) -> str | None:
    """Generate PR body and create the GitHub PR."""
    logger.info("Creating GitHub PR for '%s'...", pr.title)

    # Generate the PR body
    if client is not None:
        try:
            body: str = ai.generate_pr_body(
                client=client,
                model=model,
                pr=pr,
                tasks=tasks,
                files=files,
                dep_branches=dep_branches,
                total_prs=total_prs,
                pr_index=pr_index,
                source_branch=source_branch,
            )
        except (ai.AIError, Exception) as e:
            logger.warning(
                "AI PR body generation failed (%s), using template.", e
            )
            body = ai.generate_pr_body_template(
                pr=pr,
                tasks=tasks,
                files=files,
                dep_branches=dep_branches,
                total_prs=total_prs,
                pr_index=pr_index,
                source_branch=source_branch,
            )
    else:
        body = ai.generate_pr_body_template(
            pr=pr,
            tasks=tasks,
            files=files,
            dep_branches=dep_branches,
            total_prs=total_prs,
            pr_index=pr_index,
            source_branch=source_branch,
        )

    return git_ops.create_github_pr(
        branch=pr.branch_name,
        base=pr.base_branch,
        title=pr.title,
        body=body,
        dry_run=dry_run,
    )


def _log_repo_context() -> None:
    """Log repository path, remote URLs, and fork status."""
    lines: list[str] = git_ops.describe_repo_context("origin")
    if lines:
        logger.info("─── Repository context ───")
        for line in lines:
            logger.info("  %s", line)
        logger.info("──────────────────────────")


def _get_dep_branches(
    conn: sqlite3.Connection,
    deps: list[dict[str, Any]],
) -> list[str]:
    """Get the branch names of PRs that this PR depends on."""
    branches: list[str] = []
    for d in deps:
        rows = conn.execute(
            "SELECT branch_name FROM prs WHERE pr_id = ?",
            (d["depends_on"],),
        ).fetchall()
        for r in rows:
            branches.append(r["branch_name"])
    return branches


def _print_summary(
    prs: list[PR],
    pr_urls: dict[int, str],
    created_branches: list[str],
    dry_run: bool,
) -> None:
    """Print a final execution summary."""
    prefix: str = "[DRY RUN] " if dry_run else ""

    logger.info("")
    logger.info("=" * 60)
    logger.info("%sEXECUTION COMPLETE", prefix)
    logger.info("=" * 60)
    logger.info("%sBranches processed: %d", prefix, len(created_branches))

    for pr in prs:
        url: str = pr_urls.get(pr.pr_id, "")
        status: str = f" -> {url}" if url else ""
        logger.info(
            "  [%d] %s%s", pr.merge_order, pr.branch_name, status
        )

    if pr_urls:
        logger.info("%sGitHub PRs created: %d", prefix, len(pr_urls))
    logger.info("")
