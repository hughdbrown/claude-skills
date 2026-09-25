"""Shared parsing for claude-team task cards and handoffs.

Imported by the sibling scripts (a script's own directory is on sys.path when
it runs, so `import taskcard` works under `uv run --script`). Standard library
only, so every script can use it without extra dependencies.
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATES = SKILL_DIR / "templates"
RESOURCES = SKILL_DIR / "resources"

TASK_ID_RE = re.compile(r"TASK-(\d+)")
BACKTICK_RE = re.compile(r"`([^`]+)`")
SHA_RE = re.compile(r"\b[0-9a-f]{7,40}\b")

MODEL_ALIASES = {
    "opus": "opus",
    "sonnet": "sonnet",
    "haiku": "haiku",
}


def sections(text: str) -> dict[str, str]:
    """Split markdown into {"## heading" title: body} for level-2 headings."""
    out: dict[str, str] = {}
    current: str | None = None
    lines: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
        if not in_fence and line.startswith("## "):
            if current is not None:
                out[current] = "\n".join(lines).strip()
            current = line[3:].strip()
            lines = []
        elif current is not None:
            lines.append(line)
    if current is not None:
        out[current] = "\n".join(lines).strip()
    return out


def strip_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()


def fenced_blocks(text: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"```[^\n]*\n(.*?)```", text, re.DOTALL)]


def bullet_list_after(body: str, label: str) -> list[str]:
    """Bullet items following a line like 'Allowed files:' up to the next label/blank gap."""
    items: list[str] = []
    capturing = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.lower().rstrip(":") == label.lower().rstrip(":"):
            capturing = True
            continue
        if not capturing:
            continue
        if stripped.startswith(("- ", "* ")):
            items.append(stripped[2:].strip())
        elif stripped.endswith(":") and items:
            break
        elif stripped and not stripped.startswith("<!--"):
            if items:
                break
    return items


@dataclass
class TaskCard:
    path: Path
    task_id: str
    title: str
    model: str | None
    allowed: list[str] = field(default_factory=list)
    forbidden: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    verify: list[str] = field(default_factory=list)
    text: str = ""

    @property
    def allowed_patterns(self) -> list[str]:
        return patterns(self.allowed)

    @property
    def forbidden_patterns(self) -> list[str]:
        return patterns(self.forbidden)

    @property
    def descriptive_forbidden(self) -> list[str]:
        """'Do not modify' entries that are prose (e.g. 'Database migrations'), not paths."""
        return [item for item in self.forbidden if not BACKTICK_RE.search(item)]


def patterns(items: list[str]) -> list[str]:
    """Backticked paths/globs from bullet items; prose entries are ignored."""
    return [m for item in items for m in BACKTICK_RE.findall(item)]


def parse_model(text: str) -> str | None:
    lowered = text.lower()
    for key, alias in MODEL_ALIASES.items():
        if key in lowered:
            return alias
    return None


def load_task(path: Path) -> TaskCard:
    text = path.read_text()
    first = text.splitlines()[0] if text else ""
    heading = first.lstrip("# ").strip()
    m = TASK_ID_RE.search(heading) or TASK_ID_RE.search(path.name)
    task_id = f"TASK-{m.group(1)}" if m else path.stem
    title = heading.split(":", 1)[1].strip() if ":" in heading else heading
    secs = sections(text)
    scope = secs.get("Scope", "")
    verification = secs.get("Verification", "")
    commands: list[str] = []
    for block in fenced_blocks(verification):
        commands.extend(
            line.strip() for line in block.splitlines() if line.strip() and not line.strip().startswith("#")
        )
    depends = TASK_ID_RE.findall(strip_comments(secs.get("Depends On", "")))
    return TaskCard(
        path=path,
        task_id=task_id,
        title=title,
        model=parse_model(strip_comments(secs.get("Assigned Model", ""))),
        allowed=bullet_list_after(scope, "Allowed files:"),
        forbidden=bullet_list_after(scope, "Do not modify:"),
        depends_on=[f"TASK-{d}" for d in depends],
        verify=commands,
        text=text,
    )


def matches(path: str, pattern: str) -> bool:
    """True if a repo-relative path matches a card pattern (glob, file, or dir/)."""
    pattern = pattern.strip().lstrip("./")
    if pattern.endswith("/"):
        return path.startswith(pattern)
    if any(ch in pattern for ch in "*?["):
        return fnmatch.fnmatchcase(path, pattern) or fnmatch.fnmatchcase(path, pattern.rstrip("/") + "/**")
    return path == pattern or path.startswith(pattern + "/")


def task_cards(tasks_dir: Path) -> list[TaskCard]:
    return [load_task(p) for p in sorted(tasks_dir.glob("TASK-*.md"))]


def find_card(tasks_dir: Path, task_id: str) -> Path | None:
    num = TASK_ID_RE.search(task_id.upper())
    if not num:
        return None
    hits = sorted(tasks_dir.glob(f"TASK-{num.group(1)}*.md"))
    return hits[0] if hits else None


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout
