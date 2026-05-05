import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchSupportWorkspaceSummary } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("support queue API", () => {
  it("loads workspace summary from the lightweight support endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "success",
          data: {
            views: {
              needs_action: 12,
              sla_risk: 8,
              unassigned: 7,
              requester_replied: 15,
            },
            queues: [{ id: "servicedesk_l1", code: "servicedesk_l1", name: "ServiceDesk L1", count: 18 }],
            smart_view_counts: [{ value: "my_action", label: "Нужен ответ", count: 12 }],
            smart_view_options: [{ value: "my_action", label: "Нужен ответ" }],
          },
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const summary = await fetchSupportWorkspaceSummary(300);

    expect(fetchMock).toHaveBeenCalledWith("/api/web/support/workspace/summary?limit=300", {
      credentials: "same-origin",
    });
    expect(summary.views.needs_action).toBe(12);
    expect(summary.queues[0]).toEqual({
      id: "servicedesk_l1",
      code: "servicedesk_l1",
      name: "ServiceDesk L1",
      count: 18,
    });
  });
});
