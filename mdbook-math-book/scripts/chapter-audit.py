#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Audit mdBook markdown SOURCE for the failure modes that silently ship.

Every check here corresponds to a bug that reached HEAD or the PDF in a real
house-style math book. They are cheap to run and catch the classes of error a
clean `mdbook build` does NOT: math that renders as literal text, prose that
bleeds into a formula, fences that desync an admonish block, and glyphs the
xelatex font cannot draw.

Replaces a pile of brittle `grep` one-liners (the `\\[(),;]` shell-escaping trap
in particular). Robust because it tracks escapes and fenced-code state per line.

Checks (each can be silenced with --no-<check>):
  dollars     odd count of unescaped `$` on a line  -> math/prose not separated
  delims      \\( \\) \\, \\; in prose               -> eaten by pulldown-cmark
  fences      odd number of ``` in a file            -> broken admonish block
  unicode     literal ▮ ✓ → ² etc. OUTSIDE math      -> missing-char in PDF
  artifacts   leaked subagent tool tags              -> parallel-authoring debris
  placeholder TODO / TBD / FIXME / lorem ipsum / ???
  summary     every src/*.md is listed in SUMMARY.md

Usage:
    chapter-audit.py [FILE ...]        # default: src/*.md
    chapter-audit.py --no-summary src/ch04.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PLACEHOLDERS = ("TODO", "TBD", "FIXME", "placeholder", "lorem ipsum", "???")
ARTIFACTS = ("</content>", "</invoke>", "<parameter", "antml:", "<function")
# Literal Unicode that the STIX/xelatex stack drops or warns on. Use the LaTeX
# form inside math instead: $\blacksquare$, $\checkmark$, \to, x^2, e^x.
BAD_UNICODE = "▮✓→←⇒²³½¼ˣ−"
# Backslash-before-ASCII-punctuation: pulldown-cmark strips the backslash before
# MathJax sees it, so inline `\( \) \, \;` render as literal text.
DELIM_RE = re.compile(r"\\[(),;]")


def count_unescaped_dollars(line: str) -> int:
    count, escaped = 0, False
    for ch in line:
        if escaped:
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == "$":
            count += 1
    return count


def strip_math(line: str) -> str:
    """Remove $...$ / $$...$$ spans so we only test PROSE for stray Unicode."""
    return re.sub(r"\$[^$]*\$", "", line)


def audit_file(path: Path, checks: set[str]) -> list[str]:
    errs: list[str] = []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    if "fences" in checks and sum(1 for ln in lines if ln.lstrip().startswith("```")) % 2:
        errs.append(f"{path}: odd number of ``` fences (broken admonish/code block)")

    if "artifacts" in checks:
        for n, ln in enumerate(lines, 1):
            for tag in ARTIFACTS:
                if tag in ln:
                    errs.append(f"{path}:{n}: leaked tool-call artifact '{tag}'")

    if "placeholder" in checks:
        low = text.lower()
        for p in PLACEHOLDERS:
            if p.lower() in low:
                errs.append(f"{path}: placeholder text '{p}'")

    in_fence = False
    for n, ln in enumerate(lines, 1):
        if ln.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:  # diagrams/code blocks legitimately hold odd $ and Unicode
            continue
        if "dollars" in checks and count_unescaped_dollars(ln) % 2:
            errs.append(f"{path}:{n}: odd unescaped '$' — math and prose not separated")
        if "delims" in checks and DELIM_RE.search(ln):
            errs.append(rf"{path}:{n}: backslash delimiter \( \) \, \; — use $...$ inline")
        if "unicode" in checks:
            for ch in strip_math(ln):
                if ch in BAD_UNICODE:
                    errs.append(f"{path}:{n}: literal Unicode '{ch}' in prose — use the LaTeX form in math")
                    break
    return errs


def audit_summary(files: list[Path]) -> list[str]:
    summary = Path("src/SUMMARY.md")
    if not summary.exists():
        return []
    listed = summary.read_text(encoding="utf-8")
    return [f"{f}: not listed in SUMMARY.md (mdbook will silently skip it)"
            for f in files
            if f.name != "SUMMARY.md" and f"({f.name})" not in listed]


def main() -> int:
    all_checks = {"dollars", "delims", "fences", "unicode", "artifacts", "placeholder", "summary"}
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="*")
    for c in sorted(all_checks):
        ap.add_argument(f"--no-{c}", action="store_true", help=f"skip the {c} check")
    args = ap.parse_args()

    checks = {c for c in all_checks if not getattr(args, f"no_{c}")}
    files = [Path(f) for f in args.files] or sorted(Path("src").glob("*.md"))
    if not files:
        sys.exit("chapter-audit: no files found")

    errs: list[str] = []
    for f in files:
        errs += audit_file(f, checks)
    if "summary" in checks and not args.files:
        errs += audit_summary(files)

    if errs:
        print("\n".join(errs))
        print(f"chapter-audit: FAIL ({len(errs)} issue(s)).")
        return 1
    print("chapter-audit: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
