#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["click>=8.1"]
# ///
"""Validate Go code samples included into a programming mdBook.

Every `go`/`golang` fenced block in src/**/*.md that is an mdBook include is
compiled (and tested) in an isolated temp module: the file needs a `package`
declaration, must be `gofmt`-clean, and must pass `go test .`. Long inline Go
blocks that are not includes fail the externalization policy. Source-repository
excerpts under src/source-excerpts/ are provenance-checked against their cited
upstream files instead of compiled (see ../common.py and the manifest).

    check_go_samples.py [--root .] [--src src] [--update] [--max-inline-lines 6]

Requires `go` and `gofmt` on PATH.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import common  # noqa: E402

TEST_PREFIXES = ("Test", "Example", "Benchmark")


def validate_go(file_path: Path, work: Path, block: common.CodeBlock, update: bool) -> None:
    # Structural query (ast-grep), not a regex over source text.
    if not common.ast_grep_matches("package $NAME", "go", file_path):
        raise common.CheckError(
            f"{file_path}: Go sample needs a package declaration "
            "(or mark the block `no-check`)")
    if update:
        if common.run(["gofmt", "-w", str(file_path)], file_path.parent).returncode != 0:
            raise common.CheckError(f"{file_path}: gofmt -w failed")

    code = file_path.read_text(encoding="utf-8")
    funcs = common.ast_grep_node_names("function_declaration", "go", file_path)
    is_test = any(name.startswith(TEST_PREFIXES) for name in funcs)

    d = work / f"go_{abs(hash(str(file_path)))}"
    d.mkdir(parents=True)
    (d / "go.mod").write_text("module book_sample\n\ngo 1.22\n", encoding="utf-8")
    (d / ("sample_test.go" if is_test else "sample.go")).write_text(code, encoding="utf-8")

    if common.run(["gofmt", "-l", str(d)], d).stdout.strip():
        raise common.CheckError(f"{file_path}: not gofmt-formatted (run with --update)")
    proc = common.run(["go", "test", "."], d)
    if proc.returncode != 0:
        raise common.CheckError(
            f"{file_path}: `go test .` failed\n{proc.stdout}{proc.stderr}".rstrip())


@click.command(help=__doc__)
@click.option("--root", default=".", type=click.Path(), help="book root directory")
@click.option("--src", default="src", help="markdown source dir relative to root")
@click.option("--update", is_flag=True, help="reformat included samples in place")
@click.option("--max-inline-lines", default=6, type=int,
              help="inline blocks longer than this must be externalized")
def main(root: str, src: str, update: bool, max_inline_lines: int) -> None:
    for tool in ("go", "gofmt", "ast-grep"):
        if not shutil.which(tool):
            raise SystemExit(f"`{tool}` not found on PATH")
    root_path = Path(root).resolve()
    src_path = (root_path / src).resolve()
    if not src_path.exists():
        raise SystemExit(f"source directory not found: {src_path}")
    raise SystemExit(common.drive(root_path, src_path, "go", validate_go,
                                  update=update, max_inline=max_inline_lines))


if __name__ == "__main__":
    main()
