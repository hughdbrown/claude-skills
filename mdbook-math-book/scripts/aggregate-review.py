#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Aggregate a round's per-agent review reports into one summary.md.

Reads every docs/reviews/<chapter>/round-<round>/<agent>.md, pulls each agent's
`## Verdict:` line and its `## Blocking findings` / `## Non-blocking findings`
bullets, and writes summary.md.

The verdict is the source of truth, NOT the bullet count. A real lessons-learned
trap: the aggregate header counted `- None.` / `- (empty)` bullets as blocking
findings and reported false CHANGES_REQUIRED. Here APPROVED requires that EVERY
agent report says `## Verdict: APPROVED` *and* there are zero real blocking
bullets; `None.`/`(empty)` placeholder bullets are ignored.

Usage:
    aggregate-review.py <chapter> <round>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

EXCLUDED = {"summary.md", "manifest.md", "chapter-snapshot.md"}
VERDICT_RE = re.compile(r"^## Verdict:\s*(.+?)\s*$")
PLACEHOLDER = ("none.", "(empty)", "none", "n/a")


def parse(text: str) -> tuple[str, list[str], list[str]]:
    verdict, blocking, nonblocking, mode = "UNKNOWN", [], [], None
    for line in text.splitlines():
        if verdict == "UNKNOWN" and (m := VERDICT_RE.match(line)):
            verdict = m.group(1).strip()
        if line.startswith("## Blocking findings"):
            mode = "b"; continue
        if line.startswith("## Non-blocking findings"):
            mode = "n"; continue
        if line.startswith("## "):
            mode = None; continue
        if line.startswith("- ") and line[2:].strip().lower().rstrip(".") not in \
                tuple(p.rstrip(".") for p in PLACEHOLDER):
            (blocking if mode == "b" else nonblocking if mode == "n" else []).append(line)
    return verdict, blocking, nonblocking


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: aggregate-review.py <chapter> <round>", file=sys.stderr)
        return 2
    chapter, rnd = argv[0], argv[1]
    d = Path(f"docs/reviews/{chapter}/round-{rnd}")
    if not d.is_dir():
        print(f"No review directory at {d}", file=sys.stderr)
        return 1

    reports = sorted(p for p in d.glob("*.md") if p.name not in EXCLUDED)
    per_agent, blocking_lines = [], []
    all_approved, blocking_total, nonblocking_total = bool(reports), 0, 0
    for r in reports:
        verdict, blk, nb = parse(r.read_text())
        if verdict != "APPROVED":
            all_approved = False
        blocking_total += len(blk)
        nonblocking_total += len(nb)
        per_agent.append(f"  [{r.stem}] {verdict} — {len(blk)} blocking, {len(nb)} non-blocking")
        blocking_lines += [f"- [{r.stem}] {b}" for b in blk]

    overall = "APPROVED" if (all_approved and blocking_total == 0) else "CHANGES_REQUIRED"
    parts = [f"# Review summary: {chapter} round {rnd}", "",
             f"## Overall: {overall}", "",
             f"- Blocking findings: {blocking_total}",
             f"- Non-blocking findings: {nonblocking_total}",
             f"- All verdicts APPROVED: {all_approved}", "",
             "## Per-agent", "", *per_agent, ""]
    if blocking_lines:
        parts += ["## Blocking issues", "", *blocking_lines, ""]
    parts += ["## Report files", "", *[f"- {r}" for r in reports]]
    (d / "summary.md").write_text("\n".join(parts) + "\n")

    print(f"Summary written to {d / 'summary.md'}")
    print(f"Overall: {overall} ({blocking_total} blocking, {nonblocking_total} non-blocking; "
          f"all-approved={all_approved})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
