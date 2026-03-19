---
name: hdb:design
description: Design a new software feature with a PRD and detailed implementation task list
---

# hdb:design

## Usage

```
/hdb:design <feature description>
```

## Description

Designs a new software feature grounded in the project's actual codebase. Produces two deliverables written to `docs/design/<feature-slug>-{prd,tasks}.md`:

1. **PRD** — overview, goals, acceptance criteria (as test descriptions), technical decisions, design, test strategy, rollback, and implementation stages.
2. **Task List** — test-first steps per stage: tests, code, verification commands, risks.

## Instructions

### Phase 0: Triage

1. **Classify scope** and state reasoning:
   - **Small** (1 file, <50 lines, no new patterns): task list only → skip to Phase 3.
   - **Medium** (2–5 files, existing patterns): PRD + task list → all phases.
   - **Large** (multiple subsystems, new patterns): PRD + task list. Consider splitting into sub-designs.
   - **Ambiguous** (no concrete problem/solution): clarify in Phase 1, then re-classify.

   The feature description is the scope — no tangential improvements or unnecessary abstractions.

### Phase 1: Understand

2. **Clarify (if needed)** using `AskUserQuestion` — only when the description lacks a concrete what or how. At most 3–4 questions: problem/user, constraints, out-of-scope, prior art. If clear, skip to exploration.

3. **Explore the codebase** with parallel tool calls. Every technical decision in the PRD must cite a specific file or pattern discovered here:
   - `Glob("**/*.{go,rs,py,ts}")` → project structure and file layout
   - `Read` build/config files (go.mod, Cargo.toml, package.json) → tech stack and dependencies
   - `Grep` for error handling, test patterns, naming conventions → coding standards
   - `Grep` for feature-related keywords → related existing code
   - For unfamiliar codebases: use `Agent` subagents to explore multiple areas concurrently

4. **Identify integration points.** For each, record: the file path, the function/type involved, and the convention new code must follow (naming, error handling, test style). Flag novel patterns (no codebase precedent) for Phase 2 decisions. Done when every file and convention is named.

### Phase 2: PRD

5. **Write the PRD**:
   - **Overview**: What the feature does and the problem it solves.
   - **Goals / Non-Goals**: Bulleted. Non-goals prevent scope creep.
   - **Acceptance Criteria** (as test descriptions): `TestName`: When X, assert Y. If you can't write a criterion as a test, the design is too vague.
   - **Technical Decisions**: Cite the codebase file/pattern justifying each choice. For novel patterns: present ≥2 options with trade-offs, recommend one, flag for developer. For unknowable runtime behavior: recommend a time-boxed spike.
   - **Design and Operation**: User perspective, system perspective (data flow, concurrency, state), error handling, edge cases.
   - **Test Strategy**: Levels (unit/integration/e2e), infrastructure (fixtures, mocks, temp dirs), key scenarios.
   - **Rollback and Safety**: Can the feature be disabled without data loss? One sentence for trivial features.
   - **Implementation Stages**: Ordered. Each stage: working system, ≤5 files, deliverable verifiable in under a minute.

6. **Present PRD** to the user. Wait for explicit approval before proceeding.

### Phase 3: Task List

7. **Build test-first tasks per stage.** Be specific — name files, functions, types:
   - **Tests**: functions, assertions, fixtures — always first.
   - **Code**: minimum to pass tests (files, functions, config, deps, migrations, API surface as applicable).
   - **Verify**: exact test command.
   - **Risks**: known blockers.

8. **Order tasks** top-to-bottom, no forward dependencies. Note parallelizable tasks.

9. **Validate coverage**: name the task covering each acceptance criterion. Add tasks for gaps.

10. **Present task list** to the user. Incorporate feedback.

### Phase 4: Write Files

11. **Write files** with `Write` tool to `docs/design/` (or ask user). Offer next steps: implement stage 1, commit docs, or refine.

## Implementation Protocol

Per task: (1) write tests (compile but fail), (2) confirm correct failures (add stubs if needed), (3) implement minimum to pass, (4) run tests (green = done; red = fix implementation), (5) lint/format, (6) next task.

**No untested code** — test or delete. Tests are the specification. Never weaken assertions.

## Guidelines

- **Ground decisions** in existing codebase patterns — cite specific files.
- **Keep stages small** — ≤5 files, clear deliverable, working system after each.
- **Be specific** — name files, functions, types. Vague tasks waste time.
- **Flag trade-offs** — present options with pros/cons for the developer.
- **Spike when uncertain** — add a time-boxed spike as a preliminary task.

## Example

User: `/hdb:design webhook notifications for review completion`

**Triage**: Medium — config, storage, worker, CLI (4 areas), existing patterns.

**Clarify**: "Multiple URLs per repo? Retry logic? Configurable payload format?"

**Explore**: `Glob("**/*.go")` maps structure. `Read` on `go.mod`, `internal/config/config.go`. `Grep("ReviewComplete\|jobDone")` finds the completion flow in `internal/worker/run.go` and `internal/storage/jobs.go`.

**PRD**:
- **Overview**: HTTP POST on review completion for external tools.
- **Goals**: Reliable delivery, multiple URLs, verdict in payload. **Non-goals**: payload transforms, auth beyond shared secret, webhook UI.
- **Acceptance Criteria**: `TestWebhookDelivery_SendsPostOnComplete` (POST within 5s), `TestWebhookDelivery_NoConfigNoSend` (no URL → no request), `TestWebhookConfig_ParsesTOML`, `TestWebhookPayload_IncludesVerdict`.
- **Technical decisions**: stdlib `net/http` (no HTTP client deps in `go.mod` — adding one is unjustified for simple POST requests), TOML config with `[[webhooks]]` (matches existing `[[repos]]` pattern in `config.go`), SQLite `webhook_deliveries` table (follows existing `internal/storage/jobs.go` table pattern).
- **Design**: Job done → enqueue per URL → goroutine POSTs and records result.
- **Stages**: (1) Config + storage, (2) Delivery engine, (3) Worker integration, (4) CLI commands.

**User feedback**: "Skip retry for v1." PRD updated.

**Task list** (Stage 1):

> **Task 1.1: Config parsing**
> - **Tests**: `TestConfig_WebhookSection` (TOML → structs), `TestConfig_NoWebhooks` (→ empty slice)
> - **Code**: `WebhookConfig` type + `[[webhooks]]` in `internal/config/config.go`
> - **Verify**: `go test ./internal/config/...`

> **Task 1.2: Delivery storage**
> - **Tests**: `TestInsertWebhookDelivery` (insert + read back), `TestListWebhookDeliveries` (count + order)
> - **Code**: Migration in `migrations.go`, methods in `webhooks.go`
> - **Verify**: `go test ./internal/storage/...`
> - **Risks**: File-backed SQLite for WAL — use `t.TempDir()`.

**Validate**: All criteria mapped to tasks. **Write files**. **Offer next steps**.
