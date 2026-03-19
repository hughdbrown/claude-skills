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

Designs a new software feature grounded in the project's actual codebase. Produces:

1. **PRD** — overview, goals, acceptance criteria (as test descriptions), technical decisions, design, test strategy, rollback plan, and implementation stages.
2. **Task List** — test-first implementation steps within each stage, with tests, code, verification commands, and risks.

Output files: `docs/design/<feature-slug>-prd.md` and `docs/design/<feature-slug>-tasks.md` (or user-specified location).

## Instructions

### Phase 0: Triage

1. **Classify scope** — state the classification and reasoning before proceeding:
   - **Small** (single file, <50 lines, no new patterns): produce task list only → skip to Phase 3.
   - **Medium** (2–5 files, existing patterns): produce PRD + task list → all phases.
   - **Large** (multiple subsystems, new patterns): produce PRD + task list. If the feature should be split into sub-designs, recommend the split and design each independently.
   - **Ambiguous** (no concrete problem or solution stated): do not design yet → go to Phase 1 to clarify, then re-classify.

   Do not over-scope. The feature description is the scope — no tangential improvements or abstractions beyond what is needed.

### Phase 1: Understand

2. **Clarify (if needed).** Ask targeted questions only when the description lacks a concrete what or how. Use `AskUserQuestion` with at most 3–4 questions:
   - What problem does this solve? Who is the user?
   - Constraints (performance, compatibility)?
   - What is out of scope?
   - Prior art (issues, RFCs, discussions)?

   If clear, proceed directly to exploration.

3. **Explore the codebase** — use parallel tool calls to investigate concurrently:
   - `Glob` to map project structure and find source/test files
   - `Read` root config files (go.mod, Cargo.toml, package.json) for tech stack
   - `Grep` for conventions (error handling patterns, test patterns, naming)
   - `Grep` for feature-related keywords; `Read` matching files
   - For unfamiliar codebases, use `Agent` subagents for deeper parallel exploration

4. **Identify integration points.** List the specific files and functions the feature will touch. For each, note the existing pattern (naming, error handling, test style) new code must follow. If a decision requires a pattern the codebase doesn't have (novel pattern), flag it and present options in Phase 2.

   Phase 1 is done when you can name every file, function, and convention the feature will touch or follow.

### Phase 2: PRD

5. **Write the PRD** with these sections:

   - **Overview**: One paragraph — what the feature does and the problem it solves.
   - **Goals and Non-Goals**: Bulleted. Non-goals prevent scope creep.
   - **Acceptance Criteria (as test descriptions)**: Each criterion written as `TestName`: When X, assert Y. These are specifications, not real tests yet. If you cannot state a criterion as a test, the design is too vague — refine it.
     - `TestFeature_HappyPath`: When valid input is provided, expected output is produced.
     - `TestFeature_InvalidInput`: When input is empty, `ErrInvalidInput` is returned.
     - `TestFeature_EdgeCase`: When concurrent requests arrive, each is handled independently.
   - **Technical Decisions**: For each choice (library, storage, protocol, data format), cite the specific codebase file or pattern that justifies it. For novel patterns with no precedent, present at least two options with trade-offs, recommend one, and flag for developer confirmation. If a decision depends on runtime behavior you can't determine from code, recommend a time-boxed spike as a preliminary task.
   - **Design and Operation**: User perspective (commands, inputs, outputs), system perspective (data flow, state, concurrency), error handling (failure modes and responses), edge cases.
   - **Test Strategy**: Testing levels needed (unit, integration, e2e), test infrastructure (fixtures, httptest, temp dirs, mocks), key scenarios, performance/concurrency tests if applicable.
   - **Rollback and Safety**: Can the feature be disabled without data loss? Are migrations reversible? One sentence suffices for trivial features.
   - **Implementation Stages**: Ordered phases. Each stage must produce a working system, touch ≤5 files, and have a deliverable verifiable in under a minute.

6. **Present the PRD** to the user and wait for explicit approval before proceeding. Incorporate feedback.

### Phase 3: Task List

7. **Build tasks for each stage.** Each task is test-first and specific ("Add error return to `ProcessFile()` and propagate through `RunJob()`" — not "add error handling"):

   - **Tests**: test functions, assertions, fixtures needed — tests come first.
   - **Code**: minimum implementation to pass tests. Include files to create/modify, functions/types to add, config changes, env vars, dependencies, data migrations, and API surface as applicable.
   - **Verify**: exact command to run tests (e.g., `go test ./internal/webhook/...`).
   - **Risks**: known blockers for this stage.

8. **Order tasks** top-to-bottom within each stage, no forward dependencies. Note which tasks can run in parallel.

9. **Validate coverage.** For each acceptance criterion and Design section, name the task that covers it. If any has no task, add one.

10. **Present the task list** to the user. Incorporate feedback.

### Phase 4: Write Files

11. **Write deliverables** using the `Write` tool. Default locations:
    - `docs/design/<feature-slug>-prd.md`
    - `docs/design/<feature-slug>-tasks.md`

    If no `docs/` directory exists, ask the user for an alternative.

12. **Offer next steps**: start implementing stage 1, commit the design documents, or refine a section.

## Implementation Protocol

Per task, follow this sequence:

1. Write all tests for this task. Tests should compile but fail.
2. Run tests — confirm they fail for the right reasons (not compilation errors). Add minimal stubs if needed.
3. Write implementation — only enough to make tests pass.
4. Run tests. Green = done. Red = fix implementation (not tests, unless the test has a bug).
5. Run linter/formatter. Fix issues.
6. Move to next task.

**No untested code.** Every helper, error path, or config option must be exercised by a test — or deleted. Tests are the specification; if a test and the PRD disagree, fix the test first, then the code. Never weaken assertions to make a test pass.

## Guidelines

- **Ground every decision** in the codebase's existing patterns, tools, and conventions.
- **Keep stages small** — ≤5 files, clear deliverable, working system after each stage.
- **Be specific** — name files, functions, types, and patterns. Vague tasks waste implementation time.
- **Flag risks and trade-offs** — present options with pros/cons and let the developer choose.
- **Spike when uncertain** — if a decision depends on behavior you can't determine from code, add a time-boxed spike as a preliminary task.

## Example

User: `/hdb:design webhook notifications for review completion`

Agent:

1. **Triage**: Classifies as **medium** — touches config, storage, worker, and CLI (4 areas) but follows existing patterns.

2. **Clarify**: Asks: "Should webhooks support multiple URLs per repo? Do you need retry logic? Should the payload format be configurable or fixed?"

3. **Explore**: Uses `Glob("**/*.go")` to map structure, `Read` on `go.mod` and `internal/config/config.go`, `Grep("ReviewComplete\|jobDone")` to find the review completion flow. Identifies `internal/worker/run.go` (job processing) and `internal/storage/jobs.go` (results storage) as integration points.

4. **PRD**:
   - **Overview**: HTTP POST notifications on review completion for external tool integration.
   - **Goals**: Reliable delivery, multiple URLs per repo, review verdict in payload. **Non-goals**: payload transformation, auth beyond shared secret, webhook management UI.
   - **Acceptance Criteria**:
     - `TestWebhookDelivery_SendsPostOnReviewComplete`: Job transitions to `done` with webhook configured → POST sent within 5s.
     - `TestWebhookDelivery_NoConfigNoSend`: No webhook URL → no HTTP request.
     - `TestWebhookConfig_ParsesTOML`: `[[webhooks]]` in config.toml → valid `WebhookConfig`.
     - `TestWebhookPayload_IncludesVerdict`: POST body contains verdict and findings count.
   - **Technical decisions**: stdlib `net/http` (project has no HTTP client deps — unjustified to add one), webhook config in existing TOML (matches `[[repos]]` pattern), `webhook_deliveries` table in SQLite (project already uses `internal/storage`).
   - **Design**: Worker marks job `done` → enqueue delivery per URL → delivery goroutine POSTs and records result.
   - **Test strategy**: `httptest` servers for delivery unit tests, integration tests for worker→webhook pipeline, `t.TempDir()` for SQLite.
   - **Rollback**: Additive — remove `[[webhooks]]` from config to disable.
   - **Stages**: (1) Config and storage, (2) Delivery engine, (3) Worker integration, (4) CLI management.

5. **User feedback**: "Skip retry logic for v1." Agent updates PRD accordingly.

6. **Task list** (Stage 1 excerpt):

   > **Task 1.1: Webhook config parsing**
   > - **Tests** (`internal/config/config_test.go`):
   >   - `TestConfig_WebhookSection` — TOML with `[[webhooks]]` → `WebhookConfig` structs
   >   - `TestConfig_NoWebhooks` — no webhooks section → empty slice
   > - **Code**: Add `WebhookConfig` type and `[[webhooks]]` to `Config` in `internal/config/config.go`
   > - **Verify**: `go test ./internal/config/...`

   > **Task 1.2: Webhook delivery storage**
   > - **Tests** (`internal/storage/webhooks_test.go`):
   >   - `TestInsertWebhookDelivery` — insert, read back, verify fields
   >   - `TestListWebhookDeliveries` — insert multiple, list by job ID, verify count/order
   > - **Code**: Migration in `internal/storage/migrations.go`, methods in `internal/storage/webhooks.go`
   > - **Verify**: `go test ./internal/storage/...`
   > - **Risks**: Tests need file-backed SQLite for WAL mode — use `t.TempDir()` per existing conventions.

7. **Validate**: Each acceptance criterion maps to at least one task. All Design sections covered.

8. **Write files**: `docs/design/webhook-notifications-prd.md` and `docs/design/webhook-notifications-tasks.md`.

9. **Next steps**: "Would you like to start implementing stage 1, commit the design files, or refine anything?"

10. **Implementation**: Test-first per the protocol — write tests, confirm failure, implement, confirm green, lint, commit per task.
