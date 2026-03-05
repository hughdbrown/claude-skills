"""Git operations via subprocess.run.

Every git command in the project goes through this module. No other module
calls subprocess directly.
"""

from __future__ import annotations

import logging
import os
import subprocess

from mergefix.models import MergeContext, OperationType

logger = logging.getLogger(__name__)


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


def _run_write(args: list[str], dry_run: bool, timeout: int = 60) -> str:
    """Run a state-modifying command. In dry-run mode, log and skip."""
    if dry_run:
        logger.info("[DRY RUN] $ %s", " ".join(args))
        return ""
    return _run(args, timeout)


# ── Read-only queries ────────────────────────────────────────────────


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


def get_git_dir() -> str:
    """Return the path to the .git directory."""
    return _run(["git", "rev-parse", "--git-dir"])


def get_conflicted_files() -> list[str]:
    """Return a list of file paths that have unmerged conflicts.

    Parses `git status --porcelain` for unmerged status codes:
    UU, AA, DD, AU, UA, DU, UD.
    """
    output = _run(["git", "status", "--porcelain"])
    unmerged_prefixes = {"UU", "AA", "DD", "AU", "UA", "DU", "UD"}
    files: list[str] = []
    for line in output.splitlines():
        if len(line) >= 3:
            status = line[:2]
            if status in unmerged_prefixes:
                files.append(line[3:].strip())
    return files


def get_conflict_status(file_path: str) -> str:
    """Return the two-character unmerged status for a file (e.g., 'UU', 'DD')."""
    output = _run(["git", "status", "--porcelain"])
    for line in output.splitlines():
        if len(line) >= 3 and line[3:].strip() == file_path:
            return line[:2]
    return ""


def detect_operation_type() -> OperationType:
    """Detect whether the current conflict is from a merge, rebase, or cherry-pick."""
    git_dir = get_git_dir()

    merge_head = os.path.join(git_dir, "MERGE_HEAD")
    if os.path.isfile(merge_head):
        return OperationType.MERGE

    rebase_merge = os.path.join(git_dir, "rebase-merge")
    rebase_apply = os.path.join(git_dir, "rebase-apply")
    if os.path.isdir(rebase_merge) or os.path.isdir(rebase_apply):
        return OperationType.REBASE

    cherry_pick_head = os.path.join(git_dir, "CHERRY_PICK_HEAD")
    if os.path.isfile(cherry_pick_head):
        return OperationType.CHERRY_PICK

    return OperationType.UNKNOWN


def get_merge_context() -> MergeContext:
    """Build a MergeContext describing the current merge/rebase/cherry-pick."""
    operation = detect_operation_type()
    current_branch = get_current_branch()

    incoming_ref = ""
    incoming_commits: list[str] = []

    if operation == OperationType.MERGE:
        try:
            incoming_ref = _run(
                ["git", "log", "--oneline", "-1", "MERGE_HEAD"]
            )
        except GitError:
            pass
        try:
            raw = _run(["git", "log", "--oneline", "-5", "MERGE_HEAD"])
            incoming_commits = raw.splitlines()
        except GitError:
            pass

    elif operation == OperationType.CHERRY_PICK:
        try:
            incoming_ref = _run(
                ["git", "log", "--oneline", "-1", "CHERRY_PICK_HEAD"]
            )
        except GitError:
            pass

    current_commits: list[str] = []
    try:
        raw = _run(["git", "log", "--oneline", "-5", "HEAD"])
        current_commits = raw.splitlines()
    except GitError:
        pass

    return MergeContext(
        operation=operation,
        current_branch=current_branch,
        incoming_ref=incoming_ref,
        current_commits=current_commits,
        incoming_commits=incoming_commits,
    )


def is_binary_file(file_path: str) -> bool:
    """Check if a file is binary by asking git."""
    try:
        output = _run(
            ["git", "diff", "--numstat", "--cached", "--", file_path]
        )
        # Binary files show "-" for insertions and deletions
        if output and output.startswith("-\t-"):
            return True
    except GitError:
        pass

    # Fallback: check file content
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(8192)
            return b"\x00" in chunk
    except OSError:
        return False


# ── Write operations ─────────────────────────────────────────────────


def stage_file(file_path: str, dry_run: bool = False) -> None:
    """Stage a resolved file with git add."""
    _run_write(["git", "add", file_path], dry_run)


def rm_file(file_path: str, dry_run: bool = False) -> None:
    """Remove a file via git rm."""
    _run_write(["git", "rm", file_path], dry_run)


def checkout_ours(file_path: str, dry_run: bool = False) -> None:
    """Resolve a conflict by taking the ours version."""
    _run_write(["git", "checkout", "--ours", file_path], dry_run)


def checkout_theirs(file_path: str, dry_run: bool = False) -> None:
    """Resolve a conflict by taking the theirs version."""
    _run_write(["git", "checkout", "--theirs", file_path], dry_run)
