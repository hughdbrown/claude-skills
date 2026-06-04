---
name: mdbook-math-book
description: Scaffold and author a math, technical, or code-centered mdBook in Hugh Brown's house style (HTML via MathJax + PDF via mdbook-pandoc/xelatex, mdbook-admonish callouts, justfile build, git, multi-agent review). Use when creating a new book under ~/projects/books, adding a volume to the limits/derivatives/integrals series, setting up an mdBook that needs LaTeX math in both HTML and PDF, or authoring a developer-facing technical book (prose + code samples, ~20 chapters plus appendices) such as a language, runtime, or systems topic (e.g. async Rust).
---

# Authoring a house-style math mdBook

Canonical examples on disk: `~/projects/books/math/calculus` (formal) and
`~/projects/books/math/14-day-derivatives` (informal, day-per-lesson). Copy from
them; don't reinvent. Full file templates: see [REFERENCE.md](REFERENCE.md).

This skill covers two book families that share the toolchain below: **math books**
(MathJax/LaTeX-heavy — the formula and answer-audit sections assume these) and
**technical / code books** (developer-facing prose + code samples, ~20 chapters
plus appendices — e.g. an async-Rust or systems topic). For the latter, read
*Technical / code books* next, then apply the scaffold, build, and review sections
with the substitutions it notes.

## Technical / code books (prose + code, not just math)

The same toolchain (mdbook + mdbook-pandoc PDF, mdbook-admonish, justfile, git,
multi-agent review) authors a developer-facing technical book — a language,
runtime, or systems topic taught deeply at several levels, including deep ones.
Differences from a math book:

- **Read the spec first.** The book request lives in `docs/prompt.md`; read it
  before planning. Capture findings/outline as a `docs/` artifact rather than only
  reading — concrete intermediate notes survive a session ending mid-book.
- **Plan, then propose — before writing.** Design a table of contents of about
  **20 chapters plus 2–4 appendices**, split into several major sections. Propose
  the **chapter allocation, title, audience, and tone** to the user and get
  agreement before drafting. Defaults: audience **intermediate-to-senior
  developers**; tone **direct, developer-to-developer**.
- **File layout** (instead of math `chNN`/day-per-lesson files):
  ```
  src/SUMMARY.md  preface.md  ch01.md … ch20.md
  appendix-a.md  appendix-b.md  appendix-c.md  afterword.md
  ```
  PDF lands in `book/pandoc/pdf/<book-title>.pdf`, HTML in `book/html/`. `git init`
  at scaffold time and keep the whole `book/` tree out of git (`.gitignore`:
  `/book/`, `.DS_Store`).
- **Code samples carry the argument.** Every sample must *firmly support the claim
  the surrounding text makes* — if the prose says X is faster / safe / blocking,
  the code must actually demonstrate X. A sample that merely looks plausible is a
  defect. Fence code plainly (no admonish) so it survives the xelatex PDF; keep
  diagrams ASCII per the rules below.
- **Preamble:** use the *light* preamble (no theorem environments) — these books
  rarely need `amsthm`.
- **Write one gold-standard chapter first**, verify it builds to HTML + PDF, then
  author the rest (one agent per chapter — see *Parallel authoring*).

## Toolchain — pin these versions (the #1 time sink when unpinned)

```sh
cargo install mdbook          --version '0.4.52' --force
cargo install mdbook-pandoc   --version '0.10.6' --force
cargo install mdbook-admonish --force            # 1.20.x
# pandoc >= 3.x with xelatex (system package); plus `just`
```

The triple **(mdbook 0.4.52, mdbook-pandoc 0.10.6, mdbook-admonish 1.20)** is
load-bearing: mdbook-pandoc **< 0.10 has no math support and silently renders
`$x^2$` as literal dollars in the PDF** — a real build shipped that way for weeks
(hours lost across three debug sessions). 0.11 needs mdbook 0.5; admonish 1.20
doesn't support 0.5 yet, so don't bump one without the others.

## Reusable maintenance scripts

This skill ships [`scripts/`](scripts/README.md) — copy the directory into a new
book and wire it into `just test`. They are generic (uv/PEP-723) and configured by
flags, so a new book needs no code edits. Gates a clean `mdbook build` does NOT
provide:

- `chapter-audit.py` — markdown source health (math/prose separation checks).
- `check-refs.py` — every `Theorem N.M` / `§N.K` / `Chapter N` / `Eq. (N.M)` /
  `Appendix X` and cross-volume `V1 …` citation resolves. The convention-drift
  gate; run after any renumbering.
- `pdf-math-check.py` — raw TeX leaked into the rendered PDF.
- `answer-audit.py` — every claimed answer substituted back through sympy.
- `run-review.py` + `aggregate-review.py` — multi-agent review orchestration.

See [scripts/README.md](scripts/README.md) for flags and the answer-audit schema.

## Scaffold checklist

1. `book.toml` — `[output.html] mathjax-support = true`, admonish preprocessor,
   `[output.pandoc.profile.pdf]` with `pdf-engine = "xelatex"` and
   `include-in-header = ["theme/pandoc/preamble.tex"]`. (Template in REFERENCE.)
2. `theme/head.hbs` — MathJax delimiter config. Note: although it lists `\(...\)`,
   that form does NOT survive mdBook's Markdown step — author inline math as
   `$...$` (see the delimiter warning below).
3. `theme/figures.css` + `theme/figures.js` — figure numbering/captions (optional
   but standard).
4. `theme/pandoc/preamble.tex` — amsmath/microtype/fancyhdr/hyperref. Use the
   *light* preamble (no theorem environments) for informal books.
5. Run `mdbook-admonish install .` once — writes `mdbook-admonish.css` (referenced
   by `additional-css`).
6. `src/SUMMARY.md` — table of contents (every chapter file must be listed here or
   mdbook warns and skips it).
7. `justfile` — `build` / `serve` / `pdf` / `clean`. (Template in REFERENCE.)
8. `.gitignore` — `/book/`, `.DS_Store`.

Verify the skeleton builds (`mdbook build`) with ONE real chapter before writing
the rest.

## Formula rendering across HTML · PDF · serve

**A green `mdbook build` is NOT proof math rendered.** The build exits 0 while
the PDF shows literal `$$ \frac{a}{b} $$`. Always confirm:
`pdftotext book/pandoc/pdf/*.pdf - | awk '/Definition 1/'` shows rendered Unicode,
not raw TeX — or just run `scripts/pdf-math-check.py`.

- **`math = true` is mandatory and the key name is exact.** `book.toml` needs
  `[output.pandoc.markdown.extensions]` `math = true` — *not* `tex_math_dollars`.
  Missing it ⇒ no PDF math.
- **`\frac`, not `\dfrac`, inline.** `\dfrac` forces display-size fractions inside
  `$…$`, bloating line height and pushing punctuation onto its own line. `\frac` is
  compact inline and auto-full-size in `$$…$$`.
- **No `[...](...)` inside `$…$`.** Pandoc's tokenizer reads it as a markdown link
  and errors `Unable to normalize link`. Use `\bigl( \bigr)`, `\left[ \right]`.
- **Never literal `▮` / `✓` / Unicode arrows in source.** STIX fonts lack the
  glyphs (`Missing character` warning, dropped in PDF). Use `$\blacksquare$`,
  `$\checkmark$`, `\to`. This is a cross-book hard rule.
- **`mdbook-admonish install` regenerates `mdbook-admonish.css` with `@media`
  blocks** that mdbook-pandoc's CSS parser rejects (`invalid @ rule '@media'`).
  Re-strip them after every admonish install.
- `serve` reload occasionally caches stale MathJax; hard-refresh the browser
  before trusting "the formula still shows raw text."

Full PDF-hazard table (hyperref, appendix labels, `{=latex}` blocks, page
numbering, enumitem spacing) is in [REFERENCE.md](REFERENCE.md).

## Writing conventions (match the exemplar exactly)

- **Math delimiters:** inline **`$ ... $`**, display `$$ ... $$`. Do **NOT** use
  `\( ... \)` inline — mdBook's Markdown parser (pulldown-cmark) strips the
  backslash before ASCII punctuation, so `\(`, `\)`, `\,`, `\;` are eaten *before*
  MathJax sees them and the math renders as literal text (e.g. `(f'(x))`). Display
  `$$...$$` is safe because `$` isn't escaped. Inside math, use only
  backslash+letter macros (`\frac`, `\dfrac`, `\sin`, `\to`); avoid spacing macros
  `\,` and `\;` (write a normal space instead) and set-brace `\{ \}` (use
  `\lbrace \rbrace`). This is the single most common way to silently break a math
  mdBook — the HTML still builds, it just shows raw text. Guard it with a check
  that greps `src/` for `\\[(),;]` and fails the build.
- **Bulk-fixing delimiters safely.** To convert a book that wrongly used `\(...\)`:
  `sed -E -i '' 's/\\\(/$/g; s/\\\)/$/g; s/\\[,;]/ /g' src/*.md staging/*.md`.
  **Back up `src/` first and dry-run on one file** — the spacing macros are a
  shell-escaping trap: `s/\;/ /g` (one backslash) matches *every* semicolon and
  silently eats prose `;` and `&nbsp;` HTML entities. The character class
  `\\[,;]` sidesteps it. Always rebuild and confirm `&nbsp;` survived
  (`grep -c 'nbsp;'`) and inline math now renders before moving on.
- **ASCII-only outside math.** Literal Unicode in prose (arrows `→`, superscripts
  `²`/`ˣ`, `½`) renders in HTML but throws *"Missing character"* warnings and
  drops glyphs in the xelatex PDF (STIX fonts lack them). Write `\to`, `x^2`,
  `e^x` inside math instead. Chapter H1s and SUMMARY entries are NOT math-rendered
  in the PDF/sidebar — keep them plain ASCII (`e^x`, not `eˣ`).
- **Admonish titles are plain text**, not math: `title="powers of x"`, never
  `title="powers of $x$"` (it renders literally in the title bar).
- **Callouts:** `admonish example` (worked examples), `tip` (hints), `warning`
  (common mistakes), `note` (asides/next-up), `abstract`/`info` (boxed rules).
  Don't nest them. Keep one blank line discipline; mismatched ```` ``` ```` fences
  break the build.
- **ASCII diagrams** (branching/expression-tree figures, flowcharts) go in a
  **plain fenced code block** — *not* admonish, *not* math. They render monospace
  in HTML *and* in the xelatex PDF: Menlo (the monofont) has the box-drawing
  glyphs `│ ┌ ┐ └ ┘ ├ ┤ ┬ ┴ ─` and `·`. Use **ASCII inside** the diagram
  (`x^2`, `e^(3x)`, `-`), never Unicode superscripts/minus, or the PDF warns.
  No image pipeline needed — this is the cheapest way to add figures.
- Write one **gold-standard chapter first**, then have every other chapter match
  its header block, section order, and callout usage.

## Parallel authoring (for multi-chapter books)

Independent chapters → dispatch one agent per chapter (see
`superpowers:dispatching-parallel-agents`). Each agent prompt must: (a) tell it to
**Read the exemplar chapter + a conventions/PLAN doc first**, (b) give a precise
per-chapter content spec, (c) restate the ASCII-outside-math and delimiter rules.

**Known gotcha:** sub-agents sometimes leak their tool-call closing tags
(`</content>`, `</invoke>`, `antml:` fragments) into the file tail. After a parallel
run, always:
`grep -rn '</content>\|</invoke>\|antml:\|<parameter' src/` and strip any hits.

**Answers/solutions pattern:** have each chapter agent write its answer key to a
`staging/<chapter>-answers.md` fragment (avoids write conflicts on one file), then
assemble `src/answers.md` from the fragments via a `just answers` recipe so it's
reproducible.

## Multi-agent review (for the formal sibling-series books)

The rigorous books (algebra/geometry/precalculus/calculus) review each chapter
with a **team of specialist agents** before accepting it. Orchestrated by
`scripts/run-review.py` (snapshot + manifest of agents to dispatch) and
`scripts/aggregate-review.py` (roll verdicts into `summary.md`). Roster lives as
`docs/review-agents/<name>-reviewer-prompt.md` files (auto-discovered):

- **math** (correctness — the highest-stakes; a wrong answer trains a wrong habit),
  **clarity**, **voice** (AI-slop list), **consistency** (numbering/refs),
  **source-originality**, and a topic-specific **applied** reviewer
  (applied-physics / applied-trig — dispatched only when the chapter has
  §Applications or ExamStyle). Problems volumes add a **coverage** reviewer.

Hard-won process rules (each prevented a wasted round):

- **A chapter is APPROVED iff every agent report says `## Verdict: APPROVED`** —
  trust per-agent verdicts, not the aggregate header's bullet count.
- **Every fix dispatch carries the brief:** *"re-read the chapter after your edit
  and flag anything you may have introduced."* Fixes introduce new errors; this is
  the single highest-leverage instruction.
- **3-round cap, then escalate** to the user with a written root-cause summary.
- The **applied reviewer is the highest-yield specialist** — treat its findings as
  blocking even when the math is algebraically correct.
- Dispatch all agents for a round in **one parallel batch** (17 agents return in
  ~the time of 1). See `superpowers:dispatching-parallel-agents`.

### Review roster for technical / code books

A technical book is reviewed by a team that attacks the *technology and the
prose*, not the math. Dispatch one agent per lens in a single parallel batch; each
must identify problem areas **and offer a concrete alternative** — revised text, or
a changed argument/point:

- **technical-accuracy** — claims where the technology does not behave as the text
  describes (the highest-stakes lens; treat its findings as blocking).
- **code-supports-claim** — code samples that do not firmly demonstrate the point
  the surrounding text is making.
- **logical-flow** — places where the text does not follow from one point to the
  next.
- **voice** (AI-slop) — passages that read like generated AI text rather than a
  human developer; flag and rewrite.

Same process rules as above: a chapter is APPROVED only when *every* agent report
says `## Verdict: APPROVED`; every fix dispatch carries the brief *"re-read the
chapter after your edit and flag anything you introduced"*; 3-round cap, then
escalate to the user with a root-cause summary.

## Editing an existing book

- **Renumbering / retitling ripples widely.** Inserting a mid-book chapter or
  changing the day count touches: `book.toml` `title` + PDF `output-file`,
  `SUMMARY.md` heading and entries, every `Day N` / `N days` / `Beyond the N days`
  reference, the per-chapter answer-fragment list in the justfile, and internal
  "tomorrow"/cross-links. `grep -rniE 'day 14|14 days|fourteen' src/` and fix
  each — but **do not touch sibling-book titles** (e.g. a real `Limits in 14 Days`
  reference). Then regenerate `answers.md` and re-run the gate.
- PDF page count (sanity check): `mdls -name kMDItemNumberOfPages -raw <pdf>`.

## Final verification (before declaring done)

Codify these as `just test` recipes (see REFERENCE.md) so the gate is one command
and `deploy` can depend on it. **Run the gate after every major change, not just
at the end** — batching verification lets bugs compound across commits. When a bug
slips past the gate, fix the bug *and* tighten the gate in the same session.

- [ ] `mdbook build` produces HTML **and** PDF with **no `[WARNING]` / "Missing
      character"** lines (missing-character = a Unicode glyph the PDF font lacks;
      fix the source). `just test` must include `mdbook build` — the cheaper checks
      do **not** resolve `{{#include}}` directives, so a self-referencing include
      can sit in HEAD while everything else stays green.
- [ ] `scripts/chapter-audit.py` clean — odd `$`, `\(`-delimiters, fence parity,
      literal Unicode, leaked tool tags, SUMMARY coverage, placeholders.
- [ ] `scripts/pdf-math-check.py` clean — no raw TeX survived into the PDF.
- [ ] For problems/solutions books: `scripts/answer-audit.py` clean — **the primary
      correctness gate.** A polished `Problem / Setup / Solution` block can still be
      mathematically wrong; only the CAS substitution catches a wrong sign or
      coefficient. Build it in Phase 0; write the entry when you write the solution.
- [ ] `src/SUMMARY.md`: all `# Part` / `# Appendices` headings sit **before** the
      `---` suffix-chapter separator — a `# heading` + list after `---` fails
      `mdbook test` with "Suffix chapters cannot be followed by a list."
- [ ] `src/answers.md` reproduces from the `staging/` fragments (regenerate, diff).
- [ ] Run an adversarial math-checker agent over all chapters + answers (recompute
      every example) — even with answer-audit, prose-answer/proof problems need it.
