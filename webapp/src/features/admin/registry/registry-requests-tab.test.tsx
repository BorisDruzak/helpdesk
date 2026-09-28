import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import type { AdminRegistrationClaim } from "../api";
import { canApproveClaim, claimActionHint, RegistryRequestsTab } from "./registry-requests-tab";

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
  it("routes confirmed Endpoint replacement through the audited reason action", () => {
    const value = claim({status: "conflict", source: "endpoint_possession_proof", user_confirmed_at: "2026-09-28T19:00:00Z"});
    const approve = vi.fn();
    render(<RegistryRequestsTab claims={[value]}
      registry={{assets: [], people: [], locations: [], departments: [], active_bindings: [], bindings: []}}
      onApproveClaim={approve} onRejectClaim={() => {}} onSelect={() => {}} />);
    fireEvent.click(screen.getByRole("button", {name: /^С заменой$/}));
    expect(approve).toHaveBeenCalledWith(value, true, true);
  });
  it("shows Endpoint possession provenance and preserves owner review for a conflict", () => {
    const markup = renderToStaticMarkup(<RegistryRequestsTab
      claims={[claim({status: "conflict", source: "endpoint_possession_proof", conflict_reason: "ambiguous_active_relationships"})]}
      registry={{assets: [], people: [], locations: [], departments: [], active_bindings: [], bindings: []}}
      onApproveClaim={() => {}} onRejectClaim={() => {}} onSelect={() => {}}
    />);
    expect(markup).toContain("Код привязки Endpoint");
    expect(markup).toContain("есть действующая или неоднозначная привязка");
    expect(claimActionHint(claim({status: "conflict", source: "endpoint_possession_proof"}))).toContain("не передаёт владение");
    expect(canApproveClaim(claim({status: "conflict", source: "endpoint_possession_proof"}))).toBe(false);
  });
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
