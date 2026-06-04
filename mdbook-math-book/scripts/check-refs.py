#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Verify every cross-reference in the book resolves. The convention-drift gate.

Present in all 7 house-style books — the single most-repeatedly-created script.
Renumbering, retitling, and parallel drafting all silently break cross-references;
this catches them before they ship. Checks, per file, against pools built from
all of src/:

  Theorem|Definition|Example|Proposition|Lemma|Corollary|Construction N.M
        -> a `### <Type> N.M` heading exists (same file, then book-wide)
  Eq. (N.M)   -> a `\\tag{N.M}` exists in the same file
  §N / §N.M   -> a `## §N` / `### §N.M` heading exists (same file, then book-wide)
  Chapter N   -> ch<N> is linked in src/SUMMARY.md
  Appendix X  -> src/appendix-<x>.md exists

Cross-volume (repeatable, NO code edits per book — this is the fix for the
"three edits to check-refs.py" tax in the lessons-learned):
  --cross-vol "NAME=PATH"   register a sibling book's src/ under a citation prefix
        Resolves  "NAME <Type> N.M"  and  "NAME Chapter N"  against that book.
        Abbreviations (Def/Prop/Thm/Cor/Lem/Con) also resolve, so registering
        --cross-vol "V1=../precalculus/src" makes both "V1 Definition 2.1" and
        "V1 Def 2.1" resolve. Register the same path under several names if the
        book is cited both ways:
            --cross-vol "Volume 1=../precalculus/src" --cross-vol "V1=../precalculus/src"

  --label-types "Theorem,Definition,Example,..."   override the label vocabulary
        (add Example here instead of editing the source — the other former edit).

Usage:
    check-refs.py [--label-types ...] [--cross-vol NAME=PATH ...] [FILE ...]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_LABEL_TYPES = ["Theorem", "Definition", "Example", "Proposition",
                       "Lemma", "Corollary", "Construction"]
ABBREV = {"Def": "Definition", "Prop": "Proposition", "Thm": "Theorem",
          "Cor": "Corollary", "Lem": "Lemma", "Con": "Construction"}
EQ_TAG_RE = re.compile(r"\\tag\{(\d+\.\d+)\}")
EQ_REF_RE = re.compile(r"Eq\.\s*\((\d+\.\d+)\)")
SECTION_HEADING_RE = re.compile(r"^#{2,} §(\d+(?:\.\d+)*)", re.MULTILINE)
SECTION_REF_RE = re.compile(r"§(\d+(?:\.\d+)*)")
CHAPTER_REF_RE = re.compile(r"\bChapter (\d+)")
APPENDIX_REF_RE = re.compile(r"\bAppendix ([A-Z])\b")
SUMMARY_CHAPTER_RE = re.compile(r"\(ch0*(\d+)\.md\)")


def labels_in(text: str, types: list[str]) -> set[str]:
    rx = re.compile(r"^### ((?:" + "|".join(types) + r") \d+\.\d+)", re.MULTILINE)
    return set(rx.findall(text))


def chapters_in(summary: Path) -> set[str]:
    return set(SUMMARY_CHAPTER_RE.findall(summary.read_text())) if summary.is_file() else set()


def body(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if not l.startswith("#"))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--label-types", default=",".join(DEFAULT_LABEL_TYPES))
    ap.add_argument("--cross-vol", action="append", default=[], metavar="NAME=PATH")
    ap.add_argument("files", nargs="*")
    args = ap.parse_args(argv)

    types = [t.strip() for t in args.label_types.split(",") if t.strip()]
    label_ref_rx = re.compile(r"\b(?:" + "|".join(types) + r") \d+\.\d+")

    # Cross-volume registries: prefix name -> (label set, chapter set)
    xvol: dict[str, tuple[set[str], set[str]]] = {}
    for spec in args.cross_vol:
        name, _, path = spec.partition("=")
        name, src = name.strip(), Path(path.strip())
        labels: set[str] = set()
        for f in sorted(src.glob("ch*.md")) + sorted(src.glob("appendix-*.md")):
            labels |= labels_in(f.read_text(), types)
        xvol[name] = (labels, chapters_in(src / "SUMMARY.md"))

    files = [Path(f) for f in args.files] or (sorted(Path("src").glob("*.md"))
                                              if Path("src").is_dir() else [])
    if not files:
        print("check-refs: no files"); return 0

    # Book-wide pools.
    glabels, gsections = set(), set()
    for f in Path("src").rglob("*.md") if Path("src").is_dir() else []:
        t = f.read_text()
        glabels |= labels_in(t, types)
        gsections |= set(SECTION_HEADING_RE.findall(t))
    chapters = chapters_in(Path("src/SUMMARY.md"))
    appendices = {m.group(1).upper() for a in Path("src").glob("appendix-*.md")
                  if (m := re.match(r"appendix-(.)\.md", a.name))} if Path("src").is_dir() else set()

    errors = 0
    for f in files:
        if not f.is_file():
            continue
        text = f.read_text()
        b = body(text)
        labels = labels_in(text, types)
        eqs = set(EQ_TAG_RE.findall(text))
        sections = set(SECTION_HEADING_RE.findall(text))
        masked = b  # blank out cross-vol citation spans so internal checks skip them

        # Cross-volume citations first (and mask their spans).
        for name, (xlabels, xchaps) in xvol.items():
            pat = re.compile(re.escape(name) + r"\s+(" + "|".join(types + list(ABBREV)) +
                             r")\s+(\d+\.\d+)")
            for m in pat.finditer(b):
                kind = ABBREV.get(m.group(1), m.group(1))
                key = f"{kind} {m.group(2)}"
                if key not in xlabels:
                    print(f"{f}: unresolved cross-volume reference: {name} {m.group(1)} {m.group(2)}")
                    errors += 1
                masked = masked[:m.start()] + " " * (m.end() - m.start()) + masked[m.end():]
            cpat = re.compile(re.escape(name) + r"\s+Chapter\s+(\d+)")
            for m in cpat.finditer(b):
                if xchaps and m.group(1) not in xchaps:
                    print(f"{f}: unresolved cross-volume reference: {name} Chapter {m.group(1)}")
                    errors += 1
                masked = masked[:m.start()] + " " * (m.end() - m.start()) + masked[m.end():]

        for ref in sorted(set(label_ref_rx.findall(masked))):
            if ref not in labels and ref not in glabels:
                print(f"{f}: unresolved reference: {ref}"); errors += 1
        for tag in sorted(set(EQ_REF_RE.findall(masked))):
            if tag not in eqs:
                print(f"{f}: unresolved equation reference: Eq. ({tag})"); errors += 1
        for sec in sorted(set(SECTION_REF_RE.findall(masked))):
            if sec not in sections and sec not in gsections:
                print(f"{f}: unresolved section reference: §{sec}"); errors += 1
        for n in sorted(set(CHAPTER_REF_RE.findall(masked))):
            if chapters and n not in chapters:
                print(f"{f}: unresolved chapter reference: Chapter {n}"); errors += 1
        for x in sorted(set(APPENDIX_REF_RE.findall(masked))):
            if x not in appendices:
                print(f"{f}: unresolved appendix reference: Appendix {x}"); errors += 1

    if errors:
        print(f"check-refs: {errors} unresolved reference(s)"); return 1
    print("check-refs: all references resolve"); return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
