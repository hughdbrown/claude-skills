"""Data structures shared across all modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Strategy(str, Enum):
    """Resolution strategy for a conflict block."""

    TAKE_OURS = "take_ours"
    TAKE_THEIRS = "take_theirs"
    TAKE_BOTH = "take_both"
    CUSTOM = "custom"


class OperationType(str, Enum):
    """The type of git operation that caused the conflict."""

    MERGE = "merge"
    REBASE = "rebase"
    CHERRY_PICK = "cherry-pick"
    UNKNOWN = "unknown"


@dataclass
class ConflictBlock:
    """A single conflict block within a file."""

    file_path: str
    block_index: int  # 0-based index within the file
    total_blocks: int  # total number of conflict blocks in the file
    ours: str  # content from the current branch
    theirs: str  # content from the incoming branch
    base: str | None = None  # common ancestor (diff3 mode only)
    ours_label: str = "HEAD"
    theirs_label: str = ""
    context_before: str = ""  # lines before the conflict
    context_after: str = ""  # lines after the conflict
    start_line: int = 0  # 1-based line number of <<<<<<< marker
    end_line: int = 0  # 1-based line number of >>>>>>> marker

    @property
    def ours_line_count(self) -> int:
        return len(self.ours.splitlines()) if self.ours else 0

    @property
    def theirs_line_count(self) -> int:
        return len(self.theirs.splitlines()) if self.theirs else 0

    @property
    def has_base(self) -> bool:
        return self.base is not None


@dataclass
class Resolution:
    """The AI-determined resolution for a conflict block."""

    strategy: Strategy
    resolved_content: str
    confidence: float
    reasoning: str


@dataclass
class ConflictFile:
    """A file containing one or more conflict blocks."""

    path: str
    blocks: list[ConflictBlock] = field(default_factory=list)
    original_content: str = ""  # the full file content with conflict markers

    @property
    def block_count(self) -> int:
        return len(self.blocks)


@dataclass
class MergeContext:
    """Context about the merge/rebase/cherry-pick operation."""

    operation: OperationType
    current_branch: str = ""
    incoming_ref: str = ""  # branch name, SHA, or empty
    current_commits: list[str] = field(default_factory=list)  # recent commit summaries
    incoming_commits: list[str] = field(default_factory=list)
