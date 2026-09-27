import { describe, expect, it } from "vitest";

import { normalizeCapabilityParamSchema } from "./params-schema";

describe("capability parameter schema", () => {
  it.each([
    { type: "object", additionalProperties: false, maxProperties: 0 },
    { type: "object", properties: {}, title: "No parameters" },
  ])("does not turn empty object schema metadata into input fields", (schema) => {
    expect(normalizeCapabilityParamSchema(schema, {})).toEqual([]);
  });

  it("preserves legacy flat parameter maps including a parameter named type", () => {
    const fields = normalizeCapabilityParamSchema({ type: { type: "string", title: "Kind" } }, {});
    expect(fields).toHaveLength(1);
    expect(fields[0]).toMatchObject({ name: "type", label: "Kind", type: "string" });
  });
});
