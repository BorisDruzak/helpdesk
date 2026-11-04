import { describe, expect, it } from "vitest";

import { buildProfilePayload, buildProfileValues, missingProfileFields, profileFieldsFromSchema } from ".";

describe("department-only requester profile", () => {
  it("completes a new profile without a location", () => {
    const values = { ...buildProfileValues(), full_name: "Иван Петров", department_id: "dept-real", phone: "1234" };
    expect(missingProfileFields(undefined, values)).toEqual([]);
    expect(profileFieldsFromSchema(undefined).find(field => field.key === "location_id")).toBeUndefined();
    expect(profileFieldsFromSchema(undefined).find(field => field.key === "department_id")?.label).toBe("Отдел");
  });

  it("does not submit a hidden historical location", () => {
    const values = { ...buildProfileValues(), full_name: "Иван Петров", department_id: "dept-real", phone: "1234", location_id: "old-location" };
    const payload = buildProfilePayload(values, null, profileFieldsFromSchema(undefined));
    expect(payload).not.toHaveProperty("location_id");
  });
});
