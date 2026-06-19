import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import type { RequestFormDefinition, RequestFormField } from "../types";
import {
  ALL_DYNAMIC_REQUEST_FIELD_TYPES,
  RequestFormFieldControl,
  buildDefaultFieldValues,
  collectVisiblePayload,
  fieldWithRequesterContextOptions,
  formatDynamicFieldReviewValue,
  mergeContextPrefillValues,
  missingRequiredFields,
  validateDynamicFormSchema,
  type DynamicFieldValue,
} from ".";

const baseOptions = [
  { value: "vpn", label: "VPN" },
  { value: "crm", label: "CRM" },
];

describe("requester dynamic form runtime", () => {
  it("renders every requester field type through one registry", () => {
    for (const type of ALL_DYNAMIC_REQUEST_FIELD_TYPES) {
      const field: RequestFormField = {
        key: `field_${type}`,
        label: `Поле ${type}`,
        type,
        options: optionTypes.has(type) ? baseOptions : [],
      };

      render(<FieldHarness field={field} />);
      expect(screen.getByLabelText(`Поле ${type}`)).toBeInTheDocument();
      expect(screen.queryByLabelText(`Поле формы обращения ${field.key}`)).not.toBeInTheDocument();
    }
  });

  it("keeps technical request field keys out of accessible field names", () => {
    render(
      <FieldHarness
        field={{
          key: "device_id",
          label: "Устройство",
          type: "device_picker",
          options: [{ value: "device-1", label: "Рабочая станция" }],
        }}
      />,
    );

    expect(screen.getByLabelText("Устройство")).toBeInTheDocument();
    expect(screen.queryByLabelText(/device_id/i)).not.toBeInTheDocument();
  });

  it("serializes text, number, radio, checkbox and multi-select values by field codec", () => {
    const form: RequestFormDefinition = {
      key: "access",
      title: "Доступ",
      fields: [
        { key: "summary", label: "Что нужно", type: "text" },
        { key: "seats", label: "Мест", type: "number" },
        { key: "scope", label: "Кому", type: "radio", options: baseOptions },
        { key: "urgent", label: "Срочно", type: "checkbox" },
        { key: "systems", label: "Системы", type: "multi_select", options: baseOptions },
      ],
    };

    const values = buildDefaultFieldValues(form, {
      summary: "Нужен доступ",
      seats: "2",
      scope: "vpn",
      urgent: true,
      systems: ["vpn", "crm"],
    });

    expect(collectVisiblePayload(form, values)).toEqual({
      summary: "Нужен доступ",
      seats: 2,
      scope: "vpn",
      urgent: true,
      systems: ["vpn", "crm"],
    });
  });

  it("omits hidden fields and does not block on hidden required values", () => {
    const form: RequestFormDefinition = {
      key: "conditional",
      title: "Условная форма",
      fields: [
        { key: "need_access", label: "Нужен доступ", type: "select", options: baseOptions },
        {
          key: "access_reason",
          label: "Причина",
          type: "textarea",
          required: true,
          visible_when: { field: "need_access", equals: "crm" },
        },
      ],
    };
    const values = buildDefaultFieldValues(form, { need_access: "vpn", access_reason: "" });

    expect(missingRequiredFields(form, values)).toEqual([]);
    expect(collectVisiblePayload(form, values)).toEqual({ need_access: "vpn" });
  });

  it("uses registry, device and service labels in review text instead of technical values", () => {
    const field = fieldWithRequesterContextOptions(
      { key: "device_id", label: "Устройство", type: "device_picker" },
      {
        departments: [],
        locations: [],
        devices: [{ device_id: "device-1", hostname: "laptop-42", asset_name: "Ноутбук бухгалтера" }],
        services: [{ service_code: "mail", title: "Почта", offerings: [] }],
      },
    );

    expect(field.options?.[0]).toEqual({ value: "device-1", label: "Ноутбук бухгалтера · laptop-42" });
    expect(formatDynamicFieldReviewValue(field, "device-1")).toBe("Ноутбук бухгалтера · laptop-42");
    expect(formatDynamicFieldReviewValue(field, "unknown-device")).toBe("Выбрано значение");
  });

  it("shows user picker only when the on-behalf policy allows it", () => {
    const field: RequestFormField = {
      key: "affected_person_id",
      label: "Сотрудник",
      type: "user_picker",
      options: [{ value: "person-1", label: "Иван Петров" }],
    };

    const { rerender } = render(<FieldHarness field={field} userPickerAllowed={false} />);
    expect(screen.queryByLabelText("Сотрудник")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/affected_person_id/i)).not.toBeInTheDocument();

    rerender(<FieldHarness field={field} userPickerAllowed />);
    expect(screen.getByLabelText("Сотрудник")).toBeInTheDocument();
    expect(screen.queryByLabelText(/affected_person_id/i)).not.toBeInTheDocument();
  });

  it("preserves manual edits when context prefill refreshes", () => {
    const form: RequestFormDefinition = {
      key: "prefill",
      title: "Prefill",
      fields: [
        { key: "department_id", label: "Подразделение", type: "department_picker" },
        { key: "summary", label: "Тема", type: "text" },
      ],
    };

    expect(
      mergeContextPrefillValues(
        form,
        { department_id: "manual-dept", summary: "old summary" },
        { department_id: "dept-old", summary: "old summary" },
        { department_id: "dept-new", summary: "new summary" },
      ),
    ).toEqual({
      department_id: "manual-dept",
      summary: "new summary",
    });
  });

  it("drops removed fields and initializes added fields when a schema version changes", () => {
    const nextForm: RequestFormDefinition = {
      key: "schema-v2",
      title: "Schema v2",
      fields: [
        { key: "summary", label: "Тема", type: "text" },
        { key: "systems", label: "Системы", type: "multi_select", options: baseOptions },
      ],
    };

    expect(
      mergeContextPrefillValues(
        nextForm,
        { summary: "manual", old_field: "stale" },
        { summary: "old prefill", old_field: "old" },
        { summary: "new prefill", systems: ["crm"] },
      ),
    ).toEqual({
      summary: "manual",
      systems: ["crm"],
    });
  });

  it("blocks unsupported requester publication and invalid conditions", () => {
    expect(
      validateDynamicFormSchema({
        key: "file-form",
        title: "File form",
        fields: [{ key: "attachment", label: "Файл", type: "file", required: true }],
      }).issues,
    ).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ code: "requester_file_upload_disabled", path: "fields.attachment" }),
      ]),
    );

    expect(
      validateDynamicFormSchema({
        key: "bad-condition",
        title: "Bad condition",
        fields: [
          { key: "details", label: "Детали", type: "textarea", visible_when: { field: "missing", equals: "yes" } },
        ],
      }).issues,
    ).toEqual(expect.arrayContaining([expect.objectContaining({ code: "invalid_visible_when_field" })]));

    expect(
      validateDynamicFormSchema({
        key: "unsupported",
        title: "Unsupported",
        fields: [{ key: "custom", label: "Custom", type: "matrix" as RequestFormField["type"] }],
      }).canPublish,
    ).toBe(false);
  });
});

const optionTypes = new Set<RequestFormField["type"]>([
  "select",
  "multi_select",
  "radio",
  "user_picker",
  "department_picker",
  "location_picker",
  "device_picker",
  "service_picker",
]);

function FieldHarness({
  field,
  userPickerAllowed = true,
}: {
  field: RequestFormField;
  userPickerAllowed?: boolean;
}) {
  const [value, setValue] = useState<DynamicFieldValue>(undefined);
  return (
    <RequestFormFieldControl
      field={field}
      onChange={setValue}
      userPickerAllowed={userPickerAllowed}
      value={value}
    />
  );
}
