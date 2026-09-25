# PLAN: Organization invitations

## Contracts

- `contracts/invitations.ts`: fixed

## Tasks

| Task | Model | Depends on | Owns (files) | Parallel group |
|---|---|---|---|---|
| TASK-001 map membership/role/invitation patterns | haiku | — | none (read-only) | A |
| TASK-002 schema migration | sonnet | TASK-001 | `db/migrations/` | B |
| TASK-003 repository methods | sonnet | TASK-002 | `src/repositories/invitations.ts` | C |
| TASK-004 list endpoint | sonnet | TASK-003 | `src/api/organizations/invitations.ts` (GET), its test | D |
| TASK-005 create endpoint | sonnet | TASK-004 | same route file: serialized after 004 | E |
| TASK-006 revoke endpoint | sonnet | TASK-005 | same route file: serialized after 005 | F |
| TASK-007 typed client methods | haiku | contracts only | `src/client/invitations.ts` | B |
| TASK-008 fixtures and edge-case records | haiku | TASK-002 | `test/fixtures/invitations.ts` | C |
| TASK-009 invitation list UI | sonnet | TASK-007 | `src/ui/settings/Invitations*.tsx` | C |
| TASK-010 invite form UI | sonnet | TASK-007 | `src/ui/settings/InviteForm*.tsx` | C |
| TASK-011 E2E invite/list/revoke | sonnet | 006, 009, 010 | `e2e/invitations.spec.ts` | G |

## Shared-file ownership

| File | Owner |
|---|---|
| `src/api/organizations/invitations.ts` | 004 → 005 → 006 serialized |
| `src/api/routes.ts` | coordinator (registers the router once) |
| `contracts/invitations.ts` | coordinator |

## Dependency graph

```text
TASK-001 recon (haiku)
   |
coordinator: contracts + auth rules
   +-------------------+----------------------+
   v                   v                      v
TASK-002 migration   TASK-007 client (haiku)
   |          \            |
TASK-003 repo  TASK-008    +--> TASK-009 list UI, TASK-010 form UI
   |                               |
TASK-004 → 005 → 006 endpoints     |
   +-------------------------------+
                  v
            TASK-011 E2E
                  v
     coordinator integration + final review
```

## Integration order

1. 002, 003, 008
2. 004, 005, 006 (+ coordinator registers router)
3. 007, 009, 010
4. 011, then final gate

## Final gate

```bash
pnpm test
pnpm typecheck
pnpm lint
pnpm e2e e2e/invitations.spec.ts
```
