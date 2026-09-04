#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["click>=8", "markdown-it-py>=3", "mdit-py-plugins>=0.4"]
# ///
"""Measure each day's size against the book's baseline and the 30-minute promise.

Per src/dayNN.md (parsed with mdprose.py): prose words, display-math blocks,
worked examples (admonish example), other callouts, ordered exercises under the
heading that starts with --exercise-heading, figures, and whether the day has a
"Gentle stretch" exercise and a "Stuck?" box. The baseline is the median day
(or --exemplar dayNN). A day is flagged when its words or worked examples exceed
--max-ratio times the baseline, its exercise count leaves the baseline by more
than --exercise-slack, or it lacks a Gentle stretch / Stuck? box that most days
in the book have.

The Sequences and Series review found two days at 1.3x the Day 1 baseline that
would have blown the 30-minute budget; nothing else in the gate measured it.
"""
from __future__ import annotations

import statistics
import sys
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mdprose  # noqa: E402


def measure(path: Path, exercise_heading: str) -> dict:
    doc = mdprose.parse(path)
    under = doc.under_heading(lambda h: h.lower().startswith(exercise_heading.lower()))
    exercises = [b for b in under if b.kind == "list_item" and b.list_index is not None]
    if not exercises:   # item books pull each drill in with an mdBook include directive
        exercises = [b for b in under if b.text.startswith("{{#include") and "problem" in b.text]
    return {
        "day": path.stem,
        "words": doc.prose_words(),
        "display": doc.math_blocks,
        "examples": sum(a.kind == "example" for a in doc.admonish),
        "callouts": sum(a.kind != "example" for a in doc.admonish),
        "exercises": len(exercises),
        "figures": len(doc.figures),
        "stretch": any("gentle stretch" in b.text.lower() for b in under),
        "stuck": any("stuck" in a.title.lower() for a in doc.admonish),
    }


@click.command(help=__doc__)
@click.option("--src", default="src", show_default=True)
@click.option("--exemplar", default=None, help="baseline day (dayNN); default is the median day")
@click.option("--max-ratio", type=float, default=1.3, show_default=True)
@click.option("--exercise-slack", type=int, default=2, show_default=True)
@click.option("--exercise-heading", default="Try it", show_default=True,
              help="the exercises section heading starts with this text")
def main(src, exemplar, max_ratio, exercise_slack, exercise_heading) -> None:
    days = sorted(Path(src).glob("day[0-9][0-9].md"))
    if not days:
        raise click.ClickException(f"no dayNN.md under {src}")
    rows = [measure(p, exercise_heading) for p in days]
    if exemplar:
        ex = next((r for r in rows if r["day"] == exemplar), rows[0])
    else:
        ex = {"day": "median", **{k: statistics.median(r[k] for r in rows) for k in ("words", "examples", "exercises")}}
    most_stretch = sum(r["stretch"] for r in rows) > len(rows) / 2
    most_stuck = sum(r["stuck"] for r in rows) > len(rows) / 2

    click.echo(f"{'day':<6}{'words':>7}{'ratio':>7}{'ex.':>5}{'call':>6}{'exer':>6}{'fig':>5}  flags")
    failures = 0
    for r in rows:
        ratio = r["words"] / ex["words"] if ex["words"] else 0
        flags = []
        if ratio > max_ratio:
            flags.append(f"words {ratio:.2f}x baseline")
        if ex["examples"] and r["examples"] > max_ratio * ex["examples"]:
            flags.append(f"{r['examples']} worked examples vs {ex['examples']:.0f}")
        if abs(r["exercises"] - ex["exercises"]) > exercise_slack:
            flags.append(f"{r['exercises']} exercises vs {ex['exercises']:.0f}")
        if most_stretch and not r["stretch"]:
            flags.append("no Gentle stretch")
        if most_stuck and not r["stuck"]:
            flags.append("no Stuck? box")
        if r["exercises"] == 0:
            flags.append("no exercises found (check --exercise-heading)")
        failures += bool(flags)
        click.echo(f"{r['day']:<6}{r['words']:>7}{ratio:>7.2f}{r['examples']:>5}{r['callouts']:>6}"
                   f"{r['exercises']:>6}{r['figures']:>5}  {'; '.join(flags)}")
    click.echo(f"pacing-audit: {len(rows)} days, baseline {ex['day']} = {ex['words']:.0f} words, "
               f"{ex['examples']:.0f} examples, {ex['exercises']:.0f} exercises; {failures} flagged")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
