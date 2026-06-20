import { describe, expect, it } from "vitest";

import {
  REQUESTER_BASELINE_FIXTURE_IDS,
  REQUESTER_BASELINE_FIXTURES,
  REQUESTER_FORBIDDEN_VISIBLE_TERMS,
  REQUESTER_PROFILE_FIELD_TYPES,
  REQUESTER_REQUEST_FIELD_TYPES,
  assertNoRequesterForbiddenTerms,
} from "./baseline-contract";

const EXPECTED_FIXTURE_IDS = [
  "complete_profile_primary_device",
  "incomplete_profile_no_device",
  "complete_profile_no_device",
  "pending_device_link",
  "multiple_devices_with_offline_primary",
  "waiting_request_and_consent",
  "close_rate_reopen",
  "on_behalf_allowed",
  "on_behalf_forbidden",
  "archived_user",
] as const;

describe("requester baseline contract", () => {
  it("defines every Phase A requester fixture state", () => {
    expect(REQUESTER_BASELINE_FIXTURE_IDS).toEqual(EXPECTED_FIXTURE_IDS);
    expect(Object.keys(REQUESTER_BASELINE_FIXTURES)).toEqual(EXPECTED_FIXTURE_IDS);
  });

  it("keeps fixture visible text free of requester-forbidden technical terms", () => {
    for (const fixture of Object.values(REQUESTER_BASELINE_FIXTURES)) {
      expect(assertNoRequesterForbiddenTerms(fixture.visibleText)).toEqual([]);
    }
  });

  it("records supported dynamic request and profile field matrices", () => {
    expect(REQUESTER_REQUEST_FIELD_TYPES).toEqual([
      "text",
      "textarea",
      "select",
      "multi_select",
      "radio",
      "checkbox",
      "number",
      "date",
      "datetime",
      "user_picker",
      "department_picker",
      "location_picker",
      "device_picker",
      "service_picker",
      "url",
      "phone",
      "email",
    ]);
    expect(REQUESTER_PROFILE_FIELD_TYPES).toEqual([
      "text",
      "textarea",
      "select",
      "phone",
      "email",
      "url",
      "number",
      "date",
      "checkbox",
    ]);
  });

  it("captures authorization and business invariants outside the old layout", () => {
    expect(REQUESTER_BASELINE_FIXTURES.archived_user.expected.archivedBlocked).toBe(true);
    expect(REQUESTER_BASELINE_FIXTURES.on_behalf_allowed.expected.onBehalf).toBe("allowed");
    expect(REQUESTER_BASELINE_FIXTURES.on_behalf_forbidden.expected.onBehalf).toBe("forbidden");
    expect(REQUESTER_BASELINE_FIXTURES.incomplete_profile_no_device.expected.canCreateNormalRequest).toBe(false);
    expect(REQUESTER_BASELINE_FIXTURES.complete_profile_primary_device.expected.canCreateNormalRequest).toBe(true);
    expect(REQUESTER_BASELINE_FIXTURES.waiting_request_and_consent.expected.pendingConsentCount).toBe(1);
    expect(REQUESTER_BASELINE_FIXTURES.close_rate_reopen.expected.lifecycleActions).toEqual([
      "close",
      "rate",
      "reopen",
    ]);
  });

  it("maintains an explicit forbidden visible term list for localization guards", () => {
    expect(REQUESTER_FORBIDDEN_VISIBLE_TERMS.map((item) => item.term)).toEqual([
      "Requester",
      "user",
      "ticket",
      "pairing",
      "binding",
      "claim",
      "session",
      "registry person",
      "verified",
      "not verified",
      "profile not linked",
      "*_id",
      "raw UUID",
      "backend enum",
      "policy key",
      "trace id",
      "operation id",
      "consent id",
      "artifact id",
    ]);
  });
});
