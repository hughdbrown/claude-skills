"""Shared git operations via subprocess.run.

Contains read-only git primitives that are identical across splitpr_00 and
splitpr_05.  Model-dependent helpers (e.g. those returning FileChange) stay
in each package's own git_ops module.
"""

from __future__ import annotations

import subprocess


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
