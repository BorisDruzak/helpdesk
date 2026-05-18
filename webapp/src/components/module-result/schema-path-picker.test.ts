import { describe, expect, it } from "vitest";

import { extractSchemaPaths, generateMockSampleFromSchema } from "./schema-path-picker";

describe("schema path picker helpers", () => {
  it("extracts scalar and array object paths from output_schema", () => {
    const paths = extractSchemaPaths({
      type: "object",
      properties: {
        sections: {
          type: "object",
          properties: {
            network: {
              type: "object",
              properties: {
                hostname: { type: "string", title: "Hostname" },
                primary_ip: { type: "string" },
                interfaces: {
                  type: "array",
                  items: {
                    type: "object",
                    properties: {
                      name: { type: "string" },
                      ipv4: { type: "array", items: { type: "string" } },
                    },
                  },
                },
              },
            },
          },
        },
      },
    });

    expect(paths.map((item) => item.path)).toEqual(
      expect.arrayContaining([
        "sections.network.hostname",
        "sections.network.primary_ip",
        "sections.network.interfaces[].name",
        "sections.network.interfaces[].ipv4",
      ]),
    );
    expect(paths.find((item) => item.path === "sections.network.hostname")).toMatchObject({
      label: "Hostname",
      type: "string",
      kind: "scalar",
    });
    expect(paths.find((item) => item.path === "sections.network.interfaces[].name")).toMatchObject({
      kind: "scalar",
      type: "string",
    });
  });

  it("handles invalid schemas and recursive shapes defensively", () => {
    const recursive: Record<string, unknown> = { type: "object", properties: {} };
    recursive.properties = { self: recursive };

    expect(extractSchemaPaths(null)).toEqual([]);
    expect(extractSchemaPaths(recursive).length).toBeGreaterThan(0);
    expect(extractSchemaPaths(recursive).length).toBeLessThanOrEqual(8);
  });

  it("generates a preview sample from output_schema", () => {
    const sample = generateMockSampleFromSchema({
      type: "object",
      properties: {
        status: { type: "string" },
        cpu: { type: "number" },
        ok: { type: "boolean" },
        rows: { type: "array", items: { type: "object", properties: { name: { type: "string" } } } },
      },
    }) as Record<string, unknown>;

    expect(sample.status).toBe("example");
    expect(sample.cpu).toBe(42);
    expect(sample.ok).toBe(true);
    expect(sample.rows).toEqual([{ name: "example" }]);
  });
});
