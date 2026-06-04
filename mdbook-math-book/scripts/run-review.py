#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Set up a chapter review round: snapshot + manifest of agents to dispatch.

The house-style books use a multi-agent review team (math, clarity, voice,
consistency, coverage, source-originality, plus a topic-specific applied
reviewer). This script does NOT run the agents — the controller dispatches them
with the Task tool. It creates docs/reviews/<chapter>/round-<round>/, snapshots
the chapter, and writes manifest.md listing each agent, its prompt template, and
its expected output path.

The roster is **auto-discovered** from docs/review-agents/*-reviewer-prompt.md —
so renaming the applied reviewer per book (applied-physics → applied-trig) needs
no code edit here (the lessons-learned "rename in three places" trap). Any agent
whose name contains "applied" is treated as CONDITIONAL: dispatched only when the
chapter has §Applications or ExamStyle content.

Usage:
    run-review.py <chapter> <round>
    run-review.py ch07 2
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

APPLIED_CONTENT_RE = re.compile(r"(?mi)^##+\s.*Applications\b|examstyle")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: run-review.py <chapter> <round>", file=sys.stderr)
        return 2
    chapter, rnd = argv[0], argv[1]

    src = Path(f"src/{chapter}.md")
    if not src.is_file():
        print(f"Chapter source not found: {src}", file=sys.stderr)
        return 1

    out = Path(f"docs/reviews/{chapter}/round-{rnd}")
    out.mkdir(parents=True, exist_ok=True)
    snapshot = out / "chapter-snapshot.md"
    shutil.copyfile(src, snapshot)

    agents = sorted(p.name[: -len("-prompt.md")]
                    for p in Path("docs/review-agents").glob("*-reviewer-prompt.md"))
    if not agents:
        print("No docs/review-agents/*-reviewer-prompt.md found.", file=sys.stderr)
        return 1

    has_applied = bool(APPLIED_CONTENT_RE.search(src.read_text()))

    rows = ["| Agent | Prompt template | Output path | Dispatch |",
            "|---|---|---|---|"]
    for a in agents:
        conditional = "applied" in a
        dispatch = ("conditional — yes" if conditional and has_applied
                    else "conditional — SKIP" if conditional
                    else "always")
        short = a.replace("-reviewer", "")
        rows.append(f"| {a} | docs/review-agents/{a}-prompt.md | {out}/{short}.md | {dispatch} |")

    manifest = "\n".join([
        f"# Review manifest: {chapter} round {rnd}", "",
        "Controller dispatches each 'always'/'conditional — yes' agent below via the",
        "Task tool. Each reviewer reads CHAPTER_FILE and writes its OUTPUT_PATH with a",
        "`## Verdict: APPROVED|CHANGES_REQUIRED` line and `## Blocking findings` /",
        "`## Non-blocking findings` sections. Then run:", "",
        f"    scripts/aggregate-review.py {chapter} {rnd}", "",
        "## Agents", "", *rows, "",
        "## Dispatch-context substitutions", "",
        f"- CHAPTER_FILE: {snapshot}",
        f"- CHAPTER_ID: {chapter}",
        f"- ROUND: {rnd}",
        "- STYLE_GUIDE: docs/style-guide.md",
        f"- CHAPTER_OUTLINE: docs/outlines/{chapter}-outline.md", "",
        "## Reminders (carry into every fix dispatch)", "",
        "- Fix implementer brief: \"re-read the chapter after your edit and flag",
        "  anything you may have introduced\" — prevents the fix-introduces-new-issue round.",
        "- A chapter is APPROVED iff EVERY agent report has `## Verdict: APPROVED`;",
        "  trust the per-agent verdicts, not the aggregate header's blocking count.",
        "- 3-round cap; escalate to the user with a written root-cause summary if round 3",
        "  does not land.", "",
    ])
    (out / "manifest.md").write_text(manifest)
    print(f"Review round set up at {out}")
    msg = f"  {len(agents)} agents discovered"
    if any("applied" in a for a in agents):
        msg += ("; applied reviewer dispatched" if has_applied
                else "; applied reviewer skipped (no §Applications/ExamStyle)")
    print(msg + ".")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
