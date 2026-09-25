// Fixed by the coordinator before dispatch. Workers implement against this; they do not edit it.

export type InvitationRole = "member" | "admin";

export type CreateInvitationInput = {
  email: string;          // RFC 5322, lower-cased before persistence
  role: InvitationRole;
};

export type PendingInvitation = {
  id: string;
  email: string;
  role: InvitationRole;
  createdAt: string;      // ISO 8601
  expiresAt: string | null;
};

export type ListPendingInvitationsResponse = {
  invitations: PendingInvitation[];
};

// Errors follow the existing ApiError convention: 400 validation, 403 not admin,
// 404 unknown organization or invitation (never 403, to avoid leaking existence).
