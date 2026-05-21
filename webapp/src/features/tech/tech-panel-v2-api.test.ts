import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchTechPanelV2Snapshot, TechPanelApiError } from "./tech-panel-api";

describe("fetchTechPanelV2Snapshot", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads the typed v2 snapshot with same-origin credentials", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({
        generated_at: "2026-05-21T08:00:00Z",
        readiness: { status: "blocked", blockers: [], warnings: [], gates: [] },
        security: {},
        runtime: {},
        database: {},
        agents: {},
        operations: {},
        logs: {},
        alerts: [],
        release: {},
        smoke: { status: "unknown" },
        links: {
          observer: "/app/admin/observer",
          inventory: "/app/admin/inventory",
          agent_updates: "/app/admin/agent-updates",
          command_center: "/app/support",
          approval_center: "/app/support/approvals",
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const snapshot = await fetchTechPanelV2Snapshot();

    expect(fetchMock).toHaveBeenCalledWith("/api/web/admin/tech/snapshot", { credentials: "same-origin" });
    expect(snapshot.readiness.status).toBe("blocked");
  });

  it("throws a typed Russian API error on failed response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({ status: "error", error: "Снимок техпанели недоступен", error_code: "snapshot_failed" }),
      }),
    );

    await expect(fetchTechPanelV2Snapshot()).rejects.toMatchObject({
      name: "TechPanelApiError",
      message: "Снимок техпанели недоступен",
      status: 500,
      errorCode: "snapshot_failed",
    });
  });
});
