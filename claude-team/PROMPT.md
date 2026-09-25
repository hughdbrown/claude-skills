# Claude Coordinator + Worker Agent Workflow

**Use Claude Opus 5.5 as the coordinator, technical lead, architect, and final reviewer. Use Claude Sonnet 5 as the default supervised implementation agent. Use Claude Haiku 4.5 for narrow, high-volume support work such as reconnaissance, mechanical edits, test-data generation, formatting, and focused checks.**

This division is intended to meet two goals:

1. **Quality goal:** produce software that approximately matches what would result from assigning the entire feature to Claude Opus 5.5.
2. **Cost goal:** obtain that quality using the least expensive model capable of safely performing each portion of the work.

> Default model hierarchy:
>
> - **Opus 5.5:** judgment, design, decomposition, integration, difficult debugging, security-sensitive decisions, final acceptance.
> - **Sonnet 5:** primary supervised implementation agent for bounded frontend and backend work.
> - **Haiku 4.5:** inexpensive specialized worker for narrow, low-risk, deterministic, or read-heavy tasks.

---

## Model Selection Summary

| Role | Recommended Claude model | Primary purpose | Why |
|---|---|---|---|
| Technical lead / coordinator | Claude Opus 5.5 | Requirements, architecture, task decomposition, integration, code review, difficult debugging | Strongest current Claude model for long-running agentic coding and knowledge work |
| Default implementation worker | Claude Sonnet 5 | Scoped full-stack implementation, tests, bug fixes, component work, API work | Best balance of coding capability, speed, and cost |
| High-volume support worker | Claude Haiku 4.5 | Reconnaissance, mechanical edits, test generation, code search, formatting, simple fixes | Lowest-cost fast model with strong enough reasoning for constrained tasks |
| Escalation model | Claude Opus 5.5 | Hard worker failures, ambiguous contracts, cross-cutting changes, complex refactors | Use only where higher-level judgment materially reduces rework |

Anthropic positions Opus 5.5 for long-running agentic coding and knowledge work, Sonnet 5 for everyday coding and agent workloads, and Haiku 4.5 for high-volume, cost-sensitive subagent work. [Source: Anthropic model-selection and pricing documentation.]

---

## Cost Model

Approximate public API-equivalent pricing:

| Model | Input per 1M tokens | Output per 1M tokens | Relative to Haiku | Relative to Sonnet |
|---|---:|---:|---:|---:|
| Claude Haiku 4.5 | $1 | $5 | 1× | 0.5× |
| Claude Sonnet 5 | $2 | $10 | 2× | 1× |
| Claude Opus 5.5 | $4 | $20 | 4× | 2× |

The exact cost of an agent workflow depends on:

- Input tokens, including repository context and tool results
- Output tokens, including reasoning, code, reports, and test analysis
- Cache writes and cache reads
- Tool-call iteration loops
- Number of failed or repeated worker attempts
- Whether work is independently parallelizable
- Whether worker output requires expensive integration repair

The total cost of a coordinator-worker workflow is:

\[
\text{Total Cost} =
\text{Opus planning} +
\text{Sonnet implementation} +
\text{Haiku support work} +
\text{Opus review/integration} +
\text{rework}
\]

> The goal is not to minimize model cost per request. The goal is to minimize **cost per accepted, working, maintainable feature**.

---

## Recommended Economic Strategy

Use the most capable model only where its higher-quality reasoning prevents expensive failures.

| Work type | Preferred model | Reason |
|---|---|---|
| Product interpretation and requirements | Opus 5.5 | Ambiguity and missing requirements create downstream waste |
| Architecture and domain modeling | Opus 5.5 | Incorrect boundaries, abstractions, or data models are costly to undo |
| API and schema contracts | Opus 5.5 | Workers need stable contracts before implementation begins |
| Frontend component implementation | Sonnet 5 | Usually capable when props, behavior, states, and API contracts are defined |
| Backend endpoint implementation | Sonnet 5 | Good default for bounded service, handler, validation, and repository tasks |
| Unit and integration tests | Sonnet 5 | Appropriate for behavior-sensitive test coverage |
| Boilerplate test fixtures | Haiku 4.5 | Low-risk, repetitive, highly constrained work |
| Codebase reconnaissance | Haiku 4.5 or Sonnet 5 | Use Haiku for simple search/mapping; Sonnet for reasoning-heavy tracing |
| Mechanical refactors | Haiku 4.5 | Cheap if file scope and transformation are explicit |
| Lint and type-error cleanup | Haiku 4.5 | Often deterministic and locally verifiable |
| Cross-module bug diagnosis | Sonnet 5, then Opus 5.5 | Start with Sonnet; escalate when the root cause is unclear |
| Security, auth, billing, migrations | Opus 5.5 | High-consequence changes benefit from strongest review and design |
| Final review and acceptance | Opus 5.5 | Ensures the assembled feature matches intent and preserves system coherence |

---

## Expected Cost and Quality Outcomes

| Workflow | Cost efficiency | Expected quality | Recommended use |
|---|---|---|---|
| Opus 5.5 performs everything | Lowest throughput per dollar | Highest single-agent coherence | Difficult or high-risk features; unfamiliar codebases; architecture work |
| Opus plans and reviews; Sonnet implements | Best general balance | Near-Opus quality when tasks are well-specified and verified | Default workflow for most web application development |
| Opus plans; Sonnet implements; Haiku performs support tasks | Best high-volume cost structure | Near-Opus quality if interfaces and test gates are strong | Mature repositories with good tests and stable patterns |
| Sonnet performs everything | Good economical default | Good, but more architectural and integration risk | Small-to-medium well-scoped features |
| Haiku performs everything | Lowest apparent cost, highest rework risk | Inconsistent for integrated feature work | Avoid except for narrow deterministic changes |
| Multiple workers without an Opus coordinator | Often false economy | Divergent assumptions, inconsistent contracts, merge conflicts | Avoid for features spanning multiple layers |

> A well-run Opus → Sonnet → Haiku workflow should usually provide a meaningful increase in completed work per budget over all-Opus execution, while keeping product quality close to the Opus-only baseline.

---

## Primary Division of Labor

| Stage | Primary model | Responsibility | Required output |
|---|---|---|---|
| Feature interpretation | Opus 5.5 | Clarify goals, constraints, non-goals, risks, acceptance criteria | `SPEC.md` |
| Repository reconnaissance | Haiku 4.5 or Sonnet 5 | Locate modules, conventions, tests, dependencies, data paths | Findings report |
| Architecture and design | Opus 5.5 | Define domain model, boundaries, service/API/UI responsibilities, migration path | Design notes and decisions |
| Interface contracts | Opus 5.5 | Define schemas, request/response types, invariants, error behavior | Typed contracts |
| Work decomposition | Opus 5.5 | Create bounded task cards, dependencies, allowed files, verification commands | `TASK-###.md` files |
| Mechanical preparation | Haiku 4.5 | Generate fixtures, identify call sites, list required file edits, prepare test inputs | Focused task artifact |
| Feature implementation | Sonnet 5 | Implement bounded frontend/backend/database tasks | Focused commit |
| Narrow implementation | Haiku 4.5 | Make simple, low-risk, explicit transformations | Focused commit |
| Local verification | Sonnet 5 or Haiku 4.5 | Run defined tests, typecheck, lint, report evidence | Test results |
| Diff review | Opus 5.5 | Validate contract compliance, architecture consistency, safety, scope | Accept/reject decision |
| Localized fixes | Sonnet 5 | Address explicit review comments and test failures | Follow-up commit |
| Integration | Opus 5.5 | Merge changes, resolve cross-task conflicts, validate interactions | Integration commit |
| Final acceptance | Opus 5.5 plus CI | Confirm feature satisfies requirements and release criteria | Accepted feature |

---

## Opus 5.5 Responsibilities

Claude Opus 5.5 is the **technical lead**.

Use Opus where better reasoning reduces downstream rework, prevents architectural drift, or detects risk that cheaper workers may miss.

### Opus should own

- Interpreting user or product requirements
- Identifying unclear, contradictory, or missing requirements
- Defining scope and non-goals
- Designing backend, frontend, persistence, and service boundaries
- Defining domain models and data lifecycle rules
- Designing authorization and tenancy behavior
- Defining API contracts and typed schemas
- Selecting database migration and compatibility strategies
- Defining error behavior and user-visible failure states
- Decomposing features into independent worker tasks
- Identifying shared-file ownership and merge hazards
- Defining task dependencies and execution order
- Reviewing Sonnet and Haiku code changes
- Integrating worker commits
- Diagnosing repeated worker failures
- Resolving cross-cutting test failures
- Reviewing high-risk changes involving security, payments, data migration, or deletion
- Deciding whether implementation is acceptable for merge or release

### Opus should avoid spending time on

- Simple boilerplate changes with an established pattern
- Straightforward UI component generation with fixed behavior
- Mechanical type propagation
- Formatting-only changes
- Bulk test fixture generation
- Simple code-search and repository mapping tasks
- Narrow lint and type-error fixes
- Repetitive test cases with explicit input/output behavior
- File-local transformations that have deterministic tests

> Use Opus for **judgment, contracts, integration, and difficult reasoning**. Do not waste its capacity on predictable implementation work that Sonnet or Haiku can complete safely.

---

## Sonnet 5 Responsibilities

Claude Sonnet 5 is the **default supervised implementation agent**.

Sonnet should perform most feature implementation after Opus has defined stable scope, contracts, file ownership, and testable acceptance criteria.

### Sonnet should own

- Implementing frontend components with defined props and states
- Implementing pages against an established API contract
- Implementing API endpoints using existing repository conventions
- Implementing service-layer behavior with defined invariants
- Implementing repository and persistence methods after schema decisions are fixed
- Writing unit tests and integration tests for defined behavior
- Updating API clients and typed client models
- Fixing localized bugs with reproducible failures
- Implementing form validation using an established validation pattern
- Adding loading, empty, success, and error states specified by the task
- Performing bounded refactors with clear file ownership
- Updating documentation that follows from an established interface
- Addressing explicit Opus review findings
- Running local typecheck, lint, unit, integration, and focused browser tests

### Sonnet should not own by default

- Whole-system architecture
- Security policy design
- Authorization model changes
- Product decisions with ambiguous intent
- Database redesign without an approved plan
- Large refactors spanning multiple subsystems
- Changes that require modifying multiple shared core files
- Final merge approval
- Release approval
- Repeated attempts at a problem that requires a design change

> Sonnet should implement **one coherent vertical slice or bounded subsystem change at a time**. It should not be asked to invent the architecture while also implementing it.

---

## Haiku 4.5 Responsibilities

Claude Haiku 4.5 is the **high-volume support agent**.

Haiku provides the lowest-cost execution tier, but it should be used only where failure is cheap, scope is narrow, and correctness can be checked mechanically.

### Haiku should own

- Locating relevant files, types, tests, and call sites
- Producing a repository map for a bounded area
- Listing existing patterns and examples without modifying code
- Generating test data, fixtures, mocks, and factories
- Performing formatting-only updates
- Updating comments or documentation from an approved source
- Updating generated client code or generated types
- Renaming an explicitly listed symbol across defined files
- Making simple codemods with explicit before/after transformations
- Fixing lint errors with local, non-behavioral changes
- Fixing type errors where the intended type is explicitly known
- Adding repetitive table-driven test cases
- Checking that files comply with a declared pattern
- Producing narrow code-review findings for an explicit concern
- Running pre-defined checks and reporting results
- Performing independent reconnaissance in parallel with other workers

### Haiku should not own by default

- Broad feature implementation
- Multi-layer frontend-plus-backend changes
- API contract design
- Domain-model changes
- Security or authorization logic
- Database migration strategy
- Complex asynchronous or concurrent logic
- Complex state-management changes
- Cross-module debugging without a concrete hypothesis
- Final code review or merge approval
- Any task where “correct” cannot be determined by explicit tests or constraints

> Haiku should be treated as a fast, inexpensive engineering assistant—not as an autonomous product engineer.

---

## Good Task Boundaries

### Good Haiku task

> Locate all current organization membership checks relevant to invitation creation.
>
> **Do not modify code.**
>
> Return:
>
> - File paths
> - Relevant function names
> - Current authorization conditions
> - Existing tests that cover those conditions
> - Any inconsistent patterns found
>
> Do not propose architecture changes. Do not infer requirements beyond the repository evidence.

This is appropriate for Haiku because it is read-heavy, bounded, and easy for Opus or Sonnet to validate.

### Good Sonnet task

> Implement `POST /api/organizations/:organizationId/invitations` using the approved `CreateInvitationInput` contract.
>
> **Allowed files:**
>
> - `src/api/organizations/invitations.ts`
> - `src/services/invitations.ts`
> - `src/api/organizations/invitations.test.ts`
>
> **Do not modify:**
>
> - Database migrations
> - Authorization middleware
> - Shared API schemas
> - Frontend files
>
> **Requirements:**
>
> - Require an authenticated organization administrator
> - Validate input using the approved schema
> - Persist using the existing invitation repository
> - Return the approved response type
> - Do not expose internal invitation tokens
> - Add tests for success, invalid input, forbidden caller, and cross-organization isolation
>
> **Verification:**
>
> ```bash
> pnpm test src/api/organizations/invitations.test.ts
> pnpm typecheck
> pnpm lint
> ```

This is appropriate for Sonnet because the contract, scope, authorization rules, and verification requirements are already defined.

### Bad worker task

> Implement organization invitations across the entire application.

This is too broad because it includes:

- Product decisions
- Schema design
- API behavior
- Authorization
- Email-delivery behavior
- Frontend UX
- State management
- Database migrations
- Integration testing
- Error behavior
- Security constraints

Opus must first decompose this into stable contracts and bounded tasks.

---

## Feature Decomposition Example

### Feature request

> Allow organization administrators to invite users by email, assign a role, view pending invitations, and revoke invitations.

### Opus-owned feature specification

```text
Feature: Organization invitations

Goals:
- Organization administrators can create invitations by email
- Invitations have an assigned role and expiration
- Pending invitations appear in organization settings
- Organization administrators can revoke pending invitations

Non-goals:
- No bulk invitation import
- No invitation resend flow
- No cross-organization transfer flow
- No custom invitation email templates

Security invariants:
- Only organization administrators can create or revoke invitations
- Invitation tokens never appear in list responses
- Revoked invitations cannot be accepted
- Expired invitations cannot be accepted
- A caller cannot access invitations from another organization
```

### Recommended task assignment

| Task | Model | Boundary |
|---|---|---|
| Map existing membership, role, email, and invitation patterns | Haiku 4.5 | Read-only reconnaissance |
| Define invitation lifecycle, schema, API contract, and authorization rules | Opus 5.5 | Architecture and contracts |
| Add schema migration from approved design | Sonnet 5 | Database files only |
| Add invitation repository methods | Sonnet 5 | Data-access layer only |
| Generate migration fixtures and edge-case records | Haiku 4.5 | Test files only |
| Implement create-invitation endpoint | Sonnet 5 | Route/service/test files only |
| Implement pending-invitation listing endpoint | Sonnet 5 | Route/service/test files only |
| Implement revoke-invitation endpoint | Sonnet 5 | Route/service/test files only |
| Add typed client methods | Haiku 4.5 or Sonnet 5 | Generated or client/type files only |
| Implement invitation list UI | Sonnet 5 | Component files only |
| Implement invite-user form UI | Sonnet 5 | Component files only |
| Add repetitive test fixtures and matrix cases | Haiku 4.5 | Test files only |
| Add end-to-end browser coverage | Sonnet 5 | E2E files only |
| Review, integrate, resolve conflicts, validate security rules | Opus 5.5 | All layers |

---

## Dependency Graph

```text
Haiku reconnaissance
        |
        v
Opus architecture and contract decisions
        |
        +----------------------+----------------------+
        |                      |                      |
        v                      v                      v
Sonnet database migration   Sonnet endpoints      Haiku typed-client prep
        |                      |                      |
        v                      +----------+-----------+
Sonnet repository methods               |
        |                                v
        +----------------------> Sonnet frontend implementation
                                         |
                                         v
                            Sonnet end-to-end browser tests
                                         |
                                         v
                            Opus integration and final review
```

> Parallelize only after Opus has fixed the relevant interface contract and assigned non-overlapping file ownership.

---

## Task Card Template

Store each delegated task as a file, for example `tasks/TASK-042.md`.

````md
# TASK-042: Add pending invitation list endpoint

## Goal

Implement an authenticated endpoint that returns pending invitations for one organization.

## Assigned Model

Claude Sonnet 5

## Scope

Allowed files:

- `src/api/organizations/invitations.ts`
- `src/services/invitations.ts`
- `src/api/organizations/invitations.test.ts`

Do not modify:

- Database migrations
- Frontend files
- Authentication middleware
- Shared authorization policy
- Email delivery code
- Shared API contract files

## Contract

Route:

```http
GET /api/organizations/:organizationId/invitations
```

Response:

```ts
type PendingInvitation = {
  id: string;
  email: string;
  role: "member" | "admin";
  createdAt: string;
  expiresAt: string | null;
};

type ListPendingInvitationsResponse = {
  invitations: PendingInvitation[];
};
```

## Requirements

- Require an authenticated user
- Require organization administrator role
- Return only pending, non-revoked invitations
- Exclude expired invitations
- Do not expose invitation tokens
- Follow established error-response conventions
- Use the existing repository abstraction
- Do not introduce new dependencies

## Acceptance Criteria

- Non-admin callers receive the established forbidden response
- Invitations from other organizations are not returned
- Revoked invitations are excluded
- Expired invitations are excluded
- Response conforms to the declared type contract
- Existing endpoint tests remain green

## Verification

Run:

```bash
pnpm test src/api/organizations/invitations.test.ts
pnpm typecheck
pnpm lint
```

## Handoff Format

Return:

- Summary of implementation
- Files changed
- Commands run and results
- Tests added or changed
- Known limitations or questions
- Commit SHA
````

---

## Required Worker Handoff

Every Sonnet or Haiku worker should return a structured handoff.

````md
# TASK-042 Handoff

## Status

Completed

## Summary

Implemented the pending invitation listing endpoint for organization administrators.

## Files Changed

- `src/api/organizations/invitations.ts`
- `src/services/invitations.ts`
- `src/api/organizations/invitations.test.ts`

## Verification

```text
pnpm test src/api/organizations/invitations.test.ts
PASS

pnpm typecheck
PASS

pnpm lint
PASS
```

## Tests Added

- Returns only pending invitations
- Excludes revoked invitations
- Excludes expired invitations
- Rejects non-admin organization members
- Prevents cross-organization access

## Known Limitations

- No pagination was added because it is outside the approved endpoint contract.

## Commit

```text
abc1234 Add pending organization invitation endpoint
```
````

> Do not accept “implemented successfully” as evidence. Require a focused diff, test output, commit SHA, and explicit reporting of uncertainty.

---

## Repository Artifacts

Use committed files as durable coordination state.

| Artifact | Purpose | Owner |
|---|---|---|
| `AGENTS.md` | Repository commands, coding rules, conventions, architecture boundaries, operational constraints | Human + Opus |
| `SPEC.md` | Feature requirements, non-goals, acceptance criteria, known risks | Opus |
| `PLAN.md` | Dependency graph, worker assignments, sequencing, shared-file ownership | Opus |
| `contracts/` | Typed API contracts, schemas, domain interfaces, error definitions | Opus |
| `tasks/TASK-###.md` | Worker task cards with scope and verification | Opus |
| `PROGRESS.md` or `tasks.json` | Task status, worker assignment, commits, test evidence, blockers | Orchestrator + Opus |
| `docs/decisions/` | Architecture decisions and rationale | Opus |
| CI configuration | Deterministic typecheck, lint, test, browser, and security gates | Human + Opus |

### Suggested project layout

```text
.
├── AGENTS.md
├── SPEC.md
├── PLAN.md
├── PROGRESS.md
├── contracts/
│   ├── invitations.ts
│   └── organization.ts
├── tasks/
│   ├── TASK-001-recon.md
│   ├── TASK-002-schema.md
│   ├── TASK-003-create-endpoint.md
│   ├── TASK-004-list-endpoint.md
│   └── TASK-005-ui.md
├── docs/
│   └── decisions/
└── src/
```

---

## Execution Loop

```text
1. Opus reads the feature request and relevant repository context.
2. Opus writes or updates SPEC.md.
3. Haiku or Sonnet performs bounded reconnaissance if needed.
4. Opus defines architecture, contracts, constraints, and task boundaries.
5. Opus creates independently testable task cards.
6. Sonnet and Haiku workers execute isolated tasks in separate worktrees.
7. Each worker runs required checks and creates a focused commit.
8. Workers return structured handoffs with test evidence.
9. Opus reviews each diff against its task card and contract.
10. Opus routes localized failures to Sonnet or Haiku for repair.
11. Opus integrates accepted commits into an integration branch.
12. Opus runs cross-task validation, integration tests, and browser tests.
13. Opus resolves system-level issues or escalates them to the human.
14. Opus accepts the feature only when all acceptance criteria are met.
```

---

## Repair and Escalation Loop

```text
Worker implementation
        |
        v
Scoped tests pass?
        |
   no   +----------------------------> Same worker fixes explicit failures
        |
  yes   v
Opus reviews diff and evidence
        |
   no   +----------------------------> Focused correction task
        |
  yes   v
Merge to integration branch
        |
        v
Integration and E2E checks pass?
        |
   no   +----------------------------> Opus diagnoses root cause
                                        |
                                        +--> Local mechanical fix: Haiku
                                        |
                                        +--> Local behavioral fix: Sonnet
                                        |
                                        +--> Architecture/cross-cutting fix: Opus
        |
  yes   v
Feature accepted
```

---

## Parallelism Rules

### Safe to parallelize with Haiku or Sonnet

- Repository reconnaissance in separate packages
- Test discovery and coverage-gap analysis
- Independent UI components with stable props and API contracts
- Separate API endpoints with no shared-file overlap
- Independent test suites for separate modules
- Fixture, mock, and factory creation
- Generated client/type updates
- Documentation updates from approved contracts
- Lint/type cleanup in non-overlapping file groups
- Independent review passes, such as test coverage, error handling, or API compatibility

### Parallelize cautiously

- Frontend and backend work that depends on a stable API contract
- Multiple endpoints sharing one service or repository layer
- Database schema and persistence work
- UI work sharing state-management code
- Cross-package refactors
- Performance-sensitive changes
- Browser end-to-end tests that depend on unstable UI selectors

### Do not parallelize by default

- Architecture design
- Domain-model redesign
- Authorization policy changes
- Authentication changes
- Shared configuration files
- Shared routing tables
- Shared API schemas while still evolving
- Large cross-cutting refactors
- Production incident response
- Database migration strategy
- Release branch preparation and deployment work

> If two workers may modify the same file, serialize the work, assign one worker exclusive ownership, or make the file Opus-owned.

---

## Worktree Policy

Use a separate Git worktree for each worker that changes code.

```bash
git worktree add ../project-task-042 -b agent/task-042
git worktree add ../project-task-043 -b agent/task-043
git worktree add ../project-task-044 -b agent/task-044
```

### Worker requirements

Each Sonnet or Haiku worker must:

1. Work only in the assigned worktree.
2. Read `AGENTS.md` and its task card before editing.
3. Modify only allowed files.
4. Run the required verification commands.
5. Create one focused commit.
6. Return a structured handoff.
7. Never merge directly into the integration or main branch.

### Opus responsibilities

Opus must:

1. Inspect each worker diff.
2. Check that scope boundaries were respected.
3. Review test evidence.
4. Accept, reject, or issue a focused correction task.
5. Merge or cherry-pick accepted commits into an integration branch.
6. Resolve conflicts centrally.
7. Run integration-level checks after logical merge groups.

---

## Review Policy

### Opus review checklist

Before accepting a worker change, Opus should verify:

- Does the diff satisfy the task card exactly?
- Did the worker modify only authorized files?
- Does the implementation honor the approved contract?
- Does behavior match existing repository conventions?
- Are error responses consistent?
- Are authorization and tenancy boundaries preserved?
- Are database changes safe and compatible?
- Are tests meaningful and behavior-focused?
- Does the change introduce unnecessary abstraction?
- Does the worker’s diff create future integration risk?
- Are loading, empty, retry, and failure states handled where relevant?
- Are security, privacy, or data-loss risks introduced?
- Did required commands actually pass?
- Does the change remain within declared scope?

### Automatic merge policy

Initially require Opus review for every worker-authored production change.

Later, permit automatic merge only for tightly constrained changes that pass strict CI:

- Generated client or type files
- Formatting-only changes
- Fully mechanical codemods
- Documentation generated from approved contracts
- Isolated fixture additions
- Lockfile updates with passing CI
- Mechanical lint/type fixes with no behavior change
- Test-only additions with clear, pre-approved scope

> Passing CI is evidence, not proof. Opus review remains necessary for changes with architectural, security, behavioral, or product implications.

---

## Escalation Rules

Return a task to Opus if any of the following occurs:

- Haiku fails once on a code-changing task that is not purely mechanical.
- Sonnet fails the same task twice.
- The task requires files outside its declared ownership boundary.
- The task contract is ambiguous or incomplete.
- A worker discovers conflicting repository conventions.
- Tests indicate an architecture or domain-model problem.
- Two worker results conflict on an interface or behavior.
- Shared files produce repeated merge conflicts.
- The work affects authentication, authorization, billing, encryption, secrets, privacy, deletion, or data migration.
- The implementation requires a broad refactor for safety.
- The task cannot be validated with deterministic tests or observable criteria.
- The worker has to make a product or design decision not present in the specification.

Opus should then decide whether to:

- Clarify the task specification.
- Change the interface contract.
- Redesign the task boundary.
- Serialize previously parallel work.
- Implement the difficult part itself.
- Escalate a product or engineering decision to the human.

---

## Prompting Rules

### Opus coordinator instructions

Opus should be instructed to:

- Treat `SPEC.md`, `PLAN.md`, contracts, task cards, tests, and commits as source-of-truth artifacts.
- Convert vague features into small, independently verifiable deliverables.
- Define allowed files, forbidden files, inputs, outputs, invariants, and test commands.
- Establish API and schema contracts before assigning implementation tasks.
- Identify dependencies and shared-file hazards before parallelizing.
- Reserve itself for requirements, design, contracts, review, integration, and difficult debugging.
- Use Sonnet for normal feature implementation.
- Use Haiku for reconnaissance, mechanical work, and constrained support tasks.
- Review actual diffs and test evidence rather than accepting completion claims.
- Escalate rather than repeatedly retrying workers when a problem is architectural or ambiguous.
- Keep plans operational and concise.

### Sonnet worker instructions

Sonnet should be instructed to:

- Read `AGENTS.md` and the assigned task card first.
- Stay within allowed-file boundaries.
- Follow approved contracts exactly.
- Avoid unrelated cleanup or opportunistic refactoring.
- Stop and report when repository reality conflicts with the task.
- Add or update task-relevant tests.
- Run all required verification commands.
- Create one focused commit.
- Return a structured handoff with commands, results, modified files, and uncertainties.
- Never redesign APIs, schemas, architecture, or authorization policy without escalation.

### Haiku worker instructions

Haiku should be instructed to:

- Read `AGENTS.md` and its assigned task card.
- Perform only explicitly authorized work.
- Prefer read-only reconnaissance unless a mechanical edit is clearly defined.
- Do not infer product requirements or architecture.
- Do not change shared interfaces, schemas, authorization rules, or database designs.
- Report evidence with file paths, symbol names, command output, and exact findings.
- Stop immediately when the task is ambiguous or exceeds the defined boundary.
- Create a focused commit only when code changes are explicitly authorized.
- Return a concise structured handoff.

---

## Context Management

Avoid paying repeatedly for agents to rediscover stable repository knowledge.

### Stable context belongs in committed files

Store persistent instructions in files such as `AGENTS.md`:

- Build, test, lint, and formatting commands
- Package manager and runtime versions
- Project architecture summary
- Directory ownership rules
- Coding conventions
- Error and logging conventions
- Authentication and authorization patterns
- Database migration policy
- Testing strategy
- Dependency rules
- Deployment and environment constraints
- Security constraints

### Worker context should be task-specific

Give each worker:

- Its task card
- Relevant contracts and type definitions
- Relevant existing implementation examples
- Relevant tests
- The local module’s conventions
- Allowed and forbidden files
- Required verification commands
- Expected handoff format

Do not give every worker:

- The complete feature discussion
- Every design document
- The entire repository
- Raw transcripts from other workers
- Open-ended authority to modify any file
- Permission to reinterpret the product or architecture

> Use persistent repository artifacts and narrow task context. Avoid relying on long chat histories as the coordination mechanism.

---

## Default Claude Policy

```md
# Default Claude Team Policy

## Model Roles

- Claude Opus 5.5: Coordinator, architect, contract owner, reviewer, integrator, final approver.
- Claude Sonnet 5: Default supervised implementation agent.
- Claude Haiku 4.5: High-volume reconnaissance, mechanical edits, fixtures, narrow checks, and low-risk support work.

## Opus Owns

- Requirements interpretation
- Architecture and domain decisions
- API and schema contracts
- Security-sensitive decisions
- Task decomposition
- Shared-file ownership
- Integration
- Diff review
- Final acceptance

## Sonnet Owns

- Bounded frontend implementation
- Bounded backend implementation
- Scoped service and repository changes
- Unit and integration tests
- Localized bug fixes
- Explicit repair tasks from Opus

## Haiku Owns

- Repository reconnaissance
- File/type/test discovery
- Fixture and mock generation
- Formatting-only changes
- Generated client/type updates
- Explicit mechanical refactors
- Narrow lint/type remediation
- Focused read-only review passes
- Defined test-matrix expansion

## Delegation Rule

Delegate only tasks with:

- Clear ownership
- Explicit inputs and outputs
- Defined allowed files
- Defined forbidden files
- Stable contracts
- Deterministic acceptance criteria
- Runnable verification commands
- Limited cross-task dependencies

## Escalation Rule

Return work to Opus if:

- Haiku encounters ambiguity or a non-mechanical design decision
- Sonnet fails twice
- Scope expands beyond the task card
- The contract is unclear
- Shared files become necessary
- Security, architecture, or migration decisions arise
- Integration fails for non-local reasons
```

---

## Practical Starting Configuration

Start with limited parallelism and increase only after task boundaries and CI prove reliable.

| Setting | Recommended starting point |
|---|---|
| Opus coordinators | 1 |
| Concurrent Sonnet code workers | 2–3 |
| Concurrent Haiku reconnaissance/review workers | 3–6 |
| Concurrent Haiku code-changing workers | 1–2, only for mechanical isolated tasks |
| Worker isolation | One Git worktree per code-writing worker |
| Required worker output | Commit SHA, diff summary, tests run, results, uncertainties |
| Merge policy | Opus review before merge |
| Final gate | Integration tests, typecheck, lint, relevant browser/E2E tests |
| Retry policy | Haiku: escalate quickly; Sonnet: maximum two attempts before Opus review |
| Shared files | Opus-owned unless explicitly assigned |
| Feature planning | Opus-only |
| Security-sensitive changes | Opus-owned and human-reviewed as appropriate |

Increase parallelism only after observing:

- Low merge-conflict rates
- Reliable task-card templates
- Good automated test coverage
- Fast local and CI feedback loops
- Useful worker handoffs
- Few repeated review failures
- Stable contracts
- Clear module ownership

---

## Bottom Line

> **Use Opus for judgment, Sonnet for implementation, and Haiku for high-volume constrained support work.**

For most web frontend and backend development:

- **Opus 5.5** should decide what to build, define the system boundaries, establish contracts, break work into tasks, review results, and integrate the final product.
- **Sonnet 5** should perform the majority of bounded full-stack implementation and test work.
- **Haiku 4.5** should perform cheap reconnaissance, mechanical edits, repetitive test support, and other narrow tasks with deterministic verification.

This structure aims to preserve approximately Opus-level product quality while directing most token volume to Sonnet and Haiku. The workflow succeeds when the system delegates **small, contract-driven, testable deliverables**, rather than delegating entire ambiguous features to cheaper models.
