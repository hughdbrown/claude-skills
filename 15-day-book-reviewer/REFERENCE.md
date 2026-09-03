# Reference — the review pipeline in detail

## 0. Where things live

```
<book>/
├── PLAN.md                     conventions, day table, audience, assumed background
├── docs/design/prompt.md       the originating brief (if present)
├── docs/style-guide.md         forbidden phrases, register (if present)
├── docs/review-agents/*.md     a book-specific topic lens (if present)
├── src/dayNN.md  staging/dayNN-answers.md  src/answers.md (assembled)
└── docs/reviews/round-N/       one directory per round (created by run-review.py)
    ├── contract.md             substitutions every reviewer receives
    ├── manifest.json / .md     the dispatch table (machine / human)
    ├── snapshot/               src+staging as reviewed
    ├── scans/                  slop-scan, self-echo, pacing-audit output
    ├── plagiarism-samples.md   the originality checklist
    ├── checks/<chunk>.py       correctness reviewers' sympy check files
    ├── <lens>--<chunk>.md      one report per dispatch
    ├── summary.md              aggregate verdict + fix work list
    └── fixes.md                what the controller changed and why
```

## 1. Orient (controller, before anything else)

Read, in this order: `PLAN.md`; `docs/design/prompt.md`; `docs/style-guide.md`
or the conventions section of `PLAN.md`; `src/SUMMARY.md`; `src/day01.md`.
Then `git log --oneline | head` and `ls docs/reviews` to learn what rounds
already ran. Write nothing yet. If `PLAN.md` has no *assumed background*
section, derive one from Day 1's "You'll need" and the audience paragraph and
put it in `contract.md` under `## Assumed background` so the level reviewer has
a source.

## 2. Gate (controller)

```sh
just test            # or: mdbook build && the book's check-* recipes
```

A failing gate stops the round: fix the build or report it, never review a
book that does not build. Then run the scanners once yourself so you know the
numbers before reviewers cite them:

```sh
S=~/.claude/skills/15-day-book-reviewer/scripts
$S/slop-scan.py; $S/self-echo.py; $S/pacing-audit.py
```

Render check: `ls book/html/*.html | head` and, if the book builds a PDF,
`pdftotext book/pandoc/pdf/*.pdf - | grep -c '\\frac'` should print 0. If the
book has `scripts/pdf-math-check.py`, run it.

## 3. Set up the round

```sh
$S/run-review.py --round 1          # add --days day03,day04 on a re-review
```

This snapshots, detects features (math, figures, quotes, a topic lens, the
LAN model), re-runs the scanners into `scans/`, writes the plagiarism
checklist, and produces `manifest.json` (what `aggregate-review.py` reads),
`manifest.md` (the same table for you), and `contract.md`. The scripts need
`uv` on PATH; each fetches its own deps.

## 4. Dispatch (one parallel batch)

For every agent row in the manifest, one `Agent` call, all in the same
message. Start the `script` row (qwen-resolve) in the background first. The
prompt for each agent is assembled from four parts, in this order:

```
<LENSES.md "Rules for every reviewer">
<LENSES.md "Report format">
<the lens section named in the manifest's Brief column>
<contract.md verbatim>
Your files: <Files column>. Write your report to: <Output column>.
```

Model per row is the manifest's Model column (`opus` for correctness,
originality, and the topic lens; `sonnet` otherwise). Do not downgrade a
correctness dispatch to save cost; do not upgrade a voice dispatch because it
"seems important" — the roster is the policy. Use the roster's chunking; a
whole-book correctness agent samples, and sampling is forbidden.

While agents run, do the controller's own share: re-run three random
plagiarism searches from the checklist yourself, and spot-solve two exercises
per day-pair so you can judge the correctness reports when they land.

## 5. Aggregate

```sh
$S/aggregate-review.py --round 1
```

APPROVED iff every blocking lens reported APPROVED with no real blocking
bullet. Missing reports count as CHANGES_REQUIRED. Before trusting a
correctness report:

- run its `checks/<chunk>.py` yourself; if it does not exist or does not run,
  the report is unverified and the dispatch is re-run with the rule quoted;
- re-solve one item it approved, chosen at random;
- for every finding that names a number, recompute the number.

"A subagent's claim to have verified something is not verification."

## 6. Fix (blocking findings only)

Group the work list in `summary.md` by file. For each file with blocking
findings, dispatch **one fixer** (Sonnet for prose, Opus for anything with
math) with: the findings for that file verbatim, the relevant lens brief for
context, and this brief, always:

> Apply only the listed findings. Do not restyle, reflow, or improve anything
> else. After editing, re-read the whole file and flag anything you may have
> introduced (a broken fence, a new delimiter, a changed answer, a new phrase
> from the forbidden list). If a finding is wrong, do not apply it; say why.

Fixers never touch `src/answers.md` directly; edit `staging/` and regenerate
with `just answers`. After all fixers return: `just test`, the three scanners,
and `git diff --stat`. Record what changed in `fixes.md`. Non-blocking
findings are listed there under *Deferred* with the file and line, for the
user.

Then re-review only the touched days (`run-review.py --round 2 --days ...`)
with every lens that raised a blocking finding on them, plus consistency and
promises whole-book (fixes ripple). Commit when the round is approved:

```
Apply review fixes, round N: <one line per lens with a count>
```

## 7. Escalate

Three rounds without approval, or any round where a fix re-introduces a
finding it was meant to close, stops the loop. Write `docs/reviews/escalation.md`:
the findings that will not close, the root cause as best you can name it
(a convention the book never fixed; an outline error; a reviewer and the
contract disagreeing), and what decision the user must make. Do not start
round 4.

## 8. Rationalizations this skill exists to stop

| Excuse | Reality |
|---|---|
| "The material is too simple to need a sympy script" | The last shipped defect was an off-by-one on an easy day. Write the checks file; thirty seconds. |
| "I solved them by hand, that's verification" | Hand solutions share the author's blind spots. Solve by hand *and* run the check. |
| "I only need the day file and its key" | Level and voice are judged against `PLAN.md` and the exemplar. Without them you are judging taste. |
| "That phrase is the book's deliberately chatty voice" | The forbidden list bounds the voice. Dispute the list under Contract disputes; still report the hit. |
| "It reads human to me" | One reader's impression is not a check. Count the tells, cite them, and let the scan and the exemplar decide. |
| "Time budget is a soft concern, not a finding" | The book promises 30 minutes. Over budget is blocking for the level lens; propose the cut. |
| "I'll review the whole book in one agent to keep context" | A whole-book correctness agent samples. Sampling is forbidden. Use the roster's chunks. |
| "The reviewer said it verified the numbers" | Re-run its checks file. No file, no verification. |
| "I'll apply the non-blocking findings too while I'm in there" | Non-blocking is the user's call. Defer and list. |
| "Round 3 nearly landed; one more round" | Three is the cap. Escalate with a root cause. |

## 9. Adapting to a book

- **No `staging/`:** correctness reviewers read the answers section of the
  day or `src/answers.md`; the manifest's file list adjusts automatically.
- **Non-math book (Darwin):** correctness means fidelity to the source and
  the world; the `checks/` file holds `skip` entries with the claim checked
  and how. Pacing uses `--exercise-heading '^##\s+try it'` (already the default).
- **SAT/PSAT/ACT items in per-item directories:** the book's own
  `docs/review-agents/` lenses take precedence (topic lens); run its
  `answer-audit.py` as the mechanical check.
- **Phrase list:** copy `scripts/slop-phrases.txt` into the book as
  `docs/slop-phrases.txt` and pass `--phrases` when the book's style guide
  adds or exempts phrases; never edit the skill's copy for one book.
