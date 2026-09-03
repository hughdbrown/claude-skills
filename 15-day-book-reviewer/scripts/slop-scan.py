#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["click>=8", "markdown-it-py>=3", "mdit-py-plugins>=0.4"]
# ///
"""Scan a 15-day book's prose for AI-slop phrases and structural tics.

The Markdown is parsed (mdprose.py); only prose blocks are scanned, so code
fences, display math, inline math, and admonish wrappers never produce hits.
Phrases come from slop-phrases.txt (or --phrases) in three tiers:

  blocking  one hit is a finding (the style guide's forbidden list)
  soft      a structural tic; blocking only when clustered (>= --cluster hits
            in one file), otherwise a signal
  note      a teaching move the series uses on purpose; counted, never blocking

Also reports em-dash density per file (dashes per 100 prose words) when it
exceeds --dash-rate. Exit 1 if any blocking finding exists.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mdprose  # noqa: E402


def load_phrases(path: Path) -> dict[str, list[re.Pattern]]:
    groups: dict[str, list[re.Pattern]] = {"blocking": [], "soft": [], "note": []}
    current = "blocking"
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip().lower()
            groups.setdefault(current, [])
            continue
        groups[current].append(re.compile(line, re.IGNORECASE))
    return groups


def scan_file(path: Path, groups: dict[str, list[re.Pattern]], cluster: int) -> dict:
    doc = mdprose.parse(path)
    hits: dict[str, list[dict]] = {"blocking": [], "soft": [], "note": []}
    for b in mdprose.prose_blocks(doc, include_headings=True):
        for cls, pats in groups.items():
            for pat in pats:
                for m in pat.finditer(b.text):
                    # anchors like ^ apply to the block, i.e. a sentence opener
                    hits.setdefault(cls, []).append(
                        {"line": mdprose.locate(doc, b, m.group(0)), "match": m.group(0), "pattern": pat.pattern})
    words = doc.prose_words()
    dashes = sum(b.text.count("—") for b in doc.blocks)
    soft = sorted(hits["soft"], key=lambda h: h["line"])
    return {"file": str(path), "words": words,
            "dash_rate": round(100.0 * dashes / words, 2) if words else 0.0,
            "blocking": sorted(hits["blocking"], key=lambda h: h["line"]),
            "soft": soft, "soft_clustered": len(soft) >= cluster,
            "note": sorted(hits["note"], key=lambda h: h["line"])}


@click.command(help=__doc__)
@click.option("--src", multiple=True, default=("src", "staging"), show_default=True,
              help="directories whose *.md files are scanned")
@click.option("--phrases", type=click.Path(exists=True, path_type=Path),
              default=Path(__file__).with_name("slop-phrases.txt"), show_default=True)
@click.option("--cluster", type=int, default=3, show_default=True, help="soft hits per file that block")
@click.option("--dash-rate", type=float, default=1.5, show_default=True, help="em-dashes per 100 words to flag")
@click.option("--json", "as_json", is_flag=True, help="emit JSON results before the text report")
def main(src: tuple[str, ...], phrases: Path, cluster: int, dash_rate: float, as_json: bool) -> None:
    groups = load_phrases(phrases)
    files = sorted(p for d in src for p in Path(d).glob("*.md") if p.is_file())
    if not files:
        raise click.ClickException("no markdown files found under " + ", ".join(src))
    results = [scan_file(p, groups, cluster) for p in files]
    if as_json:
        click.echo(json.dumps(results, indent=2))
    n_block = 0
    for r in results:
        blocking = list(r["blocking"]) + (r["soft"] if r["soft_clustered"] else [])
        n_block += len(blocking)
        if not blocking and not r["soft"] and not r["note"] and r["dash_rate"] <= dash_rate:
            continue
        click.echo(f"== {r['file']}  ({r['words']} words, {r['dash_rate']} em-dashes/100w)")
        for h in r["blocking"]:
            click.echo(f"  BLOCK  {r['file']}:{h['line']}  \"{h['match']}\"")
        tag = "BLOCK" if r["soft_clustered"] else "soft "
        for h in r["soft"]:
            click.echo(f"  {tag}  {r['file']}:{h['line']}  \"{h['match']}\"")
        for h in r["note"]:
            click.echo(f"  note   {r['file']}:{h['line']}  \"{h['match']}\"")
        if r["dash_rate"] > dash_rate:
            click.echo(f"  signal em-dash density {r['dash_rate']}/100 words exceeds {dash_rate}")
    total_soft = sum(len(r["soft"]) for r in results)
    total_note = sum(len(r["note"]) for r in results)
    click.echo(f"slop-scan: {len(files)} files, {n_block} blocking, {total_soft} soft, {total_note} note hits")
    sys.exit(1 if n_block else 0)


if __name__ == "__main__":
    main()
