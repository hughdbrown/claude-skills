# Test Scenarios

Fixed test scenarios for evaluating SKILL.md quality. **DO NOT MODIFY** — these
are the validation data, analogous to the pinned validation shard in autoresearch.

When evaluating the skill, mentally simulate applying it to each scenario and
assess whether the skill's instructions produce a good outcome.

## Scenario 1: Small Feature (skip PRD)

> "Add a `--verbose` flag to the CLI that prints debug information during execution"

Expected behavior:
- Skill classifies this as small (single file, <50 lines, follows existing CLI patterns)
- Skips the PRD, produces only a task list
- Task list has 1 stage with test-first ordering
- Agent explores existing CLI flag handling before designing

## Scenario 2: Medium Feature (full workflow)

> "Add webhook notifications for review completion"

Expected behavior:
- Skill classifies this as medium (touches config, storage, worker, CLI)
- Asks clarifying questions (retry logic? multiple URLs? payload format?)
- Produces full PRD with all sections
- 3–4 implementation stages
- Each task starts with tests
- Technical decisions grounded in existing project patterns

## Scenario 3: Large Feature (consider splitting)

> "Implement a plugin system that allows third-party extensions to add new review
> rules, output formats, and notification channels"

Expected behavior:
- Skill classifies this as large (new patterns, spans multiple subsystems)
- Recommends splitting into sub-designs (e.g., plugin loading, rule plugins, output plugins)
- PRD explicitly addresses architectural decisions (plugin API, isolation, versioning)
- Many implementation stages, each independently verifiable

## Scenario 4: Ambiguous Feature (needs clarification)

> "Make the app faster"

Expected behavior:
- Skill recognizes ambiguity — no specific problem identified
- Agent asks targeted questions before proceeding
- Does NOT attempt to design without understanding the bottleneck
- May recommend a profiling spike as a preliminary stage

## Scenario 5: Cross-Cutting Concern (many files)

> "Add structured logging throughout the application"

Expected behavior:
- Classifies as medium or large depending on codebase size
- Explores existing logging patterns thoroughly
- PRD addresses: log format, log levels, what to log, where logs go
- Stages ordered so that logging infrastructure comes first, then adoption file-by-file
- Each stage produces a working system with partial logging

## Scenario 6: Feature in Unfamiliar Codebase

> "Add user authentication to this web app" (agent has never seen this codebase)

Expected behavior:
- Agent spends significant time in Phase 1 exploring the codebase
- Uses parallel tool calls to investigate project structure, tech stack, conventions
- Identifies existing auth-adjacent code (session handling, middleware, etc.)
- All technical decisions reference what the project already uses
- Flags novel patterns that have no precedent in the codebase

## Scenario 7: Feature with External Dependencies

> "Integrate Stripe payment processing for subscription billing"

Expected behavior:
- PRD addresses: which Stripe SDK version, API vs. SDK, webhook handling
- Technical decisions compare options (Stripe Checkout vs. custom form)
- Test strategy includes mock/stub approach for external API
- Rollback section addresses data migration and subscription state
- Stages isolate external dependency integration from business logic
