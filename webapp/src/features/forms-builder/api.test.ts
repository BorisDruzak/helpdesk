import { afterEach, describe, expect, it, vi } from "vitest";

import { validateAdminFormsCatalog } from "./api";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("forms builder api", () => {
  it("normalizes an empty validation response into a safe report", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          status: "success",
          data: {},
        })
      )
    );

    const result = await validateAdminFormsCatalog({
      title: "Каталог заявок",
      description: "",
      forms: [],
    });

    expect(result.summary.errors_count).toBe(0);
    expect(result.summary.warnings_count).toBe(0);
    expect(result.summary.can_publish).toBe(true);
    expect(result.errors).toEqual([]);
    expect(result.warnings).toEqual([]);
  });
});
