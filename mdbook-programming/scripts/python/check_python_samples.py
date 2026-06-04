#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["click>=8.1"]
# ///
"""Validate Python code samples included into a programming mdBook.

Every `python`/`py` fenced block in src/**/*.md that is an mdBook include is
syntax-checked with py_compile, format-checked with ruff (if installed), and —
when the file is a test module (`test_*.py`, `*_test.py`, or contains
`def test_*`) — run with pytest (if installed). Long inline Python blocks that
are not includes fail the externalization policy. Source-repository excerpts
under src/source-excerpts/ are provenance-checked, not run (see ../common.py).

    check_python_samples.py [--root .] [--src src] [--update] [--max-inline-lines 6]

ruff and pytest are optional; their checks are skipped (not failed) when absent.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import common  # noqa: E402


def validate_python(file_path: Path, work: Path, block: common.CodeBlock, update: bool) -> None:
    if update and shutil.which("ruff"):
        common.run(["ruff", "format", str(file_path)], file_path.parent)

    proc = common.run([sys.executable, "-m", "py_compile", str(file_path)], file_path.parent)
    if proc.returncode != 0:
        raise common.CheckError(
            f"{file_path}: py_compile failed\n{proc.stdout}{proc.stderr}".rstrip())

    if shutil.which("ruff"):
        fmt = common.run(["ruff", "format", "--check", str(file_path)], file_path.parent)
        if fmt.returncode != 0:
            raise common.CheckError(f"{file_path}: not ruff-formatted (run with --update)")

    # Test detection: filename convention, or a `test_*` function found by ast-grep
    # (structural query, not a regex over source text).
    name = file_path.name
    defs = common.ast_grep_node_names("function_definition", "python", file_path)
    is_test = (name.startswith("test_") or name.endswith("_test.py")
               or any(d.startswith("test_") for d in defs))
    if is_test and shutil.which("pytest"):
        proc = common.run(["pytest", "-q", str(file_path)], file_path.parent)
        if proc.returncode not in (0, 5):  # 5 == no tests collected
            raise common.CheckError(
                f"{file_path}: pytest failed\n{proc.stdout}{proc.stderr}".rstrip())


@click.command(help=__doc__)
@click.option("--root", default=".", type=click.Path(), help="book root directory")
@click.option("--src", default="src", help="markdown source dir relative to root")
@click.option("--update", is_flag=True, help="reformat included samples in place")
@click.option("--max-inline-lines", default=6, type=int,
              help="inline blocks longer than this must be externalized")
def main(root: str, src: str, update: bool, max_inline_lines: int) -> None:
    if not shutil.which("ast-grep"):
        raise SystemExit("`ast-grep` not found on PATH")
    root_path = Path(root).resolve()
    src_path = (root_path / src).resolve()
    if not src_path.exists():
        raise SystemExit(f"source directory not found: {src_path}")
    raise SystemExit(common.drive(root_path, src_path, "python", validate_python,
                                  update=update, max_inline=max_inline_lines))


if __name__ == "__main__":
    main()
