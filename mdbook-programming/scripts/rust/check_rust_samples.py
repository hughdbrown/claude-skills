#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["click>=8.1"]
# ///
"""Validate Rust code samples included into a programming mdBook.

Every `rust`/`rs` fenced block in src/**/*.md that is an mdBook include is
format-checked with rustfmt. Then:

  * If the included file lives inside a real cargo project (an ancestor has a
    `Cargo.toml`) — the recommended layout, `code/chNN/` crates pulled in with
    `{{#rustdoc_include code/ch03/src/lib.rs:anchor}}` — compilation and tests
    are the workspace's job. Run `cargo test --workspace` from the justfile;
    this checker only confirms the anchor exists and the file is rustfmt-clean.
  * Otherwise the file is compiled standalone with `rustc --test` (which both
    compiles and runs any `#[test]`s) in an isolated temp dir.

Rustdoc fence annotations are honored: `no_run` (compile, don't run),
`compile_fail` (expect a compile error), `edition2015/2018/2021`, and
`ignore`/`no-check` (skip). Long inline Rust blocks that are not includes fail
the externalization policy. Source-repository excerpts under
src/source-excerpts/ are provenance-checked, not compiled (see ../common.py).

    check_rust_samples.py [--root .] [--src src] [--update] [--max-inline-lines 6]

Requires `rustc`; `rustfmt` recommended (format checks skipped if absent).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import common  # noqa: E402

NO_RUN = {"no_run", "norun"}
COMPILE_FAIL = {"compile_fail", "compile-fail"}
EDITION = {"edition2015": "2015", "edition2018": "2018", "edition2021": "2021"}


def _rustfmt_check(file_path: Path) -> None:
    if not shutil.which("rustfmt"):
        return
    chk = common.run(["rustfmt", "--edition", "2021", "--check", str(file_path)],
                     file_path.parent)
    if chk.returncode != 0:
        raise common.CheckError(f"{file_path}: not rustfmt-formatted (run with --update)")


def validate_rust(file_path: Path, work: Path, block: common.CodeBlock, update: bool) -> None:
    if update and shutil.which("rustfmt"):
        common.run(["rustfmt", "--edition", "2021", str(file_path)], file_path.parent)

    in_cargo = any((p / "Cargo.toml").exists() for p in file_path.parents)
    _rustfmt_check(file_path)
    if in_cargo:
        # Compilation/tests handled by `cargo test --workspace` in the justfile.
        return

    if not shutil.which("rustc"):
        raise common.CheckError("`rustc` not on PATH (needed for standalone Rust samples)")
    edition = next((v for k, v in EDITION.items() if k in block.tokens), "2021")
    compile_fail = bool(block.tokens & COMPILE_FAIL)
    no_run = compile_fail or bool(block.tokens & NO_RUN)

    d = work / f"rs_{abs(hash(str(file_path)))}"
    d.mkdir(parents=True)
    out = d / "sample"
    proc = common.run(
        ["rustc", "--edition", edition, "--test", str(file_path), "-o", str(out)], d)
    if compile_fail:
        if proc.returncode == 0:
            raise common.CheckError(f"{file_path}: marked compile_fail but it compiled")
        return
    if proc.returncode != 0:
        raise common.CheckError(f"{file_path}: rustc failed\n{proc.stderr}".rstrip())
    if not no_run and common.run([str(out), "--quiet"], d).returncode != 0:
        raise common.CheckError(f"{file_path}: compiled test binary failed at runtime")


@click.command(help=__doc__)
@click.option("--root", default=".", type=click.Path(), help="book root directory")
@click.option("--src", default="src", help="markdown source dir relative to root")
@click.option("--update", is_flag=True, help="reformat included samples in place")
@click.option("--max-inline-lines", default=6, type=int,
              help="inline blocks longer than this must be externalized")
def main(root: str, src: str, update: bool, max_inline_lines: int) -> None:
    root_path = Path(root).resolve()
    src_path = (root_path / src).resolve()
    if not src_path.exists():
        raise SystemExit(f"source directory not found: {src_path}")
    raise SystemExit(common.drive(root_path, src_path, "rust", validate_rust,
                                  update=update, max_inline=max_inline_lines))


if __name__ == "__main__":
    main()
