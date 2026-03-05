"""Phase 5: Report — generate markdown summary from the database.

Reads all tables from DB. Writes a markdown file. No AI calls.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from splitpr_00 import db

logger = logging.getLogger(__name__)


def generate_report(
    conn: sqlite3.Connection,
    output_path: Path,
) -> None:
    """Generate the markdown report from the database."""
    sections: list[str] = []

    sections.append(_run_summary(conn))
    sections.append(_theme_inventory(conn))
    sections.append(_cross_cutting_section(conn))
    sections.append(_dependency_dag(conn))
    sections.append(_partition_table(conn))
    sections.append(_completeness_check(conn))
    sections.append(_tasks_by_pr(conn))

    report = "\n\n".join(sections) + "\n"
    output_path.write_text(report)

    logger.info(f"Report written to {output_path}")


def _run_summary(conn: sqlite3.Connection) -> str:
    """Run Summary section."""
    meta = db.get_all_metadata(conn)
    lines = [
        "# Split PR Report",
        "",
        "## Run Summary",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Source branch | `{meta.get('source_branch', 'unknown')}` |",
        f"| Base branch | `{meta.get('base_branch', 'unknown')}` |",
        f"| Merge base | `{meta.get('merge_base_sha', 'unknown')[:12]}` |",
        f"| Total commits | {meta.get('total_commits', '0')} |",
        f"| Total files | {meta.get('total_files', '0')} |",
        f"| Insertions | +{meta.get('total_insertions', '0')} |",
        f"| Deletions | -{meta.get('total_deletions', '0')} |",
        f"| Model | `{meta.get('model', 'unknown')}` |",
        f"| Timestamp | {meta.get('run_timestamp', 'unknown')} |",
        f"| Script version | {meta.get('script_version', 'unknown')} |",
    ]
    return "\n".join(lines)


def _theme_inventory(conn: sqlite3.Connection) -> str:
    """Theme Inventory table."""
    themes = db.get_all_themes(conn)
    if not themes:
        return "## Theme Inventory\n\nNo themes identified."

    lines = [
        "## Theme Inventory",
        "",
        "| Theme | Commits | Files | Net Lines | Description |",
        "|-------|---------|-------|-----------|-------------|",
    ]
    total_commits = 0
    total_files = 0
    total_lines = 0
    for t in themes:
        lines.append(
            f"| {t.name} | {t.commit_count} | {t.file_count} | "
            f"{_signed(t.net_lines)} | {t.description} |"
        )
        total_commits += t.commit_count
        total_files += t.file_count
        total_lines += t.net_lines
    lines.append(
        f"| **TOTAL** | **{total_commits}** | **{total_files}** | "
        f"**{_signed(total_lines)}** | |"
    )
    return "\n".join(lines)


def _cross_cutting_section(conn: sqlite3.Connection) -> str:
    """Cross-Cutting Files table."""
    cross_cutting = db.get_cross_cutting_files(conn)
    if not cross_cutting:
        return "## Cross-Cutting Files\n\nNo cross-cutting files."

    themes = db.get_all_themes(conn)
    theme_id_to_name = {t.theme_id: t.name for t in themes}

    # Get resolutions from file_assignments
    assignments = db.get_all_file_assignments(conn)
    file_to_assignment: dict[str, dict] = {}
    for a in assignments:
        if a["file_path"] in cross_cutting:
            file_to_assignment[a["file_path"]] = a

    lines = [
        "## Cross-Cutting Files",
        "",
        "| File | Themes | Assigned To | Strategy |",
        "|------|--------|-------------|----------|",
    ]
    for file_path, theme_ids in sorted(cross_cutting.items()):
        theme_names = [theme_id_to_name.get(tid, "?") for tid in theme_ids]
        assignment = file_to_assignment.get(file_path, {})

        # Find which PR it was assigned to
        assigned_pr_id = assignment.get("pr_id")
        assigned_to = "?"
        if assigned_pr_id:
            prs = db.get_all_prs(conn)
            for pr in prs:
                if pr.pr_id == assigned_pr_id and pr.theme_id:
                    assigned_to = theme_id_to_name.get(pr.theme_id, "?")

        strategy = assignment.get("strategy", "?")
        lines.append(
            f"| `{file_path}` | {', '.join(theme_names)} | "
            f"{assigned_to} | {strategy} |"
        )
    return "\n".join(lines)


def _dependency_dag(conn: sqlite3.Connection) -> str:
    """Dependency DAG table and ASCII tree."""
    prs = db.get_all_prs(conn)
    all_deps = db.get_all_pr_dependencies(conn)
    themes = db.get_all_themes(conn)
    theme_id_to_name = {t.theme_id: t.name for t in themes}

    if not prs:
        return "## Dependency DAG\n\nNo PRs created."

    pr_id_to_name: dict[int, str] = {}
    for pr in prs:
        name = theme_id_to_name.get(pr.theme_id, pr.branch_name) if pr.theme_id else pr.branch_name
        pr_id_to_name[pr.pr_id] = name

    # Table
    lines = [
        "## Dependency DAG",
        "",
        "| PR | Theme | Depends On | Merge Order |",
        "|----|-------|------------|-------------|",
    ]
    for pr in prs:
        name = pr_id_to_name.get(pr.pr_id, "?")
        deps = [
            d for d in all_deps if d["pr_id"] == pr.pr_id
        ]
        dep_names = [pr_id_to_name.get(d["depends_on"], "?") for d in deps]
        dep_str = ", ".join(dep_names) if dep_names else "(none)"
        order_label = _ordinal_label(pr.merge_order)
        lines.append(f"| {pr.pr_id} | {name} | {dep_str} | {order_label} |")

    # ASCII tree
    lines.append("")
    lines.append("```")
    lines.extend(_ascii_tree(prs, all_deps, pr_id_to_name))
    lines.append("```")

    return "\n".join(lines)


def _ascii_tree(
    prs: list,
    all_deps: list[dict],
    pr_id_to_name: dict[int, str],
) -> list[str]:
    """Build a simple ASCII dependency tree."""
    # Find roots (PRs with no dependencies)
    all_pr_ids = {pr.pr_id for pr in prs}
    has_deps = {d["pr_id"] for d in all_deps}
    roots = [pr for pr in prs if pr.pr_id not in has_deps]

    # Build children map (reverse of depends_on)
    children: dict[int, list[int]] = {pr.pr_id: [] for pr in prs}
    for d in all_deps:
        dep_on = d["depends_on"]
        pr_id = d["pr_id"]
        if dep_on in children:
            children[dep_on].append(pr_id)

    lines: list[str] = []

    def _render(pr_id: int, prefix: str, is_last: bool) -> None:
        connector = "└── " if is_last else "├── "
        name = pr_id_to_name.get(pr_id, "?")
        lines.append(f"{prefix}{connector}{pr_id}:{name}")
        child_prefix = prefix + ("    " if is_last else "│   ")
        kids = sorted(children.get(pr_id, []))
        for i, child_id in enumerate(kids):
            _render(child_id, child_prefix, i == len(kids) - 1)

    for i, root in enumerate(roots):
        if i == 0:
            name = pr_id_to_name.get(root.pr_id, "?")
            lines.append(f"{root.pr_id}:{name}")
            kids = sorted(children.get(root.pr_id, []))
            for j, child_id in enumerate(kids):
                _render(child_id, "", j == len(kids) - 1)
        else:
            lines.append("")
            _render(root.pr_id, "", True)

    return lines


def _partition_table(conn: sqlite3.Connection) -> str:
    """Partition Table section."""
    prs = db.get_all_prs(conn)
    themes = db.get_all_themes(conn)
    theme_id_to_name = {t.theme_id: t.name for t in themes}

    if not prs:
        return "## Partition Table\n\nNo partitions."

    lines = [
        "## Partition Table",
        "",
        "| PR | Branch | Theme | Files | Net Lines | Cherry-Picks |",
        "|----|--------|-------|-------|-----------|--------------|",
    ]
    for pr in prs:
        name = theme_id_to_name.get(pr.theme_id, "—") if pr.theme_id else "—"
        cherry_picks = db.get_cherry_picks_for_pr(conn, pr.pr_id)
        clean_count = sum(1 for cp in cherry_picks if cp["is_clean"])
        cp_str = f"{clean_count} clean / {len(cherry_picks)} total"

        lines.append(
            f"| {pr.pr_id} | `{pr.branch_name}` | {name} | "
            f"{pr.file_count} | {_signed(pr.net_lines)} | {cp_str} |"
        )

    return "\n".join(lines)


def _completeness_check(conn: sqlite3.Connection) -> str:
    """Completeness Check section."""
    total_changed = len(db.get_all_changed_files(conn))
    total_assigned = conn.execute(
        "SELECT COUNT(DISTINCT file_path) FROM file_assignments"
    ).fetchone()[0]
    unassigned = db.get_unassigned_files(conn)
    duplicates = db.get_duplicate_assignments(conn)

    lines = [
        "## Completeness Check",
        "",
        "```",
        f"Original files:  {total_changed}",
        f"Assigned files:  {total_assigned}",
        f"Unassigned:      {len(unassigned)}",
        f"Duplicates:      {len(duplicates)}",
        "```",
    ]

    if unassigned:
        lines.append(f"\nUnassigned files: {', '.join(unassigned[:20])}")
    if duplicates:
        lines.append(f"\nDuplicate files: {', '.join(duplicates[:20])}")

    return "\n".join(lines)


def _tasks_by_pr(conn: sqlite3.Connection) -> str:
    """Tasks by PR section."""
    prs = db.get_all_prs(conn)
    themes = db.get_all_themes(conn)
    theme_id_to_name = {t.theme_id: t.name for t in themes}

    if not prs:
        return "## Tasks\n\nNo tasks generated."

    sections: list[str] = ["## Tasks"]

    for pr in prs:
        theme_name = theme_id_to_name.get(pr.theme_id, "—") if pr.theme_id else "—"
        deps = db.get_pr_dependencies(conn, pr.pr_id)

        dep_strs: list[str] = []
        for d in deps:
            dep_pr = conn.execute(
                "SELECT branch_name FROM prs WHERE pr_id = ?",
                (d["depends_on"],),
            ).fetchone()
            if dep_pr:
                dep_strs.append(f"`{dep_pr['branch_name']}`")

        header = f"\n### PR {pr.pr_id}: {pr.branch_name} ({theme_name})"
        dep_line = f"Depends on: {', '.join(dep_strs)}" if dep_strs else "Depends on: (none)"
        base_line = f"Base: `{pr.base_branch}`"

        sections.append(header)
        sections.append(f"{dep_line} | {base_line}")
        sections.append("")

        tasks = db.get_tasks_for_pr(conn, pr.pr_id)
        if not tasks:
            sections.append("_No tasks generated._")
            continue

        for task in tasks:
            sections.append(f"**{task.ordinal}. {task.subject}** [{task.task_type}]")
            sections.append(f"   {task.description}")
            if task.acceptance:
                sections.append(f"   Acceptance: {task.acceptance}")
            if task.recovery_cmds:
                cmds = task.recovery_cmds.split("\n")[:3]
                sections.append("   Recovery:")
                for cmd in cmds:
                    sections.append(f"   ```{cmd}```")
            sections.append("")

    return "\n".join(sections)


def _signed(n: int) -> str:
    """Format a number with +/- sign."""
    return f"+{n}" if n >= 0 else str(n)


def _ordinal_label(n: int) -> str:
    """Convert merge order number to a label."""
    suffixes = {1: "st", 2: "nd", 3: "rd"}
    suffix = suffixes.get(n % 10, "th") if n % 100 not in (11, 12, 13) else "th"
    return f"{n}{suffix}"
