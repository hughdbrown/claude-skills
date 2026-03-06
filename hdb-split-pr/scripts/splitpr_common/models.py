"""Data structures shared across all modules."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FileChange:
    """A file changed in a commit or in the overall diff."""

    path: str
    status: str  # A/M/D/R
    old_path: str | None = None  # non-null only for renames
    insertions: int = 0
    deletions: int = 0


@dataclass
class Commit:
    """A single commit on the branch."""

    sha: str
    ordinal: int  # 1-based, oldest first
    subject: str
    body: str = ""
    author: str = ""
    date: str = ""  # ISO 8601
    files: list[FileChange] = field(default_factory=list)

    @property
    def files_changed(self) -> int:
        return len(self.files)

    @property
    def total_insertions(self) -> int:
        return sum(f.insertions for f in self.files)

    @property
    def total_deletions(self) -> int:
        return sum(f.deletions for f in self.files)


@dataclass
class Theme:
    """A logical grouping of related commits."""

    theme_id: int
    name: str
    description: str = ""
    commit_count: int = 0
    file_count: int = 0
    net_lines: int = 0


@dataclass
class Dependency:
    """A dependency edge between two themes/PRs."""

    from_theme: str
    depends_on: str
    reason: str = ""


@dataclass
class PR:
    """A planned pull request."""

    pr_id: int
    theme_id: int | None
    branch_name: str
    title: str
    merge_order: int
    base_branch: str
    description: str = ""
    file_count: int = 0
    net_lines: int = 0


@dataclass
class Task:
    """A single task within a PR."""

    task_id: int
    pr_id: int
    ordinal: int
    subject: str
    description: str
    acceptance: str = ""
    recovery_cmds: str = ""
    task_type: str = ""  # infrastructure/core/config/integration/test/docs/lint/verify
    source_commits: str = ""  # comma-separated SHAs
    source_files: str = ""  # comma-separated file paths
