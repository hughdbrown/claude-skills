"""SQLite schema and helpers for logging conflict resolutions.

Every resolution is logged so the user has an audit trail of what was
decided and why.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mergefix.models import Resolution, Strategy

_SCHEMA = """
CREATE TABLE IF NOT EXISTS run_metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resolutions (
    resolution_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path      TEXT NOT NULL,
    block_index    INTEGER NOT NULL,
    total_blocks   INTEGER NOT NULL,
    strategy       TEXT NOT NULL,
    confidence     REAL NOT NULL,
    reasoning      TEXT NOT NULL,
    ours_content   TEXT,
    theirs_content TEXT,
    base_content   TEXT,
    resolved_content TEXT NOT NULL,
    ours_label     TEXT,
    theirs_label   TEXT,
    applied        BOOLEAN NOT NULL DEFAULT 0,
    flagged        BOOLEAN NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skipped_files (
    file_path TEXT PRIMARY KEY,
    reason    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a connection with foreign keys enabled."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.row_factory = sqlite3.Row
    return conn


def initialize(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
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


# ── resolutions ──────────────────────────────────────────────────────


def insert_resolution(
    conn: sqlite3.Connection,
    file_path: str,
    block_index: int,
    total_blocks: int,
    resolution: Resolution,
    ours_content: str,
    theirs_content: str,
    base_content: str | None,
    ours_label: str,
    theirs_label: str,
    applied: bool,
    flagged: bool,
) -> int:
    """Insert a resolution record. Returns the resolution_id."""
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        """INSERT INTO resolutions
           (file_path, block_index, total_blocks, strategy, confidence,
            reasoning, ours_content, theirs_content, base_content,
            resolved_content, ours_label, theirs_label, applied, flagged,
            created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            file_path,
            block_index,
            total_blocks,
            resolution.strategy.value,
            resolution.confidence,
            resolution.reasoning,
            ours_content,
            theirs_content,
            base_content,
            resolution.resolved_content,
            ours_label,
            theirs_label,
            applied,
            flagged,
            now,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_all_resolutions(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM resolutions ORDER BY file_path, block_index"
    ).fetchall()
    return [dict(r) for r in rows]


def get_resolution_summary(conn: sqlite3.Connection) -> dict[str, int]:
    """Return counts by strategy."""
    rows = conn.execute(
        "SELECT strategy, COUNT(*) as cnt FROM resolutions GROUP BY strategy"
    ).fetchall()
    return {row["strategy"]: row["cnt"] for row in rows}


def get_confidence_summary(conn: sqlite3.Connection) -> dict[str, int]:
    """Return counts by confidence band."""
    rows = conn.execute(
        """SELECT
            CASE
                WHEN confidence >= 0.9 THEN 'high'
                WHEN confidence >= 0.7 THEN 'medium'
                ELSE 'low'
            END as band,
            COUNT(*) as cnt
           FROM resolutions
           GROUP BY band"""
    ).fetchall()
    return {row["band"]: row["cnt"] for row in rows}


def count_flagged(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM resolutions WHERE flagged = 1"
    ).fetchone()
    return row["cnt"] if row else 0


def count_applied(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM resolutions WHERE applied = 1"
    ).fetchone()
    return row["cnt"] if row else 0


# ── skipped_files ────────────────────────────────────────────────────


def insert_skipped_file(
    conn: sqlite3.Connection, file_path: str, reason: str
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO skipped_files (file_path, reason, created_at) "
        "VALUES (?, ?, ?)",
        (file_path, reason, now),
    )
    conn.commit()


def get_skipped_files(conn: sqlite3.Connection) -> list[dict[str, str]]:
    rows = conn.execute(
        "SELECT file_path, reason FROM skipped_files ORDER BY file_path"
    ).fetchall()
    return [dict(r) for r in rows]
