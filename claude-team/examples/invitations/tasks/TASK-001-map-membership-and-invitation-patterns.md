# TASK-001: Map membership, role, and invitation patterns

## Goal

Give the coordinator a factual map of how membership and roles are checked today, so the
invitation contracts reuse existing patterns.

## Assigned Model

Claude Haiku 4.5

## Depends On

None

## Scope

Allowed files:

- None: read-only task; do not modify any file

Do not modify:

- Everything

## Contract

n/a (reconnaissance)

## Requirements

- Locate every organization-membership and role check used by API routes
- Locate any existing invitation, email-sending, or token-generation code
- Note the error-response helper routes use for 403/404

## Acceptance Criteria

- Every finding has a file path and symbol name
- Existing tests covering those checks are listed
- Inconsistent patterns are listed without recommendations

## Verification

Run:

```bash
# none: evidence is file paths and symbols
```

## Handoff Format

Return Status, Summary, findings table (path, symbol, condition, tests), inconsistencies.
