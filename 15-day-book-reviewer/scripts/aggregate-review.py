#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["click>=8", "markdown-it-py>=3", "mdit-py-plugins>=0.4"]
# ///
"""Roll a round's per-dispatch reports into summary.md, with a per-file fix list.

Reads docs/reviews/round-<N>/manifest.json for the expected reports, parses each
report as Markdown (mdprose.py): the `## Verdict: ...` heading, and the list
items under `## Blocking findings` / `## Non-blocking findings`. Placeholder
bullets (`None.`) are ignored — the documented false-CHANGES_REQUIRED trap.

Overall verdict: APPROVED iff every report from a *blocking* dispatch says
APPROVED and carries no real blocking bullet. Non-blocking lenses are listed
but cannot fail the round. A missing report, or one without a Verdict heading,
counts as CHANGES_REQUIRED: an agent that did not report did not review.

Blocking bullets are grouped by the file they cite, which is the fix work
list. Exit 1 unless APPROVED.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mdprose  # noqa: E402

FILE_RE = re.compile(r"((?:src|staging|figures)/[\w./-]+?\.(?:md|typ|svg))")   # a path cited inside prose
PLACEHOLDER = {"none", "(empty)", "n/a", "nothing"}


def parse_report(path: Path) -> tuple[str, list[str], list[str]]:
    doc = mdprose.parse(path)
    verdict = "MISSING"
    for h in doc.headings:
        if h.level == 2 and h.text.lower().startswith("verdict:"):
            v = h.text.split(":", 1)[1].strip().upper()
            verdict = "APPROVED" if v.startswith("APPROVED") else "CHANGES_REQUIRED" if v else "MISSING"
            break
    def items(section: str) -> list[str]:   # top-level bullets only; plain keeps `paths` and $math$
        return [b.plain for b in doc.under_heading(lambda h: h.lower().startswith(section))
                if b.kind == "list_item" and b.list_depth == 1
                and b.text.strip().lower().rstrip(".") not in PLACEHOLDER]
    blocking, nonblocking = items("blocking findings"), items("non-blocking findings")
    return verdict, blocking, nonblocking


@click.command(help=__doc__)
@click.option("--round", "rnd", type=int, required=True)
def main(rnd: int) -> None:
    d = Path(f"docs/reviews/round-{rnd}")
    manifest = d / "manifest.json"
    if not manifest.is_file():
        raise click.ClickException(f"no {manifest}; run run-review.py first")
    m = json.loads(manifest.read_text())

    expected: list[tuple[str, Path, bool]] = []
    for disp in m["dispatches"]:
        if disp["kind"] == "agent":
            expected.append((disp["lens"], Path(disp["output"]), disp["blocking"]))
        else:  # a script lane writes one report per day; pick up whatever exists
            expected += [(disp["lens"], p, False) for p in sorted(d.glob(f"{disp['lens']}--*.md"))]

    per, by_file, all_ok = [], defaultdict(list), True
    n_block = n_non = 0
    for lens, path, is_blocking in expected:
        verdict, blk, nb = parse_report(path) if path.is_file() else ("MISSING", [], [])
        ok = verdict == "APPROVED" and not blk
        if is_blocking and not ok:
            all_ok = False
        n_block += len(blk); n_non += len(nb)
        per.append(f"- [{path.stem}] {verdict} — {len(blk)} blocking, {len(nb)} non-blocking"
                   + ("" if is_blocking else " (non-blocking lens)"))
        for b in blk:
            hit = FILE_RE.search(b)
            by_file[hit.group(1) if hit else "(no file cited)"].append(f"[{path.stem}] {b}")

    overall = "APPROVED" if all_ok else "CHANGES_REQUIRED"
    parts = [f"# Review summary: round {rnd}", "", f"## Overall: {overall}", "",
             f"- Dispatches expected: {len(expected)}", f"- Blocking findings: {n_block}",
             f"- Non-blocking findings: {n_non}", "", "## Per-dispatch", "", *per, ""]
    if by_file:
        parts += ["## Blocking findings by file (fix work list)", ""]
        for f, items in sorted(by_file.items()):
            parts += [f"### {f}", ""] + [f"- {i}" for i in items] + [""]
    (d / "summary.md").write_text("\n".join(parts))
    click.echo(f"round {rnd}: {overall} — {n_block} blocking across {len(by_file)} files; see {d}/summary.md")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
