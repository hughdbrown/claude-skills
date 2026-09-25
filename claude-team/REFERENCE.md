# claude-team reference

Load the section you need; `SKILL.md` has the workflow.

- [Routing by work type](#routing-by-work-type)
- [Workflow choices and expected outcomes](#workflow-choices-and-expected-outcomes)
- [Division of labor by stage](#division-of-labor-by-stage)
- [Opus responsibilities](#opus-responsibilities)
- [Sonnet responsibilities](#sonnet-responsibilities)
- [Haiku responsibilities](#haiku-responsibilities)
- [Good and bad task boundaries](#good-and-bad-task-boundaries)
- [Review](#review)
- [Escalation](#escalation)
- [Worker prompting rules](#worker-prompting-rules)
- [Context management](#context-management)
- [Repository artifacts](#repository-artifacts)
- [Worktree policy](#worktree-policy)
- [Starting configuration](#starting-configuration)

---

## Routing by work type

| Work type | Model | Reason |
|---|---|---|
| Product interpretation and requirements | Opus | Ambiguity and missing requirements create downstream waste |
| Architecture and domain modeling | Opus | Wrong boundaries or data models are costly to undo |
| API and schema contracts | Opus | Workers need stable contracts before implementation |
| Frontend component implementation | Sonnet | Capable once props, states, behavior, and API contract are defined |
| Backend endpoint implementation | Sonnet | Good default for bounded handler/service/validation/repository work |
| Unit and integration tests | Sonnet | Behavior-sensitive coverage |
| Boilerplate fixtures | Haiku | Low-risk, repetitive, constrained |
| Codebase reconnaissance | Haiku (Sonnet if tracing) | Haiku for search/mapping; Sonnet for reasoning-heavy tracing |
| Mechanical refactors | Haiku | Cheap when file scope and transformation are explicit |
| Lint and type-error cleanup | Haiku | Usually deterministic and locally verifiable |
| Cross-module bug diagnosis | Sonnet → Opus | Start with Sonnet; escalate when root cause is unclear |
| Security, auth, billing, migrations | Opus | High consequence |
| Final review and acceptance | Opus | Keeps the assembled feature coherent with intent |

## Workflow choices and expected outcomes

| Workflow | Cost efficiency | Expected quality | Use for |
|---|---|---|---|
| Opus does everything | Lowest throughput per dollar | Highest coherence | Hard or high-risk features, unfamiliar codebases, architecture work |
| Opus plans + reviews, Sonnet implements | Best general balance | Near-Opus when tasks are well specified and verified | Default for most web app work |
| Opus plans, Sonnet implements, Haiku supports | Best high-volume cost | Near-Opus if interfaces and test gates are strong | Mature repos with good tests and stable patterns |
| Sonnet does everything | Good economical default | More architectural/integration risk | Small–medium well-scoped features |
| Haiku does everything | Lowest apparent cost, highest rework | Inconsistent | Only narrow deterministic changes |
| Many workers, no coordinator | False economy | Divergent assumptions, conflicts | Avoid for multi-layer features |

## Division of labor by stage

| Stage | Model | Output |
|---|---|---|
| Feature interpretation | Opus | `SPEC.md` |
| Repository reconnaissance | Haiku or Sonnet | Findings report |
| Architecture and design | Opus | Design notes, `docs/decisions/` |
| Interface contracts | Opus | Typed contracts |
| Work decomposition | Opus | `PLAN.md`, `tasks/TASK-###.md` |
| Mechanical preparation | Haiku | Fixtures, call-site lists, test inputs |
| Feature implementation | Sonnet | Focused commit + handoff |
| Narrow implementation | Haiku | Focused commit + handoff |
| Local verification | Sonnet or Haiku | Test output in handoff |
| Diff review | Opus | Accept / reject / correction task |
| Localized fixes | Sonnet | Follow-up commit |
| Integration | Opus | Integration branch |
| Final acceptance | Opus + CI | Accepted feature |

## Opus responsibilities

**Owns:** interpreting requirements; finding unclear, contradictory, or missing requirements;
scope and non-goals; backend/frontend/persistence/service boundaries; domain models and data
lifecycle; authorization and tenancy; API contracts and typed schemas; migration and
compatibility strategy; error behavior and user-visible failure states; decomposition into
independent tasks; shared-file ownership and merge hazards; dependencies and order; reviewing
worker diffs; integrating commits; diagnosing repeated worker failures; cross-cutting test
failures; high-risk review (security, payments, migration, deletion); merge/release decisions.

**Avoids:** boilerplate with an established pattern, fixed-behavior UI generation, mechanical
type propagation, formatting, bulk fixtures, simple code search, narrow lint/type fixes,
repetitive explicit test cases, file-local transformations with deterministic tests.

## Sonnet responsibilities

**Owns:** components with defined props/states; pages against an established API; endpoints
using existing conventions; service logic with defined invariants; persistence methods after
schema decisions; unit and integration tests; API clients and typed models; localized bugs with
reproducible failures; form validation using the established pattern; loading/empty/success/
error states specified by the card; bounded refactors with clear ownership; docs that follow
from an established interface; Opus review findings; running local checks.

**Does not own by default:** whole-system architecture, security policy, authorization model,
ambiguous product decisions, database redesign, large multi-subsystem refactors, edits to
multiple shared core files, merge or release approval, repeated attempts at a problem that
needs a design change.

Sonnet implements one coherent vertical slice or bounded subsystem change at a time, and is
never asked to invent the architecture while implementing it.

## Haiku responsibilities

**Owns:** locating files, types, tests, and call sites; repository maps of a bounded area;
listing existing patterns; fixtures, mocks, and factories; formatting; comments/docs from an
approved source; generated clients and types; renaming an explicitly listed symbol across
defined files; codemods with explicit before/after; local non-behavioral lint fixes; type fixes
where the intended type is known; table-driven test rows; checking files against a declared
pattern; narrow single-concern review findings; running predefined checks; parallel recon.

**Does not own by default:** broad features, multi-layer changes, contract design, domain
model changes, security/auth logic, migration strategy, complex async or concurrent logic,
complex state management, cross-module debugging without a concrete hypothesis, final review,
or any task whose correctness cannot be determined by explicit tests or constraints.

Treat Haiku as a fast, inexpensive engineering assistant, not an autonomous engineer.

## Good and bad task boundaries

**Good Haiku task:** "Locate all current organization membership checks relevant to invitation
creation. Do not modify code. Return file paths, function names, current authorization
conditions, tests covering them, and inconsistent patterns found. Do not propose architecture
or infer requirements beyond repository evidence." It is read-heavy, bounded, and easy to validate.

**Good Sonnet task:** "Implement `POST /api/organizations/:organizationId/invitations` using
the approved `CreateInvitationInput` contract. Allowed: route, service, route test. Do not
modify migrations, auth middleware, shared schemas, frontend. Require org admin; validate with
the approved schema; persist via the existing repository; return the approved type; never
expose invitation tokens; test success, invalid input, forbidden caller, cross-org isolation.
Verify with `pnpm test <file>`, `pnpm typecheck`, `pnpm lint`." The contract, scope, auth
rules, and verification are all fixed before the task is handed out.

**Bad task:** "Implement organization invitations across the entire application." It bundles
product decisions, schema, API behavior, auth, email delivery, UX, state, migrations,
integration testing, error behavior, and security. Opus must decompose it first.

## Review

Before accepting a worker change, verify:

- The diff satisfies the task card exactly.
- Only authorized files changed (`check_scope.py`).
- The approved contract is honored.
- Behavior matches repository conventions.
- Error responses are consistent.
- Authorization and tenancy boundaries hold.
- Database changes are safe and compatible.
- Tests are meaningful and behavior-focused, not just coverage.
- No unnecessary abstraction.
- No future integration risk (e.g., a helper that duplicates another task's helper).
- Loading, empty, retry, and failure states are handled where relevant.
- No security, privacy, or data-loss risk.
- Required commands actually passed (`validate_handoff.py`, and re-run them yourself if in doubt).
- The change stayed within declared scope.

**Auto-merge policy.** At first, review every production change a worker writes. Later,
consider auto-accepting only tightly constrained changes that pass strict CI: generated
clients and types, formatting, fully mechanical codemods, docs generated from approved
contracts, isolated fixtures, lockfile updates, mechanical lint/type fixes, and pre-approved
test-only additions. Passing CI is evidence, not proof.

## Escalation

Return the task to Opus when:

- Haiku fails once on a code-changing task that is not purely mechanical.
- Sonnet fails the same task twice.
- The task needs files outside its boundary.
- The contract is ambiguous or incomplete.
- The worker finds conflicting repository conventions.
- Tests reveal an architecture or domain-model problem.
- Two workers' results conflict on an interface or behavior.
- Shared files produce repeated merge conflicts.
- Auth, billing, encryption, secrets, privacy, deletion, or migration is involved.
- Safety requires a broad refactor.
- The task can't be validated with deterministic tests or observable criteria.
- The worker would have to make a product or design decision not in the spec.

Opus then chooses one: clarify the card, change the contract, redesign the boundary,
serialize parallel work, implement the hard part itself, or escalate to the human.

## Worker prompting rules

The templates in `templates/worker-*.md` encode these rules. Adjust the templates rather than
writing each prompt from scratch.

**Coordinator (you):** treat SPEC, PLAN, contracts, cards, tests, and commits as the source of
truth rather than the chat history. Turn vague features into small, verifiable deliverables.
Fix contracts before assigning work, identify shared-file hazards before parallelizing, review
diffs and evidence rather than claims, escalate rather than retry on design problems, and keep
plans short and operational.

**Sonnet:** read AGENTS.md and the card first, stay in the allowed files, follow contracts
exactly, do no opportunistic cleanup, stop and report when the repo conflicts with the card,
add tests relevant to the task, run all verification, make one focused commit, return a
structured handoff, and never redesign APIs, schemas, architecture, or authorization.

**Haiku:** do only explicitly authorized work, default to read-only, never infer requirements
or architecture, never change shared interfaces, schemas, auth, or DB design, report evidence
(paths, symbols, output), stop immediately on ambiguity, commit only when edits are
authorized, and return a concise handoff.

## Context management

Stable knowledge goes in committed files (`AGENTS.md`): commands, runtime versions,
architecture summary, directory ownership, conventions, error/logging patterns, the auth
pattern, migration policy, testing strategy, dependency rules, deployment constraints, and
security constraints.

Each worker gets only its card, the relevant contracts and types, a few relevant existing
examples and tests, the local conventions, the allowed and forbidden files, the verification
commands, and the handoff format.

Workers do not get the whole feature discussion, every design doc, the entire repo, other
workers' raw transcripts, open-ended file authority, or permission to reinterpret product or
architecture.

## Repository artifacts

| Artifact | Purpose | Owner |
|---|---|---|
| `AGENTS.md` | Commands, rules, conventions, boundaries | Human + Opus |
| `SPEC.md` | Requirements, non-goals, acceptance criteria, risks | Opus |
| `PLAN.md` | Dependency graph, assignments, sequencing, shared-file ownership | Opus |
| `contracts/` | Typed API contracts, schemas, interfaces, errors | Opus |
| `tasks/TASK-###-*.md` | Task cards | Opus |
| `tasks/status.json` | Coordinator decisions (via `progress.py set`) | Opus |
| `handoffs/TASK-###.md` | Worker handoffs | Workers |
| `PROGRESS.md` | Generated status table (`progress.py show --write`) | Generated |
| `docs/decisions/` | Architecture decisions and rationale | Opus |

Decide with the user whether these files get committed to the product repo or kept on a
side branch or in a scratch directory. Many teams commit `AGENTS.md` and `contracts/` but
not tasks or handoffs.

## Worktree policy

Every worker that writes code gets its own git worktree. In Claude Code that means the
`Agent` tool with `isolation: "worktree"`. Outside Claude Code, create them by hand:
`git worktree add ../proj-task-042 -b agent/task-042`.

Workers stay in their worktree, read AGENTS.md and the card, edit only allowed files, run
verification, make one focused commit, return a handoff, and never merge.

The coordinator inspects each diff, checks scope and evidence, then accepts, rejects, or
issues a correction task. It cherry-picks accepted commits into an integration branch,
resolves conflicts centrally, and runs integration checks after each logical merge group.

## Starting configuration

| Setting | Start at |
|---|---|
| Opus coordinators | 1 |
| Concurrent Sonnet coders | 2–3 |
| Concurrent Haiku scouts/reviewers | 3–6 |
| Concurrent Haiku coders | 1–2, mechanical isolated tasks only |
| Isolation | One worktree per code-writing worker |
| Required worker output | Commit SHA, diff summary, tests run and results, uncertainties |
| Merge policy | Opus review before merge |
| Final gate | Integration tests, typecheck, lint, relevant E2E |
| Retries | Haiku: escalate quickly; Sonnet: max two attempts |
| Shared files | Coordinator-owned unless explicitly assigned |
| Feature planning | Opus only |
| Security-sensitive changes | Opus-owned; human review as appropriate |

Increase parallelism only after you see: low merge-conflict rates, reliable task-card
templates, good test coverage, fast feedback loops, useful handoffs, few repeated review
failures, stable contracts, and clear module ownership.
