#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["click>=8", "markdown-it-py>=3", "mdit-py-plugins>=0.4"]
# ///
"""Blind second solve of a day's exercises on the LAN model (optional lane).

A different model than the one that drafted the book solves each ordered
exercise under the day's "Try it..." heading from the problem's own Markdown,
never seeing the key. The model's final answer is printed beside the key's
paragraph for the same exercise number so the controller can eyeball
disagreements. Every mismatch is a LEAD for the correctness reviewer, not a
verdict — the local model is wrong some of the time too. Writes
docs/reviews/round-<N>/qwen-resolve--dayNN.md in the report format with
`## Verdict: APPROVED` always (a non-blocking lens) and the comparisons under
Non-blocking findings. Skips silently when the endpoint does not answer.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mdprose  # noqa: E402

PROMPT = """You are checking one exercise from a high-school {topic} book. Solve it yourself from scratch.
Show brief reasoning, then a final line exactly in the form
ANSWER: <the value, expression, or a one-sentence answer>
and nothing after it.

Exercise {num}:
{problem}"""


def call(host: str, model: str, prompt: str, timeout: int = 600) -> str:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "stream": False, "think": True,
                       "options": {"temperature": 0.2, "num_predict": 4000}}).encode()
    req = urllib.request.Request(host.rstrip("/") + "/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return (json.load(r).get("message") or {}).get("content") or ""


def alive(host: str) -> bool:
    try:
        with urllib.request.urlopen(host.rstrip("/") + "/api/tags", timeout=3):
            return True
    except Exception:
        return False


def exercises(doc: mdprose.Doc, heading: str) -> list[tuple[int, str]]:
    """(number, exact source) for each ordered item under the exercises heading."""
    return [(b.list_index, b.source) for b in doc.under_heading(lambda h: h.lower().startswith(heading.lower()))
            if b.kind == "list_item" and b.list_index is not None]


def key_paragraphs(doc: mdprose.Doc) -> dict[int, str]:
    """Exercise number -> the key's prose, from ordered items or '**N.**' paragraphs."""
    keys: dict[int, list[str]] = {}
    current = None
    for b in mdprose.prose_blocks(doc):
        num = None
        if b.kind == "list_item" and b.list_index is not None:
            num = b.list_index
        else:
            head, dot, _ = b.text.strip().partition(".")
            if dot and head.isdigit():
                num = int(head)
        if num is not None:
            current = num
            keys.setdefault(num, []).append(b.plain)
        elif current is not None:
            keys[current].append(b.plain)
    return {k: " ".join(v) for k, v in keys.items()}


def final_answer(text: str) -> str:
    for line in reversed(text.splitlines()):
        head, sep, rest = line.partition("ANSWER:")
        if sep and not head.strip():
            return rest.strip()
    return "(no ANSWER line)"


@click.command(help=__doc__)
@click.argument("days", nargs=-1, required=True)
@click.option("--round", "rnd", type=int, default=1, show_default=True)
@click.option("--host", default="http://10.0.0.222:11434", show_default=True)
@click.option("--model", default="qwen3.8-flash-next:125b-mlx", show_default=True)
@click.option("--topic", default="math", show_default=True)
@click.option("--exercise-heading", default="Try it", show_default=True)
def main(days, rnd, host, model, topic, exercise_heading) -> None:
    if not alive(host):
        click.echo(f"qwen-resolve: {host} not reachable; lane skipped"); return
    out = Path(f"docs/reviews/round-{rnd}"); out.mkdir(parents=True, exist_ok=True)
    for day in days:
        src = Path(f"src/{day}.md")
        if not src.is_file():
            click.echo(f"missing {src}", err=True); continue
        exs = exercises(mdprose.parse(src), exercise_heading)
        staging = Path(f"staging/{day}-answers.md")
        keys = key_paragraphs(mdprose.parse(staging)) if staging.exists() else {}
        rows = []
        for num, problem in exs:
            try:
                text = call(host, model, PROMPT.format(topic=topic, num=num, problem=problem))
            except Exception as e:
                rows.append(f"- {num}: endpoint error {e}"); continue
            rows.append(f"- **{num}.** model: `{final_answer(text)}`\n  key: {keys.get(num, '(no key paragraph found)')[:220]}")
        (out / f"qwen-resolve--{day}.md").write_text("\n".join([
            f"# qwen-resolve — {day} round-{rnd}", "",
            f"Model {model} solved {len(exs)} exercises blind. Compare each model answer with the",
            "key paragraph; a disagreement is a lead for the correctness reviewer, not a verdict.", "",
            "## Verdict: APPROVED", "", "## Blocking findings", "", "- None.", "",
            "## Non-blocking findings", "", *(rows or ["- None."]), ""]))
        click.echo(f"{day}: {len(exs)} exercises -> {out}/qwen-resolve--{day}.md")


if __name__ == "__main__":
    main()
