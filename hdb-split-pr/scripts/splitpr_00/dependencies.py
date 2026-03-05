"""Phase 2: Dependency Analysis — DAG construction, cycle detection, merge ordering.

Reads: themes, commit_files, cross_cutting_files from DB + git diffs.
Writes: prs, pr_dependencies, cherry_pick_candidates.
"""

from __future__ import annotations

import logging
import sqlite3
from collections import defaultdict, deque

import anthropic

from splitpr_00 import ai
from splitpr_00 import db
from splitpr_00 import git_ops
from splitpr_00.models import PR, Theme

logger = logging.getLogger(__name__)


def run_dependency_analysis(
    conn: sqlite3.Connection,
    client: anthropic.Anthropic,
    model: str,
    verbose: bool = False,
) -> None:
    """Execute Phase 2: Dependency Analysis.

    1. Get themes and their file lists
    2. Gather diffs for cross-cutting files and files with potential imports
    3. Call AI to identify dependency edges
    4. Build DAG and detect cycles
    5. Compute topological order
    6. Create PR records with merge ordering
    7. Populate cherry-pick candidates
    """
    base_branch = db.get_metadata(conn, "base_branch")
    source_branch = db.get_metadata(conn, "source_branch")
    themes = db.get_all_themes(conn)

    if len(themes) <= 1:
        logger.info("Single theme — no dependency analysis needed.")
        _create_single_pr(conn, themes, base_branch)
        _populate_cherry_picks(conn)
        conn.commit()
        logger.info("Phase 2 (Dependencies) complete.")
        return

    # ── 1. Build theme file lists ────────────────────────────────────
    theme_files: dict[str, list[str]] = {}
    theme_name_to_id: dict[str, int] = {}
    for theme in themes:
        shas = db.get_commits_for_theme(conn, theme.theme_id)
        files: set[str] = set()
        for sha in shas:
            files.update(db.get_commit_file_paths(conn, sha))
        theme_files[theme.name] = sorted(files)
        theme_name_to_id[theme.name] = theme.theme_id

    # ── 2. Gather diffs for analysis ─────────────────────────────────
    cross_cutting = db.get_cross_cutting_files(conn)
    files_to_diff: set[str] = set(cross_cutting.keys())
    # Also include files that might have imports (common code extensions)
    import_extensions = {".py", ".ts", ".js", ".go", ".rs", ".java", ".rb"}
    for file_list in theme_files.values():
        for f in file_list:
            if any(f.endswith(ext) for ext in import_extensions):
                files_to_diff.add(f)

    # Limit to avoid overwhelming the AI prompt
    diff_texts: dict[str, str] = {}
    total_diff_chars = 0
    for file_path in sorted(files_to_diff):
        if total_diff_chars > 100_000:
            break
        try:
            diff = git_ops.get_file_diff(base_branch, file_path, max_lines=200)
            if diff:
                diff_texts[file_path] = diff
                total_diff_chars += len(diff)
        except git_ops.GitError:
            continue

    # ── 3. Call AI for dependency analysis ────────────────────────────
    logger.info("Analyzing dependencies between themes...")
    analysis_text = _build_dependency_prompt(themes, theme_files, diff_texts)

    if verbose:
        logger.info(
            f"AI call: analyze dependencies for {len(themes)} themes, "
            f"{len(diff_texts)} file diffs"
        )

    result = ai.analyze_dependencies(client, model, analysis_text)
    deps = result.get("dependencies", [])

    # Validate: only keep edges where both themes exist
    valid_deps: list[dict] = []
    for d in deps:
        if d["theme"] in theme_name_to_id and d["depends_on"] in theme_name_to_id:
            valid_deps.append(d)
        else:
            logger.warning(
                f"Skipping invalid dependency: {d['theme']} -> {d['depends_on']}"
            )

    # ── 4. Build DAG and detect cycles ───────────────────────────────
    theme_names = [t.name for t in themes]
    edges = [(d["theme"], d["depends_on"]) for d in valid_deps]

    order = topological_sort(theme_names, edges)
    if order is None:
        logger.warning("Cycle detected in dependency graph, merging cyclic themes...")
        theme_names, edges, valid_deps, themes = _resolve_cycles(
            conn, theme_names, edges, valid_deps, themes, theme_name_to_id
        )
        order = topological_sort(theme_names, edges)
        if order is None:
            raise RuntimeError(
                "Could not resolve dependency cycles after merging"
            )
        # Rebuild name-to-id map
        theme_name_to_id = {t.name: t.theme_id for t in themes}

    if verbose:
        logger.info(f"Merge order: {' → '.join(order)}")

    # ── 5. Create PR records ─────────────────────────────────────────
    logger.info("Creating PR records...")
    _create_prs(conn, themes, order, valid_deps, base_branch, theme_name_to_id)
    conn.commit()

    # ── 6. Populate cherry-pick candidates ───────────────────────────
    _populate_cherry_picks(conn)
    conn.commit()

    logger.info("Phase 2 (Dependencies) complete.")


def topological_sort(
    nodes: list[str], edges: list[tuple[str, str]]
) -> list[str] | None:
    """Topological sort using Kahn's algorithm.

    edges: [(dependent, dependency)] meaning dependent depends on dependency.
    Returns sorted list (dependencies first) or None if cycle exists.
    """
    in_degree: dict[str, int] = {n: 0 for n in nodes}
    adj: dict[str, list[str]] = {n: [] for n in nodes}

    for dependent, dependency in edges:
        if dependent in adj and dependency in adj:
            adj[dependency].append(dependent)
            in_degree[dependent] += 1

    queue = deque(n for n in nodes if in_degree[n] == 0)
    result: list[str] = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(nodes):
        return None
    return result


def _resolve_cycles(
    conn: sqlite3.Connection,
    theme_names: list[str],
    edges: list[tuple[str, str]],
    valid_deps: list[dict],
    themes: list[Theme],
    theme_name_to_id: dict[str, int],
) -> tuple[list[str], list[tuple[str, str]], list[dict], list[Theme]]:
    """Merge cyclic themes until the graph is acyclic.

    Strategy: find strongly connected components, merge each into one theme.
    """
    sccs = _find_sccs(theme_names, edges)
    cyclic_groups = [scc for scc in sccs if len(scc) > 1]

    if not cyclic_groups:
        return theme_names, edges, valid_deps, themes

    for group in cyclic_groups:
        merged_name = "+".join(sorted(group))
        logger.info(f"Merging cyclic themes: {group} → '{merged_name}'")
        db.set_metadata(
            conn,
            f"cycle_merge_{merged_name}",
            f"Merged themes {group} due to cycle",
        )

    # For simplicity, merge the first cyclic group and recurse
    group = cyclic_groups[0]
    merged_name = "+".join(sorted(group))

    # Remove the old themes from the list, add the merged one
    new_theme_names = [n for n in theme_names if n not in group]
    new_theme_names.append(merged_name)

    # Update edges: replace any group member with the merged name, remove self-loops
    new_edges: list[tuple[str, str]] = []
    new_deps: list[dict] = []
    for d in valid_deps:
        src = merged_name if d["theme"] in group else d["theme"]
        tgt = merged_name if d["depends_on"] in group else d["depends_on"]
        if src != tgt:
            new_edges.append((src, tgt))
            new_deps.append(
                {"theme": src, "depends_on": tgt, "reason": d["reason"]}
            )

    # Create a synthetic merged theme in memory
    merged_theme = Theme(
        theme_id=-1,  # will be assigned on insert
        name=merged_name,
        description=f"Merged from cyclic themes: {', '.join(group)}",
        commit_count=sum(
            t.commit_count for t in themes if t.name in group
        ),
        file_count=sum(t.file_count for t in themes if t.name in group),
        net_lines=sum(t.net_lines for t in themes if t.name in group),
    )
    # Insert into DB
    merged_id = db.insert_theme(conn, merged_theme)

    # Reassign commits from old themes to merged theme
    for old_name in group:
        old_id = theme_name_to_id.get(old_name)
        if old_id:
            shas = db.get_commits_for_theme(conn, old_id)
            for sha in shas:
                db.insert_commit_theme(conn, sha, merged_id, 0.5)

    new_themes = [t for t in themes if t.name not in group]
    merged_theme.theme_id = merged_id
    new_themes.append(merged_theme)

    # Recurse if more cycles exist
    return _resolve_cycles(
        conn,
        new_theme_names,
        new_edges,
        new_deps,
        new_themes,
        {t.name: t.theme_id for t in new_themes},
    )


def _find_sccs(
    nodes: list[str], edges: list[tuple[str, str]]
) -> list[list[str]]:
    """Find strongly connected components using Tarjan's algorithm."""
    index_counter = [0]
    stack: list[str] = []
    lowlink: dict[str, int] = {}
    index: dict[str, int] = {}
    on_stack: dict[str, bool] = {}
    result: list[list[str]] = []

    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for dependent, dependency in edges:
        if dependency in adj:
            adj[dependency].append(dependent)

    def strongconnect(v: str) -> None:
        index[v] = index_counter[0]
        lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack[v] = True

        for w in adj.get(v, []):
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif on_stack.get(w, False):
                lowlink[v] = min(lowlink[v], index[w])

        if lowlink[v] == index[v]:
            component: list[str] = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                component.append(w)
                if w == v:
                    break
            result.append(component)

    for v in nodes:
        if v not in index:
            strongconnect(v)

    return result


def _create_single_pr(
    conn: sqlite3.Connection,
    themes: list[Theme],
    base_branch: str,
) -> None:
    """Create a single PR when there's only one theme."""
    theme = themes[0] if themes else None
    source = db.get_metadata(conn, "source_branch") or "feature"
    pr = PR(
        pr_id=0,
        theme_id=theme.theme_id if theme else None,
        branch_name=source,
        title=theme.description if theme else "All changes",
        merge_order=1,
        base_branch=base_branch,
        description=theme.description if theme else "",
        file_count=theme.file_count if theme else 0,
        net_lines=theme.net_lines if theme else 0,
    )
    db.insert_pr(conn, pr)


def _create_prs(
    conn: sqlite3.Connection,
    themes: list[Theme],
    order: list[str],
    valid_deps: list[dict],
    base_branch: str,
    theme_name_to_id: dict[str, int],
) -> None:
    """Create PR records in topological order with correct base branches."""
    source = db.get_metadata(conn, "source_branch") or "feature"

    # Build dependency map for determining base branches
    dep_map: dict[str, list[str]] = defaultdict(list)
    for d in valid_deps:
        dep_map[d["theme"]].append(d["depends_on"])

    # Map theme name to PR for linking dependencies
    theme_to_pr_id: dict[str, int] = {}
    theme_to_branch: dict[str, str] = {}

    for merge_order, theme_name in enumerate(order, start=1):
        theme_id = theme_name_to_id.get(theme_name)
        theme = next((t for t in themes if t.name == theme_name), None)

        # Determine base: if this theme depends on others, base on the
        # latest dependency's branch. Otherwise use the main base.
        deps_of_theme = dep_map.get(theme_name, [])
        if deps_of_theme:
            # Base on the last dependency in the order
            latest_dep = max(deps_of_theme, key=lambda d: order.index(d))
            pr_base = theme_to_branch.get(latest_dep, base_branch)
        else:
            pr_base = base_branch

        branch_name = f"split/{source}/{theme_name}"
        theme_to_branch[theme_name] = branch_name

        pr = PR(
            pr_id=0,
            theme_id=theme_id,
            branch_name=branch_name,
            title=theme.description if theme else theme_name,
            merge_order=merge_order,
            base_branch=pr_base,
            description=theme.description if theme else "",
            file_count=theme.file_count if theme else 0,
            net_lines=theme.net_lines if theme else 0,
        )
        pr_id = db.insert_pr(conn, pr)
        theme_to_pr_id[theme_name] = pr_id

    # Insert dependency edges between PRs
    for d in valid_deps:
        pr_id = theme_to_pr_id.get(d["theme"])
        dep_pr_id = theme_to_pr_id.get(d["depends_on"])
        if pr_id and dep_pr_id:
            db.insert_pr_dependency(conn, pr_id, dep_pr_id, d.get("reason", ""))


def _populate_cherry_picks(conn: sqlite3.Connection) -> None:
    """For each PR, identify commits that are cherry-pick candidates.

    A commit is a cherry-pick candidate for a PR if its theme matches.
    It is 'clean' if all files in the commit belong to that PR's theme.
    """
    prs = db.get_all_prs(conn)
    themes = db.get_all_themes(conn)
    theme_id_to_name = {t.theme_id: t.name for t in themes}

    for pr in prs:
        if pr.theme_id is None:
            continue

        # Get all commits for this theme
        shas = db.get_commits_for_theme(conn, pr.theme_id)

        # Get all files owned by this theme
        theme_files: set[str] = set()
        for sha in shas:
            theme_files.update(db.get_commit_file_paths(conn, sha))

        for sha in shas:
            commit_files = set(db.get_commit_file_paths(conn, sha))
            # A commit is clean if all its files belong to this theme's file set
            # (This is approximate before partition; will be refined after Phase 3)
            is_clean = commit_files.issubset(theme_files)
            # Check if any commit file is cross-cutting
            cross_cutting = db.get_cross_cutting_files(conn)
            if any(f in cross_cutting for f in commit_files):
                is_clean = False
            db.insert_cherry_pick(conn, pr.pr_id, sha, is_clean)


def _build_dependency_prompt(
    themes: list[Theme],
    theme_files: dict[str, list[str]],
    diff_texts: dict[str, str],
) -> str:
    """Build the user prompt for dependency analysis."""
    parts: list[str] = []
    parts.append("Here are the themes and their files:\n")

    for theme in themes:
        files = theme_files.get(theme.name, [])
        file_list = "\n".join(f"  - {f}" for f in files[:30])
        if len(files) > 30:
            file_list += f"\n  ... and {len(files) - 30} more files"
        parts.append(f"### Theme: {theme.name}\n{theme.description}\nFiles:\n{file_list}\n")

    if diff_texts:
        parts.append("\n---\nRelevant file diffs (for import/dependency analysis):\n")
        for file_path, diff in sorted(diff_texts.items()):
            parts.append(f"#### {file_path}\n```diff\n{diff}\n```\n")

    parts.append(
        "\nAnalyze the themes above and identify any dependencies between them. "
        "A theme depends on another if it uses code introduced by that theme."
    )

    return "\n".join(parts)
