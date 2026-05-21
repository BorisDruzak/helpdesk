import { describe, expect, it, vi, afterEach } from "vitest";

import { buildApprovalConsentCenterUrl, fetchApprovalConsentCenter } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("approval consent center api", () => {
  it("builds typed query params", () => {
    expect(
      buildApprovalConsentCenterUrl({
        scope: "team",
        kind: "pending_consent",
        status: "pending",
        risk: "high",
        limit: 25,
        offset: 10,
      }),
    ).toBe("/api/web/support/approvals?scope=team&kind=pending_consent&status=pending&risk=high&limit=25&offset=10");
  });

  it("unwraps success response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            status: "success",
            data: {
              generated_at: "2026-05-21T10:00:00+00:00",
              scope: "team",
              filters: { limit: 50, offset: 0 },
              summary: {
                total_count: 0,
                pending_count: 0,
                overdue_count: 0,
                high_risk_count: 0,
                waiting_user_count: 0,
                waiting_approver_count: 0,
                blocking_sla_count: 0,
                ticket_approvals_count: 0,
                change_approvals_count: 0,
                risky_tool_consents_count: 0,
                remote_assist_consents_count: 0,
                closure_approvals_count: 0,
                policy_overrides_count: 0,
              },
              sections: [],
              items: [],
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(fetchApprovalConsentCenter({ scope: "team" })).resolves.toMatchObject({
      scope: "team",
      items: [],
    });
  });
});
