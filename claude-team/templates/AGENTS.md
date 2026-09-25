# AGENTS.md

Stable repository knowledge every worker reads before its task card.
Keep it short; workers pay for every line on every task.

## Commands

| Purpose | Command |
|---|---|
| Install | |
| Build | |
| Unit tests (one file) | |
| All tests | |
| Typecheck | |
| Lint / format | |

## Architecture

<!-- 5–10 lines: layers, where each kind of code lives -->

## Conventions

- Error responses:
- Logging:
- Validation:
- Auth / tenancy pattern:

## Boundaries

- Coordinator-owned (workers never edit): shared schemas, auth middleware, migrations policy, CI config, routing tables
- New dependencies require coordinator approval

## Worker rules

1. Read this file and your task card first.
2. Edit only the files your task card allows.
3. Follow the contract exactly; stop and report if the repo disagrees with it.
4. No opportunistic cleanup or refactoring.
5. Run every verification command; paste real output in the handoff.
6. One focused commit. Never merge.
