# Skill Auto-Optimization

Autonomous iterative improvement of SKILL.md, adapted from the autoresearch
methodology. The agent proposes changes, evaluates them against a fixed rubric,
keeps improvements, discards regressions, and loops indefinitely.

## Setup

To set up a new optimization run, work with the user to:

1. **Agree on a run tag**: propose a tag based on today's date (e.g. `mar19`).
   The branch `skill-optimize/<tag>` must not already exist.
2. **Create the branch**: `git checkout -b skill-optimize/<tag>` from current main.
3. **Read the in-scope files**:
   - `SKILL.md` — the file you modify. The skill definition being optimized.
   - `rubric.md` — fixed evaluation criteria. Do not modify.
   - `scenarios.md` — fixed test scenarios. Do not modify.
   - `evaluate.py` — fixed evaluation script. Do not modify.
4. **Run the baseline evaluation**: `python evaluate.py > run.log 2>&1`
5. **Parse the baseline**: `grep "^quality_score:" run.log`
6. **Initialize results.tsv** with the header row and baseline result.
7. **Confirm and go**: confirm setup looks good, then begin experimentation.

## Constraints

**What you CAN do:**
- Modify `SKILL.md` — this is the only file you edit. Everything about the skill
  is fair game: structure, wording, phases, examples, guidelines, formatting.

**What you CANNOT do:**
- Modify `rubric.md`, `scenarios.md`, or `evaluate.py`. They are read-only.
  They define the fixed evaluation, like `prepare.py` in autoresearch.
- Change the evaluation methodology or scoring formula.
- Add new files that affect evaluation.

**The goal is simple: get the highest quality_score.**

All changes to SKILL.md are fair game: restructure sections, reword instructions,
add or remove content, improve the example, tighten guidelines, strengthen
test-first emphasis, add tool usage guidance. The only constraint is that SKILL.md
remains a valid, usable Claude Code skill file.

**Simplicity criterion**: All else being equal, simpler is better. A small score
improvement that adds ugly complexity is not worth it. Conversely, simplifying the
skill while maintaining or improving the score is a great outcome. A 0.01 score
improvement from adding 50 lines of redundant content? Probably not worth it. A
0.01 improvement from removing redundancy? Definitely keep.

**The first run**: Your very first run should always be to establish the baseline —
evaluate SKILL.md as-is.

## Output Format

The evaluation script prints scores like this:

```
quality_score:            7.764706
structural_completeness:  8
instruction_clarity:      8
actionability:            7
example_quality:          8
conciseness:              7
adaptability:             7
test_first_fidelity:      8
grounding:                8
```

Extract the key metric:

```
grep "^quality_score:" run.log
```

The per-dimension scores tell you WHERE to focus improvements. If `actionability`
is the lowest score, focus your next experiment on making instructions more
actionable. If `conciseness` is low, try trimming redundancy.

## Logging Results

Log every experiment to `results.tsv` (tab-separated). Do NOT commit results.tsv.

Header and columns:

```
commit	quality_score	status	dimension_scores	description
```

1. git commit hash (short, 7 chars)
2. quality_score (e.g. 7.764706) — use 0.000000 for crashes
3. status: `keep`, `discard`, or `crash`
4. dimension scores as compact string: `s=8,c=8,a=7,e=8,n=7,d=7,t=8,g=8`
   (s=structural, c=clarity, a=actionability, e=example, n=conciseness,
    d=adaptability, t=test_first, g=grounding)
5. short text description of what this experiment tried

Example:

```
commit	quality_score	status	dimension_scores	description
a1b2c3d	7.764706	keep	s=8,c=8,a=7,e=8,n=7,d=7,t=8,g=8	baseline
b2c3d4e	7.882353	keep	s=8,c=8,a=8,e=8,n=7,d=7,t=8,g=8	add tool usage examples to Phase 1
c3d4e5f	7.764706	discard	s=8,c=8,a=7,e=8,n=6,d=7,t=8,g=8	add verbose exploration checklist (hurt conciseness)
d4e5f6g	0.000000	crash	-	evaluation script error after removing frontmatter
```

## The Experiment Loop

The experiment runs on a dedicated branch (e.g. `skill-optimize/mar19`).

LOOP FOREVER:

1. **Analyze current state**: Read SKILL.md and the most recent results.tsv entries.
   Identify the lowest-scoring dimensions — these are your improvement targets.

2. **Form a hypothesis**: Decide on ONE specific change to try. Examples:
   - "Phase 1 doesn't specify which tools to use for codebase exploration — add
     concrete Glob/Grep/Read examples to improve actionability"
   - "The example section doesn't show agent reasoning — add 'why' annotations
     to improve example quality"
   - "Phase 0 triage criteria are vague — add concrete decision rules for
     small/medium/large classification to improve instruction clarity"
   - "Guidelines section repeats points from Instructions — consolidate to
     improve conciseness"

3. **Edit SKILL.md** with the change. Make ONE focused change per experiment.
   Avoid combining multiple unrelated changes — if one helps and one hurts,
   you won't know which is which.

4. **git commit** with a descriptive message (e.g. "add tool usage to Phase 1 exploration").

5. **Run the evaluation**: `python evaluate.py > run.log 2>&1`

6. **Parse results**: `grep "^quality_score:\|^structural_completeness:\|^instruction_clarity:\|^actionability:\|^example_quality:\|^conciseness:\|^adaptability:\|^test_first_fidelity:\|^grounding:" run.log`

7. **If the grep output is empty**, the evaluation crashed. Run `tail -n 20 run.log`
   to see the error. Common causes: malformed SKILL.md, missing frontmatter,
   evaluation script error. Fix or revert.

8. **Record the result** in results.tsv (do NOT commit results.tsv).

9. **Decision**:
   - If quality_score **improved** (higher): KEEP the commit. This is your new baseline.
   - If quality_score is **equal or worse**: `git reset --hard HEAD~1` to discard.
   - If the change **trades dimensions** (e.g. actionability +1 but conciseness -1,
     same overall score): DISCARD unless the gaining dimension was specifically
     your weakest. Prefer Pareto improvements.

10. **Loop**: Go back to step 1.

## Improvement Strategies

When looking for improvements, focus on the lowest-scoring dimensions first.
Here are strategies organized by dimension:

**Structural Completeness**: Add missing sections. Ensure frontmatter, usage,
description, instructions (all phases), guidelines, example, and implementation
protocol all exist with meaningful content.

**Instruction Clarity**: Replace vague language ("as needed", "as appropriate")
with specific criteria. Add decision rules for ambiguous situations. Define what
"done" looks like for each phase.

**Actionability**: Add specific tool names (Glob, Grep, Read, Agent, Write).
Specify output formats for deliverables. Name the artifacts each phase produces.
Tell the agent exactly what to present to the user and when to wait.

**Example Quality**: Walk through every phase in the example. Show agent reasoning
("I chose X because the project already uses Y"). Show user interaction points.
Include realistic PRD and task list content, not placeholders.

**Conciseness**: Remove redundant instructions that appear in both Instructions
and Guidelines. Replace long explanations with concise rules. Delete filler
phrases. Merge sections that overlap.

**Adaptability**: Add explicit handling for each scenario type (small/medium/large,
ambiguous, cross-cutting, unfamiliar codebase). Include decision trees or clear
criteria for branching behavior.

**Test-First Fidelity**: Ensure acceptance criteria are written as test descriptions.
Ensure every task starts with tests. Ensure the implementation protocol enforces
test-first. Add explicit prohibition of untested code.

**Grounding**: Add specific exploration instructions (what to search for, which
files to check). Require that every technical decision references a codebase
finding. Add fallback guidance for novel patterns with no precedent.

## Evaluation Variability

LLM-based evaluation has some inherent variability. A score change of +/- 0.1 may
be noise. To account for this:

- Focus on changes that target specific dimensions, not just the composite score
- If a change improves a dimension by 1+ point, that's a real signal
- If the composite changes by < 0.1, consider running the evaluation twice and
  averaging before deciding
- Track per-dimension scores in results.tsv to spot real trends vs. noise

## Autonomy

**NEVER STOP**: Once the experiment loop has begun, do NOT pause to ask the human
if you should continue. Do NOT ask "should I keep going?" or "is this a good
stopping point?". The human might be asleep, or gone from the computer and expects
you to continue working *indefinitely* until you are manually stopped.

You are autonomous. If you run out of ideas, think harder:
- Re-read the rubric for dimensions you haven't targeted yet
- Re-read the scenarios and simulate applying the skill to each one
- Look for subtle clarity issues in the instructions
- Try restructuring the skill's organization
- Try rewriting the example from scratch
- Try combining insights from previous near-misses

The loop runs until the human interrupts you, period.

As a rough estimate: each experiment takes ~1 minute (edit + commit + evaluate +
decide). You can run ~60 experiments per hour, or ~500 overnight. The user expects
to return to meaningful improvement in the quality_score.
