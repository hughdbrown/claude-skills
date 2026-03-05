"""Git operations via subprocess.run.

Every git command in the project goes through this module. No other module
calls subprocess directly.

Read-only primitives are imported from splitpr_common.git_ops; this module
adds model-dependent helpers that return FileChange / Commit objects.
"""

from __future__ import annotations

from splitpr_common.git_ops import (  # noqa: F401 — re-exported
    GitError,
    _run,
    detect_base_branch,
    get_current_branch,
    get_diff_stat,
    get_head_rev,
    get_merge_base,
    get_repo_toplevel,
    is_git_repo,
)
from splitpr_00.models import Commit, FileChange


def list_commits(merge_base: str) -> list[Commit]:
    """List all non-merge commits from merge_base to HEAD, oldest first.

    Uses a custom format to parse sha, subject, body, author, date.
    """
    separator = "---COMMIT-SEP---"
    field_sep = "---FIELD-SEP---"
    fmt = f"%H{field_sep}%s{field_sep}%b{field_sep}%an{field_sep}%aI"
    output = _run([
        "git", "log",
        "--no-merges",
        "--reverse",
        f"--format={separator}{fmt}",
        f"{merge_base}..HEAD",
    ])
    if not output:
        return []
    commits: list[Commit] = []
    for ordinal, block in enumerate(output.split(separator), start=0):
        block = block.strip()
        if not block:
            continue
        parts = block.split(field_sep, 4)
        if len(parts) < 5:
            continue
        sha, subject, body, author, date = parts
        commits.append(Commit(
            sha=sha.strip(),
            ordinal=ordinal,
            subject=subject.strip(),
            body=body.strip(),
            author=author.strip(),
            date=date.strip(),
        ))
    # Fix ordinals to be 1-based
    for i, c in enumerate(commits):
        c.ordinal = i + 1
    return commits


def get_commit_files(sha: str) -> list[FileChange]:
    """Get the list of files changed by a specific commit with status."""
    output = _run([
        "git", "show",
        "--name-status",
        "--format=",
        "--diff-filter=ACDMRT",
        sha,
    ])
    return _parse_name_status(output)


def get_changed_files(base: str) -> list[FileChange]:
    """Get all files changed between base and HEAD with status."""
    output = _run([
        "git", "diff",
        "--name-status",
        f"{base}..HEAD",
    ])
    return _parse_name_status(output)


def get_changed_files_numstat(base: str) -> list[FileChange]:
    """Get all files changed between base and HEAD with insertion/deletion counts."""
    output = _run([
        "git", "diff",
        "--numstat",
        f"{base}..HEAD",
    ])
    status_output = _run([
        "git", "diff",
        "--name-status",
        f"{base}..HEAD",
    ])
    status_map: dict[str, str] = {}
    old_path_map: dict[str, str] = {}
    for line in status_output.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            status = parts[0][0]  # First char: A/M/D/R
            file_path = parts[-1]
            status_map[file_path] = status
            if status == "R" and len(parts) >= 3:
                old_path_map[parts[2]] = parts[1]

    files: list[FileChange] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        ins_str, del_str, path = parts[0], parts[1], parts[2]
        insertions = int(ins_str) if ins_str != "-" else 0
        deletions = int(del_str) if del_str != "-" else 0
        files.append(FileChange(
            path=path,
            status=status_map.get(path, "M"),
            old_path=old_path_map.get(path),
            insertions=insertions,
            deletions=deletions,
        ))
    return files


def get_commit_numstat(sha: str) -> list[FileChange]:
    """Get insertion/deletion counts per file for a specific commit."""
    numstat = _run(["git", "show", "--numstat", "--format=", sha])
    name_status = _run([
        "git", "show", "--name-status", "--format=", sha
    ])

    status_map: dict[str, str] = {}
    old_path_map: dict[str, str] = {}
    for line in name_status.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            status = parts[0][0]
            file_path = parts[-1]
            status_map[file_path] = status
            if status == "R" and len(parts) >= 3:
                old_path_map[parts[2]] = parts[1]

    files: list[FileChange] = []
    for line in numstat.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        ins_str, del_str, path = parts[0], parts[1], parts[2]
        insertions = int(ins_str) if ins_str != "-" else 0
        deletions = int(del_str) if del_str != "-" else 0
        files.append(FileChange(
            path=path,
            status=status_map.get(path, "M"),
            old_path=old_path_map.get(path),
            insertions=insertions,
            deletions=deletions,
        ))
    return files


def get_file_diff(base: str, file_path: str, max_lines: int = 500) -> str:
    """Return the diff for a single file, truncated to max_lines."""
    output = _run(["git", "diff", f"{base}..HEAD", "--", file_path])
    lines = output.splitlines()
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + f"\n... (truncated, {len(lines)} total lines)"
    return output


def get_file_diff_for_commits(
    shas: list[str], file_path: str, max_lines: int = 300
) -> str:
    """Return combined diffs for a file across specific commits."""
    parts: list[str] = []
    for sha in shas:
        try:
            output = _run(["git", "show", sha, "--", file_path])
            if output:
                parts.append(f"# Commit {sha}\n{output}")
        except GitError:
            continue
    combined = "\n\n".join(parts)
    lines = combined.splitlines()
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + f"\n... (truncated)"
    return combined


def _parse_name_status(output: str) -> list[FileChange]:
    """Parse git name-status output into FileChange objects."""
    files: list[FileChange] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0][0]  # First character: A/M/D/R/C
        if status == "R" and len(parts) >= 3:
            files.append(FileChange(
                path=parts[2],
                status="R",
                old_path=parts[1],
            ))
        else:
            files.append(FileChange(
                path=parts[-1],
                status=status,
            ))
    return files
