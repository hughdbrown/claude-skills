#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["click>=8.1"]
# ///
"""Report token usage and estimated cost of a Claude Code session, by model and agent.

    session_cost.py                       # newest session for the current directory
    session_cost.py --session 706c76cb    # session id (prefix ok)
    session_cost.py --transcript path/to/session.jsonl
    session_cost.py --json

Reads the main transcript plus every subagents/agent-*.jsonl beside it, so a
coordinator can see what the team actually cost and compare it with pricing
the same tokens at the baseline (Opus) rate. That comparison is a rough lower
bound on the all-Opus cost: a single Opus agent would not have used the exact
same tokens, but it tells you whether delegation moved volume to cheaper tiers.

Prices come from resources/pricing.json; edit it when prices change.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

import click

from taskcard import RESOURCES

PROJECTS = Path.home() / ".claude" / "projects"


def project_dir(cwd: Path) -> Path:
    return PROJECTS / str(cwd.resolve()).replace("/", "-").replace(".", "-")


def resolve_transcript(transcript: Path | None, session: str | None) -> Path:
    if transcript:
        return transcript
    if session:
        hits = sorted(PROJECTS.glob(f"*/{session}*.jsonl"))
        if not hits:
            raise click.ClickException(f"no transcript for session {session!r} under {PROJECTS}")
        return hits[0]
    # Walk up from cwd: a session started in the repo root still counts when run from a subdir.
    for directory in (Path.cwd(), *Path.cwd().parents):
        candidates = sorted(project_dir(directory).glob("*.jsonl"), key=os.path.getmtime)
        if candidates:
            return candidates[-1]
    raise click.ClickException(f"no transcripts for {Path.cwd()} or its parents; pass --session or --transcript")


def usage_by_request(path: Path) -> dict[str, tuple[str, dict]]:
    """Assistant usage keyed by requestId (a response split into blocks repeats its usage)."""
    out: dict[str, tuple[str, dict]] = {}
    with path.open() as fh:
        for n, line in enumerate(fh):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = entry.get("message")
            if entry.get("type") != "assistant" or not isinstance(msg, dict) or "usage" not in msg:
                continue
            key = entry.get("requestId") or f"{path.name}:{n}"
            prev = out.get(key)
            if prev is None or msg["usage"].get("output_tokens", 0) >= prev[1].get("output_tokens", 0):
                out[key] = (msg.get("model", "unknown"), msg["usage"])
    return out


def price_for(model: str, pricing: dict) -> dict | None:
    for prefix in sorted(pricing["models"], key=len, reverse=True):
        if model.startswith(prefix):
            return pricing["models"][prefix]
    return None


def cost(tokens: dict, price: dict, mult: dict) -> float:
    per = 1_000_000
    return (
        tokens["input"] * price["input"]
        + tokens["cache_write_5m"] * price["input"] * mult["write_5m"]
        + tokens["cache_write_1h"] * price["input"] * mult["write_1h"]
        + tokens["cache_read"] * price["input"] * mult["read"]
        + tokens["output"] * price["output"]
    ) / per


def agent_label(path: Path, main: Path) -> str:
    if path == main:
        return "main"
    meta = path.with_suffix(".meta.json")
    if meta.exists():
        try:
            data = json.loads(meta.read_text())
            return data.get("description") or data.get("name") or path.stem
        except json.JSONDecodeError:
            pass
    return path.stem


@click.command()
@click.option("--session", help="Session id or prefix.")
@click.option("--transcript", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--pricing",
    "pricing_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=RESOURCES / "pricing.json",
    show_default=True,
)
@click.option("--json", "as_json", is_flag=True)
def main(session: str | None, transcript: Path | None, pricing_path: Path, as_json: bool) -> None:
    """Summarize tokens and cost for one session including its subagents."""
    pricing = json.loads(pricing_path.read_text())
    mult = pricing["cache_multipliers"]
    baseline = pricing["models"][pricing["baseline_model"]]
    main_path = resolve_transcript(transcript, session)
    files = [main_path, *sorted(main_path.with_suffix("").glob("subagents/*.jsonl"))]

    zero = lambda: {"input": 0, "cache_write_5m": 0, "cache_write_1h": 0, "cache_read": 0, "output": 0, "requests": 0}  # noqa: E731
    by_model: dict[str, dict] = defaultdict(zero)
    by_agent: dict[tuple[str, str], dict] = defaultdict(zero)
    unpriced: set[str] = set()
    for path in files:
        label = agent_label(path, main_path)
        for model, u in usage_by_request(path).values():
            cc = u.get("cache_creation") or {}
            w1h = cc.get("ephemeral_1h_input_tokens", 0)
            w5m = cc.get("ephemeral_5m_input_tokens", u.get("cache_creation_input_tokens", 0) - w1h)
            for bucket in (by_model[model], by_agent[(label, model)]):
                bucket["input"] += u.get("input_tokens", 0)
                bucket["cache_write_5m"] += w5m
                bucket["cache_write_1h"] += w1h
                bucket["cache_read"] += u.get("cache_read_input_tokens", 0)
                bucket["output"] += u.get("output_tokens", 0)
                bucket["requests"] += 1

    def priced(tokens: dict, model: str) -> tuple[float | None, float]:
        price = price_for(model, pricing)
        if price is None:
            unpriced.add(model)
        return (cost(tokens, price, mult) if price else None), cost(tokens, baseline, mult)

    models_out = []
    for model, t in sorted(by_model.items()):
        actual, base = priced(t, model)
        models_out.append({"model": model, **t, "cost": actual, "baseline_cost": base})
    agents_out = []
    for (label, model), t in sorted(by_agent.items(), key=lambda kv: -kv[1]["output"]):
        actual, _ = priced(t, model)
        agents_out.append({"agent": label, "model": model, "output": t["output"], "requests": t["requests"], "cost": actual})
    total = sum(m["cost"] or 0 for m in models_out)
    # Compare like with like: unpriced models are left out of both sides.
    base_total = sum(m["baseline_cost"] for m in models_out if m["cost"] is not None)
    report = {
        "transcript": str(main_path),
        "files": len(files),
        "models": models_out,
        "agents": agents_out,
        "total_cost": round(total, 4),
        "baseline_cost": round(base_total, 4),
        "unpriced_models": sorted(unpriced),
    }
    if as_json:
        click.echo(json.dumps(report, indent=2))
        return

    click.echo(f"Transcript: {main_path}  ({len(files) - 1} subagent file(s))\n")
    click.echo(f"{'model':<28}{'reqs':>6}{'input':>10}{'cache_w':>11}{'cache_r':>12}{'output':>10}{'cost $':>10}")
    for m in models_out:
        cw = m["cache_write_5m"] + m["cache_write_1h"]
        c = f"{m['cost']:.2f}" if m["cost"] is not None else "?"
        click.echo(f"{m['model']:<28}{m['requests']:>6}{m['input']:>10}{cw:>11}{m['cache_read']:>12}{m['output']:>10}{c:>10}")
    scope = " (priced models only)" if unpriced else ""
    click.echo(f"\nTotal{scope}: ${total:.2f}   Same tokens at {pricing['baseline_model']} rates: ${base_total:.2f}")
    if base_total:
        click.echo(f"Delegation saved ~{100 * (1 - total / base_total):.0f}% versus pricing everything at the baseline")
    if unpriced:
        click.echo(f"Unpriced models (add to pricing.json): {', '.join(sorted(unpriced))}")
    click.echo("\nTop agents by output tokens:")
    for a in agents_out[:10]:
        c = f"${a['cost']:.2f}" if a["cost"] is not None else "?"
        click.echo(f"  {a['agent'][:48]:<50}{a['model']:<28}{a['output']:>9} out  {c}")


if __name__ == "__main__":
    main()
