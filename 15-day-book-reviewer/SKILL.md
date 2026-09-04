---
name: 15-day-book-reviewer
description: Multi-agent editorial review of a book in Hugh Brown's "N in 15 Days" mdBook series (math/15-day-*, sat/15-day-*, aerospace, darwin). Use when asked to review, check, proofread, audit, or QA a 15-day book or one of its days for correctness of text and problems/answers, coverage, reading level and pacing, plagiarism, or AI-sounding prose, or when a book is finished drafting and needs its adversarial review round before deploy.
---

# 15-day book reviewer

You are the **controller**. You orient, gate, dispatch reviewers by lens,
verify their reports, dispatch fixers for blocking findings, and stop after
three rounds. Reviewers never edit; fixers never review; you never take a
reviewer's word for a number.

Scripts: `~/.claude/skills/15-day-book-reviewer/scripts/` (alias `$S` below).
Lens briefs: [LENSES.md](LENSES.md). Pipeline detail, fix protocol,
escalation, rationalization table: [REFERENCE.md](REFERENCE.md).

## Quick start

```sh
cd ~/projects/books/math/15-day-limits
just test                                   # gate: the book must build
$S/run-review.py --round 1                  # snapshot, scans, manifest, contract
# dispatch the agent rows of docs/reviews/round-1/manifest.md in waves of at most five
$S/aggregate-review.py --round 1            # APPROVED iff every blocking lens approves
# fix blocking findings per file, re-review touched days as round 2, commit
```

## Workflow checklist

Create a todo per line and work them in order.

1. **Orient.** Read `PLAN.md`, `docs/design/prompt.md`, the style guide (or
   PLAN's conventions), `src/SUMMARY.md`, `src/day01.md`. Note prior rounds
   under `docs/reviews/`.
2. **Gate.** `just test` green; scanners run once by you; rendered HTML and
   PDF spot-checked. A book that does not build is not reviewed.
3. **Round setup.** `run-review.py --round N`. Read `contract.md`; add an
   `## Assumed background` section if PLAN.md lacks one.
4. **Dispatch** the manifest's agent rows in waves of **at most five**,
   correctness first (REFERENCE §4 order), model and files per the manifest,
   prompt = rules + report format + lens brief + contract. Launch the next
   wave as completions arrive. Start `qwen-resolve` in the background if the
   manifest lists it.
5. **While they run:** three random plagiarism searches yourself; two
   exercises per day-pair solved yourself.
6. **Aggregate.** `aggregate-review.py --round N`. Re-run every correctness
   `checks/*.py`; recompute every number a finding cites; re-solve one
   approved item per correctness report.
7. **Fix** blocking findings only, one fixer per file, with the re-read brief
   (REFERENCE §6). `just test`, scanners, `just answers` if staging changed.
   Write `fixes.md` with a *Deferred* list of non-blocking findings.
8. **Re-review** touched days as the next round; consistency and promises
   whole-book.
9. **Commit** on approval: `Apply review fixes, round N: ...`.
10. **Escalate** after round 3 or a regressing fix: `docs/reviews/escalation.md`
    with root cause and the decision needed. No round 4.

## The lenses (roster.toml decides chunk, model, blocking)

| Lens | Chunk | Model | Finds |
|---|---|---|---|
| correctness | day-pair | opus | wrong answers/steps; must solve first, then run a sympy checks file, then read the key |
| level | day-triple | sonnet | untaught prerequisites, over-budget days, bad exercise ramp |
| voice | day-triple | sonnet | scanner BLOCK lines, structural AI tells, register drift, repeats |
| coverage | book | sonnet | plan rows untaught, core topics missing, reference pages out of sync |
| consistency | book | sonnet | refs, numbering, notation, constants, answers order |
| promises | book | sonnet | front matter, glossary, teasers promising what the book never delivers |
| originality | book | opus | web-sampled sentences, quotations, recalled sources, within-book echo |
| figures | book | sonnet | rasterize and look: overlaps, wrong geometry, shadowed glyphs |
| series | book | sonnet | sibling titles and notation (non-blocking) |
| topic | day-triple | opus | the book's own `docs/review-agents/` brief, when present |
| qwen-resolve | script | LAN | blind re-solve; leads only, when the host answers |

## Hard rules

- A round is APPROVED iff **every blocking lens** says `## Verdict: APPROVED`.
- A correctness report with no runnable `checks/<chunk>.py` is unverified: re-dispatch.
- Every fix dispatch carries *"re-read the file after your edit and flag anything you may have introduced."*
- Non-blocking findings are deferred to the user, never silently applied.
- Three rounds, then escalate. Never start round 4.

## Common mistakes

- Reviewing before `just test` passes, then chasing findings the build would have caught.
- One whole-book correctness agent "to keep context": it samples. Use the roster.
- Launching every agent at once: they share one session limit and die together. Five at a time.
- Trusting "verified" in a report. Run the checks file. Recompute the number.
- Letting a voice reviewer excuse a forbidden phrase as "the book's chatty voice."
- Fixing a finding in `src/answers.md` instead of `staging/` (it is regenerated).
