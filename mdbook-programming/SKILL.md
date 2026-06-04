---
name: mdbook-programming
description: Scaffold, author, edit, and review a developer-facing programming mdBook (Go, Python, or Rust) in Hugh Brown's house style — HTML + PDF via mdbook-pandoc/xelatex, every code sample externalized to a real file and verified by a compiling/testing checker (go test / pytest / rustc), justfile build+deploy, git, multi-agent review. Use when creating a new programming book under ~/projects/books, adding chapters to a Go/Python/Rust book (e.g. async-rust, rust-cli, golang-with-ai, polars), wiring up code-sample verification or include-based listings, or reviewing/editing such a book. For math/LaTeX-heavy books use mdbook-math-book instead; this skill shares its toolchain but replaces the formula machinery with verified-code machinery.
---

# Authoring a house-style programming mdBook

Developer-facing technical books — a language, runtime, library, or systems
topic taught deeply at several levels — for **Go, Python, or Rust**. Shares the
toolchain and review process of [`mdbook-math-book`](../mdbook-math-book/SKILL.md)
(read it for the formal/PDF machinery), but swaps the math-rendering concerns for
the defining rule of a programming book:

> **Every displayed code sample lives in a real source file and is pulled into
> the prose with an mdBook include. Nothing the reader sees is hand-typed into a
> Markdown fence. The build compiles and tests what it shows.**

Canonical example on disk: `~/projects/books/golang/golang-with-ai` (external
samples + `{{#include}}` + a compiling checker + a provenance manifest — the
evolved pattern). `~/projects/books/rust/async-rust` is the *older* inline-code
pattern this skill supersedes; don't copy its code handling.

Full templates and the PDF-hazard table: [REFERENCE.md](REFERENCE.md).
Reusable tooling: [`scripts/`](scripts/README.md). Build/deploy: [`justfile`](justfile).

## The externalization rule (this is the whole point)

Code is **independently verifiable** only if it lives outside the prose:

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

The checker compiles/tests the *included file*, so the reader sees exactly what
the toolchain verified. Three sample homes (pick per book — see scripts/README):

- **`code/` Cargo crates** (Rust, best) — real crates per chapter; mark regions
  with `// ANCHOR: name … // ANCHOR_END: name` and pull them with
  `{{#rustdoc_include}}`. Tests run via `cargo test --workspace` (justfile).
- **`src/<lang>/chNN/`** — standalone self-contained `.go`/`.py`/`.rs` files the
  checker compiles and runs directly.
- **`src/source-excerpts/chNN/`** — verbatim excerpts of **real repository code**
  the book cites, each listed in `src/source-excerpts/manifest.tsv` and
  provenance-checked against upstream (`exact`/`normalized`). Their tests live in
  their own repo; the book proves they still match the cited file.

**Code must carry the argument.** A sample must *firmly demonstrate the claim the
surrounding prose makes* — if the text says X is faster / safe / blocking, the
code must actually show X, not merely look plausible. A sample that compiles but
doesn't support the point is a defect (the `code-supports-claim` review lens).

Short illustrative fragments (≤ 6 lines) may stay inline; a longer inline block
that isn't an include **fails `chapter-audit` and the code checker**. Deliberate
non-compiling fragments use a `no-check`/`ignore` fence or a `book:skip` comment.

## Toolchain — pin these versions (the #1 time sink when unpinned)

```sh
cargo install mdbook          --version '0.4.52' --force
cargo install mdbook-pandoc   --version '0.10.6' --force
cargo install mdbook-admonish --force            # 1.20.x
# pandoc >= 3.x with xelatex (system package); plus `just` and `uv`
# ast-grep (code-construct queries):  brew install ast-grep   (or cargo install ast-grep)
# plus the language toolchain(s): go+gofmt | python3(+ruff,pytest) | rustc+rustfmt+cargo
```

The triple **(mdbook 0.4.52, mdbook-pandoc 0.10.6, mdbook-admonish 1.20)** is
load-bearing — see mdbook-math-book for why bumping one breaks the others.
`just install-tools` runs the cargo line.

## Reusable scripts — the gate a clean `mdbook build` does NOT provide

[`scripts/`](scripts/README.md) is copy-into-a-new-book uv PEP-723 scripts
(`uv run --script …`; CLIs use `click`, declared inline and auto-installed by uv).
Code constructs are identified with **`ast-grep`** (via `subprocess`), never
regex. Per-language checkers live under `scripts/<lang>/`, so a single-language
book copies only what it needs.

- `scripts/<lang>/check_<lang>_samples.py` — compile + test every **included**
  sample; enforce externalization; provenance-check source excerpts. Wired into
  `mdbook build` via `scripts/mdbook_code_preprocessor.py` so a broken sample
  can't reach HTML or PDF. `check_code_samples.py` dispatches over all languages
  present.
- `chapter-audit.py` — Markdown source health (fence parity, un-externalized
  inline code, PDF-hostile Unicode in prose, leaked tool tags, **British spelling
  in prose**, SUMMARY coverage).
- `check-refs.py` — every `Chapter N` / `§N.M` / `Listing N.M` / `Figure N.M` /
  `Appendix X` and intra-book link resolves. Run after any renumbering.

## Scaffold checklist

1. **Read the spec first.** The book request lives in `docs/prompt.md`; read it
   and capture the outline as a `docs/` artifact (concrete notes survive a
   session ending mid-book).
2. **Plan, then propose — before writing.** ~20 chapters + 2–4 appendices, split
   into major sections. Propose **chapter allocation, title, audience, tone** and
   get agreement. Defaults: audience **intermediate-to-senior developers**; tone
   **direct, developer-to-developer**.
3. `book.toml` — `[preprocessor.code-samples]` running the preprocessor;
   `[output.pandoc.profile.pdf]` with `pdf-engine = "xelatex"`. (Template in
   REFERENCE.) Use the **light preamble** — these books rarely need theorem
   environments.
4. File layout: `src/SUMMARY.md preface.md ch01.md … ch20.md appendix-a.md …
   afterword.md`, plus the sample home(s) above. PDF → `book/pandoc/pdf/`,
   HTML → `book/html/`.
5. `mdbook-admonish install .` once (then re-strip `@media` blocks from
   `mdbook-admonish.css` — see REFERENCE).
6. Copy `scripts/` and the `justfile`; set `langs := …` in the justfile.
7. `git init`; `.gitignore`: `/book/`, `.gh-pages/`, `.DS_Store`,
   `**/target/` (Rust), `__pycache__/`.
8. **Write one gold-standard chapter first**, verify `just test` is green
   (build + PDF + code checker), then author the rest.

## Writing conventions (match the gold-standard chapter exactly)

- **American English throughout.** Every book made with this skill uses American
  spelling and vocabulary — *color*, *behavior*, *initialize*, *canceled*,
  *gray*, *math*, *fall* — not the British forms (*colour*, *behaviour*,
  *initialise*, *cancelled*, *grey*, *maths*, *autumn*). This applies to prose,
  headings, captions, and comments in authored code samples (real source
  excerpts keep their upstream spelling verbatim). Set the editor/locale and any
  spell-check dictionary to `en-US`.
- **Code is externalized and verified** (the rule above). Reference the source
  project and file in prose for excerpts; say so when an excerpt is abridged.
- **Fence code plainly** (no admonish wrapper) so it survives xelatex. Use the
  fence language tag the checker recognizes (`go`/`golang`, `python`/`py`,
  `rust`/`rs`); add `no-check`/`ignore`/`no_run`/`compile_fail` as needed.
- **ASCII-only in prose.** Literal Unicode arrows `→`, superscripts `²`, etc.
  render in HTML but throw *"Missing character"* and drop in the xelatex PDF.
  Inside fenced code blocks, box-drawing chars `│ ┌ ┐ └ ┘ ├ ┤ ┬ ┴ ─` are fine
  (Menlo has them) — that's the cheapest way to draw a diagram, no image
  pipeline.
- **Callouts:** `admonish note/tip/warning/example/abstract` for asides, hints,
  pitfalls, worked walk-throughs, and boxed rules. Don't nest them; keep blank-line
  discipline; mismatched ``` fences break the build.
- Chapter H1s are plain text — write `# Title`, never `# Chapter N — Title` (the
  book class prepends "Chapter N"; doubling shows in the TOC).

## Parallel authoring & multi-agent review

For multi-chapter books, dispatch one agent per chapter (see
`superpowers:dispatching-parallel-agents`); each must **read the gold-standard
chapter + the PLAN/conventions doc first**, follow the externalization rule, and
write its samples as real files. After a parallel run, strip any leaked tool
tags: `grep -rn '</content>\|</invoke>\|antml:\|<parameter' src/`.

Review each chapter with a team attacking the *technology and the prose* (one
agent per lens, single parallel batch; each must flag problems **and offer a
concrete alternative**). Roster — adapt the math book's `docs/review-agents/`
specs to the language:

- **technical-accuracy** — claims where the technology doesn't behave as written
  (highest-stakes; treat as blocking).
- **code-supports-claim** — samples that don't firmly demonstrate the surrounding
  point.
- **source-originality / provenance** — excerpts that drifted from, or
  misrepresent, the cited repository.
- **logical-flow** and **voice** (AI-slop) — see mdbook-math-book.

A chapter is APPROVED only when *every* agent reports `## Verdict: APPROVED`;
every fix dispatch carries *"re-read the chapter after your edit and flag
anything you introduced"*; 3-round cap, then escalate with a root-cause summary.

## Editing an existing book

- **Renumbering ripples widely:** `book.toml` title + PDF `output-file`,
  `SUMMARY.md`, every `Chapter N` / `Listing N.M` reference, sample dir names
  (`ch05/` → `ch06/`), and `source-excerpts/manifest.tsv` paths. `grep -rniE`
  then re-run `check-refs.py` and the code checker.
- Moving a real-repo example into the book: add the excerpt file under
  `source-excerpts/`, a `manifest.tsv` row, and `{{#include}}` it — don't paste.

## Final verification (before declaring done)

Codified as `just test` so the gate is one command and `deploy` depends on it.
**Run it after every major change, not just at the end.** When a bug slips the
gate, fix the bug *and* tighten the gate in the same session.

- [ ] `mdbook build` produces HTML **and** PDF with **no `[WARNING]` / "Missing
      character"** lines (`just check-warnings`).
- [ ] **Code checker clean** — every included sample compiles/tests; no
      un-externalized long inline block; every source excerpt matches upstream.
      This is the primary correctness gate for a programming book.
- [ ] `chapter-audit.py` clean (fences, inline-code, Unicode, tags, British
      spelling, SUMMARY).
- [ ] `check-refs.py` clean (cross-references and links resolve).
- [ ] Rust: `cargo test --workspace` over `code/` is green.
- [ ] `src/SUMMARY.md`: `# Part` / `# Appendices` headings sit **before** the
      `---` suffix-chapter separator (else `mdbook test` fails).
