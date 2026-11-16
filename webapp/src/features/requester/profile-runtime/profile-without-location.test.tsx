import { describe, expect, it } from "vitest";

import { buildProfilePayload, buildProfileValues, missingProfileFields, profileFieldsFromSchema } from ".";

describe("department-only requester profile", () => {
  it("completes a new profile without a location", () => {
    const values = { ...buildProfileValues(), full_name: "Иван Петров", department_id: "dept-real", phone: "1234" };
    expect(missingProfileFields(undefined, values)).toEqual([]);
    expect(profileFieldsFromSchema(undefined).find(field => field.key === "location_id")).toBeUndefined();
    expect(profileFieldsFromSchema(undefined).find(field => field.key === "department_id")?.label).toBe("Отдел");
  });

  it("ignores historical office fields even when the old schema requires them", () => {
    const fields = [
      { key: "location_id", label: "Локация", type: "select", required: true, visible: true, editable: true },
      { key: "workplace_label", label: "Рабочее место", type: "text", required: true, visible: true, editable: true },
    ];
    const schema = { schema_key: "requester_profile", fields, required_fields: fields };
    const values = { ...buildProfileValues(), full_name: "Иван Петров", department_id: "dept-real", phone: "1234" };
    expect(profileFieldsFromSchema(schema)).toEqual([]);
    expect(missingProfileFields(schema, values)).toEqual([]);
    const payload = buildProfilePayload({ ...values, location_id: "old-location", workplace_label: "Кабинет 42" }, null, fields);
    expect(payload).not.toHaveProperty("location_id");
    expect(payload).not.toHaveProperty("workplace_label");
  });
});
