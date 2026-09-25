# Rationale

## The two goals

1. **Quality:** ship about what Opus 5.5 would have shipped if it did the whole feature alone.
2. **Cost:** pay for Opus only where its judgment prevents expensive failures. Everything
   else goes to Sonnet 5 or Haiku 4.5.

The metric is **cost per accepted, working, maintainable feature**. A cheap attempt that
needs an Opus repair can cost more than having Opus do the task once.

## Why quality holds up

Cheaper models lose most of their quality when they have to make judgment calls: working
out what the requirement means, where a boundary goes, what shape an interface takes, or
what to do when the repo disagrees with the plan. The workflow keeps those calls on Opus
and hands workers tasks where the calls are already made:

- **Contracts first.** Workers code against a fixed type or schema, so parallel work
  converges instead of diverging.
- **Allowed-file lists.** They bound the damage a worker can do and make merges predictable.
- **Deterministic verification.** Tests and typechecks, not the worker's own say-so,
  decide whether a task is done.
- **Opus reviews real diffs.** It checks the actual code change, catching the class of
  mistakes cheaper models make (scope creep, convention drift, security oversights) before
  they compound.
- **Fast escalation.** A worker failing on a design problem is a signal to take the task
  back, not to retry.

## Where it breaks down

| Symptom | Usual cause | Fix |
|---|---|---|
| Workers return conflicting helpers or types | Contract not fixed before dispatch | Stop, write the contract, re-dispatch |
| Repeated merge conflicts | Two cards own the same file | Serialize, or make the file coordinator-owned |
| Worker "completes" but tests are shallow | Acceptance criteria not observable | Rewrite criteria as behaviors; reject |
| Sonnet fails twice | The task hides a design decision | Take it back; split or decide |
| Coordinator spends most tokens on review | Cards too big or too vague | Smaller cards, tighter scope |
| Savings near zero | Opus did the implementation anyway | Delegate more; check with `session_cost.py` |

## When not to use it

- Small changes (a file or two, one layer). The overhead of cards and handoffs outweighs
  the savings.
- Exploratory or ambiguous work where the spec will change as you go.
- Tightly coupled changes that can't be split into disjoint file sets.
- Repos without runnable tests. Without deterministic verification, Opus has to review
  everything line by line, and most of the savings disappear.

## Dependency shape of a typical feature

```text
Haiku recon ─▶ Opus contracts ─┬─▶ Sonnet migration ─▶ Sonnet repository ─┐
                               ├─▶ Sonnet endpoints ──────────────────────┼─▶ Sonnet UI ─▶ Sonnet E2E ─▶ Opus integration
                               └─▶ Haiku typed-client prep ───────────────┘
```

Parallelize only after the relevant contract is fixed and file ownership doesn't overlap.
