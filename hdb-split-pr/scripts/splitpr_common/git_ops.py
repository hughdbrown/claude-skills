"""Shared git operations via subprocess.run.

Contains read-only git primitives and model-dependent helpers that are
identical across splitpr_00 and splitpr_05.  Write operations (with
dry-run support) stay in splitpr_05.git_ops.
"""

from __future__ import annotations

import subprocess

from splitpr_common.models import Commit, FileChange


class GitError(Exception):
    """Raised when a git command fails."""

    def __init__(self, cmd: list[str], returncode: int, stderr: str):
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(
            f"git command failed (rc={returncode}): {' '.join(cmd)}\n{stderr}"
        )


def _run(args: list[str], timeout: int = 60) -> str:
    """Run a git command, return stdout. Raise GitError on failure."""
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise GitError(args, result.returncode, result.stderr.strip())
    return result.stdout.strip()


# ── Read-only primitives ─────────────────────────────────────────────


def is_git_repo() -> bool:
    """Check if the current directory is inside a git work tree."""
    try:
        _run(["git", "rev-parse", "--is-inside-work-tree"])
        return True
    except (GitError, subprocess.TimeoutExpired):
        return False


def get_current_branch() -> str:
    """Return the current branch name, or 'HEAD' if detached."""
    return _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])


def get_repo_toplevel() -> str:
    """Return the absolute path to the repository root."""
    return _run(["git", "rev-parse", "--show-toplevel"])


def get_head_rev() -> str:
    """Return the full SHA of HEAD."""
    return _run(["git", "rev-parse", "HEAD"])


def detect_base_branch(explicit: str | None = None) -> str:
    """Determine the base branch.

    If explicit is given, verify it exists and return it.
    Otherwise try 'master' then 'main'.
    Raises GitError if none found.
    """
    if explicit:
        _run(["git", "rev-parse", "--verify", explicit])
        return explicit
    for candidate in ("master", "main"):
        try:
            _run(["git", "rev-parse", "--verify", candidate])
            return candidate
        except GitError:
            continue
    raise GitError(
        ["git", "rev-parse", "--verify", "master|main"],
        1,
        "Neither 'master' nor 'main' branch exists. Use --base to specify.",
    )


def get_merge_base(base: str) -> str:
    """Return the merge-base SHA between base and HEAD."""
    return _run(["git", "merge-base", base, "HEAD"])


def get_diff_stat(base: str) -> str:
    """Return the --stat output for the full diff."""
    return _run(["git", "diff", "--stat", f"{base}..HEAD"])


# ── Model-dependent helpers ──────────────────────────────────────────


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
        return "\n".join(lines[:max_lines]) + "\n... (truncated)"
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
