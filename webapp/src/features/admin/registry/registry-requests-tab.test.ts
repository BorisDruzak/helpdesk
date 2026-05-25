import { describe, expect, it } from "vitest";

import type { AdminRegistrationClaim } from "../api";
import { canApproveClaim, claimActionHint } from "./registry-requests-tab";

function claim(overrides: Partial<AdminRegistrationClaim>): AdminRegistrationClaim {
  return {
    claim_id: "claim-1",
    device_id: "device-1",
    asset_id: null,
    person_id: "person-1",
    person_name: "User",
    status: "pending_user_confirmation",
    claim_type: "agent_reported",
    relationship_type: "primary_user",
    confidence: null,
    submitted_at: null,
    user_confirmed_at: null,
    conflict_reason: null,
    profile_snapshot: {},
    ...overrides,
  };
}

describe("registry request actions", () => {
  it("blocks ordinary approval until user confirmation is present", () => {
    expect(canApproveClaim(claim({ status: "pending_user_confirmation" }))).toBe(false);
    expect(claimActionHint(claim({ status: "pending_user_confirmation" }))).toContain("Ожидается подтверждение пользователя");
  });

  it("allows ordinary approval after user confirmation", () => {
    expect(canApproveClaim(claim({ status: "user_confirmed", user_confirmed_at: "2026-05-25T10:00:00Z" }))).toBe(true);
    expect(canApproveClaim(claim({ status: "conflict", user_confirmed_at: "2026-05-25T10:00:00Z" }))).toBe(true);
  });

  it("marks terminal claims as already finished", () => {
    expect(canApproveClaim(claim({ status: "approved" }))).toBe(false);
    expect(claimActionHint(claim({ status: "approved" }))).toContain("уже завершена");
  });
});
