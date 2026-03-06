"""SQLite schema, connection management, and all read/write helpers.

The database is the handoff artifact to the next script. Every table is
designed so the downstream extractor can work without re-querying git
history or making additional AI calls.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from splitpr_common.models import Commit, FileChange, PR, Task, Theme

_SCHEMA = """
CREATE TABLE IF NOT EXISTS run_metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS commits (
    sha           TEXT PRIMARY KEY,
    ordinal       INTEGER NOT NULL,
    subject       TEXT NOT NULL,
    body          TEXT,
    author        TEXT,
    date          TEXT,
    files_changed INTEGER,
    insertions    INTEGER,
    deletions     INTEGER
);

CREATE TABLE IF NOT EXISTS commit_files (
    sha        TEXT NOT NULL REFERENCES commits(sha),
    file_path  TEXT NOT NULL,
    status     TEXT,
    old_path   TEXT,
    insertions INTEGER,
    deletions  INTEGER,
    PRIMARY KEY (sha, file_path)
);

CREATE TABLE IF NOT EXISTS changed_files (
    file_path  TEXT PRIMARY KEY,
    status     TEXT,
    insertions INTEGER,
    deletions  INTEGER
);

CREATE TABLE IF NOT EXISTS themes (
    theme_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    description  TEXT,
    commit_count INTEGER,
    file_count   INTEGER,
    net_lines    INTEGER
);

CREATE TABLE IF NOT EXISTS commit_themes (
    sha        TEXT NOT NULL REFERENCES commits(sha),
    theme_id   INTEGER NOT NULL REFERENCES themes(theme_id),
    confidence REAL,
    PRIMARY KEY (sha, theme_id)
);

CREATE TABLE IF NOT EXISTS cross_cutting_files (
    file_path    TEXT NOT NULL,
    theme_id     INTEGER NOT NULL REFERENCES themes(theme_id),
    commit_count INTEGER,
    PRIMARY KEY (file_path, theme_id)
);

CREATE TABLE IF NOT EXISTS prs (
    pr_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_id    INTEGER REFERENCES themes(theme_id),
    branch_name TEXT NOT NULL,
    title       TEXT NOT NULL,
    merge_order INTEGER NOT NULL,
    base_branch TEXT NOT NULL,
    description TEXT,
    file_count  INTEGER,
    net_lines   INTEGER
);

CREATE TABLE IF NOT EXISTS pr_dependencies (
    pr_id      INTEGER NOT NULL REFERENCES prs(pr_id),
    depends_on INTEGER NOT NULL REFERENCES prs(pr_id),
    reason     TEXT,
    PRIMARY KEY (pr_id, depends_on),
    CHECK (pr_id != depends_on)
);

CREATE TABLE IF NOT EXISTS file_assignments (
    file_path    TEXT NOT NULL,
    pr_id        INTEGER NOT NULL REFERENCES prs(pr_id),
    strategy     TEXT,
    ai_reasoning TEXT,
    PRIMARY KEY (file_path, pr_id)
);

CREATE TABLE IF NOT EXISTS cherry_pick_candidates (
    pr_id    INTEGER NOT NULL REFERENCES prs(pr_id),
    sha      TEXT NOT NULL REFERENCES commits(sha),
    is_clean BOOLEAN,
    PRIMARY KEY (pr_id, sha)
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    pr_id          INTEGER NOT NULL REFERENCES prs(pr_id),
    ordinal        INTEGER NOT NULL,
    subject        TEXT NOT NULL,
    description    TEXT NOT NULL,
    acceptance     TEXT,
    recovery_cmds  TEXT,
    task_type      TEXT,
    source_commits TEXT,
    source_files   TEXT
);
"""

_TABLES = [
    "run_metadata",
    "commits",
    "commit_files",
    "changed_files",
    "themes",
    "commit_themes",
    "cross_cutting_files",
    "prs",
    "pr_dependencies",
    "file_assignments",
    "cherry_pick_candidates",
    "tasks",
]


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a connection with foreign keys enabled."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.row_factory = sqlite3.Row
    return conn


def initialize(conn: sqlite3.Connection) -> None:
    """Drop all tables and recreate them. Idempotent fresh start."""
    for table in reversed(_TABLES):
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.executescript(_SCHEMA)
    conn.commit()


# ── run_metadata ─────────────────────────────────────────────────────

def set_metadata(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO run_metadata (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()


def get_metadata(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute(
        "SELECT value FROM run_metadata WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else None


def get_all_metadata(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM run_metadata").fetchall()
    return {row["key"]: row["value"] for row in rows}


# ── commits ──────────────────────────────────────────────────────────

def insert_commit(conn: sqlite3.Connection, commit: Commit) -> None:
    conn.execute(
        """INSERT INTO commits
           (sha, ordinal, subject, body, author, date, files_changed, insertions, deletions)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            commit.sha,
            commit.ordinal,
            commit.subject,
            commit.body,
            commit.author,
            commit.date,
            commit.files_changed,
            commit.total_insertions,
            commit.total_deletions,
        ),
    )


def insert_commit_files(
    conn: sqlite3.Connection, sha: str, files: list[FileChange]
) -> None:
    conn.executemany(
        """INSERT INTO commit_files
           (sha, file_path, status, old_path, insertions, deletions)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            (sha, f.path, f.status, f.old_path, f.insertions, f.deletions)
            for f in files
        ],
    )


def get_all_commits(conn: sqlite3.Connection) -> list[Commit]:
    rows = conn.execute(
        "SELECT * FROM commits ORDER BY ordinal"
    ).fetchall()
    return [
        Commit(
            sha=r["sha"],
            ordinal=r["ordinal"],
            subject=r["subject"],
            body=r["body"] or "",
            author=r["author"] or "",
            date=r["date"] or "",
        )
        for r in rows
    ]


def get_commit_file_paths(conn: sqlite3.Connection, sha: str) -> list[str]:
    rows = conn.execute(
        "SELECT file_path FROM commit_files WHERE sha = ?", (sha,)
    ).fetchall()
    return [r["file_path"] for r in rows]


# ── changed_files ────────────────────────────────────────────────────

def insert_changed_files(
    conn: sqlite3.Connection, files: list[FileChange]
) -> None:
    conn.executemany(
        """INSERT INTO changed_files
           (file_path, status, insertions, deletions)
           VALUES (?, ?, ?, ?)""",
        [(f.path, f.status, f.insertions, f.deletions) for f in files],
    )


def get_all_changed_files(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT file_path FROM changed_files ORDER BY file_path"
    ).fetchall()
    return [r["file_path"] for r in rows]


def get_changed_file_stats(
    conn: sqlite3.Connection,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT file_path, status, insertions, deletions FROM changed_files"
    ).fetchall()
    return [dict(r) for r in rows]


# ── themes ───────────────────────────────────────────────────────────

def insert_theme(conn: sqlite3.Connection, theme: Theme) -> int:
    cursor = conn.execute(
        """INSERT INTO themes
           (name, description, commit_count, file_count, net_lines)
           VALUES (?, ?, ?, ?, ?)""",
        (
            theme.name,
            theme.description,
            theme.commit_count,
            theme.file_count,
            theme.net_lines,
        ),
    )
    return cursor.lastrowid


def get_all_themes(conn: sqlite3.Connection) -> list[Theme]:
    rows = conn.execute("SELECT * FROM themes ORDER BY theme_id").fetchall()
    return [
        Theme(
            theme_id=r["theme_id"],
            name=r["name"],
            description=r["description"] or "",
            commit_count=r["commit_count"] or 0,
            file_count=r["file_count"] or 0,
            net_lines=r["net_lines"] or 0,
        )
        for r in rows
    ]


def get_theme_by_name(conn: sqlite3.Connection, name: str) -> Theme | None:
    row = conn.execute(
        "SELECT * FROM themes WHERE name = ?", (name,)
    ).fetchone()
    if not row:
        return None
    return Theme(
        theme_id=row["theme_id"],
        name=row["name"],
        description=row["description"] or "",
        commit_count=row["commit_count"] or 0,
        file_count=row["file_count"] or 0,
        net_lines=row["net_lines"] or 0,
    )


# ── commit_themes ────────────────────────────────────────────────────

def insert_commit_theme(
    conn: sqlite3.Connection,
    sha: str,
    theme_id: int,
    confidence: float = 1.0,
) -> None:
    conn.execute(
        """INSERT INTO commit_themes (sha, theme_id, confidence)
           VALUES (?, ?, ?)""",
        (sha, theme_id, confidence),
    )


def get_themes_for_commit(conn: sqlite3.Connection, sha: str) -> list[int]:
    rows = conn.execute(
        "SELECT theme_id FROM commit_themes WHERE sha = ?", (sha,)
    ).fetchall()
    return [r["theme_id"] for r in rows]


def get_commits_for_theme(
    conn: sqlite3.Connection, theme_id: int
) -> list[str]:
    rows = conn.execute(
        "SELECT sha FROM commit_themes WHERE theme_id = ? ORDER BY sha",
        (theme_id,),
    ).fetchall()
    return [r["sha"] for r in rows]


# ── cross_cutting_files ─────────────────────────────────────────────

def insert_cross_cutting(
    conn: sqlite3.Connection,
    file_path: str,
    theme_id: int,
    commit_count: int,
) -> None:
    conn.execute(
        """INSERT INTO cross_cutting_files
           (file_path, theme_id, commit_count)
           VALUES (?, ?, ?)""",
        (file_path, theme_id, commit_count),
    )


def get_cross_cutting_files(
    conn: sqlite3.Connection,
) -> dict[str, list[int]]:
    """Return {file_path: [theme_id, ...]} for all cross-cutting files."""
    rows = conn.execute(
        "SELECT file_path, theme_id FROM cross_cutting_files ORDER BY file_path"
    ).fetchall()
    result: dict[str, list[int]] = {}
    for r in rows:
        result.setdefault(r["file_path"], []).append(r["theme_id"])
    return result


# ── prs ──────────────────────────────────────────────────────────────

def insert_pr(conn: sqlite3.Connection, pr: PR) -> int:
    cursor = conn.execute(
        """INSERT INTO prs
           (theme_id, branch_name, title, merge_order, base_branch,
            description, file_count, net_lines)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            pr.theme_id,
            pr.branch_name,
            pr.title,
            pr.merge_order,
            pr.base_branch,
            pr.description,
            pr.file_count,
            pr.net_lines,
        ),
    )
    return cursor.lastrowid


def get_all_prs(conn: sqlite3.Connection) -> list[PR]:
    rows = conn.execute(
        "SELECT * FROM prs ORDER BY merge_order"
    ).fetchall()
    return [
        PR(
            pr_id=r["pr_id"],
            theme_id=r["theme_id"],
            branch_name=r["branch_name"],
            title=r["title"],
            merge_order=r["merge_order"],
            base_branch=r["base_branch"],
            description=r["description"] or "",
            file_count=r["file_count"] or 0,
            net_lines=r["net_lines"] or 0,
        )
        for r in rows
    ]


def update_pr_stats(
    conn: sqlite3.Connection,
    pr_id: int,
    file_count: int,
    net_lines: int,
) -> None:
    conn.execute(
        "UPDATE prs SET file_count = ?, net_lines = ? WHERE pr_id = ?",
        (file_count, net_lines, pr_id),
    )


# ── pr_dependencies ─────────────────────────────────────────────────

def insert_pr_dependency(
    conn: sqlite3.Connection,
    pr_id: int,
    depends_on: int,
    reason: str = "",
) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO pr_dependencies
           (pr_id, depends_on, reason) VALUES (?, ?, ?)""",
        (pr_id, depends_on, reason),
    )


def get_pr_dependencies(
    conn: sqlite3.Connection, pr_id: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT depends_on, reason FROM pr_dependencies
           WHERE pr_id = ?""",
        (pr_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_pr_dependencies(
    conn: sqlite3.Connection,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT pr_id, depends_on, reason FROM pr_dependencies"
    ).fetchall()
    return [dict(r) for r in rows]


# ── file_assignments ─────────────────────────────────────────────────

def insert_file_assignment(
    conn: sqlite3.Connection,
    file_path: str,
    pr_id: int,
    strategy: str = "unambiguous",
    ai_reasoning: str = "",
) -> None:
    conn.execute(
        """INSERT INTO file_assignments
           (file_path, pr_id, strategy, ai_reasoning)
           VALUES (?, ?, ?, ?)""",
        (file_path, pr_id, strategy, ai_reasoning),
    )


def get_files_for_pr(conn: sqlite3.Connection, pr_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT file_path FROM file_assignments WHERE pr_id = ?",
        (pr_id,),
    ).fetchall()
    return [r["file_path"] for r in rows]


def get_all_file_assignments(
    conn: sqlite3.Connection,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT file_path, pr_id, strategy, ai_reasoning
           FROM file_assignments ORDER BY pr_id, file_path"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_unassigned_files(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """SELECT file_path FROM changed_files
           WHERE file_path NOT IN (SELECT file_path FROM file_assignments)"""
    ).fetchall()
    return [r["file_path"] for r in rows]


def get_duplicate_assignments(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """SELECT file_path FROM file_assignments
           WHERE strategy != 'split_by_hunk'
           GROUP BY file_path
           HAVING COUNT(DISTINCT pr_id) > 1"""
    ).fetchall()
    return [r["file_path"] for r in rows]


# ── cherry_pick_candidates ───────────────────────────────────────────

def insert_cherry_pick(
    conn: sqlite3.Connection,
    pr_id: int,
    sha: str,
    is_clean: bool,
) -> None:
    conn.execute(
        """INSERT INTO cherry_pick_candidates (pr_id, sha, is_clean)
           VALUES (?, ?, ?)""",
        (pr_id, sha, is_clean),
    )


def get_cherry_picks_for_pr(
    conn: sqlite3.Connection, pr_id: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT sha, is_clean FROM cherry_pick_candidates
           WHERE pr_id = ? ORDER BY sha""",
        (pr_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_cherry_picks_for_pr_ordered(
    conn: sqlite3.Connection, pr_id: int
) -> list[dict[str, Any]]:
    """Get cherry-pick candidates in commit ordinal order."""
    rows = conn.execute(
        """SELECT c.sha, c.ordinal, c.subject, cp.is_clean
           FROM cherry_pick_candidates cp
           JOIN commits c ON cp.sha = c.sha
           WHERE cp.pr_id = ?
           ORDER BY c.ordinal""",
        (pr_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_file_statuses(
    conn: sqlite3.Connection,
) -> dict[str, str]:
    """Return {file_path: status} for all changed files."""
    rows = conn.execute(
        "SELECT file_path, status FROM changed_files"
    ).fetchall()
    return {r["file_path"]: r["status"] for r in rows}


# ── tasks ────────────────────────────────────────────────────────────

def insert_task(conn: sqlite3.Connection, task: Task) -> int:
    cursor = conn.execute(
        """INSERT INTO tasks
           (pr_id, ordinal, subject, description, acceptance,
            recovery_cmds, task_type, source_commits, source_files)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            task.pr_id,
            task.ordinal,
            task.subject,
            task.description,
            task.acceptance,
            task.recovery_cmds,
            task.task_type,
            task.source_commits,
            task.source_files,
        ),
    )
    return cursor.lastrowid


def get_tasks_for_pr(conn: sqlite3.Connection, pr_id: int) -> list[Task]:
    rows = conn.execute(
        "SELECT * FROM tasks WHERE pr_id = ? ORDER BY ordinal",
        (pr_id,),
    ).fetchall()
    return [
        Task(
            task_id=r["task_id"],
            pr_id=r["pr_id"],
            ordinal=r["ordinal"],
            subject=r["subject"],
            description=r["description"],
            acceptance=r["acceptance"] or "",
            recovery_cmds=r["recovery_cmds"] or "",
            task_type=r["task_type"] or "",
            source_commits=r["source_commits"] or "",
            source_files=r["source_files"] or "",
        )
        for r in rows
    ]


def get_all_tasks(conn: sqlite3.Connection) -> list[Task]:
    rows = conn.execute(
        "SELECT * FROM tasks ORDER BY pr_id, ordinal"
    ).fetchall()
    return [
        Task(
            task_id=r["task_id"],
            pr_id=r["pr_id"],
            ordinal=r["ordinal"],
            subject=r["subject"],
            description=r["description"],
            acceptance=r["acceptance"] or "",
            recovery_cmds=r["recovery_cmds"] or "",
            task_type=r["task_type"] or "",
            source_commits=r["source_commits"] or "",
            source_files=r["source_files"] or "",
        )
        for r in rows
    ]
