# SPEC: Organization invitations

## Request

> Allow organization administrators to invite users by email, assign a role, view pending
> invitations, and revoke invitations.

## Goals

- Org admins can create invitations by email with an assigned role and expiration
- Pending invitations appear in organization settings
- Org admins can revoke pending invitations

## Non-goals

- No bulk invitation import
- No resend flow
- No cross-organization transfer
- No custom email templates

## Acceptance Criteria

- Admin can create, list, and revoke invitations through the UI and API
- Non-admins receive the standard forbidden response on every invitation endpoint
- E2E test covers invite → list → revoke

## Invariants

- Only organization administrators can create or revoke invitations
- Invitation tokens never appear in list responses
- Revoked or expired invitations cannot be accepted
- A caller cannot see or act on another organization's invitations

## Open Questions

- (resolved with user) Default expiration is 7 days

## Risks

- Token leakage through list endpoint or logs
- Cross-tenant access through unscoped repository queries
