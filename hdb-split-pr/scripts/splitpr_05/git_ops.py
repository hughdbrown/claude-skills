"""Git operations via subprocess.run.

Every git command in the project goes through this module. No other module
calls subprocess directly.
"""

from __future__ import annotations

import logging
import subprocess

from splitpr_05.models import Commit, FileChange

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


def get_diff_stat(base: str) -> str:
    """Return the --stat output for the full diff."""
    return _run(["git", "diff", "--stat", f"{base}..HEAD"])


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


# ── Write operations (with dry-run support) ──────────────────────────


def _run_write(
    args: list[str], dry_run: bool, timeout: int = 60
) -> str:
    """Run a state-modifying command. In dry-run mode, log and skip."""
    if dry_run:
        logger.info("[DRY RUN] $ %s", " ".join(args))
        return ""
    return _run(args, timeout)


def branch_exists(name: str) -> bool:
    """Check if a local branch exists."""
    try:
        _run(["git", "rev-parse", "--verify", f"refs/heads/{name}"])
        return True
    except GitError:
        return False


def has_uncommitted_changes() -> bool:
    """Check if there are uncommitted changes in the working tree."""
    output = _run(["git", "status", "--porcelain"])
    return bool(output.strip())


def create_branch(
    name: str, start_point: str, dry_run: bool = False
) -> None:
    """Create and switch to a new branch from start_point."""
    _run_write(["git", "checkout", "-b", name, start_point], dry_run)


def checkout_branch(name: str, dry_run: bool = False) -> None:
    """Switch to an existing branch."""
    _run_write(["git", "checkout", name], dry_run)


def cherry_pick(shas: list[str], dry_run: bool = False) -> bool:
    """Cherry-pick one or more commits in order. Returns True on success."""
    if not shas:
        return True
    try:
        _run_write(["git", "cherry-pick"] + shas, dry_run)
        return True
    except GitError as e:
        logger.warning("Cherry-pick failed: %s", e)
        return False


def cherry_pick_abort() -> None:
    """Abort an in-progress cherry-pick."""
    try:
        _run(["git", "cherry-pick", "--abort"])
    except GitError:
        pass  # No cherry-pick in progress


def checkout_files_from_branch(
    source_branch: str,
    files: list[str],
    dry_run: bool = False,
) -> None:
    """Check out specific files from a source branch into the working tree.

    Handles batching to avoid command-line length limits.
    Files are staged automatically by ``git checkout <branch> -- <files>``.
    """
    if not files:
        return
    batch_size: int = 50
    for i in range(0, len(files), batch_size):
        batch: list[str] = files[i : i + batch_size]
        _run_write(
            ["git", "checkout", source_branch, "--"] + batch,
            dry_run,
        )


def rm_files(
    files: list[str], dry_run: bool = False
) -> None:
    """Remove files from the working tree and index."""
    if not files:
        return
    batch_size: int = 50
    for i in range(0, len(files), batch_size):
        batch: list[str] = files[i : i + batch_size]
        _run_write(["git", "rm", "-f", "--ignore-unmatch"] + batch, dry_run)


def commit(message: str, dry_run: bool = False) -> None:
    """Create a commit with the given message."""
    _run_write(["git", "commit", "-m", message], dry_run)


def push_branch(
    branch: str,
    remote: str = "origin",
    dry_run: bool = False,
) -> None:
    """Push a branch to a remote with upstream tracking."""
    _run_write(
        ["git", "push", "-u", remote, branch],
        dry_run,
        timeout=120,
    )


def create_github_pr(
    branch: str,
    base: str,
    title: str,
    body: str,
    dry_run: bool = False,
) -> str | None:
    """Create a GitHub PR using the gh CLI. Returns the PR URL or None."""
    if dry_run:
        logger.info(
            '[DRY RUN] $ gh pr create --base "%s" --title "%s" --body "..."',
            base,
            title,
        )
        return None
    try:
        result = subprocess.run(
            [
                "gh", "pr", "create",
                "--base", base,
                "--title", title,
                "--body", body,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.error("Failed to create PR: %s", result.stderr.strip())
            return None
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.error("Failed to create PR: %s", e)
        return None


def gh_available() -> bool:
    """Check if the gh CLI is installed and authenticated."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def delete_branch(
    name: str, force: bool = False, dry_run: bool = False
) -> None:
    """Delete a local branch."""
    flag = "-D" if force else "-d"
    _run_write(["git", "branch", flag, name], dry_run)


def get_diff_names(base: str, head: str = "HEAD") -> list[str]:
    """Return the list of file names changed between base and head."""
    output = _run(["git", "diff", "--name-only", f"{base}..{head}"])
    return [line.strip() for line in output.splitlines() if line.strip()]


# ── Remote / repository identification ───────────────────────────────


def get_repo_toplevel() -> str:
    """Return the absolute path to the repository root."""
    return _run(["git", "rev-parse", "--show-toplevel"])


def get_remote_url(remote: str = "origin") -> str | None:
    """Return the push URL for a remote, or None if the remote is missing."""
    try:
        return _run(["git", "remote", "get-url", "--push", remote])
    except GitError:
        return None


def get_all_remotes() -> dict[str, str]:
    """Return {remote_name: push_url} for every configured remote."""
    try:
        output = _run(["git", "remote", "-v"])
    except GitError:
        return {}
    remotes: dict[str, str] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and line.rstrip().endswith("(push)"):
            remotes[parts[0]] = parts[1]
    return remotes


def parse_github_remote(url: str) -> tuple[str, str] | None:
    """Extract (owner, repo) from a GitHub remote URL.

    Handles:
      git@github.com:owner/repo.git
      https://github.com/owner/repo.git
      ssh://git@github.com/owner/repo.git
    Returns None if the URL is not a recognisable GitHub URL.
    """
    import re

    # SSH: git@github.com:owner/repo.git
    m = re.match(r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$", url)
    if m:
        return m.group(1), m.group(2)

    # HTTPS or SSH-scheme: https://github.com/owner/repo.git
    m = re.match(
        r"(?:https?|ssh)://(?:[^@]+@)?github\.com/([^/]+)/([^/]+?)(?:\.git)?$",
        url,
    )
    if m:
        return m.group(1), m.group(2)

    return None


def get_gh_repo_info() -> dict[str, str] | None:
    """Query ``gh`` for the current repo's GitHub metadata.

    Returns a dict with keys like ``nameWithOwner``, ``isFork``,
    ``parent_nameWithOwner`` (if a fork), or None on failure.
    """
    try:
        result = subprocess.run(
            [
                "gh", "repo", "view",
                "--json", "nameWithOwner,isFork,parent",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return None
        import json

        data: dict = json.loads(result.stdout)
        info: dict[str, str] = {
            "nameWithOwner": data.get("nameWithOwner", ""),
            "isFork": str(data.get("isFork", False)),
        }
        parent = data.get("parent")
        if parent and isinstance(parent, dict):
            info["parent_nameWithOwner"] = parent.get("nameWithOwner", "")
        return info
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        return None


def describe_repo_context(remote: str = "origin") -> list[str]:
    """Build human-readable lines describing the repo and remote target.

    Designed for logging at the start of execution so the operator knows
    exactly which repository will be modified.
    """
    lines: list[str] = []

    toplevel: str = get_repo_toplevel()
    lines.append(f"Repo path:      {toplevel}")

    url: str | None = get_remote_url(remote)
    if url:
        lines.append(f"Push remote:    {remote} -> {url}")
        parsed = parse_github_remote(url)
        if parsed:
            lines.append(f"GitHub repo:    {parsed[0]}/{parsed[1]}")
    else:
        lines.append(f"Push remote:    {remote} (not configured)")

    # Show all remotes so the user can see origin vs upstream
    all_remotes: dict[str, str] = get_all_remotes()
    if len(all_remotes) > 1:
        for name, rurl in sorted(all_remotes.items()):
            if name != remote:
                lines.append(f"Other remote:   {name} -> {rurl}")

    gh_info: dict[str, str] | None = get_gh_repo_info()
    if gh_info:
        is_fork: bool = gh_info.get("isFork", "False") == "True"
        if is_fork:
            parent: str = gh_info.get("parent_nameWithOwner", "unknown")
            lines.append(f"Fork of:        {parent}")
        else:
            lines.append("Fork:           no (this is the source repo)")

    return lines
