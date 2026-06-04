#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["click>=8.1"]
# ///
"""Dispatcher: run the per-language code-sample checkers a book actually uses.

Most house-style programming books are single-language (a Go book, a Rust book,
a Python book), so each language's checker lives under `scripts/<lang>/` and can
be copied and run on its own. This dispatcher is a convenience for the justfile:
it runs the checkers for whichever `scripts/<lang>/` directories are present
(or the ones named with --langs) and fails if any fails.

    check_code_samples.py                 # auto-detect from scripts/<lang>/ dirs
    check_code_samples.py --langs rust    # just one
    check_code_samples.py --update        # reformat samples in place, then check
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import click

CHECKERS = {
    "go": "go/check_go_samples.py",
    "python": "python/check_python_samples.py",
    "rust": "rust/check_rust_samples.py",
}


@click.command(help=__doc__)
@click.option("--root", default=".", type=click.Path(), help="book root directory")
@click.option("--src", default="src", help="markdown source dir relative to root")
@click.option("--langs", default="", help="comma list of languages; default: auto-detect")
@click.option("--update", is_flag=True, help="reformat included samples in place")
@click.option("--max-inline-lines", default=6, type=int,
              help="inline blocks longer than this must be externalized")
def main(root: str, src: str, langs: str, update: bool, max_inline_lines: int) -> None:
    here = Path(__file__).resolve().parent
    if langs.strip():
        selected = [l.strip().lower() for l in langs.split(",") if l.strip()]
    else:
        selected = [l for l, rel in CHECKERS.items() if (here / rel).exists()]
    if not selected:
        raise SystemExit("no per-language checkers found under scripts/<lang>/")

    rc = 0
    for lang in selected:
        rel = CHECKERS.get(lang)
        if not rel or not (here / rel).exists():
            click.echo(f"no checker for language {lang!r}", err=True)
            rc = 1
            continue
        cmd = ["uv", "run", "--script", str(here / rel), "--root", root,
               "--src", src, "--max-inline-lines", str(max_inline_lines)]
        if update:
            cmd.append("--update")
        rc |= subprocess.run(cmd, check=False).returncode
    raise SystemExit(1 if rc else 0)


if __name__ == "__main__":
    main()
