# REFERENCE — house-style mdBook templates

Copy-paste starting points. Adjust titles/filenames per book. The live, working
copies are in `~/projects/books/math/14-day-derivatives` (informal) and
`~/projects/books/math/calculus` (formal, with theorem environments).

## book.toml (informal math book)

```toml
[book]
title    = "Your Title"
authors  = ["Hugh Brown"]
language = "en"
src      = "src"
description = "One-line description."

[output.html]
mathjax-support = true
default-theme   = "light"
additional-css  = ["./mdbook-admonish.css", "theme/figures.css"]
additional-js   = ["theme/figures.js"]

[output.html.search]
enable = true

[output.html.fold]
enable = true
level  = 1

[preprocessor.admonish]
command = "mdbook-admonish"
assets_version = "3.1.0" # managed by `mdbook-admonish install`

[output.pandoc.markdown.extensions]
math = true

[output.pandoc.profile.pdf]
output-file        = "your-title.pdf"
pdf-engine         = "xelatex"
standalone         = true
table-of-contents  = true
toc-depth          = 2
number-sections    = false
include-in-header  = ["theme/pandoc/preamble.tex"]

[output.pandoc.profile.pdf.variables]
documentclass = "book"
papersize     = "letter"
fontsize      = "11pt"
linestretch   = "1.1"
mainfont      = "STIX Two Text"
mathfont      = "STIX Two Math"
monofont      = "Menlo"
```

For a **formal** book, set `number-sections = true`, add theorem environments to
the preamble, and add Lua filters (`inject-appendix.lua`, `needspace-headers.lua`,
`image-blocks-to-figures.lua`, `rewrite-figure-ext.lua`) under `filters = [...]` —
copy them from `~/projects/books/math/calculus/theme/pandoc/`.

## theme/head.hbs

```html
<script>
window.MathJax = {
  tex2jax: {
    inlineMath: [['\\(', '\\)'], ['$', '$']],
    displayMath: [['\\[', '\\]'], ['$$', '$$']],
    processEscapes: true
  }
};
</script>
```

## theme/pandoc/preamble.tex (light — informal books)

```latex
\usepackage{amsmath, amssymb, mathtools}
\usepackage{microtype}
% Default book-class list spacing is near-zero, which reads cramped when items
% hold multi-line math (problems books especially). Open it up:
\usepackage{enumitem}
\setlist[enumerate]{itemsep=0.5em, topsep=0.6em, parsep=0.25em}
\setlist[itemize]{itemsep=0.5em, topsep=0.6em, parsep=0.25em}
\widowpenalty=10000
\clubpenalty=10000
\raggedbottom
\usepackage{needspace}
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[RO]{\small\itshape\nouppercase{\leftmark}}
\fancyhead[LE]{\small\itshape\nouppercase{\leftmark}}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0.4pt}
\renewcommand{\footrulewidth}{0pt}
\fancypagestyle{plain}{%
  \fancyhf{}\fancyfoot[C]{\thepage}%
  \renewcommand{\headrulewidth}{0pt}\renewcommand{\footrulewidth}{0pt}%
}
\AtBeginDocument{%
  \hypersetup{colorlinks=true, linkcolor=black, citecolor=black,
    urlcolor=blue!50!black, pdfborder={0 0 0},
    bookmarksnumbered=true, bookmarksopen=true, bookmarksopenlevel=1}%
}
```

`figures.css` / `figures.js` (figure numbering + caption wrapping): copy verbatim
from `~/projects/books/math/14-day-derivatives/theme/`.

## PDF build hazards (each cost real debug time across the book series)

| Symptom | Root cause | Fix |
|---|---|---|
| PDF shows literal `$$ \mathbb{N} = … $$` | mdbook-pandoc < 0.10, or `math = true` missing from `book.toml` | Pin mdbook-pandoc 0.10.6; key is `math = true` (not `tex_math_dollars`) |
| `Missing character: There is no ▮ (U+25AE)` | STIX Two has no `▮` / `✓` / Unicode-arrow glyph | `$\blacksquare$`, `$\checkmark$`, `\to` — never literal Unicode in source |
| `Failed to parse CSS …: invalid @ rule '@media'` | mdbook-pandoc's CSS parser rejects `@media` | Strip `@media` blocks from `mdbook-admonish.css`; re-strip after every `mdbook-admonish install` |
| `Unable to normalize link '<arg>'` | pandoc reads `[t](a)` inside `$…$` as a link | Never use bare `[...](...)` inside math; use `\bigl( \bigr)`, `\left[ \right]` |
| `Undefined control sequence. \hypersetup` | `include-in-header` runs before pandoc loads hyperref | Wrap in `\AtBeginDocument{\hypersetup{…}}` (already in the light preamble above) |
| Appendices labeled chapters 22–25, not A–D | book class needs `\appendix` fired mid-document | pandoc Lua filter `theme/pandoc/inject-appendix.lua` + `filters` key in the pdf profile |
| Odd/even page numbers in different positions | `\pagestyle{headings}` default | Add `\pagestyle{plain}` for bottom-centered folios; redefine `\cleardoublepage` to make blank versos `\thispagestyle{empty}` |
| Raw LaTeX in a ```` ```{=latex} ```` block prints verbatim | mdbook-pandoc's CommonMark parser doesn't enable `raw_attribute` | Use a Lua filter instead — `{=latex}` fenced blocks do not work |
| `# Chapter N — Title` doubles to "N Chapter N — Title" in TOC | book class prepends "Chapter N" after `\chapter{}` | Write `# Title` only; never put the chapter number in the H1 |

Formal books add theorem environments via `amsthm`/`tcolorbox` and number with
`\numberwithin{equation}{chapter}` — copy `preamble.tex` and the Lua filters from
`~/projects/books/math/algebra` (formal) rather than re-deriving.

## justfile

```make
default: build

build:
    mdbook build

serve:
    mdbook serve --open

pdf: build
    @open book/pandoc/pdf/your-title.pdf 2>/dev/null || true

clean:
    mdbook clean

admonish-assets:
    mdbook-admonish install .

# The verification gate. `deploy` should depend on this. Run it after every
# major change, not just at the end. mdbook build must stay in the gate — the
# cheaper checks don't resolve {{#include}} directives.
# For a PROBLEMS/solutions book, append `answer-audit` to this line (it needs a
# populated scripts/answers/answers.yaml; it is the primary correctness gate).
test: check-warnings chapter-audit check-refs pdf-math-check check-answers
    @echo "OK: all checks passed."

# Every cross-reference resolves. For a problems volume citing its exposition
# volume, add: --cross-vol "Volume 1=../<book>/src" --cross-vol "V1=../<book>/src"
check-refs:
    @UV_CACHE_DIR=.uv-cache uv run scripts/check-refs.py

# Fail on ANY pandoc/mdbook warning (missing PDF glyph = a Unicode char to fix).
check-warnings:
    #!/usr/bin/env bash
    set -euo pipefail
    out="$(mdbook build 2>&1 || true)"
    echo "$out" | grep -Ei 'WARNING|Missing character' && { echo FAIL >&2; exit 1; } || echo "no warnings."

# Markdown source health (replaces the old grep recipes — robust, escape-aware):
# odd $, \(-delimiters, fence parity, literal Unicode, leaked tags, SUMMARY coverage.
chapter-audit:
    @UV_CACHE_DIR=.uv-cache uv run scripts/chapter-audit.py

# No raw TeX leaked into the rendered PDF (build passing != math rendered).
pdf-math-check: check-warnings
    @UV_CACHE_DIR=.uv-cache uv run scripts/pdf-math-check.py

# Problems books only: every claimed answer substituted back through sympy.
answer-audit:
    @UV_CACHE_DIR=.uv-cache uv run scripts/answer-audit.py

# Multi-agent review (formal books). `review` sets up the round + manifest; the
# controller then dispatches the agents; `aggregate` rolls up their verdicts.
review chapter round:
    @UV_CACHE_DIR=.uv-cache uv run scripts/run-review.py {{chapter}} {{round}}

aggregate chapter round:
    @UV_CACHE_DIR=.uv-cache uv run scripts/aggregate-review.py {{chapter}} {{round}}

# Generated answers.md must still match the staging fragments (day-per-lesson books).
check-answers:
    #!/usr/bin/env bash
    set -euo pipefail
    t=$(mktemp); cat staging/_answers-header.md > "$t"
    for d in 02 03 ...; do cat "staging/day$d-answers.md" >> "$t"; printf '\n\n---\n\n' >> "$t"; done
    diff -q "$t" src/answers.md >/dev/null || { echo "run 'just answers'" >&2; rm -f "$t"; exit 1; }; rm -f "$t"
```

If you use the staging-fragments answers pattern, add:

```make
answers:
    @cat staging/_answers-header.md > src/answers.md
    @for d in 01 02 03 ...; do \
        cat staging/$d-answers.md >> src/answers.md; \
        printf '\n\n---\n\n' >> src/answers.md; \
    done
```

## Lesson/chapter template (informal day-per-lesson)

```markdown
# Day N — Title

> **Today in one line:** <single-sentence promise>
> **Time:** ~30 min &nbsp;•&nbsp; **You'll need:** <prior days>

## The big idea
<intuition first>

​```admonish example title="Worked example"
... step by step ...
​```

## Try it yourself
1. ...

​```admonish tip title="Stuck?"
<nudge, not full answer>
​```

## What you learned today
- recap bullets

​```admonish abstract title="Rule of the day"
$$ ... $$
​```

​```admonish note title="Tomorrow"
<hook to Day N+1>
​```
```
