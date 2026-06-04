#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Shared library for the per-language code-sample checkers.

The central rule of a house-style programming book: **displayed code is never
hand-typed into the prose.** It lives in a real source file (a compilable
project under `code/`, or a standalone sample under `<lang>/`) and the chapter
pulls it in with an mdBook include directive:

    ```rust
    {{#rustdoc_include code/ch03/src/lib.rs:retry}}
    ```
    ```go
    {{#include go/ch07/worker_test.go}}
    ```
    ```python
    {{#include python/ch04/pipeline.py}}
    ```

This module does the language-agnostic work — fence extraction, include
resolution, anchor checks, the externalization policy, and source-excerpt
provenance — and exposes `drive()`. Each `scripts/<lang>/check_<lang>_samples.py`
imports this, supplies a `validate(file_path, work, block, update)` callback that
compiles/runs the sample in that language, and calls `drive()`.

Shipped as a uv PEP-723 script (no third-party deps); imported by the per-language
checkers via a `sys.path` insert, so it needs no packaging.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# Fence language -> normalized key, and file suffix -> normalized key.
LANG_BY_FENCE = {
    "go": "go", "golang": "go",
    "python": "python", "py": "python", "python3": "python",
    "rust": "rust", "rs": "rust",
}
LANG_BY_SUFFIX = {".go": "go", ".py": "python", ".rs": "rust"}

SKIP_TOKENS = {"no-check", "nocheck", "ignore", "skip", "check=skip", "check=false"}
INCLUDE_RE = re.compile(
    r"^\s*\{\{#(?:include|rustdoc_include|playground)\s+([^}:]+)(?::([^}]*))?\}\}\s*$"
)
SOURCE_EXCERPT_DIR = "source-excerpts"
SOURCE_EXCERPT_MANIFEST = "source-excerpts/manifest.tsv"


class CheckError(Exception):
    pass


@dataclass(frozen=True)
class CodeBlock:
    path: Path
    start_line: int  # first body line (1-based)
    end_line: int    # last body line (inclusive)
    info: str        # fence info string, e.g. "rust no_run"
    code: str

    @property
    def _info_tokens(self) -> list[str]:
        # Fence info is space- or comma-separated: `go no-check`, `rust,compile_fail`.
        return [t for t in re.split(r"[\s,]+", self.info.strip()) if t]

    @property
    def language(self) -> str:
        toks = self._info_tokens
        return LANG_BY_FENCE.get(toks[0].lower(), "") if toks else ""

    @property
    def tokens(self) -> set[str]:
        return {t.lower() for t in self._info_tokens}

    @property
    def label(self) -> str:
        return f"{self.path}:{self.start_line}"


@dataclass(frozen=True)
class Include:
    path: Path
    anchor: str | None


@dataclass(frozen=True)
class SourceExcerpt:
    excerpt: Path
    source: Path
    mode: str  # "exact" | "normalized"


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


# --- Structural code queries via ast-grep (NOT regex) ----------------------
# The checkers identify language constructs (a Go `package` clause, a Go/Python
# test function) by querying the parsed syntax tree with ast-grep, not by
# regex-matching source text. ast-grep returns exit 0 with a JSON array on
# stdout whether or not anything matched; a non-zero exit is a real error.
def _ast_grep_bin() -> str:
    for name in ("ast-grep", "sg"):
        if shutil.which(name):
            return name
    raise CheckError("`ast-grep` not found on PATH "
                     "(install: `brew install ast-grep` / `cargo install ast-grep`)")


def ast_grep_matches(pattern: str, lang: str, file_path: Path) -> list[dict]:
    """JSON matches of a concrete `pattern` against `file_path` in `lang`.

    `ast-grep run` follows grep exit conventions: 0 = matched, 1 = no match (or
    an unparseable target), >=2 = a real tool error (e.g. bad language)."""
    proc = run([_ast_grep_bin(), "run", "--pattern", pattern, "--lang", lang,
                "--json", str(file_path)], file_path.parent)
    if proc.returncode >= 2:
        raise CheckError(f"ast-grep failed on {file_path}:\n{proc.stderr}".rstrip())
    return json.loads(proc.stdout or "[]")


def ast_grep_node_names(kind: str, lang: str, file_path: Path) -> list[str]:
    """Names of every `kind` node (with a `name` field) in `file_path` — e.g.
    every `function_declaration` (Go) / `function_definition` (Python),
    regardless of signature. Used to detect test functions structurally."""
    rule = (f"id: q\nlanguage: {lang}\n"
            f"rule: {{kind: {kind}, has: {{field: name, pattern: $NAME}}}}")
    proc = run([_ast_grep_bin(), "scan", "--inline-rules", rule, "--json",
                str(file_path)], file_path.parent)
    if proc.returncode >= 2:
        raise CheckError(f"ast-grep scan failed on {file_path}:\n{proc.stderr}".rstrip())
    return [m["metaVariables"]["single"]["NAME"]["text"]
            for m in json.loads(proc.stdout or "[]")
            if "NAME" in m.get("metaVariables", {}).get("single", {})]


# --- Markdown fence extraction (matched ``` / ~~~ runs) --------------------
def extract_code_blocks(path: Path) -> list[CodeBlock]:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    blocks: list[CodeBlock] = []
    fence_re = re.compile(r"^[ \t]*(`{3,}|~{3,})([^\n\r]*)$")
    in_block = False
    fence_char, fence_len, info, start_line = "", 0, "", 0
    body: list[str] = []
    for idx, line in enumerate(lines, start=1):
        stripped = line.rstrip("\n\r")
        if not in_block:
            m = fence_re.match(stripped)
            if not m:
                continue
            in_block, fence_char, fence_len = True, m.group(1)[0], len(m.group(1))
            info, start_line, body = m.group(2).strip(), idx + 1, []
            continue
        if re.match(rf"^[ \t]*{re.escape(fence_char)}{{{fence_len},}}[ \t]*$", stripped):
            blocks.append(CodeBlock(path, start_line, idx - 1, info, "".join(body)))
            in_block, fence_char, fence_len, info, body = False, "", 0, "", []
            continue
        body.append(line)
    if in_block:
        raise CheckError(f"{path}:{start_line - 1}: unterminated fenced code block")
    return blocks


def should_skip(block: CodeBlock) -> bool:
    if block.tokens & SKIP_TOKENS:
        return True
    for line in block.code.splitlines()[:5]:
        if "book:skip" in line or "book:no-check" in line:
            return True
    return False


def parse_include(block: CodeBlock) -> Include | None:
    lines = [ln.strip() for ln in block.code.splitlines() if ln.strip()]
    if len(lines) != 1:
        return None
    m = INCLUDE_RE.match(lines[0])
    if not m:
        return None
    target = (block.path.parent / m.group(1).strip()).resolve()
    spec = (m.group(2) or "").strip()
    # `:anchor` is a named region; `:start:end` is a line range (digits only).
    anchor = spec if spec and not re.fullmatch(r"\d*(:\d*)?", spec) else None
    return Include(target, anchor)


def anchor_defined(file_path: Path, anchor: str) -> bool:
    text = file_path.read_text(encoding="utf-8")
    return f"ANCHOR: {anchor}" in text or f"ANCHOR:{anchor}" in text


def under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


# --- Source-excerpt provenance --------------------------------------------
def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def load_manifest(src_dir: Path) -> dict[Path, SourceExcerpt]:
    manifest = src_dir / SOURCE_EXCERPT_MANIFEST
    if not manifest.exists():
        return {}
    out: dict[Path, SourceExcerpt] = {}
    for n, raw in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in raw.split("\t")]
        if len(parts) != 3:
            raise CheckError(f"{manifest}:{n}: expected 3 tab-separated fields "
                             "(excerpt, source, mode)")
        excerpt_raw, source_raw, mode = parts
        if mode not in {"exact", "normalized"}:
            raise CheckError(f"{manifest}:{n}: bad mode {mode!r} (exact|normalized)")
        excerpt = (src_dir / excerpt_raw).resolve()
        source = Path(source_raw).expanduser().resolve()
        if not excerpt.exists():
            raise CheckError(f"{manifest}:{n}: excerpt not found: {excerpt}")
        if not source.exists():
            raise CheckError(f"{manifest}:{n}: source not found: {source}")
        out[excerpt] = SourceExcerpt(excerpt, source, mode)
    return out


def check_excerpt(entry: SourceExcerpt) -> None:
    have = entry.excerpt.read_text(encoding="utf-8")
    want = entry.source.read_text(encoding="utf-8")
    if entry.mode == "exact" and have in want:
        return
    if entry.mode == "normalized" and _normalize(have) in _normalize(want):
        return
    raise CheckError(f"{entry.excerpt}: excerpt no longer matches source {entry.source} "
                     f"(mode={entry.mode}) — reconcile or update the excerpt")


def find_markdown(src: Path) -> list[Path]:
    return sorted(p for p in src.rglob("*.md") if p.is_file())


# --- The driver ------------------------------------------------------------
Validator = Callable[[Path, Path, CodeBlock, bool], None]


def drive(root: Path, src: Path, lang: str, validate: Validator, *,
          update: bool = False, max_inline: int = 6) -> int:
    """Walk src/**/*.md, validate every `lang` sample, enforce externalization
    and provenance. `validate(file_path, work_dir, block, update)` raises
    CheckError on failure. Returns a process exit code."""
    errors: list[str] = []
    counts = {"included": 0, "compiled": 0, "skipped": 0, "inline_ok": 0, "excerpts": 0}
    excerpt_refs: set[Path] = set()

    try:
        manifest = load_manifest(src)
    except CheckError as e:
        manifest = {}
        errors.append(str(e))
    excerpt_root = (src / SOURCE_EXCERPT_DIR).resolve()

    with tempfile.TemporaryDirectory(prefix=f"book-{lang}-") as tmp:
        work = Path(tmp)
        for md in find_markdown(src):
            try:
                blocks = extract_code_blocks(md)
            except CheckError as e:
                errors.append(str(e))
                continue
            for block in blocks:
                if block.language != lang:
                    continue
                inc = parse_include(block)
                if inc is None:
                    if should_skip(block):
                        counts["skipped"] += 1
                    elif len(block.code.strip().splitlines()) > max_inline:
                        errors.append(
                            f"{block.label}: inline {lang} block is "
                            f"{len(block.code.strip().splitlines())} lines — externalize it "
                            "to a file and {{#include}} it (or mark `no-check` for a "
                            "deliberate fragment)")
                    else:
                        counts["inline_ok"] += 1
                    continue
                counts["included"] += 1
                if not inc.path.exists():
                    errors.append(f"{block.label}: included file not found: {inc.path}")
                    continue
                if inc.anchor and not anchor_defined(inc.path, inc.anchor):
                    errors.append(f"{block.label}: anchor '{inc.anchor}' not defined in {inc.path}")
                if under(inc.path, excerpt_root):
                    excerpt_refs.add(inc.path)
                    if inc.path not in manifest:
                        errors.append(f"{block.label}: excerpt missing from "
                                      f"{SOURCE_EXCERPT_MANIFEST}: {inc.path}")
                    continue  # provenance-checked below, not compiled
                if should_skip(block):
                    counts["skipped"] += 1
                    continue
                if LANG_BY_SUFFIX.get(inc.path.suffix) != lang:
                    errors.append(f"{block.label}: {lang} block includes a "
                                  f"non-{lang} file: {inc.path}")
                    continue
                try:
                    validate(inc.path, work, block, update)
                    counts["compiled"] += 1
                except CheckError as e:
                    errors.append(str(e))

        if manifest:
            on_disk = {p.resolve() for p in excerpt_root.rglob("*")
                       if p.is_file() and LANG_BY_SUFFIX.get(p.suffix) == lang}
            listed = {p for p in manifest if LANG_BY_SUFFIX.get(p.suffix) == lang}
            for p in sorted(on_disk - set(manifest)):
                errors.append(f"{p}: excerpt file not in {SOURCE_EXCERPT_MANIFEST}")
            for p in sorted(listed - excerpt_refs):
                errors.append(f"{p}: manifest excerpt is never {{#include}}d from a chapter")
            for entry in manifest.values():
                if LANG_BY_SUFFIX.get(entry.excerpt.suffix) != lang:
                    continue
                try:
                    check_excerpt(entry)
                    counts["excerpts"] += 1
                except CheckError as e:
                    errors.append(str(e))

    if errors:
        print(f"{lang} code-sample check FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1
    print(f"{lang} code-sample check OK — compiled {counts['compiled']}, "
          f"included {counts['included']}, excerpts {counts['excerpts']}, "
          f"short-inline {counts['inline_ok']}, skipped {counts['skipped']}",
          file=sys.stderr)
    return 0
