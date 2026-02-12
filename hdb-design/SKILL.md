---
name: hdb:design
description: Design a new software feature with a PRD and detailed implementation task list
---

# hdb:design

Design a new software feature with a PRD and detailed implementation task list.

## Usage

```
/hdb:design <feature description>
```

## Description

Collaboratively designs a new software feature with the developer. Explores the existing codebase to ground all technical decisions in the project's actual architecture, conventions, and dependencies. Produces two deliverables:

1. **Product Requirements Document (PRD)** — what the feature does, technical decisions, how it operates, and ordered implementation stages.
2. **Detailed Task List** — within each stage, test-first scoped steps covering tests to write, code to implement, config changes, environment variables, dependencies, and documentation.

Both deliverables are written to files in the project for reference during implementation.

## Instructions

When the user invokes `/hdb:design <feature description>`:

### Phase 0: Triage

1. **Estimate the feature's scope.** Based on the description, classify as:
   - **Small** (single file, <50 lines, no new patterns) — skip the PRD. Produce only a task list and proceed directly to Phase 3.
   - **Medium** (2-5 files, follows existing patterns) — produce both PRD and task list.
   - **Large** (spans multiple subsystems, introduces new patterns) — produce both PRD and task list. Consider whether the feature should be split into separate designs; if so, recommend the split and design each part independently.

   State the classification and reasoning before proceeding.

### Phase 1: Understand the request and codebase

2. **Clarify the feature request.** If the description is vague or ambiguous, ask targeted questions:
   - What problem does this solve? Who is the target user?
   - Are there constraints (performance, compatibility, backward compatibility)?
   - What is explicitly out of scope?
   - Are there existing issues, RFCs, or prior discussions to reference?

   If the description is already clear and specific, proceed without interrogating the user.

3. **Explore the codebase in parallel** to understand:
   - Project structure (directories, key files, entry points)
   - Tech stack (language, framework, build system, package manager, dependencies)
   - Existing conventions (naming, file layout, test patterns, config format, error handling)
   - Architecture (how components interact, data flow, API boundaries)
   - Related existing code that touches the area this feature will affect

   These aspects are independent — use subagents or parallel tool calls to investigate them concurrently.

4. **Identify integration points** where the new feature connects to existing code, and note which existing patterns the feature should follow.

### Phase 2: Draft the PRD

5. **Write the PRD** with these sections:

   **Overview** — One-paragraph summary of the feature and the problem it solves.

   **Goals and Non-Goals** — What the feature will and will not do. Non-goals prevent scope creep during implementation.

   **Acceptance Criteria (as test descriptions)** — Numbered list of specific, verifiable conditions written as test names and assertions. Each criterion should be testable: "When X happens, Y is the result." Example format:
   - `TestFeature_HappyPath`: When valid input is provided, the expected output is produced.
   - `TestFeature_InvalidInput`: When input is empty, an `ErrInvalidInput` error is returned.
   - `TestFeature_EdgeCase`: When concurrent requests arrive, each is handled independently.

   These are not yet real tests — they are specifications in test language. They define the behavioral contract the implementation must satisfy. If you cannot write a criterion as a test description, the design is too vague — refine it.

   **Technical Decisions** — Concrete choices about libraries, storage, protocols, APIs, and data formats. Ground every decision in what the project already uses. When the project has no precedent for a choice, present the trade-offs and recommend an option. Flag decisions that the developer should weigh in on.

   **Design and Operation** — How the feature works:
   - User perspective: commands, UI, inputs, outputs, observable behavior
   - System perspective: data flow, state transitions, concurrency, persistence
   - Error handling: what can go wrong, how each failure mode is handled
   - Edge cases: empty inputs, concurrent access, partial failures, large data

   **Test Strategy** — What levels of testing are needed (unit, integration, e2e)? What test infrastructure is required (test fixtures, httptest servers, temp directories, mock agents)? What are the key scenarios to cover? Are there performance or concurrency tests needed?

   **Rollback and Safety** — Can this feature be disabled without data loss? If it adds a database migration, is the migration reversible? If it changes CLI behavior, is backward compatibility maintained? For trivial features, a single sentence suffices.

   **Implementation Stages** — Ordered phases that build on each other. Each stage must:
   - Produce a working (if incomplete) system when finished
   - Touch no more than ~5 files (if a stage needs more, split it)
   - Have a clear deliverable that can be verified in under a minute (a passing test suite, a working command, a visible output)

6. **Present the PRD to the user** for review. Wait for feedback and incorporate it before proceeding to the task list. If the user approves without changes, continue.

### Phase 3: Build the task list

7. **For each implementation stage**, produce a task list. Each task follows **test-first ordering** and must be cleanly scoped:

   - **Tests to write** — test functions, what they assert, test fixtures or infrastructure needed. Tests come first in every task.
   - **Code to implement** — the minimum code that makes those tests pass. Include whichever of the following apply:
     - **Files**: directories and files to create or modify, with the purpose of each change
     - **Code**: functions, types, interfaces, structs, methods, or constants to add or change
     - **Config**: config file changes, feature flags, default values
     - **Environment**: environment variables to add, with descriptions and defaults
     - **Dependencies**: libraries, modules, or crates to import (with version constraints if relevant)
     - **Data**: database migrations, schema changes, seed data
     - **API surface**: CLI commands, HTTP endpoints, or SDK methods to add
   - **Verification** — the command to run tests and confirm green
   - **Documentation**: README sections, doc comments, man pages, or guide pages to write or update (if applicable)

   Example task:

   > **Task 2.1: Webhook delivery sender**
   > - **Tests**: In `internal/webhook/sender_test.go`:
   >   - `TestSend_SuccessfulDelivery` — httptest server returns 200, verify delivery recorded as success
   >   - `TestSend_ServerError` — httptest server returns 500, verify delivery recorded as failed
   >   - `TestSend_Timeout` — httptest server delays beyond timeout, verify error returned
   > - **Code**: In `internal/webhook/sender.go`:
   >   - `Send(ctx, url, secret, payload) (*DeliveryResult, error)` — HTTP POST with HMAC signature, timeout from context
   > - **Verify**: `go test ./internal/webhook/...`

   **Risks**: For each stage, note known risks or blockers. E.g., "This stage depends on WAL mode; if tests use an in-memory DB, delivery tracking tests will need a file-backed DB."

8. **Order tasks within each stage** so they can be executed top-to-bottom. Earlier tasks must not depend on later ones. If two tasks are independent, note that they can be done in parallel.

9. **Validate coverage.** Walk through each acceptance criterion and each section of the Design and Operation section. Confirm that at least one task addresses each. Flag any gaps before presenting to the user.

10. **Present the task list to the user** for review. Incorporate feedback.

### Phase 4: Write deliverables

11. **Write the PRD and task list to files.** Ask the user where they would like the files. Suggest:
    - `docs/design/<feature-slug>-prd.md`
    - `docs/design/<feature-slug>-tasks.md`

    If the project has no `docs/` directory, offer to create it or suggest the project root.

12. **Offer next steps:**
    - Start implementing stage 1
    - Commit the design documents
    - Refine a specific section

## Implementation Protocol

When implementing each stage (whether immediately or in a later session), follow this sequence per task:

1. Write the test file(s) with all tests for this task. Tests should compile but fail.
2. Run the tests. Confirm they fail for the right reasons (missing functions, wrong return values — not compilation errors). If they don't compile, add minimal stubs to make them compile.
3. Write the implementation code — only enough to make the tests pass.
4. Run the tests. If green, the task is done. If red, fix the implementation (not the tests, unless the test has a bug).
5. Run the project's linter/formatter (e.g., `go vet`, `go fmt`). Fix any issues.
6. Move to the next task.

**Do not write code that no test exercises.** If you find yourself adding a helper function, error path, or configuration option that no test covers, either write a test for it or delete it.

## Guidelines

- **Ground decisions in the codebase.** Match the project's existing patterns, tools, and conventions. Do not introduce new frameworks, languages, or paradigms without strong justification.
- **Keep stages small and incremental.** Each stage should touch no more than ~5 files, add clear demonstrable value, and leave the system in a working state.
- **Be specific in tasks.** "Add error handling" is too vague. "Add an error return to `ProcessFile()` in `internal/worker/process.go` and propagate it through `RunJob()` to the caller" is actionable.
- **Flag risks and open questions.** If a decision has meaningful trade-offs, present the options with pros and cons and let the developer choose.
- **Do not over-scope.** The feature description is the scope. Do not introduce tangential improvements, refactors, or "nice to haves" unless the developer asks for them.
- **Respect the project's complexity budget.** A simple feature gets a simple design. Do not add abstractions, extension points, or configurability beyond what is needed now.
- **Spike when uncertain.** If a technical decision depends on behavior you can't determine from reading code (e.g., "will SQLite handle 1000 concurrent webhook deliveries?"), recommend a time-boxed spike before finalizing the design. The spike is a task in a preliminary stage, and the PRD notes which decisions depend on its results.
- **Tests are the specification, code is the implementation.** During implementation, treat tests as the authority on what the code should do. If a test and the PRD disagree, the test is wrong — fix the test first, then fix the code. Never make a test pass by weakening its assertions.

## Example

User: `/hdb:design webhook notifications for review completion`

Agent:

1. Triages as **medium** — touches config, storage, worker, and CLI (4 areas) but follows existing patterns throughout.

2. Asks clarifying questions: "Should webhooks support multiple URLs per repo? Do you need retry logic for failed deliveries? Should the payload format be configurable or fixed?"

3. Explores the codebase in parallel: reads the daemon server, config system, storage layer, and worker pool to understand how reviews are processed and completed.

4. Drafts the PRD:
   - **Overview**: Send HTTP POST notifications when code reviews complete, so external tools (CI, chat, dashboards) can react to review results.
   - **Goals**: Deliver webhooks reliably, support multiple URLs per repo, include review verdict and findings in payload. **Non-goals**: payload transformation, authentication beyond a shared secret, UI for webhook management.
   - **Acceptance Criteria**:
     - `TestWebhookDelivery_SendsPostOnReviewComplete`: When a review job transitions to `done` and a webhook URL is configured, an HTTP POST is sent to that URL within 5 seconds.
     - `TestWebhookDelivery_NoConfigNoSend`: When no webhook URL is configured, no HTTP request is made.
     - `TestWebhookConfig_ParsesTOML`: A `[[webhooks]]` section in config.toml produces a valid `WebhookConfig` struct.
     - `TestWebhookPayload_IncludesVerdict`: The POST body contains the review verdict and findings count.
   - **Technical decisions**: Use stdlib `net/http` (no new deps), store webhook config in existing TOML, add `webhook_deliveries` table to SQLite for delivery tracking.
   - **Design**: After worker marks a job as `done`, enqueue a delivery for each configured webhook URL. A delivery goroutine sends the POST and records the result.
   - **Test strategy**: Unit tests with `httptest` servers for delivery. Integration tests for the worker-to-webhook pipeline using the test agent. Temp directories for SQLite in tests.
   - **Rollback**: Webhook feature is additive. Removing `[[webhooks]]` from config disables it. The `webhook_deliveries` table can be dropped without affecting core functionality.
   - **Stages**: (1) Config and storage, (2) Delivery engine, (3) Worker integration, (4) CLI management commands.

5. Presents PRD for feedback. User says: "Skip retry logic for v1, we can add it later." Agent updates the PRD.

6. Builds the task list with test-first ordering. Stage 1 example:

   > **Task 1.1: Webhook config parsing**
   > - **Tests**: In `internal/config/config_test.go`:
   >   - `TestConfig_WebhookSection` — TOML with `[[webhooks]]` produces `WebhookConfig` structs
   >   - `TestConfig_NoWebhooks` — TOML without webhooks section produces empty slice
   > - **Code**: Add `[[webhooks]]` section to `Config` struct and `WebhookConfig` type with fields `URL`, `Secret`, `Events` in `internal/config/config.go`
   > - **Verify**: `go test ./internal/config/...`

   > **Task 1.2: Webhook delivery storage**
   > - **Tests**: In `internal/storage/webhooks_test.go`:
   >   - `TestInsertWebhookDelivery` — insert a delivery record, read it back, verify fields
   >   - `TestListWebhookDeliveries` — insert multiple, list by job ID, verify count and order
   > - **Code**: Add `webhook_deliveries` table migration in `internal/storage/migrations.go`. Add `InsertWebhookDelivery` and `ListWebhookDeliveries` methods in `internal/storage/webhooks.go`
   > - **Verify**: `go test ./internal/storage/...`

   > **Risks**: Storage tests need a file-backed SQLite DB for WAL mode; in-memory won't work. Use `t.TempDir()` per existing test conventions.

7. Validates coverage: each acceptance criterion maps to at least one task. All PRD design sections are covered.

8. Writes `docs/design/webhook-notifications-prd.md` and `docs/design/webhook-notifications-tasks.md`.

9. Offers: "Would you like me to commit the design files as the first commit on this branch?"

10. Offers: "The design documents are written. Would you like to start implementing stage 1, commit the documents, or refine anything?"

11. During implementation, follows the test-first protocol: writes tests, confirms they fail, writes code, confirms they pass, moves to the next task. Each completed task gets its own commit with the stage and task number in the commit message header.
