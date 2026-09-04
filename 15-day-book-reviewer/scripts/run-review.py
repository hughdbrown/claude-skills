#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["click>=8", "markdown-it-py>=3", "mdit-py-plugins>=0.4"]
# ///
"""Set up a book-level review round: snapshot, feature detection, and a manifest.

A 15-day round reviews the whole book at once with lenses chunked per
roster.toml: correctness per day-pair, voice/level per day-triple, the
cross-cutting lenses once over the whole book. This script does NOT dispatch
agents; the controller does, from the manifest, in one parallel batch.

Creates docs/reviews/round-<N>/ with:
  snapshot/               src/*.md and staging/*.md as reviewed (git rev noted)
  manifest.json           machine-readable dispatch list (aggregate-review reads it)
  manifest.md             the same, for humans
  contract.md             the substitutions every reviewer prompt receives
  scans/                  output of the deterministic scanners
  plagiarism-samples.md   the originality checklist
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.request
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mdprose  # noqa: E402

HERE = Path(__file__).resolve().parent
QUOTE_RE = re.compile(r"[\"“][^\"”]{40,}[\"”]")   # natural-language quotation, on prose text


def git_rev() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "no-git"


def lan_alive(host: str) -> bool:
    try:
        with urllib.request.urlopen(host.rstrip("/") + "/api/tags", timeout=3):
            return True
    except Exception:
        return False


def chunk_days(days: list[str], how: str) -> list[list[str]]:
    size = {"day": 1, "pair": 2, "triple": 3}.get(how)
    return [days] if size is None else [days[i:i + size] for i in range(0, len(days), size)]


@click.command(help=__doc__)
@click.option("--round", "rnd", type=int, required=True, help="round number")
@click.option("--roster", type=click.Path(exists=True, path_type=Path), default=HERE / "roster.toml", show_default=True)
@click.option("--days", default=None, help="comma-separated subset, e.g. day03,day04 (re-review after fixes)")
@click.option("--skip-scans", is_flag=True)
@click.option("--frontback/--no-frontback", default=None,
              help="review front/back matter as its own chunk (default: yes on a full round, no with --days)")
@click.option("--lan-host", default="http://10.0.0.222:11434", show_default=True)
@click.option("--exercise-heading", default=None, help="forwarded to pacing-audit (e.g. Drill for an item book)")
@click.option("--echo-exclude", multiple=True,
              help="file names self-echo should skip (compilation pages that repeat day text by design)")
def main(rnd: int, roster: Path, days: str | None, skip_scans: bool, frontback: bool | None, lan_host: str,
         exercise_heading: str | None, echo_exclude: tuple[str, ...]) -> None:
    src = Path("src")
    all_days = sorted(p.stem for p in src.glob("day[0-9][0-9].md"))
    if not all_days:
        raise click.ClickException("no src/dayNN.md found; run from the book root")
    day_list = days.split(",") if days else all_days
    # front/back matter = every src page that is not a day and not the table of contents
    extras = sorted(p.stem for p in src.glob("*.md") if p.stem not in all_days and p.name != "SUMMARY.md")
    do_frontback = (days is None) if frontback is None else frontback

    lenses = tomllib.loads(roster.read_text())["lens"]
    out = Path(f"docs/reviews/round-{rnd}")
    (out / "snapshot").mkdir(parents=True, exist_ok=True)
    (out / "scans").mkdir(exist_ok=True)
    for d in ("src", "staging"):
        for p in Path(d).glob("*.md"):
            shutil.copyfile(p, out / "snapshot" / f"{d}--{p.name}")

    docs = [mdprose.parse(src / f"{d}.md") for d in all_days]
    features = {
        "if-math": any(doc.math_blocks or any(b.had_math for b in doc.blocks) for doc in docs),
        "if-figures": any(doc.figures for doc in docs) or any(Path("figures").rglob("*.typ")),
        "if-quotes": any(QUOTE_RE.search(b.text) for doc in docs for b in doc.blocks),
        "if-topic-prompt": Path("docs/review-agents").is_dir() and any(Path("docs/review-agents").glob("*.md")),
        "if-lan": lan_alive(lan_host),
        "always": True,
    }

    items_dir = Path("src/problems")          # item books keep each question in its own directory
    rec = ["--recursive"] if items_dir.is_dir() else []
    scans_note = []
    if not skip_scans:
        pacing = ["--exercise-heading", exercise_heading] if exercise_heading else []
        echo = rec + [a for f in echo_exclude for a in ("--exclude", f)]
        for script, extra in (("slop-scan.py", rec), ("self-echo.py", echo), ("pacing-audit.py", pacing),
                              ("plagiarism-sample.py", rec + ["--out", str(out / "plagiarism-samples.md")])):
            res = subprocess.run([sys.executable, str(HERE / script), *extra], capture_output=True, text=True)
            (out / "scans" / script.replace(".py", ".txt")).write_text(res.stdout + res.stderr)
            scans_note.append(f"- {script}: exit {res.returncode} -> scans/{script.replace('.py', '.txt')}")

    dispatches: list[dict] = []
    skipped: list[str] = []
    for name, cfg in lenses.items():
        cond = cfg.get("when", "always")
        if not features.get(cond, False):
            skipped.append(f"{name} ({cond} false)"); continue
        if cfg["model"] == "local":
            dispatches.append({"n": len(dispatches) + 1, "lens": name, "kind": "script", "model": "local",
                               "blocking": False, "files": [f"src/{d}.md" for d in day_list],
                               "output": f"{out}/{name}--dayNN.md",
                               "command": f"scripts/{name}.py {' '.join(day_list)} --round {rnd}"})
            continue
        chunks: list[tuple[str, list[str]]] = []
        if cfg["chunk"] == "book":
            chunks.append(("book", [f"src/{d}.md" for d in all_days] + [f"src/{e}.md" for e in extras]))
        else:
            for ch in chunk_days(day_list, cfg["chunk"]):
                files = [f"src/{d}.md" for d in ch]
                files += [f"staging/{d}-answers.md" for d in ch if Path(f"staging/{d}-answers.md").exists()]
                files += [f"src/problems/{d}/" for d in ch if (items_dir / d).is_dir()]
                chunks.append(("+".join(ch), files))
            if do_frontback and cfg["chunk"] != "day" and extras:
                # its own dispatch, so a re-review of touched days can approve on its own
                chunks.append(("frontback", [f"src/{e}.md" for e in extras if e != "answers"]))
        for label, files in chunks:
            dispatches.append({"n": len(dispatches) + 1, "lens": name, "kind": "agent", "model": cfg["model"],
                               "blocking": bool(cfg["blocking"]), "files": files,
                               "output": f"{out}/{name}--{label}.md", "brief": f"LENSES.md#{cfg['prompt']}"})
    (out / "manifest.json").write_text(json.dumps(
        {"round": rnd, "days": day_list, "features": features, "dispatches": dispatches, "skipped": skipped}, indent=2))

    rows = ["| # | Lens | Model | Blocking | Files | Output | Brief |", "|---|---|---|---|---|---|---|"]
    for d in dispatches:
        brief = d.get("brief") or f"run `{d['command']}` in the background"
        rows.append(f"| {d['n']} | {d['lens']} | {d['model'] if d['kind'] == 'agent' else 'script'} | "
                    f"{'yes' if d['blocking'] else 'no'} | {' '.join(d['files'])} | {d['output']} | {brief} |")
    for s in skipped:
        rows.append(f"| – | {s} | – | – | SKIPPED | – | – |")

    background = Path("docs/reviews/assumed-background.md")   # the controller's addition survives re-runs
    (out / "contract.md").write_text("\n".join([
        f"# Review contract: round {rnd}", "",
        f"- BOOK_ROOT: {Path.cwd()}", f"- GIT_REV: {git_rev()}", f"- ROUND: {rnd}",
        f"- DAYS: {', '.join(day_list)}", f"- FRONT_BACK: {', '.join(extras)}",
        "- PLAN: PLAN.md (conventions, day table, assumed background)",
        "- BRIEF: docs/design/prompt.md (originating request, if present)",
        "- STYLE: docs/style-guide.md (if present) else the conventions section of PLAN.md",
        "- EXEMPLAR: src/day01.md (voice and shape baseline)",
        f"- SCANS: {out}/scans/ (slop-scan, self-echo, pacing-audit) and {out}/plagiarism-samples.md",
        f"- OUTPUT_DIR: {out}",
        "- REPORT FORMAT: LENSES.md 'Report format' — a `## Verdict:` heading is mandatory", "",
        "## Features detected", "", *[f"- {k}: {v}" for k, v in features.items()], "",
        "## Scanner runs", "", *(scans_note or ["- skipped"]), "",
        *(["## Assumed background", "", background.read_text().strip(), ""] if background.is_file() else []),
    ]))
    (out / "manifest.md").write_text("\n".join([
        f"# Review manifest: round {rnd}", "",
        "Dispatch every agent row below in ONE parallel batch via the Agent tool, with",
        "the brief named in the last column plus contract.md; start any `script` row in",
        "the background first. Each reviewer writes its Output file. Then run:", "",
        f"    aggregate-review.py --round {rnd}", "",
        "## Dispatches", "", *rows, "",
        "## Reminders", "",
        "- Reviewers are read-only. Fixers edit. Never the same agent in one round.",
        "- Correctness reviewers solve first, run a mechanical check, then read the key.",
        "- A round is APPROVED iff every blocking lens says `## Verdict: APPROVED`.",
        "- Every fix dispatch carries: \"re-read the file after your edit and flag anything",
        "  you may have introduced\".",
        "- 3-round cap; then escalate to the user with a root-cause summary.", "",
    ]))
    click.echo(f"round {rnd}: {len(dispatches)} dispatches -> {out}/manifest.md; features: "
               + ", ".join(k for k, v in features.items() if v and k != "always"))


if __name__ == "__main__":
    main()
