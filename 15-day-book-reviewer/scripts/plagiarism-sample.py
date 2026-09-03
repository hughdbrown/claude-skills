#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["click>=8", "markdown-it-py>=3", "mdit-py-plugins>=0.4"]
# ///
"""Pick the sentences most worth searching on the web, and list every quotation.

An originality reviewer cannot search every sentence. From the parsed prose
(mdprose.py) this picks, per file, the --per-file most *distinctive* sentences:
12-28 words, no math, no digits, and the lowest share of common words, which is
where a lifted sentence would show. It also lists every quoted span of
--quote-words or more words so the reviewer can confirm each has an attribution
nearby (the Darwin book once handed the source's sentence back with three words
swapped and no quotation marks).

Writes a Markdown checklist the reviewer works through with WebSearch, one
exact-phrase query per sentence. No network access here.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mdprose  # noqa: E402

SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(])")
QUOTE_RE = re.compile(r"[\"“]([^\"”]{20,}?)[\"”]")
WORD_RE = re.compile(r"[A-Za-z']+")
STOP = set("""a an the and or but of to in on at by for with from as is are was were be been
being it its this that these those there here you your we our i he she they them his her
their not no so if then than when which who what how why do does did done have has had
can could will would should may might must into out up down over under about more most
very just also only one two all any some such each other same own too now""".split())


@click.command(help=__doc__)
@click.option("--src", default="src", show_default=True)
@click.option("--per-file", type=int, default=3, show_default=True)
@click.option("--quote-words", type=int, default=8, show_default=True)
@click.option("--out", type=click.Path(path_type=Path), default=None, help="write the checklist here")
def main(src, per_file, quote_words, out) -> None:
    files = sorted(p for p in Path(src).glob("*.md") if p.name not in ("SUMMARY.md", "answers.md"))
    lines = ["# Plagiarism samples", "",
             "For each sentence: WebSearch the exact phrase in quotes. Record the top hit and",
             "whether it is a match, a paraphrase, or clean. A hit on the author's own",
             "published sibling book is clean; a hit on any other text is a finding.", ""]
    quotes = ["## Quotations to verify attribution", ""]
    n_samples = n_quotes = 0
    for f in files:
        doc = mdprose.parse(f)
        cands = []
        for b in mdprose.prose_blocks(doc):
            if b.had_math:
                continue
            for s in SENT_SPLIT_RE.split(b.text):
                s = s.strip()
                words = WORD_RE.findall(s)
                if not (12 <= len(words) <= 28) or any(ch.isdigit() for ch in s):
                    continue
                rare = sum(w.lower() not in STOP for w in words) / len(words)
                cands.append((rare, mdprose.locate(doc, b, s), s))
            for m in QUOTE_RE.finditer(b.text):
                if len(m.group(1).split()) >= quote_words:
                    n_quotes += 1
                    quotes.append(f"- [ ] `{f}:{mdprose.locate(doc, b, m.group(1))}` — \"{m.group(1)[:120]}\"")
        cands.sort(reverse=True)
        if cands[:per_file]:
            lines.append(f"## {f}")
            for _, ln, s in cands[:per_file]:
                n_samples += 1
                lines.append(f"- [ ] `{f}:{ln}` — \"{s}\"")
            lines.append("")
    body = "\n".join(lines + [""] + quotes + [""])
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(body)
        click.echo(f"wrote {out}: {n_samples} sentences to search, {n_quotes} quotations to verify")
    else:
        click.echo(body)


if __name__ == "__main__":
    main()
