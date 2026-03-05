"""Phase 1: Inventory — catalog commits, classify themes, identify cross-cutting files.

Reads from git, writes to: run_metadata, commits, commit_files,
changed_files, themes, commit_themes, cross_cutting_files.
"""

from __future__ import annotations

import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone

import anthropic

from splitpr_00 import __version__
from splitpr_00 import ai
from splitpr_00 import db
from splitpr_00 import git_ops
from splitpr_00.models import Commit, FileChange, Theme

logger = logging.getLogger(__name__)

# Maximum commits per AI classification batch
_BATCH_SIZE = 50


def run_inventory(
    conn: sqlite3.Connection,
    client: anthropic.Anthropic,
    model: str,
    base_branch: str,
    source_branch: str,
    merge_base: str,
    verbose: bool = False,
) -> None:
    """Execute Phase 1: Inventory.

    1. Store run metadata
    2. List and store all commits
    3. Get per-commit file lists
    4. Get overall changed files with stats
    5. Classify commits into themes via AI
    6. Identify cross-cutting files
    """
    # ── 1. Run metadata ──────────────────────────────────────────────
    db.set_metadata(conn, "base_branch", base_branch)
    db.set_metadata(conn, "source_branch", source_branch)
    db.set_metadata(conn, "merge_base_sha", merge_base)
    db.set_metadata(conn, "model", model)
    db.set_metadata(conn, "script_version", __version__)
    db.set_metadata(
        conn,
        "run_timestamp",
        datetime.now(timezone.utc).isoformat(),
    )

    # ── 2. List commits ──────────────────────────────────────────────
    logger.info("Listing commits...")
    commits = git_ops.list_commits(merge_base)
    db.set_metadata(conn, "total_commits", str(len(commits)))

    if verbose:
        logger.info(f"Found {len(commits)} commits")

    for commit in commits:
        db.insert_commit(conn, commit)
    conn.commit()

    # ── 3. Per-commit file lists ─────────────────────────────────────
    logger.info("Getting per-commit file lists...")
    for commit in commits:
        files = git_ops.get_commit_numstat(commit.sha)
        commit.files = files
        db.insert_commit_files(conn, commit.sha, files)
    conn.commit()

    # ── 4. Overall changed files ─────────────────────────────────────
    logger.info("Getting overall changed files...")
    changed_files = git_ops.get_changed_files_numstat(base_branch)
    db.insert_changed_files(conn, changed_files)

    total_insertions = sum(f.insertions for f in changed_files)
    total_deletions = sum(f.deletions for f in changed_files)
    db.set_metadata(conn, "total_files", str(len(changed_files)))
    db.set_metadata(conn, "total_insertions", str(total_insertions))
    db.set_metadata(conn, "total_deletions", str(total_deletions))
    conn.commit()

    if verbose:
        logger.info(
            f"Changed files: {len(changed_files)}, "
            f"+{total_insertions}/-{total_deletions}"
        )

    # ── 5. Classify commits into themes ──────────────────────────────
    logger.info("Classifying commits into themes...")
    themes_result = _classify_commits(client, model, commits, verbose)
    theme_name_to_id = _store_themes(conn, commits, themes_result)
    conn.commit()

    # ── 6. Identify cross-cutting files ──────────────────────────────
    logger.info("Identifying cross-cutting files...")
    _compute_cross_cutting(conn, theme_name_to_id)
    conn.commit()

    logger.info("Phase 1 (Inventory) complete.")


def _classify_commits(
    client: anthropic.Anthropic,
    model: str,
    commits: list[Commit],
    verbose: bool,
) -> dict:
    """Call AI to classify commits into themes. Handles batching for large branches."""
    # Build commit descriptions
    commit_descriptions: list[str] = []
    for c in commits:
        file_list = ", ".join(
            f"{f.path} (+{f.insertions}/-{f.deletions})" for f in c.files
        ) or "(no files)"
        commit_descriptions.append(
            f"SHA: {c.sha}\nSubject: {c.subject}\nFiles: {file_list}"
        )

    # Batch if needed
    if len(commits) > _BATCH_SIZE:
        return _classify_batched(client, model, commit_descriptions, verbose)

    user_content = (
        "Here are all commits on this branch (oldest first):\n\n"
        + "\n\n".join(commit_descriptions)
        + "\n\nClassify every commit into themes. Every SHA listed above "
        "must appear in exactly one theme."
    )

    if verbose:
        logger.info(f"AI call: classify {len(commits)} commits")

    return ai.classify_commits(client, model, user_content)


def _classify_batched(
    client: anthropic.Anthropic,
    model: str,
    commit_descriptions: list[str],
    verbose: bool,
) -> dict:
    """Classify commits in batches, accumulating themes across batches."""
    all_themes: dict[str, dict] = {}  # name -> {description, commit_shas, confidence}

    batches = ai.batch_if_needed(commit_descriptions, max_chars=120_000)
    for i, batch in enumerate(batches):
        existing = list(all_themes.keys())
        existing_hint = ""
        if existing:
            existing_hint = (
                f"\n\nExisting themes from previous batches: {', '.join(existing)}. "
                "Classify into these themes if they fit, or create new themes if needed."
            )

        user_content = (
            f"Batch {i + 1} of {len(batches)}. "
            "Here are commits on this branch (oldest first):\n\n"
            + "\n\n".join(batch)
            + "\n\nClassify every commit into themes. Every SHA must appear "
            "in exactly one theme."
            + existing_hint
        )

        if verbose:
            logger.info(
                f"AI call: classify batch {i + 1}/{len(batches)} "
                f"({len(batch)} commits)"
            )

        result = ai.classify_commits(client, model, user_content)

        for theme in result.get("themes", []):
            name = theme["name"]
            if name in all_themes:
                all_themes[name]["commit_shas"].extend(theme["commit_shas"])
                all_themes[name]["confidence"] = min(
                    all_themes[name]["confidence"],
                    theme.get("confidence", 1.0),
                )
            else:
                all_themes[name] = {
                    "description": theme.get("description", ""),
                    "commit_shas": list(theme.get("commit_shas", [])),
                    "confidence": theme.get("confidence", 1.0),
                }

    # Rebuild into the standard response format
    return {
        "themes": [
            {
                "name": name,
                "description": data["description"],
                "commit_shas": data["commit_shas"],
                "confidence": data["confidence"],
            }
            for name, data in all_themes.items()
        ]
    }


def _store_themes(
    conn: sqlite3.Connection,
    commits: list[Commit],
    themes_result: dict,
) -> dict[str, int]:
    """Store themes and commit-theme mappings in the database.

    Returns a mapping of theme_name -> theme_id.
    """
    # Build a lookup from SHA to commit for computing stats
    sha_to_commit: dict[str, Commit] = {c.sha: c for c in commits}
    # Track all classified SHAs to find stragglers
    classified_shas: set[str] = set()

    theme_name_to_id: dict[str, int] = {}

    for theme_data in themes_result.get("themes", []):
        name: str = theme_data["name"]
        description: str = theme_data.get("description", "")
        shas: list[str] = theme_data.get("commit_shas", [])
        confidence: float = theme_data.get("confidence", 1.0)

        # Filter to only valid SHAs
        valid_shas = [s for s in shas if s in sha_to_commit]
        if not valid_shas:
            logger.warning(f"Theme '{name}' has no valid commits, skipping")
            continue

        # Compute theme stats
        theme_files: set[str] = set()
        total_ins = 0
        total_del = 0
        for sha in valid_shas:
            c = sha_to_commit[sha]
            for f in c.files:
                theme_files.add(f.path)
                total_ins += f.insertions
                total_del += f.deletions

        theme = Theme(
            theme_id=0,  # will be set by DB
            name=name,
            description=description,
            commit_count=len(valid_shas),
            file_count=len(theme_files),
            net_lines=total_ins - total_del,
        )
        theme_id = db.insert_theme(conn, theme)
        theme_name_to_id[name] = theme_id

        for sha in valid_shas:
            db.insert_commit_theme(conn, sha, theme_id, confidence)
            classified_shas.add(sha)

    # Check for unclassified commits
    all_shas = {c.sha for c in commits}
    unclassified = all_shas - classified_shas
    if unclassified:
        logger.warning(
            f"{len(unclassified)} commits were not classified: "
            f"{', '.join(sorted(unclassified)[:5])}..."
        )
        # Assign to a catch-all "uncategorized" theme
        uncategorized_files: set[str] = set()
        total_ins = 0
        total_del = 0
        for sha in unclassified:
            c = sha_to_commit[sha]
            for f in c.files:
                uncategorized_files.add(f.path)
                total_ins += f.insertions
                total_del += f.deletions

        theme = Theme(
            theme_id=0,
            name="uncategorized",
            description="Commits not classified into any theme",
            commit_count=len(unclassified),
            file_count=len(uncategorized_files),
            net_lines=total_ins - total_del,
        )
        theme_id = db.insert_theme(conn, theme)
        theme_name_to_id["uncategorized"] = theme_id
        for sha in unclassified:
            db.insert_commit_theme(conn, sha, theme_id, 0.0)

    return theme_name_to_id


def _compute_cross_cutting(
    conn: sqlite3.Connection,
    theme_name_to_id: dict[str, int],
) -> None:
    """Identify files touched by commits from multiple themes.

    A file is cross-cutting if it appears in commit_files for commits
    belonging to more than one theme.
    """
    # Query: for each file, which themes' commits touch it, and how many
    rows = conn.execute(
        """
        SELECT cf.file_path, ct.theme_id, COUNT(*) as cnt
        FROM commit_files cf
        JOIN commit_themes ct ON cf.sha = ct.sha
        GROUP BY cf.file_path, ct.theme_id
        """
    ).fetchall()

    # Group by file
    file_themes: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for r in rows:
        file_themes[r["file_path"]].append((r["theme_id"], r["cnt"]))

    # Only keep files touched by multiple themes
    for file_path, theme_counts in file_themes.items():
        if len(theme_counts) > 1:
            for theme_id, count in theme_counts:
                db.insert_cross_cutting(conn, file_path, theme_id, count)
