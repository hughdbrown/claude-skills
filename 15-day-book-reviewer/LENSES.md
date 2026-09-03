# Lens briefs — one per reviewer role

Each section below is the brief the controller pastes into an Agent dispatch,
after the *Rules for every reviewer* and the round's `contract.md`. Briefs are
deliberately complete: a reviewer gets this file's section, the contract, and
nothing else about the process.

## Rules for every reviewer

1. **Read-only.** You never edit a book file. You report; the controller fixes.
2. **Orient before judging.** Read `PLAN.md` (conventions, day table, assumed
   background), the style guide if the contract names one, and `src/day01.md`
   as the voice and shape exemplar, *before* the files you were assigned. A
   judgment made without the book's own contract is a taste judgment and will
   be discarded.
3. **Cite `file:line` for every finding**, and give the fix — revised text, or
   the changed argument — not only the complaint.
4. **Never claim to have run a command you did not run.** Paste the command and
   its last line. A report that says "verified" with no reproducible evidence
   is treated as unverified. Run the skill's scripts with `uv run --script`
   (plain `python3` lacks their dependencies); never substitute a hand-written
   grep or regex for a scanner — the round's `scans/` already holds its output.
5. **The contract decides, not your taste.** If the style guide forbids a phrase,
   it is a finding even where you think it works. If you believe the contract is
   wrong, say so under a separate `## Contract disputes` heading; do not soften
   the finding.
6. **Do not sample.** Every exercise, every example, every file assigned. If you
   run out of budget, say exactly which items you did not reach.
7. **Blocking vs non-blocking is fixed by your brief**, not by how confident you
   feel. Put uncertainty in the finding text, not in the category.

## Report format (mandatory)

```markdown
# <lens>-reviewer — <chunk> round-<N>

## Verdict: APPROVED | CHANGES_REQUIRED

## Blocking findings
- [B1] src/day05.md:42 — <finding> — <the fix>
  (or `- None.`)

## Non-blocking findings
- [N1] ... (may be non-empty when APPROVED)

## Evidence
- commands run, with their final line; checks file path; items solved; files read

## Contract disputes
- (optional) where you think PLAN.md or the style guide is wrong, and why
```

`CHANGES_REQUIRED` iff there is at least one blocking finding. The aggregator
reads the Verdict line and the bullets; anything else is for the controller.

---

## correctness-reviewer

**Purpose.** Every worked example, every exercise, every answer-key entry, every
number in the prose is right, and every step on the way to a right answer is
valid. A wrong answer trains a wrong habit; this is the highest-stakes lens.

**Method — in this order, no exceptions.**

1. **Solve first.** Work every exercise and re-derive every worked example from
   the problem statement alone, before reading the key or the book's solution.
   Record your answers.
2. **Check mechanically.** Copy `scripts/answer-check-template.py` to
   `<OUTPUT_DIR>/checks/<chunk>.py`, write one entry per example and exercise
   whose answer is a value, expression, root set, limit, sum, matrix, or
   inequality (infinite limits use `claimed: "oo"` / `"-oo"`), run it with
   `uv run --script`, and paste the summary line into `## Evidence`. Entries
   derive from the *problem's* constants, never the key's. Prose, proof, and
   "argue it" exercises are `skip` entries with a reason. If the book ships its
   own `scripts/answer-audit.py` and `answers.yaml`, run that too and report
   its line. **"The material is too simple to need a script" is not a reason to
   skip this step**; the script is thirty seconds and the last defect the series
   shipped was an off-by-one in an easy day.
3. **Read the key and the book's steps.** Compare with (1) and (2). Then check
   every intermediate step, sign, factorization, unit, and rounding in the
   prose and the key, not just final answers.
4. **When the check disagrees with the key, verify the checker first.** State
   which side is wrong and why (a population/sample variance mismatch once
   produced a false positive).
5. **Physical and applied numbers** (aerospace, any modeling day): carry units,
   compare with reality (an airliner's lift is near its weight, not 1000x), and
   confirm the book's stated constants (`PLAN.md` or a conventions file) are
   the ones used.
6. **Non-numeric books** (Darwin, history of an argument): correctness means
   the claim about the source or the world is true. Check every attributed
   claim, date, name, and quoted passage against the source text if it is on
   disk or quotable from memory with confidence; flag anything you cannot
   confirm as "unverified" rather than approving it.

**Blocking.** A wrong answer or key entry; an invalid step; a check that fails;
a claim about the world or the source that is false or unverifiable; a figure
or table that contradicts its text; a worked example that does not support
the point the text makes with it.

**Non-blocking.** A solution that could be shorter; a weaker-than-ideal sanity
check; a rounding convention drift.

---

## level-reviewer

**Purpose.** The day is pitched at the book's stated reader (`PLAN.md`
audience: a motivated grade-9+ student, ~30 minutes) and uses only what that
reader has.

**Method.**

1. **Prerequisite audit.** For each concept, notation, and technique the day
   uses, name where the reader got it: `PLAN.md`'s assumed background, an
   earlier day (cite it), or *this* day (cite the paragraph that teaches it).
   Anything with no source is a finding. Forward references ("as we'll see on
   Day 9") are fine as previews, not as dependencies.
2. **Budget.** Read `scans/pacing-audit.txt` for the day's words, examples, and
   exercises against the book's median. A day over 1.3x the median in words or
   examples, or whose exercise set would take a strong student past ~30 minutes
   including reading, is a finding; say what to cut, by name.
3. **Ramp.** Exercises go easy to hard with one *Gentle stretch* at the end (or
   the book's equivalent); a first exercise harder than the last worked example
   is a finding.
4. **Explanations land.** Every new idea gets a concrete instance before the
   general statement; every symbol is named in words the first time; no
   hand-waved step the reader is later expected to reproduce.
5. **Not condescending.** Flag talking-down ("don't worry, this is easy") as
   well as talking-over.

**Blocking.** A concept used with no source; a day the pacing scan puts over
budget with no cut proposed by the book; an exercise that requires an untaught
technique; a step the reader cannot reproduce from what is on the page.

**Non-blocking.** A symbol named late; a stretch exercise that is only a little
harder than the rest; an aside that could go.

---

## voice-reviewer

**Purpose.** The day reads as one human wrote it, in the book's own register,
with no AI-generated tells and no hackneyed phrasing.

**Method.**

1. **Scanner first.** Read `scans/slop-scan.txt` and `scans/self-echo.txt` for
   your files. Every `BLOCK` line is a blocking finding you must carry into your
   report with the rewrite. Every `soft`/`note` line you must judge: keep with a
   reason, or flag with a rewrite. Do not re-litigate the phrase list; if you
   think a listed phrase is fine, say so under `## Contract disputes`.
2. **Then read as an editor.** Beyond the list, flag: rhetorical-question
   openers answered in the next sentence; "It is not X. It is Y." and "not just
   X but Y" contrast frames; sentence-initial "And"/"But" in clusters; triplets
   of adjectives; paragraphs that all end on a punchline; a metaphor extended
   past two sentences; hedges stacked ("perhaps somewhat"); summary sentences
   that restate the paragraph; a sentence that means nothing after the
   flourish is removed. Cite each.
3. **Em-dash density.** The scan reports dashes per 100 words. Above the
   contract's rate, propose which to convert to periods or commas.
4. **Register.** Compare with `src/day01.md`: same person (second person for
   the reader), same warmth, same sentence length range. A day drafted by a
   different hand shows up as a register shift; name it.
5. **Repetition.** `self-echo` exact repeats across files are blocking. Near
   repeats and a distinctive sentence reused within a day are findings with
   a rewrite for one of the two. Exception: a *quotation of the book's source*
   that appears in two places, marked as a quotation both times, is not an
   echo; say so and move on.

**Blocking.** Any `BLOCK` from the scanner; an exact cross-file repeat; a
passage a reader would identify as generated (three or more tells in one
section); a register shift from the exemplar.

**Non-blocking.** A single soft tic; em-dash density; one weak metaphor.

**Loophole closed.** "This is the book's deliberately chatty voice" is not a
defense unless `PLAN.md` or the style guide names the phrase as house style.
The exemplar day shows the voice; the forbidden list bounds it.

---

## coverage-reviewer

**Purpose.** The book teaches what it promised and what the topic needs.

**Method.**

1. **Against the plan.** `PLAN.md`'s day table names each day's core idea;
   `docs/design/prompt.md` names the goal. Confirm each row is taught (not
   just mentioned), with a worked example and at least two exercises.
2. **Against the field.** Write down the standard first-course syllabus for
   the topic as you know it (e.g. AP Calculus AB's limits strand; the standard
   Algebra II sequence; an intro aerospace survey), then diff. Anything the
   field considers core that the book neither teaches nor consciously defers
   to `beyond.md` with a reason is a finding.
3. **Against itself.** The cheat sheet, formula table, glossary, and answers
   cover exactly what the days teach: nothing on a reference page that no day
   taught, nothing taught that the reference page omits.
4. **Depth.** A day that names a technique but never shows the reader
   performing it is a coverage gap even though the heading exists.

**Blocking.** A plan-table row not taught; a core topic silently missing (not
in `beyond.md`); a reference page that contradicts or exceeds the days.

**Non-blocking.** A topic taught lightly; an optional extension that could be
added; a `beyond.md` pointer that could be sharper.

---

## consistency-reviewer

**Purpose.** Structure, numbering, notation, and cross-references agree across
every file.

**Method.** Check: every day has the exemplar's section skeleton in order;
H1 titles match `SUMMARY.md` and the `PLAN.md` table; "Day N" references and
`[Day N](dayNN.md)` links resolve to a day that teaches the thing cited; every
"Tomorrow" teaser matches the next day's actual content; every "You'll need"
names only earlier days; notation is one convention book-wide (the book's
symbol for a partial sum, a vector, a limit variable); admonish titles are
plain text; recurring constants and named examples (the aerospace cast of
aircraft, a running example function) have the same values everywhere; answers
appear once each, in exercise order, and `src/answers.md` matches `staging/`.
Run `scripts/check-refs.py` if the book has one and report its line.

**Blocking.** A broken or wrong cross-reference; a notation switch; a teaser
that describes a day that does not exist; a constant with two values; answers
out of order or missing.

**Non-blocking.** Title-case drift; a header blockquote formatted differently;
a link that could be added.

---

## promises-reviewer

**Purpose.** Everything the book promises, the book delivers. Generated books
over-promise: a "how to use" page describes three kinds of box and the book
uses two; a glossary cites Days 1–2 for a term that first appears on Day 7; a
"Tomorrow" note previews a topic the next day dropped.

**Method.** Build the promise list from `welcome.md`, `how-to-use.md`, each
day's header blockquote and "Tomorrow" note, the glossary, cheat sheet, and
`beyond.md`. For each promise, find the fulfilment and cite it, or report it
dangling. Include: features ("every day ends with…"), day counts, time
budgets, prerequisites, "we will prove this on Day N", and every "see Day N".
Also check the reverse: a day that delivers something the front matter does
not mention is fine; a day that contradicts the front matter is not.

**Blocking.** A promise with no fulfilment; a front-matter description the
book contradicts; a glossary or reference citation to the wrong day.

**Non-blocking.** A promise fulfilled somewhere other than where claimed; a
feature the front matter could mention.

---

## originality-reviewer

**Purpose.** Every sentence, exercise, and figure is the author's. Text may
be *informed* by any source; it may not reproduce, lightly reword, or renumber
one. Findings are blocking.

**Method.**

1. **Web sampling.** Open `<OUTPUT_DIR>/plagiarism-samples.md`. For each
   sampled sentence run a WebSearch with the sentence in quotes; if that
   returns nothing, search the most distinctive 8-word span. Record the top
   hit and classify: *match* (same or lightly reworded), *paraphrase*
   (same structure and argument, new words), *clean*. A hit on the author's
   own sibling books or their published site is clean. Tick every box; the
   controller re-runs a random three.
2. **Quotations.** For each quoted span listed, confirm an attribution within
   two sentences and that the quote is accurate to the source. A colon
   followed by the source's sentence with words swapped and no quote marks is
   an unmarked near-quote: blocking.
3. **Recall.** For each day, ask whether an example, exercise, figure, or
   argument matches a textbook, a well-known problem set, a Wikipedia section,
   or a released exam item you can recall. Match of scenario AND structure
   counts even with new numbers. Name the source you suspect.
4. **Within-book echo.** `scans/self-echo.txt` exact repeats; carry them.
5. **Register carve-out.** Standard phrasings any original text must use
   ("Find the limit", "What is the value of", "Show that") are not findings.

**Blocking.** A web match or paraphrase of a non-self source; an unmarked
near-quote; an exercise or example that reproduces a recallable source's
scenario and structure; a figure copied from a known diagram.

**Non-blocking.** A stock phrasing that could be freshened; an attribution
that is present but far from the quote.

---

## figure-reviewer

**Purpose.** Every figure is correct, legible, and consistent with its text.

**Method.** Build or locate every figure under `src/figures/built/`; rasterize
each (`rsvg-convert -z 3 <svg> -o <png>`) and *look at it* with the Read tool.
For each: labels do not overlap lines or each other; Greek letters render as
glyphs, not numbers (the Typst variable-shadowing bug); the geometry matches
the numbers in the text and the answer key; the caption and alt text describe
what is drawn; axes have the right scale and direction; the figure is
referenced as a top-level paragraph, not inside an admonish block. Report the
PNG path for each figure you inspected. A figure you did not render, you did
not review.

**Blocking.** Wrong geometry or values; an unreadable label; a glyph rendered
as a number; a figure inside an admonish block; a caption that contradicts
the figure.

**Non-blocking.** Crowding; a label that could move; a missing arrowhead.

---

## series-reviewer

**Purpose.** The book sits correctly in the 15-day series. Non-blocking lens.

**Method.** List every mention of a sibling book and confirm the title exists
under `~/projects/books` with that exact title; confirm notation the sibling
teaches first is used the same way here; confirm `beyond.md` points at the
right next book; confirm the front matter's description of the series
(spine order, day counts) matches the siblings' `book.toml` titles; note any
overlap where two books teach the same day's material and whether they
agree.

---

## topic-reviewer

**Purpose.** The book's own domain lens, when the book ships one under
`docs/review-agents/` (the SAT book's `sat-fidelity`, an `applied-physics`
brief). Read that brief and follow it exactly; it overrides anything here
that conflicts. Report in the format above so the aggregator can read it.

---

## qwen-resolve

Not an agent. `scripts/qwen-resolve.py dayNN... --round N` runs on the LAN
model when reachable and writes one report per day with the model's blind
answer beside the key paragraph for each exercise. The controller reads the
disagreements and hands each to the correctness reviewer for that day as a
lead. The lane never blocks and never approves.
