#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["click>=8.1"]
# ///
"""Audit a programming mdBook's Markdown SOURCE for failure modes that ship green.

A clean `mdbook build` does NOT catch any of these — they render wrong, drop in
the PDF, or quietly disable a chapter:

  fences      odd number of ``` / ~~~ in a file        -> broken admonish/code block
  inline-code a long (> N line) fenced Go/Python/Rust   -> violates "code lives in
              block that is NOT an {{#include}}            files, not prose" (this is
                                                            the book style's core rule)
  unicode     literal box-drawing/arrow/curly-quote      -> "Missing character" in the
              glyphs the xelatex font lacks                 xelatex PDF
  artifacts   leaked subagent tool tags                  -> parallel-authoring debris
  placeholder TODO / TBD / FIXME / lorem ipsum / ???     -> unfinished prose
  british     British spelling in prose (colour, behaviour, -ise, ...)
                                                         -> house style is American English
  summary     every src/**/*.md is listed in SUMMARY.md  -> mdbook silently skips it
              (source-excerpts/ and samples/ excepted)

Each `--no-<check>` flag disables one check. `--max-inline-lines` (default 6)
tunes the inline-code gate; raise it for a book that shows many short shells.

Usage:
    chapter-audit.py [FILE ...]            # default: src/**/*.md
    chapter-audit.py --no-unicode src/ch04.md
"""

from __future__ import annotations

import re
from pathlib import Path

import click

PLACEHOLDERS = ("TODO", "TBD", "FIXME", "placeholder", "lorem ipsum", "???")
ARTIFACTS = ("</content>", "</invoke>", "<parameter", "antml:", "<function")
# Glyphs the STIX/Palatino + Menlo xelatex stack drops or warns on in prose.
# Box-drawing chars ARE allowed inside fenced blocks (Menlo has them) — we only
# flag them in prose. Curly quotes/dashes are fine in prose with most mainfonts,
# so they are NOT flagged here; arrows and math superscripts in prose are.
BAD_UNICODE_PROSE = "→←⇒⇐²³½¼ˣ"
CODE_LANGS = {"go", "golang", "python", "py", "python3", "rust", "rs"}
INCLUDE_RE = re.compile(r"\{\{#(?:include|rustdoc_include|playground)\s")
FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})([^\n\r]*)$")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")


def _british_dict() -> dict[str, str]:
    """British -> American spellings to flag in prose. Explicit forms only — a
    blanket -ise/-our rule would mis-flag American words (exercise, four). These
    are stems known to be genuinely British so the generated inflections (incl.
    ones that never occur, e.g. a rare -iser) cannot create false positives."""
    out: dict[str, str] = {}
    # -ise/-isation verbs that are -ize/-ization in American English.
    ize_stems = [
        "initial", "serial", "deserial", "normal", "optim", "synchron", "organ",
        "priorit", "custom", "capital", "summar", "recogn", "minim", "maxim",
        "util", "visual", "author", "categor", "emphas", "special", "general",
        "central", "standard", "modular", "token", "parameter", "container",
    ]
    for stem in ize_stems:
        for sb, sa in (("ise", "ize"), ("ised", "ized"), ("ises", "izes"),
                       ("ising", "izing"), ("isation", "ization"),
                       ("iser", "izer"), ("isers", "izers")):
            out[stem + sb] = stem + sa
    # -yse verbs -> -yze.
    for stem in ["anal", "paral", "catal"]:
        for sb, sa in (("yse", "yze"), ("ysed", "yzed"), ("yses", "yzes"),
                       ("ysing", "yzing")):
            out[stem + sb] = stem + sa
    # Explicit irregulars / -our / -re / -ence / misc.
    out.update({
        "colour": "color", "colours": "colors", "coloured": "colored",
        "colouring": "coloring", "colourful": "colorful",
        "behaviour": "behavior", "behaviours": "behaviors",
        "behavioural": "behavioral",
        "favour": "favor", "favours": "favors", "favoured": "favored",
        "favourite": "favorite", "favourites": "favorites",
        "labour": "labor", "neighbour": "neighbor", "neighbours": "neighbors",
        "honour": "honor", "flavour": "flavor", "flavours": "flavors",
        "rumour": "rumor", "harbour": "harbor", "endeavour": "endeavor",
        "centre": "center", "centres": "centers", "centred": "centered",
        "metre": "meter", "metres": "meters", "litre": "liter", "litres": "liters",
        "fibre": "fiber", "fibres": "fibers", "calibre": "caliber",
        "licence": "license", "licences": "licenses",
        "defence": "defense", "offence": "offense",
        "catalogue": "catalog", "catalogues": "catalogs",
        "cancelled": "canceled", "cancelling": "canceling",
        "labelled": "labeled", "labelling": "labeling",
        "modelled": "modeled", "modelling": "modeling",
        "travelled": "traveled", "travelling": "traveling",
        "traveller": "traveler", "signalled": "signaled", "signalling": "signaling",
        "marshalled": "marshaled", "marshalling": "marshaling",
        "grey": "gray", "greyscale": "grayscale", "maths": "math",
        "whilst": "while", "amongst": "among", "learnt": "learned",
        "spelt": "spelled", "programme": "program", "programmes": "programs",
        "artefact": "artifact", "artefacts": "artifacts",
        "enquire": "inquire", "enquiry": "inquiry", "enquiries": "inquiries",
        "judgement": "judgment", "acknowledgement": "acknowledgment",
        "dependant": "dependent", "grey-scale": "gray-scale",
    })
    return out


BRITISH = _british_dict()


def fence_lang(info: str) -> str:
    # Fence info is space- or comma-separated: `go no-check`, `rust,compile_fail`.
    toks = [t for t in re.split(r"[\s,]+", info.strip()) if t]
    return toks[0].lower() if toks else ""


def audit_file(path: Path, checks: set[str], max_inline: int) -> list[str]:
    errs: list[str] = []
    lines = path.read_text(encoding="utf-8").splitlines()

    if "artifacts" in checks:
        for n, ln in enumerate(lines, 1):
            for tag in ARTIFACTS:
                if tag in ln:
                    errs.append(f"{path}:{n}: leaked tool-call artifact '{tag}'")

    if "placeholder" in checks:
        low = "\n".join(lines).lower()
        for p in PLACEHOLDERS:
            if p.lower() in low:
                errs.append(f"{path}: placeholder text '{p}'")

    in_fence = False
    fence_char = ""
    fence_len = 0
    fence_lang_cur = ""
    fence_start = 0
    body: list[str] = []
    fence_count = 0

    for n, ln in enumerate(lines, 1):
        m = FENCE_RE.match(ln)
        if not in_fence and m:
            fence_count += 1
            in_fence = True
            fence_char, fence_len = m.group(1)[0], len(m.group(1))
            fence_lang_cur = fence_lang(m.group(2))
            fence_start, body = n, []
            continue
        if in_fence and re.match(rf"^[ \t]*{re.escape(fence_char)}{{{fence_len},}}[ \t]*$", ln):
            fence_count += 1
            if "inline-code" in checks and fence_lang_cur in CODE_LANGS:
                joined = "\n".join(body)
                nonblank = [b for b in body if b.strip()]
                if not INCLUDE_RE.search(joined) and len(nonblank) > max_inline:
                    errs.append(
                        f"{path}:{fence_start}: inline {fence_lang_cur} block "
                        f"({len(nonblank)} lines) is not an {{#include}} — move it to a "
                        "file (or mark the fence `no-check` for a deliberate fragment)")
            in_fence = False
            continue
        if in_fence:
            body.append(ln)
            continue
        # prose line — strip inline code spans so code identifiers aren't judged.
        prose = re.sub(r"`[^`]*`", "", ln) if ("unicode" in checks or "british" in checks) else ln
        if "unicode" in checks:
            for ch in prose:
                if ch in BAD_UNICODE_PROSE:
                    errs.append(f"{path}:{n}: literal Unicode '{ch}' in prose "
                                "(drops in the xelatex PDF)")
                    break
        if "british" in checks:
            seen: set[str] = set()
            for word in WORD_RE.findall(prose):
                am = BRITISH.get(word.lower())
                if am and word.lower() not in seen:
                    seen.add(word.lower())
                    errs.append(f"{path}:{n}: British spelling '{word}' in prose "
                                f"— use American '{am}' (house style is American English)")

    if "fences" in checks and fence_count % 2:
        errs.append(f"{path}: odd number of code fences (unterminated block)")
    return errs


def audit_summary(src: Path) -> list[str]:
    summary = src / "SUMMARY.md"
    if not summary.exists():
        return []
    listed = summary.read_text(encoding="utf-8")
    out = []
    for f in sorted(src.glob("*.md")):
        if f.name == "SUMMARY.md":
            continue
        if f"({f.name})" not in listed:
            out.append(f"{f}: not listed in SUMMARY.md (mdbook will silently skip it)")
    return out


ALL_CHECKS = ("fences", "inline-code", "unicode", "artifacts", "placeholder",
              "british", "summary")


@click.command(help=__doc__)
@click.argument("files", nargs=-1, type=click.Path())
@click.option("--max-inline-lines", default=6, type=int,
              help="inline checked-language blocks longer than this must be externalized")
@click.option("--no-fences", is_flag=True, help="skip the fences check")
@click.option("--no-inline-code", is_flag=True, help="skip the inline-code check")
@click.option("--no-unicode", is_flag=True, help="skip the unicode check")
@click.option("--no-artifacts", is_flag=True, help="skip the artifacts check")
@click.option("--no-placeholder", is_flag=True, help="skip the placeholder check")
@click.option("--no-british", is_flag=True, help="skip the British-spelling check")
@click.option("--no-summary", is_flag=True, help="skip the summary check")
def main(files: tuple[str, ...], max_inline_lines: int, no_fences: bool,
         no_inline_code: bool, no_unicode: bool, no_artifacts: bool,
         no_placeholder: bool, no_british: bool, no_summary: bool) -> None:
    disabled = {
        "fences": no_fences, "inline-code": no_inline_code, "unicode": no_unicode,
        "artifacts": no_artifacts, "placeholder": no_placeholder,
        "british": no_british, "summary": no_summary,
    }
    checks = {c for c in ALL_CHECKS if not disabled[c]}

    if files:
        paths = [Path(f) for f in files]
    else:
        # Top-level chapter prose only; excerpt/sample trees are code, not prose.
        paths = sorted(Path("src").glob("*.md"))
    if not paths:
        raise SystemExit("chapter-audit: no files found")

    errs: list[str] = []
    for f in paths:
        errs += audit_file(f, checks, max_inline_lines)
    if "summary" in checks and not files:
        errs += audit_summary(Path("src"))

    if errs:
        click.echo("\n".join(errs))
        click.echo(f"chapter-audit: FAIL ({len(errs)} issue(s)).")
        raise SystemExit(1)
    click.echo("chapter-audit: OK")


if __name__ == "__main__":
    main()
