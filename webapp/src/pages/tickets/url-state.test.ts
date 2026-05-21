import { describe, expect, it } from "vitest";

import { getTicketsWorkspaceUrlState, normalizeTicketsSmartViewParam } from "./url-state";

describe("tickets workspace URL state", () => {
  it("maps command center smart views to queue smart views", () => {
    expect(normalizeTicketsSmartViewParam("new_unassigned")).toBe("unassigned");
    expect(normalizeTicketsSmartViewParam("operator_action")).toBe("my_action");
    expect(normalizeTicketsSmartViewParam("requires_operator_action")).toBe("my_action");
    expect(normalizeTicketsSmartViewParam("unread_user_messages")).toBe("requester_reply");
    expect(normalizeTicketsSmartViewParam("pending_approval")).toBe("waiting_approval");
    expect(normalizeTicketsSmartViewParam("sla_risk")).toBe("sla_risk");
    expect(normalizeTicketsSmartViewParam("unknown_signal")).toBeNull();
  });

  it("opens the queue view when smart_view or search is present", () => {
    const state = getTicketsWorkspaceUrlState(new URLSearchParams("smart_view=new_unassigned&search=directum"));

    expect(state.smartView).toBe("unassigned");
    expect(state.search).toBe("directum");
    expect(state.shouldOpenQueue).toBe(true);
  });
});
