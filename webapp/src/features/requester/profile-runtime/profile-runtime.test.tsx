import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import type { RequesterProfile, RequesterProfileSchema } from "../types";
import {
  ALL_REQUESTER_PROFILE_FIELD_TYPES,
  RequesterProfileFieldControl,
  buildProfilePayload,
  buildProfileValues,
  missingProfileFields,
  validateRequesterProfileSchema,
  type RequesterProfileValue,
} from ".";

const schema: RequesterProfileSchema = {
  schema_key: "requester_profile",
  fields: [
    { key: "full_name", label: "ФИО", type: "text", required: true, visible: true, system: true, editable: true },
    { key: "department_id", label: "Подразделение", type: "select", required: true, visible: true, system: true, editable: true },
    { key: "location_id", label: "Локация", type: "select", required: true, visible: true, system: true, editable: true },
    { key: "phone", label: "Телефон", type: "phone", required: true, visible: true, system: true, editable: true },
    { key: "internal_extension", label: "Внутренний номер", type: "phone", visible: true, editable: true },
    { key: "cost_center", label: "Центр затрат", type: "text", required: true, visible: true, custom: true, editable: true },
  ],
  custom_fields: [
    { key: "cost_center", label: "Центр затрат", type: "text", required: true, visible: true, custom: true, editable: true },
  ],
  required_fields: [
    { key: "full_name", label: "ФИО" },
    { key: "department_id", label: "Подразделение" },
    { key: "location_id", label: "Локация" },
    { key: "phone", label: "Телефон или внутренний номер" },
    { key: "cost_center", label: "Центр затрат" },
  ],
};

describe("requester profile runtime", () => {
  it("renders every requester profile field type through one registry", () => {
    for (const type of ALL_REQUESTER_PROFILE_FIELD_TYPES) {
      render(
        <FieldHarness
          field={{
            key: `field_${type}`,
            label: `Поле ${type}`,
            type,
            options: type === "select" ? [{ value: "one", label: "Один" }] : [],
            visible: true,
            editable: true,
          }}
        />,
      );
      expect(screen.getByLabelText(`Поле ${type}`)).toBeInTheDocument();
      expect(screen.queryByLabelText(`Поле профиля field_${type}`)).not.toBeInTheDocument();
    }
  });

  it("keeps technical profile keys out of accessible field names", () => {
    render(
      <FieldHarness
        field={{
          key: "department_id",
          label: "Подразделение",
          type: "select",
          options: [{ value: "dept-it", label: "ИТ" }],
          visible: true,
          editable: true,
        }}
      />,
    );

    expect(screen.getByLabelText("Подразделение")).toBeInTheDocument();
    expect(screen.queryByLabelText(/department_id/i)).not.toBeInTheDocument();
  });

  it("treats internal extension as satisfying the phone completion requirement", () => {
    const values = buildProfileValues({
      person_id: "person-1",
      full_name: "Иван Петров",
      department_id: "dept-it",
      location_id: "loc-ekb",
      phone: "",
      internal_extension: "4567",
      custom_fields: { cost_center: "CC-10" },
    });

    expect(missingProfileFields(schema, values)).toEqual([]);
  });

  it("builds payload only from visible editable fields and preserves hidden custom values", () => {
    const profile: RequesterProfile = {
      person_id: "person-1",
      full_name: "Иван Петров",
      phone: "+7",
      internal_extension: "4567",
      department_id: "dept-it",
      location_id: "loc-ekb",
      custom_fields: {
        cost_center: "OLD",
        hidden_custom: "DO_NOT_ERASE",
      },
    };
    const values = buildProfileValues(profile);
    values.phone = "";
    values.internal_extension = "8899";
    values.custom_fields.cost_center = "CC-20";
    values.custom_fields.hidden_custom = "";

    expect(buildProfilePayload(values, profile, schema.fields)).toEqual({
      person_id: "person-1",
      full_name: "Иван Петров",
      department_id: "dept-it",
      location_id: "loc-ekb",
      phone: "",
      internal_extension: "8899",
      custom_fields: {
        cost_center: "CC-20",
      },
    });
  });

  it("rejects unsupported profile schema publication inputs before save", () => {
    expect(
      validateRequesterProfileSchema({
        ...schema,
        fields: [
          ...schema.fields,
          { key: "bad", label: "Матрица", type: "matrix", visible: true, custom: true, editable: true },
        ],
      }).issues,
    ).toEqual(expect.arrayContaining([expect.objectContaining({ code: "unsupported_profile_field_type" })]));

    expect(
      validateRequesterProfileSchema({
        ...schema,
        fields: [
          { key: "full_name", label: "ФИО", type: "text", required: true, visible: false, system: true },
        ],
      }).issues,
    ).toEqual(expect.arrayContaining([expect.objectContaining({ code: "required_hidden_field" })]));
  });
});

function FieldHarness({ field }: { field: RequesterProfileSchema["fields"][number] }) {
  const [value, setValue] = useState<RequesterProfileValue>(field.type === "checkbox" ? false : "");
  return <RequesterProfileFieldControl field={field} onChange={setValue} value={value} />;
}
