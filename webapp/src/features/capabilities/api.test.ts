import { afterEach, describe, expect, it, vi } from "vitest";

import { getToolPresentation, listAdminCapabilities, resetToolPresentation, saveToolPresentation } from "./api";

function okResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("capabilities API", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("passes device_id when loading a device-scoped capability catalog", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      okResponse({
        status: "ok",
        capabilities: [],
      }),
    );

    await listAdminCapabilities("device-1");

    const url = String(fetchMock.mock.calls[0]?.[0]);
    expect(url).toContain("/api/web/admin/capabilities?");
    expect(url).toContain("device_id=device-1");
  });

  it("passes device_id to presentation override endpoints while keeping overrides global", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      Promise.resolve(okResponse({
        status: "ok",
        tool_id: "system.collect",
        module_default_schema: {},
        override_schema: null,
        effective_schema: {},
        source: "module_default",
      })),
    );

    await getToolPresentation("system.collect", null, "device-1");
    await saveToolPresentation("system.collect", { version: "1.0", blocks: [{ type: "raw_json" }] }, null, "device-1");
    await resetToolPresentation("system.collect", null, "device-1");

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("device_id=device-1");
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain("device_id=device-1");
    expect(String(fetchMock.mock.calls[2]?.[0])).toContain("device_id=device-1");
    expect(fetchMock.mock.calls[1]?.[1]?.body).toBe(
      JSON.stringify({
        presentation_schema: { version: "1.0", blocks: [{ type: "raw_json" }] },
        tool_version: null,
        enabled: true,
      }),
    );
  });
});
