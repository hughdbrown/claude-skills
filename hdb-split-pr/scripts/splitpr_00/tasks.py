"""Phase 4: Task Generation — create detailed tasks with recovery commands per PR.

Reads: prs, file_assignments, commits, commit_files from DB + git diffs.
Writes: tasks table.
"""

from __future__ import annotations

import logging
import sqlite3

import anthropic

from splitpr_00 import ai
from splitpr_00 import db
from splitpr_00 import git_ops
from splitpr_00.models import Task

logger = logging.getLogger(__name__)


def run_task_generation(
    conn: sqlite3.Connection,
    client: anthropic.Anthropic,
    model: str,
    verbose: bool = False,
) -> None:
    """Execute Phase 4: Task Generation.

    For each PR:
    1. Gather assigned files and their diffs
    2. Identify relevant commits
    3. Call AI to generate ordered tasks
    4. Attach recovery commands
    5. Store in tasks table
    """
    base_branch = db.get_metadata(conn, "base_branch")
    source_branch = db.get_metadata(conn, "source_branch")
    prs = db.get_all_prs(conn)

    for pr in prs:
        logger.info(f"Generating tasks for PR {pr.pr_id}: {pr.title}...")

        files = db.get_files_for_pr(conn, pr.pr_id)
        if not files:
            logger.warning(f"PR {pr.pr_id} has no files, skipping task generation")
            continue

        # Gather diffs for this PR's files
        diff_texts: dict[str, str] = {}
        total_diff_chars = 0
        for file_path in files:
            if total_diff_chars > 80_000:
                break
            try:
                diff = git_ops.get_file_diff(base_branch, file_path, max_lines=200)
                if diff:
                    diff_texts[file_path] = diff
                    total_diff_chars += len(diff)
            except git_ops.GitError:
                continue

        # Get relevant commits (cherry-pick candidates for this PR)
        cherry_picks = db.get_cherry_picks_for_pr(conn, pr.pr_id)
        commit_shas = [cp["sha"] for cp in cherry_picks]

        # Get commit details
        commit_details: list[dict] = []
        for sha in commit_shas:
            rows = conn.execute(
                "SELECT sha, subject FROM commits WHERE sha = ?", (sha,)
            ).fetchall()
            for r in rows:
                commit_details.append({"sha": r["sha"], "subject": r["subject"]})

        # Get PR dependencies for context
        deps = db.get_pr_dependencies(conn, pr.pr_id)
        dep_branches: list[str] = []
        for d in deps:
            dep_pr = conn.execute(
                "SELECT branch_name FROM prs WHERE pr_id = ?",
                (d["depends_on"],),
            ).fetchone()
            if dep_pr:
                dep_branches.append(dep_pr["branch_name"])

        # Build the AI prompt
        prompt = _build_task_prompt(
            pr, files, diff_texts, commit_details, dep_branches,
            source_branch, base_branch,
        )

        if verbose:
            logger.info(
                f"AI call: generate tasks for PR {pr.pr_id} "
                f"({len(files)} files, {len(commit_details)} commits)"
            )

        result = ai.generate_tasks(client, model, prompt)

        # Store tasks
        for ordinal, task_data in enumerate(result.get("tasks", []), start=1):
            source_files_list = task_data.get("source_files", [])

            # Build recovery commands
            recovery_cmds = _build_recovery_commands(
                source_branch, base_branch, source_files_list, commit_shas,
            )

            task = Task(
                task_id=0,
                pr_id=pr.pr_id,
                ordinal=ordinal,
                subject=task_data.get("subject", ""),
                description=task_data.get("description", ""),
                acceptance=task_data.get("acceptance", ""),
                recovery_cmds=recovery_cmds,
                task_type=task_data.get("task_type", ""),
                source_commits=",".join(commit_shas),
                source_files=",".join(source_files_list),
            )
            db.insert_task(conn, task)

        conn.commit()

    logger.info("Phase 4 (Tasks) complete.")


def _build_task_prompt(
    pr,
    files: list[str],
    diff_texts: dict[str, str],
    commit_details: list[dict],
    dep_branches: list[str],
    source_branch: str,
    base_branch: str,
) -> str:
    """Build the user prompt for task generation."""
    parts: list[str] = []

    parts.append(f"## PR: {pr.title}")
    parts.append(f"Branch: {pr.branch_name}")
    parts.append(f"Base: {pr.base_branch}")
    if dep_branches:
        parts.append(f"Depends on: {', '.join(dep_branches)}")
    parts.append(f"Source branch: {source_branch}")
    parts.append("")

    parts.append("### Files in this PR:")
    for f in files:
        parts.append(f"  - {f}")
    parts.append("")

    if commit_details:
        parts.append("### Relevant commits:")
        for c in commit_details:
            parts.append(f"  - {c['sha'][:8]}: {c['subject']}")
        parts.append("")

    if diff_texts:
        parts.append("### File diffs:")
        for file_path, diff in sorted(diff_texts.items()):
            parts.append(f"\n#### {file_path}")
            parts.append(f"```diff\n{diff}\n```")
        parts.append("")

    parts.append(
        "Generate an ordered task list for implementing this PR. "
        "Each task should reference specific files and describe concrete changes. "
        f"Recovery commands should reference the source branch '{source_branch}'."
    )

    return "\n".join(parts)


def _build_recovery_commands(
    source_branch: str,
    base_branch: str,
    source_files: list[str],
    commit_shas: list[str],
) -> str:
    """Build recovery git commands for a task."""
    cmds: list[str] = []

    for file_path in source_files[:5]:  # Limit to avoid huge command lists
        cmds.append(f"git show {source_branch}:{file_path}")
        cmds.append(f"git diff {base_branch}..{source_branch} -- {file_path}")

    if source_files:
        checkout_files = " ".join(source_files[:10])
        cmds.append(f"git checkout {source_branch} -- {checkout_files}")

    if commit_shas:
        for sha in commit_shas[:3]:
            cmds.append(f"git show {sha}")

    return "\n".join(cmds)
