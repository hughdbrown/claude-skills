# Worked example: organization invitations

Feature request:

> Allow organization administrators to invite users by email, assign a role, view pending
> invitations, and revoke invitations.

This directory shows the coordinator's artifacts for that request, as they would appear
in a target repo:

- `SPEC.md`: goals, non-goals, invariants
- `contracts/invitations.ts`: the fixed contract every worker codes against
- `PLAN.md`: task table, dependency graph, shared-file ownership
- `tasks/TASK-001-*.md`: read-only Haiku recon card
- `tasks/TASK-004-*.md`: Sonnet endpoint card
- `handoffs/TASK-004.md`: a handoff that passes `validate_handoff.py --no-git` (its SHA is illustrative)

Try the scripts against it:

```bash
cd examples/invitations
../../scripts/progress.py show
../../scripts/render_worker_prompt.py tasks/TASK-004-list-pending-invitations-endpoint.md
../../scripts/validate_handoff.py handoffs/TASK-004.md --task tasks/TASK-004-list-pending-invitations-endpoint.md --no-git
```
