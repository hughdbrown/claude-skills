# Design — 15-day-book-reviewer

Date: 2026-09-03. Author: Hugh Brown with Claude.

## Purpose

One skill that reviews any book in the "N in 15 Days" series for five things
the author asked for — technical coverage, correct text and problems/answers,
content pitched at the right level, plagiarism, and removal of AI/LLM tropes —
plus four lenses added during design: a rendered-output gate before review,
figure inspection, dangling-promise checking, and series consistency. It also
fixes the policy for the sub-agents an LLM controller may deploy.

## Scope

The 15-day family only: `math/15-day-*`, `sat/15-day-*`, `aerospace/15-day-aerospace`,
`darwin/14-day-origin-of-species`, and future siblings with the same shape
(`src/dayNN.md`, `staging/dayNN-answers.md`, `PLAN.md`, `justfile`). The
formal math texts and the developer-facing books keep their own rosters under
`mdbook-math-book` and `mdbook-programming`.

## Decisions (each confirmed by the author)

| Question | Decision |
|---|---|
| Plagiarism check | LLM recall + within-book echo + web sampling of distinctive sentences (WebSearch/firecrawl). No local reference corpus. |
| After review | Apply blocking fixes automatically; list non-blocking for the author. |
| Trope lens | Forbidden phrase list is blocking; structural tics blocking only when clustered; a third "note" tier for teaching moves the series uses on purpose. |
| Dispatch | Hybrid by lens: correctness per day-pair (Opus), voice/level per day-triple (Sonnet), cross-cutting lenses whole-book, originality on Opus. ~20 agents per round. |
| Local model | Optional lane on the LAN ollama host; leads only; skipped when unreachable. |
| "Right level" | Prerequisite audit against PLAN.md + earlier days, and a 30-minute budget measured against the median day. |
| Mechanical verification | Correctness reviewers must run a sympy checks file per chunk (or the book's own answer-audit) in addition to solving by hand; a report without a runnable checks file is unverified. |

## What was inherited from prior practice

From `sat/15-day-sat-math`: the role-prompt shape (purpose, method, blocking,
non-blocking, report format), the `## Verdict:` contract, the snapshot +
manifest + aggregate scripts, and the lessons-learned rules (reviewers never
edit; verify the verifier; re-read after fixing; three-round cap; APPROVED
iff every verdict). From the linear-algebra and sequences books: the day-pair
correctness wave and the whole-book consistency/voice pass. From the Darwin
book: self-repetition, unmarked near-quotes, "It is not X. It is Y." clusters,
dangling promises. From the SAT book's scripts: the blind local-model re-solve.

## What is new

- Deterministic scanners for tropes, self-repetition, pacing, and plagiarism
  sampling, run once per round so every reviewer cites the same numbers.
- A roster file that fixes chunk, model, and blocking per lens, so the policy
  is data rather than a reviewer's judgment.
- A per-chunk sympy checks file as a hard requirement of the correctness lens.
- Level and promises as distinct lenses.
- Feature detection so figure, topic, and LAN lanes dispatch only when the
  book has them.

## Implementation constraints (from the author, mid-build)

- Markup is never regex-scanned: `scripts/mdprose.py` parses Markdown with
  markdown-it-py + dollarmath; TOML via `tomllib`; the manifest is JSON.
  Regexes are confined to natural-language text (phrase list, sentence split).
- Command-line parsing uses `click`, not `argparse`.
- Correctness reviewers must run mechanical checks (sympy) in addition to
  solving by hand.

## Testing

Baseline (no skill): an agent asked to review Day 5 of the limits book solved
by hand but ran no code ("doesn't warrant a symbolic-math script"), read only
the day and its key, excused the tropes as "deliberately chatty," measured
nothing against the book's baseline, and wrote free-form prose with no verdict.
Each of those is now a named rule or a rationalization-table row. The green
test runs a controller with the skill on a scratch copy of the same book.
