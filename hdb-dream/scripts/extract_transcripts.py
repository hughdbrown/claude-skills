#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["click>=8.1"]
# ///
"""Digest recent Claude Code session transcripts for the /dream skill.

Scans ~/.claude/projects/**/*.jsonl for files modified within the window,
then prints user messages (and session summaries) newer than the cutoff,
grouped by project. Tool results, system reminders, command echoes, and meta
entries are skipped so the digest stays small enough to review in one pass.

    extract_transcripts.py                 # last 24 hours
    extract_transcripts.py --hours 48
    extract_transcripts.py --max-chars 200 --max-messages 20
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import click

SKIP_PREFIXES = ("<", "Caveat:")


def message_text(obj: dict) -> str | None:
    """Return the plain user text of a transcript entry, or None to skip it."""
    if obj.get("isMeta"):
        return None
    if obj.get("type") == "summary":
        summary = obj.get("summary", "").strip()
        return f"[session summary] {summary}" if summary else None
    if obj.get("type") != "user":
        return None
    content = obj.get("message", {}).get("content")
    if isinstance(content, str):
        parts = [content]
    elif isinstance(content, list):
        parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
    else:
        return None
    text = "\n".join(p for p in parts if p).strip()
    if not text or text.startswith(SKIP_PREFIXES):
        return None
    return text


def entry_time(obj: dict) -> datetime | None:
    stamp = obj.get("timestamp")
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None


@click.command()
@click.option("--hours", default=24.0, show_default=True, help="Review window in hours.")
@click.option(
    "--projects-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path.home() / ".claude" / "projects",
    show_default=True,
)
@click.option("--max-chars", default=400, show_default=True, help="Truncate each message to this length.")
@click.option("--max-messages", default=40, show_default=True, help="Cap messages per session.")
def main(hours: float, projects_dir: Path, max_chars: int, max_messages: int) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    sessions_by_project: dict[str, list[tuple[Path, list[str]]]] = {}

    for jsonl in sorted(projects_dir.glob("*/*.jsonl")):
        mtime = datetime.fromtimestamp(jsonl.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            continue
        quotes: list[str] = []
        with jsonl.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                stamp = entry_time(obj)
                if stamp is not None and stamp < cutoff:
                    continue
                text = message_text(obj)
                if text is None:
                    continue
                if len(text) > max_chars:
                    text = text[:max_chars] + " [...]"
                quotes.append(text)
        if quotes:
            over = len(quotes) - max_messages
            quotes = quotes[:max_messages]
            if over > 0:
                quotes.append(f"[... {over} more messages omitted]")
            sessions_by_project.setdefault(jsonl.parent.name, []).append((jsonl, quotes))

    if not sessions_by_project:
        click.echo(f"No transcript activity in the last {hours:g} hours.")
        return

    for project, sessions in sorted(sessions_by_project.items()):
        click.echo(f"\n## Project: {project}")
        memory_index = projects_dir / project / "memory" / "MEMORY.md"
        click.echo(f"memory index: {memory_index if memory_index.exists() else '(none)'}")
        for path, quotes in sessions:
            click.echo(f"\n### Session: {path.name}")
            for quote in quotes:
                block = quote.replace("\n", "\n  ")
                click.echo(f"- {block}")


if __name__ == "__main__":
    main()
