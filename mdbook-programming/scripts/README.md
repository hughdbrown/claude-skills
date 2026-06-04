# scripts/ — reusable tooling for a house-style programming mdBook

Copy what your book needs into its `scripts/` and wire it into `just test`.
Every script is a [uv](https://docs.astral.sh/uv/) PEP-723 single file — the
`#!/usr/bin/env -S uv run --script` shebang plus an inline `# /// script` metadata
block, so `uv run --script scripts/<x>.py` runs it with its declared deps and no
manual virtualenv. The CLIs use [`click`](https://click.palletsprojects.com/)
(the one Python dependency, declared in each `# /// script` block; uv installs it
on first run). Add any further dependency by listing it there — never `pip install`
into the ambient environment.

**Code is never identified with regular expressions.** To find language
constructs (a Go `package` clause, a Go/Python test function) the checkers query
the parsed syntax tree with [`ast-grep`](https://ast-grep.github.io/) via
`subprocess` (`ast-grep run --lang go` / `ast-grep scan --inline-rules`), not
regex over source text — see `common.ast_grep_matches` / `ast_grep_node_names`.
(Markdown structure — fences, `{{#include}}` directives, prose cross-references —
is still parsed textually; ast-grep is for *code*.)

**External tools** the checkers shell out to: `ast-grep` (required for Go/Python
construct queries), the language toolchains `go`+`gofmt`, `rustc`+`rustfmt`, and
the optional Python `ruff`/`pytest` (skipped, not failed, when absent). Install
ast-grep with `brew install ast-grep` or `cargo install ast-grep`.

## What each piece does

| Path | Gate it provides | Why a clean `mdbook build` misses it |
|---|---|---|
| `common.py` | Shared library: fence extraction, include/anchor resolution, the externalization policy, source-excerpt provenance, the `drive()` loop | — (imported by the language checkers) |
| `go/check_go_samples.py` | Every included `.go` sample is `gofmt`-clean and passes `go test .` in an isolated module | mdbook never compiles code; a broken sample ships green |
| `python/check_python_samples.py` | Every included `.py` sample passes `py_compile`, `ruff format --check`, and (test modules) `pytest` | same |
| `rust/check_rust_samples.py` | Every included `.rs` sample is `rustfmt`-clean and compiles/runs (`rustc --test`), honoring `no_run`/`compile_fail`/`editionNNNN`; crate-resident files defer to `cargo test` | same |
| `check_code_samples.py` | Dispatcher — runs whichever `scripts/<lang>/` checkers are present (or `--langs`) | convenience for the justfile / preprocessor |
| `mdbook_code_preprocessor.py` | Same checks, run **inside `mdbook build`** so a bad sample blocks HTML+PDF | makes the gate impossible to forget |
| `chapter-audit.py` | Markdown **source** health: fence parity, **long inline code that should be an `{{#include}}`**, PDF-hostile Unicode in prose, leaked tool tags, placeholders, **British spelling in prose** (house style is American English), SUMMARY coverage | these render wrong, read off-house-style, or drop in the PDF; build still exits 0 |
| `check-refs.py` | Every `Chapter N` / `§N.M` / `Listing N.M` / `Figure N.M` / `Appendix X` and intra-book `[..](chNN.md)` link resolves | renumbering/parallel drafting break refs silently |

## The one rule these enforce

**Displayed code is never hand-typed into the prose.** It lives in a real file
and the chapter pulls it in:

````markdown
```rust
{{#rustdoc_include code/ch03/src/lib.rs:retry}}
```
```go
{{#include go/ch07/worker_test.go}}
```
```python
{{#include python/ch04/pipeline.py}}
```
````

The checker compiles/tests the *included file*, so what the reader sees is
exactly what the toolchain verified. Inline blocks longer than
`--max-inline-lines` (default 6) **fail** unless they are an include or marked
`no-check`/`ignore` (or carry a `book:skip` comment) — that escape hatch is for
deliberate fragments that cannot stand alone.

## Sample layout

- **`code/`** (Rust, recommended) — real Cargo crates, one per chapter:
  `code/ch03/Cargo.toml`, `code/ch03/src/lib.rs`. Mark regions with
  `// ANCHOR: name` … `// ANCHOR_END: name` and include with
  `{{#rustdoc_include code/ch03/src/lib.rs:name}}`. Compilation and tests run via
  `cargo test --workspace` in the justfile; the checker confirms the anchor
  exists and the file is `rustfmt`-clean. Add `code/` to a Cargo workspace.
- **`src/<lang>/chNN/`** — standalone samples (a single self-contained `.go` /
  `.py` / `.rs` file). These the checker compiles/runs directly.
- **`src/source-excerpts/chNN/`** — verbatim excerpts of **real repository code**
  the book cites. Each must be listed in `src/source-excerpts/manifest.tsv`:

  ```
  # excerpt<TAB>source<TAB>mode
  source-excerpts/ch01/server_handler.go	/abs/path/to/repo/internal/http.go	exact
  source-excerpts/ch02/retry.rs	~/repos/foo/src/retry.rs	normalized
  ```

  `exact` requires the excerpt to be a verbatim substring of the source;
  `normalized` matches after collapsing whitespace (for line-wrapped fragments).
  The checker fails if an excerpt drifts from upstream, is on disk but not in the
  manifest, or is in the manifest but never `{{#include}}`d. Excerpts are
  provenance-checked, not compiled — their tests live in their own repository.

## Running

```bash
uv run --script scripts/check_code_samples.py          # all detected languages
uv run --script scripts/rust/check_rust_samples.py     # one language
uv run --script scripts/check_code_samples.py --update # gofmt/rustfmt/ruff-format in place
uv run --script scripts/chapter-audit.py
uv run --script scripts/check-refs.py
```

All of the above are wired into `just test` (see the book's justfile), and
`check_code_samples` also runs inside `mdbook build` via the preprocessor.
