import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchOperationDetail } from "./operation-detail-api";

describe("fetchOperationDetail", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads operation detail from the read-only operation endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({
        status: "success",
        operation: {
          operation_id: "op-1",
          device_id: "device-1",
          ticket_id: "ticket-1",
          kind: "tool_call",
          tool_name: "inventory.collect",
          status: "failed",
          trace_id: "trace-1",
          error_message: "failed",
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const payload = await fetchOperationDetail("op-1");

    expect(fetchMock).toHaveBeenCalledWith("/api/web/admin/operations/op-1", { credentials: "same-origin" });
    expect(payload.operation.operation_id).toBe("op-1");
    expect(payload.links.device_operations).toBe("/app/admin/device?device=device-1");
    expect(payload.links.ticket).toBe("/app/tickets/ticket-1");
    expect(payload.links.observer).toBe("/app/admin/observer?trace_id=trace-1");
  });
});
