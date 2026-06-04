#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["click>=8.1"]
# ///
"""mdBook preprocessor: fail `mdbook build` when a code sample doesn't verify.

Wire it into book.toml so a broken sample can never reach HTML or the PDF:

    [preprocessor.code-samples]
    command = "uv run --script scripts/mdbook_code_preprocessor.py"
    renderers = ["html", "pandoc"]

It runs the per-language checkers (auto-detected from scripts/<lang>/ dirs) over
src/ and, on success, passes the book through unchanged. mdBook invokes it twice:
once as `supports <renderer>` (we answer yes for everything) and once with the
book JSON on stdin.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import click


@click.command(
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
    help=__doc__)
@click.argument("protocol_args", nargs=-1, type=click.UNPROCESSED)
def main(protocol_args: tuple[str, ...]) -> None:
    # mdBook capability probe: `<command> supports <renderer>` -> exit 0 = yes.
    if protocol_args and protocol_args[0] == "supports":
        raise SystemExit(0)

    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError as err:
        raise SystemExit(f"invalid mdBook preprocessor input: {err}")
    book = payload[1] if isinstance(payload, list) and len(payload) == 2 else payload

    here = Path(__file__).resolve().parent
    proc = subprocess.run(
        ["uv", "run", "--script", str(here / "check_code_samples.py")], check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)

    json.dump(book, sys.stdout)


if __name__ == "__main__":
    main()
