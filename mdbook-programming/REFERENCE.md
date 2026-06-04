# REFERENCE — house-style programming mdBook templates

Copy-paste starting points. The live, working copy is
`~/projects/books/golang/golang-with-ai`. For PDF/preamble machinery shared with
the math books, see `../mdbook-math-book/REFERENCE.md`.

## book.toml (programming book)

```toml
[book]
title    = "Your Title"
authors  = ["Hugh Brown"]
language = "en"
src      = "src"
description = "One-line description."

[build]
build-dir = "book"

# Fail `mdbook build` when any included code sample doesn't compile/test.
[preprocessor.code-samples]
command    = "uv run --script scripts/mdbook_code_preprocessor.py"
renderers  = ["html", "pandoc"]

# Worked examples / pitfalls as callouts (optional but standard).
[preprocessor.admonish]
command        = "mdbook-admonish"
assets_version = "3.1.0"   # managed by `mdbook-admonish install`

[output.html]
default-theme  = "light"
additional-css = ["./mdbook-admonish.css"]
git-repository-url = "https://github.com/you/your-book"

[output.html.search]
enable = true

[output.html.fold]
enable = true
level  = 1

# Rust only: turn included samples into runnable/editable playground blocks.
[output.html.playground]
editable = true

[output.pandoc.profile.pdf]
output-file       = "your-title.pdf"
pdf-engine        = "xelatex"
standalone        = true
table-of-contents = true
toc-depth         = 2
include-in-header = ["theme/pandoc/preamble.tex"]

[output.pandoc.profile.pdf.variables]
documentclass    = "report"
geometry         = ["margin=1in"]
fontsize         = "11pt"
mainfont         = "Palatino"
mainfontfallback = ["TeX Gyre Pagella", "DejaVu Serif"]
sansfont         = "Helvetica Neue"
sansfontfallback = ["TeX Gyre Heros", "DejaVu Sans"]
monofont         = "Menlo"
monofontfallback = ["DejaVu Sans Mono", "Liberation Mono"]
colorlinks = true
linkcolor  = "blue"
urlcolor   = "blue"
toc        = true
```

After `mdbook-admonish install .`, strip the `@media` blocks from
`mdbook-admonish.css` — mdbook-pandoc's CSS parser rejects `@media` with
`invalid @ rule '@media'`. Re-strip after every admonish install.

## .gitignore

```gitignore
/book/
/.gh-pages/
.DS_Store
**/target/        # Rust code/ crates
__pycache__/
*.pyc
.uv-cache/
```

## theme/pandoc/preamble.tex (light — programming books)

Use the light preamble verbatim from `../mdbook-math-book/REFERENCE.md` (amsmath
for the occasional formula, microtype, fancyhdr headers, enumitem spacing,
`\AtBeginDocument{\hypersetup{…}}`). Programming books almost never need theorem
environments, so do **not** pull in the formal preamble.

## Sample layout

### Rust — `code/` Cargo workspace (recommended)

```
code/
├── Cargo.toml            # [workspace] members = ["ch03", "ch07", ...]
├── ch03/
│   ├── Cargo.toml
│   └── src/lib.rs
└── ch07/
    ├── Cargo.toml
    └── src/main.rs
```

`code/ch03/src/lib.rs`:

```rust
// ANCHOR: retry
pub fn retry<F: Fn() -> bool>(max: u32, f: F) -> bool {
    (0..max).any(|_| f())
}
// ANCHOR_END: retry

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn stops_on_success() {
        let mut n = 0;
        assert!(retry(3, || { n += 1; n == 2 }));
    }
}
```

In the chapter — only the anchored region is shown, but the whole crate is
compiled and `cargo test --workspace` runs the test:

````markdown
```rust
{{#rustdoc_include code/ch03/src/lib.rs:retry}}
```
````

### Go / Python — standalone sample files

```
src/go/ch07/worker_test.go      # self-contained: package + funcs + Test*
src/python/ch04/pipeline.py     # self-contained module (+ test_* for pytest)
```

`src/go/ch07/worker_test.go` (the checker runs `go test .`):

```go
package main

import "testing"

func Sum(xs []int) (total int) {
	for _, x := range xs {
		total += x
	}
	return
}

func TestSum(t *testing.T) {
	if Sum([]int{1, 2, 3}) != 6 {
		t.Fatal("wrong")
	}
}
```

Include the whole file (or a `:anchor` / `:start:end` slice):

````markdown
```go
{{#include go/ch07/worker_test.go}}
```
````

### Real-repository excerpts — `src/source-excerpts/`

For a book whose argument is "learn from real projects." Copy the verbatim
excerpt, register it, cite the project/file in prose:

```
# src/source-excerpts/manifest.tsv  (TAB-separated)
# excerpt	source	mode
source-excerpts/ch01/server_handler.go	/Users/you/repos/svc/internal/http.go	exact
source-excerpts/ch02/retry.rs	~/repos/foo/src/retry.rs	normalized
```

````markdown
```go no-check
{{#include source-excerpts/ch01/server_handler.go}}
```
````

Excerpts are `no-check` (they're package fragments) — their correctness comes
from the upstream repo's own tests; the checker proves the excerpt still *matches*
that repo via the manifest.

## Chapter template

```markdown
# Title

> **In one line:** <what this chapter buys the reader>

## The problem

<motivate before showing code>

​```rust
{{#rustdoc_include code/chNN/src/lib.rs:thing}}
​```

The code above (from `code/chNN`) shows <the exact claim it demonstrates>.

​```admonish warning title="Common mistake"
<the pitfall this chapter exists to prevent>
​```

## How it works

<deeper level — internals, trade-offs>

​```admonish note title="Next"
<hook to the next chapter>
​```
```

## PDF build hazards (each cost real debug time)

| Symptom | Root cause | Fix |
|---|---|---|
| `Missing character: There is no → (U+2192)` | STIX/Palatino lacks the glyph; literal Unicode in **prose** | ASCII in prose; box-drawing chars are OK **inside** fenced code (Menlo has them) |
| `{{#include …}}` prints verbatim in the PDF | a non-include line snuck into the fence, or the file path is wrong | the include must be the **only** line in the block; `check-refs`/code checker catch missing files |
| `Failed to parse CSS …: invalid @ rule '@media'` | mdbook-pandoc rejects `@media` in `mdbook-admonish.css` | strip `@media` blocks after every `mdbook-admonish install` |
| `# Chapter N — Title` doubles to "N Chapter N — Title" in TOC | book/report class prepends the number | write `# Title` only |
| `Undefined control sequence \hypersetup` | header runs before pandoc loads hyperref | wrap in `\AtBeginDocument{…}` (in the light preamble) |
| Appendices numbered as chapters | book class needs `\appendix` fired mid-document | pandoc Lua filter `inject-appendix.lua` (copy from a math book) |
| `Suffix chapters cannot be followed by a list` | a `# heading` + list after `---` in SUMMARY.md | put all `# Part`/`# Appendices` headings before the `---` separator |

A green `mdbook build` is **not** proof. Always also run `just test` — the code
checker, chapter-audit, and check-refs catch what the build exits 0 on.

## justfile & scripts

The build/test/deploy [`justfile`](justfile) and the [`scripts/`](scripts/README.md)
gate ship with this skill — copy both into the book and set `langs := …` in the
justfile. `deploy` rebuilds, re-runs the full `test` gate, and publishes
`book/html/` to the `gh-pages` branch via a git worktree.
