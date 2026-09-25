---
name: claude-team
description: "Run a software feature as a coordinated Claude team: Opus 5.5 is tech lead (spec, architecture, contracts, task cards, diff review, integration, final acceptance), Sonnet 5 subagents implement bounded tasks in their own worktrees, and Haiku 4.5 subagents do reconnaissance, fixtures, mechanical edits, and narrow checks. The aim is near-Opus quality at lower cost. Use this skill whenever the user wants to delegate, fan out, parallelize, or split a multi-file or multi-layer feature (frontend + backend + DB) across subagents or cheaper models. Also use it when they mention a coordinator/worker, tech-lead, or \"claude team\" workflow, model tiering or routing (Opus/Sonnet/Haiku), cutting the token cost of agent work, task cards, SPEC.md/PLAN.md/AGENTS.md, worker handoffs, or reviewing and integrating subagent commits, even if they don't name this skill. Don't use it for a small change one agent can finish directly."
---

# claude-team: Opus coordinates, Sonnet implements, Haiku supports

You (the session model, ideally Opus 5.5) are the **technical lead**. You decide what to
build, fix the contracts, cut the work into small verifiable task cards, dispatch cheaper
workers, review their actual diffs and test output, and integrate. Workers never design and
never merge.

Two goals, in this order:

1. **Quality:** the result should be about what Opus would have produced doing everything itself.
2. **Cost:** get that quality with the cheapest model that can do each piece safely.

What you are minimizing is **cost per accepted, working, maintainable feature**, not cost
per request. A cheap worker whose output needs an expensive repair costs more than doing the
task properly the first time. Most of the rules below come from that.

If the session is not running on Opus, tell the user. The coordinator role is the part that
needs the strongest model.

## When not to use this

Delegation has fixed overhead: a spec, task cards, handoffs, and reviews. Skip the team and
just do the work when:

- The change is small (roughly under ~200 lines, or one or two files in one layer).
- Requirements are still fuzzy and you'd spend the session in discussion with the user.
- The work is one tightly coupled change that can't be split into non-overlapping file sets.

A middle path that often works: you plan and review, and one Sonnet worker implements.

## How the tiers map to Claude Code

| Role | How to dispatch |
|---|---|
| Coordinator (Opus 5.5) | You, in the main session |
| Implementation worker (Sonnet 5) | `Agent` tool, `model: "sonnet"`, `subagent_type: "general-purpose"`, `isolation: "worktree"` |
| Code-writing support worker (Haiku 4.5) | `Agent` tool, `model: "haiku"`, `isolation: "worktree"` |
| Read-only recon / review (Haiku 4.5) | `Agent` tool, `model: "haiku"`, `subagent_type: "Explore"` (read-only tools, so it can't edit) |
| Escalation | You do it yourself, or spawn `model: "opus"` for a self-contained hard subproblem |

Subagents run in the background and notify you when they finish. Launch independent workers
in **one message** so they run concurrently. Don't poll them, and don't predict their results.
Only use the `Workflow` tool when the user has explicitly opted into multi-agent
orchestration. Otherwise use `Agent` calls. `scripts/render_worker_prompt.py` produces both
the prompt and the matching `Agent` settings from a task card.

## The loop

Scripts live in this skill's `scripts/` directory. They are `uv run --script` files, so run
them directly (`<skill>/scripts/new_task.py ...`). Run them from the target repo root: they
default to `tasks/` and `handoffs/` in the current directory.

### 1. Specify (Opus)

Read the request and enough of the repo to understand it. Write `SPEC.md` from
`templates/SPEC.md`: goals, **non-goals**, acceptance criteria, invariants (security, tenancy,
data integrity), open questions, and risks. Take open questions to the user **before**
dispatching anything. A worker that hits an ambiguity either guesses wrong or stops, and both
waste a round trip.

If the repo has no `AGENTS.md`, create one from `templates/AGENTS.md` with the build, test,
lint, and typecheck commands, conventions, and coordinator-owned areas. Every worker reads it,
so it saves each worker from rediscovering the same facts at their own token cost.

### 2. Reconnoiter (Haiku, parallel)

For unfamiliar areas, dispatch read-only Haiku scouts, one per package or concern:
"locate X; return file paths, symbols, current conditions, existing tests; do not modify
code; do not propose architecture." Use Sonnet for recon only when finding the answer means
tracing behavior across modules. You check what they report. It is input to your design,
and you make the decisions.

### 3. Design and contracts (Opus only)

Decide the domain model, the layer boundaries, the API/schema contracts (typed, in
`contracts/` or inline in cards), error behavior, the migration strategy, and the
authorization rules. **Contracts must be fixed before any implementation is dispatched.**
Parallel workers that each code against a guessed interface produce divergent code that you
then have to reconcile at Opus prices.

### 4. Plan and cut task cards (Opus)

Write `PLAN.md` (`templates/PLAN.md`): the task table, dependencies, **shared-file
ownership**, parallel groups, integration order, and the final gate. Then create one card per task:

```bash
scripts/new_task.py "Add pending invitation list endpoint" --model sonnet \
  --allow src/api/invitations.ts --allow src/api/invitations.test.ts \
  --forbid "Database migrations" --forbid src/auth/ \
  --verify "pnpm test src/api/invitations.test.ts" --verify "pnpm typecheck" \
  --depends-on TASK-002
```

Fill in Contract, Requirements, and Acceptance Criteria yourself. A card is ready to delegate
only if it has all of the following:

- a single coherent deliverable (one vertical slice or one bounded subsystem change)
- explicit allowed files (backticked paths or globs, so `check_scope.py` can enforce them) and forbidden areas
- a stable contract it implements, not one it invents
- observable acceptance criteria
- runnable verification commands
- no file overlap with any card that runs in parallel

A card that fails any of these is not ready to delegate. Fix the card, split it, or do the
task yourself. "Implement invitations across the app" is a feature, not a task. See
`examples/invitations/` for a worked decomposition.

**Picking the model for a card** (full table in `REFERENCE.md`):

- **Haiku:** read-only search and mapping, fixtures and factories, formatting, generated
  types and clients, explicit renames and codemods, lint and type fixes where the intended
  type is known, table-driven test rows, narrow single-concern review passes. Use it only
  where failure is cheap and correctness can be checked mechanically.
- **Sonnet:** endpoints, services, repositories, components, pages, forms, and API clients
  built against a fixed contract, plus behavior-level unit and integration tests, localized
  bug fixes with a repro, and repair tasks from your review.
- **Opus (you):** requirements, architecture, contracts, auth, security, billing,
  migrations, deletion, cross-cutting refactors, repeated worker failures, integration,
  and acceptance.

### 5. Dispatch

```bash
scripts/progress.py ready                          # cards whose dependencies are accepted
scripts/render_worker_prompt.py tasks/TASK-004-*.md # prompt + Agent settings
```

Give each worker **only** its card, `AGENTS.md`, the relevant contracts and examples, and
the handoff format. Don't give it the feature discussion, other workers' transcripts, or
open-ended authority. Extra context costs tokens and invites scope creep. Start with 2–3
concurrent Sonnet coders, 3–6 Haiku scouts, and at most 1–2 Haiku coders. Raise these limits
only after a few tasks come back with no merge conflicts and handoffs you can use.

### 6. Verify the evidence

When a worker finishes, run the mechanical checks before you read any code:

```bash
scripts/check_scope.py tasks/TASK-004-*.md --commit <sha> --repo <worker worktree>
scripts/validate_handoff.py handoffs/TASK-004.md --task tasks/TASK-004-*.md --repo <worktree>
```

`check_scope.py` flags changed files that are forbidden or not listed on the card, and prints
the prose "do not modify" areas for you to check by eye. `validate_handoff.py` rejects
handoffs that are missing required sections, have no commit SHA or no command output, list
files that don't match the commit, or say "Completed" when the output shows a failure.
"Implemented successfully" is a claim. Evidence is a focused diff, real test output, and a
SHA.

### 7. Review (Opus)

Read the actual diff (`git show <sha>`). Use the review checklist in `REFERENCE.md#review`.
In short: does it match the card and contract exactly, follow repo conventions, keep auth and
tenancy boundaries, have tests that pin behavior, avoid needless abstraction, and cover
loading, empty, and error states? Then decide:

```bash
scripts/progress.py set TASK-004 accepted --note "cherry-picked as 1a2b3c4"
scripts/progress.py set TASK-005 rejected --note "list response includes token"
```

A rejection becomes a **focused correction task** for the same worker, naming the exact
failure. Don't send a vague "please fix".

### 8. Repair and escalate

Route each failure to the cheapest model that can fix it: a local mechanical fix goes to
Haiku, a local behavioral fix to Sonnet, and architecture or cross-cutting problems to you.
Stop retrying and take the task back when any of these happen:

- Haiku fails once on anything that isn't purely mechanical.
- Sonnet fails the same task **twice**.
- The worker needs files outside its card, or hits conflicting conventions or an unclear contract.
- The work touches auth, billing, secrets, encryption, privacy, deletion, or data migration.
- Two workers' results disagree on an interface, or shared files keep conflicting.
- Correctness can't be verified deterministically, or a product decision is needed.

Once you have the task back, choose one: clarify the card, change the contract, redraw
the boundary, serialize work that ran in parallel, implement the hard part yourself, or ask
the user. Retrying a worker on a problem that's really a design problem just burns tokens.

### 9. Integrate and accept (Opus)

Cherry-pick or merge the accepted commits into an integration branch in dependency order,
and resolve conflicts yourself. After each logical group, run the integration-level checks.
At the end, run the final gate from `PLAN.md` (full tests, typecheck, lint, E2E). Accept the
feature only when every acceptance criterion in `SPEC.md` holds. Regenerate the status table
with `scripts/progress.py show --write PROGRESS.md`, clean up the worker worktrees, and
report to the user.

Optionally, run `scripts/session_cost.py` to report tokens and cost by model and by
agent, compared with pricing the same tokens at Opus rates. It shows whether delegation
actually moved volume to the cheaper tiers.

## Parallelism

- **Safe:** recon in separate packages, independent components or endpoints with no shared
  files, fixtures, generated types, docs from approved contracts, lint fixes in disjoint file
  groups, and independent review passes.
- **Cautious:** frontend and backend against the same contract, endpoints sharing a service
  layer, schema and persistence work, shared state management, cross-package refactors.
- **Never by default:** architecture, domain model, auth policy, shared config and routing
  tables, still-changing schemas, migration strategy, incident response, release prep.

If two tasks might touch the same file, serialize them, give one task exclusive ownership, or
make the file coordinator-owned.

## Files in this skill

| Path | Use |
|---|---|
| `REFERENCE.md` | Full responsibility lists per model, work-type routing table, review checklist, escalation rules, worker prompting rules, starting configuration |
| `templates/` | `SPEC.md`, `PLAN.md`, `AGENTS.md`, `TASK.md`, `HANDOFF.md`, and the `worker-sonnet.md` / `worker-haiku.md` prompt templates |
| `scripts/new_task.py` | Scaffold the next numbered task card |
| `scripts/render_worker_prompt.py` | Card → worker prompt + `Agent` settings (`--json` available) |
| `scripts/check_scope.py` | Enforce allowed/forbidden files on a commit, range, or worktree |
| `scripts/validate_handoff.py` | Reject handoffs without evidence |
| `scripts/progress.py` | `show` / `ready` / `set` task status; writes `PROGRESS.md` |
| `scripts/session_cost.py` | Token and cost report for a session and its subagents |
| `resources/pricing.json` | Per-model prices used by `session_cost.py`; edit when prices change |
| `examples/invitations/` | Worked example: spec, plan, two task cards, and a handoff |
| `docs/` | Human-facing background: rationale, cost model, script guide |
