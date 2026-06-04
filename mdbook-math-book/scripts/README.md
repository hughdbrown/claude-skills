# scripts/ — reusable maintenance tools for a house-style math mdBook

Copy this whole directory into a new book's `scripts/` and wire it into the
`just test` / `just check` gate (see REFERENCE.md). Every script is a
[uv](https://docs.astral.sh/uv/) PEP-723 single file — `./script.py` runs it with
its declared deps and no virtualenv. They also run under plain `python3` if
`sympy`/`pyyaml` are already installed. Distilled from seven books in
`~/projects/books/math`; each check maps to a bug that actually shipped.

| Script | Gate it provides | Why a clean `mdbook build` misses it |
|---|---|---|
| `chapter-audit.py` | Markdown **source** health: odd `$` (math/prose not separated), `\(`-style delimiters, fence parity, literal Unicode in prose, leaked tool tags, placeholders, SUMMARY coverage | These render or silently drop — the build still exits 0 |
| `check-refs.py` | Every cross-reference (`Theorem N.M`, `§N.K`, `Chapter N`, `Eq. (N.M)`, `Appendix X`, and cross-volume `V1 …`) **resolves** | renumbering/retitling/parallel drafting break refs silently; mdbook doesn't validate them |
| `pdf-math-check.py` | Raw TeX (`\frac`, `$$`, `\begin{`) leaked into the **rendered PDF** | A too-old mdbook-pandoc or missing `math = true` passes literal `$$…$$` to the page; the build succeeds |
| `answer-audit.py` | Every claimed answer **substituted back through sympy** | A fluent, well-formatted solution can be mathematically wrong — prose review will not catch a sign error |
| `run-review.py` + `aggregate-review.py` | Multi-agent review **orchestration**: snapshot + manifest of agents to dispatch, then aggregate their verdicts | Not a build concern — it's the chapter-quality workflow (see SKILL.md "Multi-agent review") |

## Order of importance

1. **`chapter-audit.py`** — run on every book. Catches the silent-render class
   (the `$...$` vs `\(...\)` delimiter trap, stray `$` that bleeds prose into a
   formula, missing-character Unicode) before it reaches HTML or PDF.
2. **`pdf-math-check.py`** — run after every `mdbook build`. "Build passed" is
   NOT "math rendered." This is the only proof the PDF is correct.
3. **`answer-audit.py`** — for any *problems/solutions* book this is the primary
   correctness gate, not an optional extra. Build it in Phase 0, write one
   `answers.yaml` entry per problem as you draft the solution, target ≥60%
   coverage (proofs/sketches/classification legitimately `skip: true`).

## check-refs.py — cross-volume usage

Internal refs need no config. For a problems volume citing its exposition
volume, register the sibling under each prefix you cite it by (abbreviations
resolve automatically), e.g.:

```sh
check-refs.py --cross-vol "Volume 1=../precalculus/src" --cross-vol "V1=../precalculus/src"
```

Add a label type the book uses (e.g. `Example`) with `--label-types`, not a code
edit. This flag-driven design is the deliberate fix for the "three edits to
check-refs.py per new book" tax the books' lessons-learned documented.

## review pipeline — run-review.py / aggregate-review.py

`run-review.py <chapter> <round>` snapshots the chapter and writes
`docs/reviews/<chapter>/round-<round>/manifest.md` — a table of agents to
dispatch. The roster is auto-discovered from `docs/review-agents/*-reviewer-prompt.md`
(so renaming the applied reviewer per book needs no code edit). The controller
dispatches each agent with the Task tool; each writes `<agent>.md` with a
`## Verdict:` line. Then `aggregate-review.py <chapter> <round>` rolls them into
`summary.md`. APPROVED requires *every* verdict to be APPROVED — placeholder
`- None.` bullets are ignored (the documented false-CHANGES_REQUIRED trap). See
SKILL.md "Multi-agent review" for the workflow and reviewer roster.

## answer-audit.py — schema

`scripts/answers/answers.yaml` is a list of entries; see the seed file for one
worked example of each type. Exact keys (aliases raise `KeyError` at run time):

- `arithmetic` — `expression`, `claimed_value`, optional `tolerance`
- `equation_solutions` — `var`, `lhs`, `rhs`, `claimed_solutions` (list)
- `comparison` — `lhs`, `rhs`, `relation` (`<` `<=` `>` `>=` `==`)
- `set_equality` — `lhs` (list), `rhs` (list)
- `system` — `vars` (list), `equations` (list of `"lhs = rhs"`), `claimed_solution` (dict)
- `matrix_solution` — `matrix` (rows), `rhs` (list), `claimed_solution` (list)

Escape hatches: `skip: true` (not CAS-checkable — counted, not run);
`known_defect: true` (expected-fail; reports "fix detected" if it starts passing).
Powers are `^`, implicit products (`2x`, `4px`) work. For trig/calculus books,
add names to `PARSE_LOCALS` at the top of the script. When sympy won't simplify a
true identity, add a `tolerance` to fall through to the numeric check.

**Do not regex-parse LaTeX into these expressions.** It silently produces wrong
entries (`4px` → `4*px`, a single symbol). If you must ingest LaTeX, write a real
tokenizing parser; otherwise author the sympy strings by hand as above.
