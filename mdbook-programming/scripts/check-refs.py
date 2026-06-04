#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["click>=8.1"]
# ///
"""Verify every cross-reference in a programming mdBook resolves. Drift gate.

Renumbering chapters, retitling, and parallel drafting silently break
cross-references; mdbook does not validate them. This checks, per file, against
pools built from all of src/:

  Chapter N    -> chNN is linked in src/SUMMARY.md
  Appendix X   -> src/appendix-<x>.md exists
  §N / §N.M    -> a `## §N` / `### §N.M` heading exists (same file, then book-wide)
  Listing N.M  -> a `### Listing N.M` / `**Listing N.M**` caption exists book-wide
  Figure N.M   -> a `### Figure N.M` / `**Figure N.M**` caption exists book-wide
  Table N.M    -> a `### Table N.M`  / `**Table N.M**`  caption exists book-wide

Also flags broken intra-book Markdown links `[text](chNN.md)` /
`(appendix-x.md)` whose target file does not exist.

    check-refs.py [--label-types "Listing,Figure,Table"] [FILE ...]
"""

from __future__ import annotations

import re
from pathlib import Path

import click

DEFAULT_LABELS = ["Listing", "Figure", "Table"]
CHAPTER_REF_RE = re.compile(r"\bChapter (\d+)")
APPENDIX_REF_RE = re.compile(r"\bAppendix ([A-Z])\b")
SECTION_HEADING_RE = re.compile(r"^#{2,}\s+§(\d+(?:\.\d+)*)", re.MULTILINE)
SECTION_REF_RE = re.compile(r"§(\d+(?:\.\d+)*)")
SUMMARY_CHAPTER_RE = re.compile(r"\(ch0*(\d+)\.md\)")
MD_LINK_RE = re.compile(r"\]\((ch\d+\.md|appendix-[a-z]\.md)(?:#[^)]*)?\)")


def labels_in(text: str, types: list[str]) -> set[str]:
    pat = "|".join(types)
    head = re.compile(rf"^#{{2,}}\s+((?:{pat}) \d+\.\d+)", re.MULTILINE)
    bold = re.compile(rf"\*\*((?:{pat}) \d+\.\d+)\*\*")
    return set(head.findall(text)) | set(bold.findall(text))


def label_refs_in(text: str, types: list[str]) -> set[str]:
    pat = "|".join(types)
    # A reference is a mention NOT immediately wrapped as a caption (no `**`).
    return set(re.findall(rf"\b((?:{pat}) \d+\.\d+)", text))


def body(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


def chapters_in(summary: Path) -> set[str]:
    return set(SUMMARY_CHAPTER_RE.findall(summary.read_text())) if summary.is_file() else set()


@click.command(help=__doc__)
@click.option("--label-types", default=",".join(DEFAULT_LABELS),
              help="comma list of caption label vocabularies to resolve")
@click.argument("files", nargs=-1, type=click.Path())
def main(label_types: str, files: tuple[str, ...]) -> None:
    types = [t.strip() for t in label_types.split(",") if t.strip()]

    src = Path("src")
    if not src.is_dir():
        click.echo("check-refs: no src/ directory")
        return
    paths = [Path(f) for f in files] or sorted(src.glob("*.md"))

    # Book-wide pools.
    glabels, gsections = set(), set()
    for f in src.rglob("*.md"):
        t = f.read_text(encoding="utf-8")
        glabels |= labels_in(t, types)
        gsections |= set(SECTION_HEADING_RE.findall(t))
    chapters = chapters_in(src / "SUMMARY.md")
    appendices = {m.group(1).upper() for a in src.glob("appendix-*.md")
                  if (m := re.match(r"appendix-(.)\.md", a.name))}

    errors = 0
    for f in paths:
        if not f.is_file():
            continue
        text = f.read_text(encoding="utf-8")
        b = body(text)
        sections = set(SECTION_HEADING_RE.findall(text))

        for ref in sorted(label_refs_in(b, types)):
            if ref not in glabels:
                click.echo(f"{f}: unresolved reference: {ref}"); errors += 1
        for sec in sorted(set(SECTION_REF_RE.findall(b))):
            if sec not in sections and sec not in gsections:
                click.echo(f"{f}: unresolved section reference: §{sec}"); errors += 1
        for n in sorted(set(CHAPTER_REF_RE.findall(b))):
            if chapters and n not in chapters:
                click.echo(f"{f}: unresolved chapter reference: Chapter {n}"); errors += 1
        for x in sorted(set(APPENDIX_REF_RE.findall(b))):
            if x not in appendices:
                click.echo(f"{f}: unresolved appendix reference: Appendix {x}"); errors += 1
        for target in sorted(set(MD_LINK_RE.findall(text))):
            if not (src / target).exists():
                click.echo(f"{f}: broken link to missing file: {target}"); errors += 1

    if errors:
        click.echo(f"check-refs: {errors} unresolved reference(s)")
        raise SystemExit(1)
    click.echo("check-refs: all references resolve")


if __name__ == "__main__":
    main()
