# TASK-004: Add pending invitation list endpoint

## Goal

Implement an authenticated endpoint that returns pending invitations for one organization.

## Assigned Model

Claude Sonnet 5

## Depends On

TASK-003

## Scope

Allowed files:

- `src/api/organizations/invitations.ts`
- `src/services/invitations.ts`
- `src/api/organizations/invitations.test.ts`

Do not modify:

- Database migrations
- Frontend files
- `src/auth/`
- `contracts/`
- `src/api/routes.ts`

## Contract

```http
GET /api/organizations/:organizationId/invitations
```

Response: `ListPendingInvitationsResponse` from `contracts/invitations.ts`.

## Requirements

- Require an authenticated user with organization administrator role
- Return only pending, non-revoked, non-expired invitations
- Never expose invitation tokens
- Use the existing repository abstraction and error-response conventions
- No new dependencies

## Acceptance Criteria

- Non-admin callers receive the established forbidden response
- Invitations from other organizations are never returned
- Revoked and expired invitations are excluded
- Response conforms to the contract type
- Existing endpoint tests remain green

## Verification

Run:

```bash
pnpm test src/api/organizations/invitations.test.ts
pnpm typecheck
pnpm lint
```

## Handoff Format

Write the handoff to `handoffs/TASK-004.md` using `templates/HANDOFF.md`.
