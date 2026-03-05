"""Phase 3: Partition — assign every changed file to exactly one PR.

Reads: prs, pr_dependencies, changed_files, cross_cutting_files from DB.
Writes: file_assignments; updates prs.file_count/net_lines.
"""

from __future__ import annotations

import logging
import sqlite3

import anthropic

from splitpr_00 import ai
from splitpr_00 import db
from splitpr_00 import git_ops

logger = logging.getLogger(__name__)


class PartitionError(Exception):
    """Raised when partition verification fails."""

    pass


def run_partition(
    conn: sqlite3.Connection,
    client: anthropic.Anthropic,
    model: str,
    verbose: bool = False,
) -> None:
    """Execute Phase 3: Partition.

    1. Assign unambiguous files (touched by one theme only)
    2. Resolve cross-cutting files via AI
    3. Verify completeness (no duplicates, no unassigned)
    4. Update PR stats
    """
    base_branch = db.get_metadata(conn, "base_branch")
    prs = db.get_all_prs(conn)
    themes = db.get_all_themes(conn)

    theme_id_to_pr: dict[int, int] = {}
    for pr in prs:
        if pr.theme_id is not None:
            theme_id_to_pr[pr.theme_id] = pr.pr_id

    theme_id_to_name = {t.theme_id: t.name for t in themes}
    theme_name_to_pr = {
        theme_id_to_name[tid]: pid
        for tid, pid in theme_id_to_pr.items()
        if tid in theme_id_to_name
    }

    # ── 1. Assign unambiguous files ──────────────────────────────────
    logger.info("Assigning unambiguous files...")
    cross_cutting = db.get_cross_cutting_files(conn)
    cross_cutting_paths = set(cross_cutting.keys())

    # For each changed file, determine which themes' commits touch it
    all_changed = db.get_all_changed_files(conn)
    assigned_count = 0

    for file_path in all_changed:
        if file_path in cross_cutting_paths:
            continue  # Handle separately

        # Find which theme(s) touch this file
        rows = conn.execute(
            """
            SELECT DISTINCT ct.theme_id
            FROM commit_files cf
            JOIN commit_themes ct ON cf.sha = ct.sha
            WHERE cf.file_path = ?
            """,
            (file_path,),
        ).fetchall()

        theme_ids = [r["theme_id"] for r in rows]

        if len(theme_ids) == 1:
            pr_id = theme_id_to_pr.get(theme_ids[0])
            if pr_id:
                db.insert_file_assignment(
                    conn, file_path, pr_id, strategy="unambiguous"
                )
                assigned_count += 1
        elif len(theme_ids) == 0:
            # File changed overall but no commit touches it — shouldn't happen
            # Assign to the first PR as fallback
            if prs:
                db.insert_file_assignment(
                    conn, file_path, prs[0].pr_id, strategy="earliest_pr",
                    ai_reasoning="No commit found for this file; assigned to first PR",
                )
                assigned_count += 1
        else:
            # Multiple themes but not in cross_cutting — edge case
            # This can happen if cross_cutting computation missed it
            cross_cutting_paths.add(file_path)

    conn.commit()
    logger.info(f"Assigned {assigned_count} unambiguous files")

    # ── 2. Resolve cross-cutting files ───────────────────────────────
    if cross_cutting_paths:
        logger.info(f"Resolving {len(cross_cutting_paths)} cross-cutting files...")
        _resolve_cross_cutting(
            conn, client, model, base_branch, cross_cutting_paths,
            themes, prs, theme_name_to_pr, theme_id_to_name, verbose,
        )
        conn.commit()
    else:
        logger.info("No cross-cutting files to resolve")

    # ── 3. Verify completeness ───────────────────────────────────────
    logger.info("Verifying partition completeness...")
    _verify_completeness(conn)

    # ── 4. Update PR stats ───────────────────────────────────────────
    logger.info("Updating PR statistics...")
    _update_pr_stats(conn)
    conn.commit()

    logger.info("Phase 3 (Partition) complete.")


def _resolve_cross_cutting(
    conn: sqlite3.Connection,
    client: anthropic.Anthropic,
    model: str,
    base_branch: str,
    cross_cutting_paths: set[str],
    themes: list,
    prs: list,
    theme_name_to_pr: dict[str, int],
    theme_id_to_name: dict[int, str],
    verbose: bool,
) -> None:
    """Use AI to resolve cross-cutting file assignments."""
    # Build prompt with file diffs and theme context
    parts: list[str] = []
    parts.append("The following files are touched by multiple themes and need resolution.\n")
    parts.append("Available themes (in merge order):\n")

    for pr in prs:
        theme_name = theme_id_to_name.get(pr.theme_id, "unknown") if pr.theme_id else "unknown"
        deps = db.get_pr_dependencies(conn, pr.pr_id)
        dep_names = []
        for d in deps:
            dep_pr = next((p for p in prs if p.pr_id == d["depends_on"]), None)
            if dep_pr and dep_pr.theme_id:
                dep_names.append(theme_id_to_name.get(dep_pr.theme_id, "unknown"))
        dep_str = f" (depends on: {', '.join(dep_names)})" if dep_names else " (no dependencies)"
        parts.append(f"  - {theme_name} [merge order {pr.merge_order}]{dep_str}")

    parts.append("\n\nCross-cutting files:\n")

    for file_path in sorted(cross_cutting_paths):
        # Which themes touch this file?
        rows = conn.execute(
            """
            SELECT DISTINCT ct.theme_id
            FROM commit_files cf
            JOIN commit_themes ct ON cf.sha = ct.sha
            WHERE cf.file_path = ?
            """,
            (file_path,),
        ).fetchall()
        touching_themes = [
            theme_id_to_name.get(r["theme_id"], "unknown") for r in rows
        ]

        parts.append(f"\n### {file_path}")
        parts.append(f"Touched by themes: {', '.join(touching_themes)}")

        # Include the diff (truncated)
        try:
            diff = git_ops.get_file_diff(base_branch, file_path, max_lines=150)
            if diff:
                parts.append(f"```diff\n{diff}\n```")
        except git_ops.GitError:
            parts.append("(diff unavailable)")

    parts.append(
        "\n\nFor each file, assign it to exactly one theme using the "
        "appropriate strategy (earliest_pr, split_by_hunk, infrastructure, "
        "or sequential_layering). Prefer earliest_pr when in doubt."
    )

    prompt = "\n".join(parts)

    if verbose:
        logger.info(f"AI call: resolve {len(cross_cutting_paths)} cross-cutting files")

    result = ai.resolve_crosscutting(client, model, prompt)

    # Process resolutions
    resolved_files: set[str] = set()
    for resolution in result.get("resolutions", []):
        file_path = resolution["file_path"]
        assigned_theme = resolution["assigned_theme"]
        strategy = resolution.get("strategy", "earliest_pr")
        reasoning = resolution.get("reasoning", "")

        pr_id = theme_name_to_pr.get(assigned_theme)
        if pr_id is None:
            # Theme name doesn't match — try to find closest match
            logger.warning(
                f"Unknown theme '{assigned_theme}' for file '{file_path}', "
                "assigning to first PR"
            )
            pr_id = prs[0].pr_id if prs else None
            strategy = "earliest_pr"
            reasoning = f"AI returned unknown theme '{assigned_theme}'; fallback to first PR"

        if pr_id is not None:
            db.insert_file_assignment(conn, file_path, pr_id, strategy, reasoning)
            resolved_files.add(file_path)

    # Handle any cross-cutting files the AI missed
    missed = cross_cutting_paths - resolved_files
    if missed:
        logger.warning(f"AI missed {len(missed)} cross-cutting files, assigning to first PR")
        first_pr_id = prs[0].pr_id if prs else None
        if first_pr_id:
            for file_path in missed:
                db.insert_file_assignment(
                    conn, file_path, first_pr_id,
                    strategy="earliest_pr",
                    ai_reasoning="Not resolved by AI; fallback to first PR",
                )


def _verify_completeness(conn: sqlite3.Connection) -> None:
    """Verify that every changed file is assigned to exactly one PR."""
    unassigned = db.get_unassigned_files(conn)
    duplicates = db.get_duplicate_assignments(conn)

    if unassigned:
        raise PartitionError(
            f"{len(unassigned)} files are unassigned: "
            f"{', '.join(unassigned[:10])}"
            + ("..." if len(unassigned) > 10 else "")
        )

    if duplicates:
        raise PartitionError(
            f"{len(duplicates)} files assigned to multiple PRs "
            f"(without split_by_hunk): {', '.join(duplicates[:10])}"
            + ("..." if len(duplicates) > 10 else "")
        )

    total_changed = len(db.get_all_changed_files(conn))
    total_assigned = conn.execute(
        "SELECT COUNT(DISTINCT file_path) FROM file_assignments"
    ).fetchone()[0]

    logger.info(
        f"Partition verified: {total_assigned}/{total_changed} files assigned, "
        f"0 duplicates, 0 unassigned"
    )


def _update_pr_stats(conn: sqlite3.Connection) -> None:
    """Update each PR's file_count and net_lines from file_assignments."""
    prs = db.get_all_prs(conn)
    for pr in prs:
        files = db.get_files_for_pr(conn, pr.pr_id)

        # Sum insertions/deletions for assigned files
        total_ins = 0
        total_del = 0
        for f in files:
            row = conn.execute(
                "SELECT insertions, deletions FROM changed_files WHERE file_path = ?",
                (f,),
            ).fetchone()
            if row:
                total_ins += row["insertions"] or 0
                total_del += row["deletions"] or 0

        db.update_pr_stats(conn, pr.pr_id, len(files), total_ins - total_del)
