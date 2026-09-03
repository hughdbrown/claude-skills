#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["click>=8", "markdown-it-py>=3", "mdit-py-plugins>=0.4"]
# ///
"""Find distinctive sentences a book repeats across files (or within one).

Generated prose regenerates its best lines: the Darwin book's afterword repeated a
Day 6 sentence almost word for word, and three files shared one aphorism. The
Markdown is parsed (mdprose.py); sentences of at least --min-words words are
taken from prose blocks that carry no inline math (the words around math are
templated and repeat legitimately). Reports:

  exact    the same normalized sentence in two files (blocking) or twice in one
  near     two sentences sharing >= --jaccard of their word 5-grams (signal)

Boilerplate every day repeats (header blockquote, "Stuck?", ...) is skipped via
--ignore patterns. Exit 1 on any exact cross-file repeat.
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mdprose  # noqa: E402

SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(])")   # natural-language sentence split
WORD_RE = re.compile(r"[a-z0-9']+")
DEFAULT_IGNORE = [
    r"^today in one line", r"^time:", r"^time \d", r"^you'll need", r"^stuck\?",
    r"^what you learned today", r"^tomorrow", r"^try it", r"^worked example",
    r"^gentle stretch", r"^answers? to every exercise",
]


def sentences(doc: mdprose.Doc, min_words: int, ignore: list[re.Pattern]):
    for b in mdprose.prose_blocks(doc):
        if b.had_math:
            continue
        for s in SENT_SPLIT_RE.split(b.text):
            words = WORD_RE.findall(s.lower())
            if len(words) < min_words:
                continue
            norm = " ".join(words)
            low = s.lower().lstrip("*_ ")
            if any(p.search(norm) or p.search(low) for p in ignore):
                continue
            yield mdprose.locate(doc, b, s), s.strip(), norm, words


def shingles(words: list[str], n: int = 5) -> set[str]:
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


@click.command(help=__doc__)
@click.option("--src", multiple=True, default=("src", "staging"), show_default=True)
@click.option("--min-words", type=int, default=9, show_default=True)
@click.option("--jaccard", type=float, default=0.6, show_default=True)
@click.option("--ignore", multiple=True, help="extra regex (lowercase prose) to skip")
@click.option("--exclude", multiple=True, default=("answers.md",), show_default=True,
              help="file names to skip (answers.md is assembled from staging/)")
def main(src, min_words, jaccard, ignore, exclude) -> None:
    ignore_re = [re.compile(p) for p in DEFAULT_IGNORE + list(ignore)]
    files = sorted(p for d in src for p in Path(d).glob("*.md") if p.is_file() and p.name not in exclude)
    if not files:
        raise click.ClickException("no markdown files found")

    by_norm: dict[str, list[tuple[Path, int, str]]] = defaultdict(list)
    entries: list[tuple[Path, int, str, set[str]]] = []
    for f in files:
        doc = mdprose.parse(f)
        for lineno, raw, norm, words in sentences(doc, min_words, ignore_re):
            by_norm[norm].append((f, lineno, raw))
            entries.append((f, lineno, raw, shingles(words)))

    exact_cross = 0
    for norm, occ in by_norm.items():
        if len(occ) < 2:
            continue
        cross = len({o[0] for o in occ}) > 1
        exact_cross += cross
        click.echo(f"{'EXACT' if cross else 'same-file'}: \"{occ[0][2][:110]}\"")
        for f, ln, _ in occ:
            click.echo(f"    {f}:{ln}")

    near, seen = 0, set()
    for (f1, l1, r1, s1), (f2, l2, r2, s2) in combinations(entries, 2):
        if (f1 == f2 and abs(l1 - l2) < 3) or not s1 or not s2:
            continue
        j = len(s1 & s2) / len(s1 | s2)
        if j >= jaccard and r1.lower() != r2.lower() and (f1, l1, f2, l2) not in seen:
            seen.add((f1, l1, f2, l2)); near += 1
            click.echo(f"near ({j:.2f}): {f1}:{l1}  <->  {f2}:{l2}\n    \"{r1[:100]}\"\n    \"{r2[:100]}\"")

    click.echo(f"self-echo: {len(files)} files, {exact_cross} cross-file exact repeats, {near} near-duplicates")
    sys.exit(1 if exact_cross else 0)


if __name__ == "__main__":
    main()
