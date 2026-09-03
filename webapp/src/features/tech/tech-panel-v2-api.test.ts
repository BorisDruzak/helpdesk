import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchTechPanelV2Snapshot, locateTechQuery, TechPanelApiError } from "./tech-panel-api";

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

describe("locateTechQuery", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads quick locator results with encoded query and same-origin credentials", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({
        status: "ok",
        query: "T-910571",
        normalized_query: "T-910571",
        generated_at: "2026-05-21T08:00:00Z",
        matches: [
          {
            kind: "ticket",
            id: "ticket-1",
            title: "T-910571",
            severity: "warning",
            reason: "Найден тикет.",
            context: { ticket_id: "ticket-1" },
            signals: { ticket_open: true },
            links: [{ label: "Открыть тикет", href: "/app/tickets/ticket-1", kind: "ticket" }],
          },
        ],
        summary: { match_count: 1, highest_severity: "warning", primary_diagnosis: "Найден тикет." },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const payload = await locateTechQuery("T-910571");

    expect(fetchMock).toHaveBeenCalledWith("/api/web/admin/tech/locate?q=T-910571", { credentials: "same-origin" });
    expect(payload.matches[0].links[0].href).toBe("/app/tickets/ticket-1");
  });

  it("throws a typed Russian API error on locator failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({ status: "error", error: "Locator unavailable", error_code: "locator_failed" }),
      }),
    );

    await expect(locateTechQuery("device-1")).rejects.toMatchObject({
      name: "TechPanelApiError",
      message: "Locator unavailable",
      status: 500,
      errorCode: "locator_failed",
    });
  });
});
