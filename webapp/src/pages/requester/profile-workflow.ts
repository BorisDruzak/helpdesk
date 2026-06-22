import { profileFieldsFromSchema, type RequesterProfileValue, type RequesterProfileValues } from "../../features/requester/profile-runtime";
import type { RequesterProfileSchema, RequesterProfileSchemaField } from "../../features/requester/types";

export type ProfileMode = "read" | "edit" | "setup";

const SAFE_APP_PATH_RE = /^\/app(\/[A-Za-z0-9/_-]*)?(\?[A-Za-z0-9%._~=&-]*)?(#[A-Za-z0-9_-]*)?$/;

export function safeNextPath(search: string): string {
  const next = new URLSearchParams(search).get("next") || "/app/requester";
  return SAFE_APP_PATH_RE.test(next) ? next : "/app/requester";
}

export function fieldValue(values: RequesterProfileValues, field: RequesterProfileSchemaField): RequesterProfileValue {
  if (field.custom) {
    return values.custom_fields[field.key];
  }
  if (field.key === "full_name") return values.full_name;
  if (field.key === "department_id") return values.department_id;
  if (field.key === "location_id") return values.location_id;
  if (field.key === "phone") return values.phone;
  if (field.key === "internal_extension") return values.internal_extension;
  if (field.key === "position") return values.position;
  if (field.key === "workplace_label") return values.workplace_label;
  if (field.key === "preferred_contact_method") return values.preferred_contact_method;
  return undefined;
}

export function setFieldValue(
  values: RequesterProfileValues,
  field: RequesterProfileSchemaField,
  value: RequesterProfileValue,
): RequesterProfileValues {
  if (field.custom) {
    return {
      ...values,
      custom_fields: {
        ...values.custom_fields,
        [field.key]: value,
      },
    };
  }
  if (field.key in values && field.key !== "custom_fields") {
    return { ...values, [field.key]: value } as RequesterProfileValues;
  }
  return values;
}

export function fieldsWithRuntimeOptions(
  schema: RequesterProfileSchema | null | undefined,
  departments: Array<{ value: string; label: string }>,
  locations: Array<{ value: string; label: string }>,
): RequesterProfileSchemaField[] {
  return profileFieldsFromSchema(schema)
    .map((field) => {
      if (field.key === "department_id") {
        return { ...field, type: "select", options: field.options?.length ? field.options : departments };
      }
      if (field.key === "location_id") {
        return { ...field, type: "select", options: field.options?.length ? field.options : locations };
      }
      if (field.key === "preferred_contact_method" && !(field.options ?? []).length) {
        return {
          ...field,
          type: "select",
          options: [
            { value: "phone", label: "Телефон" },
            { value: "chat", label: "Чат в обращении" },
            { value: "email", label: "Электронная почта" },
          ],
        };
      }
      return field;
    })
    .sort((left, right) => (left.order ?? 1000) - (right.order ?? 1000));
}

export function sectionTitle(section: string): string {
  if (section === "identity") return "Основные данные";
  if (section === "contact") return "Связь";
  if (section === "work") return "Рабочий контекст";
  if (section === "custom") return "Дополнительные поля";
  return section;
}

export function groupedFields(fields: RequesterProfileSchemaField[]): Array<[string, RequesterProfileSchemaField[]]> {
  const groups = new Map<string, RequesterProfileSchemaField[]>();
  for (const field of fields) {
    const section = field.section || (field.custom ? "custom" : field.key === "phone" || field.key === "internal_extension" ? "contact" : field.key === "position" || field.key === "workplace_label" || field.key === "preferred_contact_method" ? "work" : "identity");
    groups.set(section, [...(groups.get(section) ?? []), field]);
  }
  return Array.from(groups.entries());
}
