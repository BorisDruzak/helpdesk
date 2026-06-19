import { useId, type ChangeEvent, type InputHTMLAttributes } from "react";

import type {
  RequesterProfile,
  RequesterProfileSchema,
  RequesterProfileSchemaField,
  RequesterProfileUpdatePayload,
} from "../types";
import { requesterSafeFieldLabel } from "../labels";

export const ALL_REQUESTER_PROFILE_FIELD_TYPES = [
  "text",
  "textarea",
  "select",
  "phone",
  "email",
  "url",
  "number",
  "date",
  "checkbox",
] as const;

const SUPPORTED_PROFILE_FIELD_TYPES = new Set<string>(ALL_REQUESTER_PROFILE_FIELD_TYPES);

const EDITABLE_BUILT_IN_FIELDS = new Set([
  "full_name",
  "department_id",
  "location_id",
  "phone",
  "internal_extension",
  "position",
  "workplace_label",
  "preferred_contact_method",
]);

const REQUIRED_PROFILE_FIELDS = [
  { key: "full_name", label: "ФИО" },
  { key: "department_id", label: "Подразделение" },
  { key: "location_id", label: "Локация" },
  { key: "phone", label: "Телефон или внутренний номер" },
] as const;

export type RequesterProfileValue = string | boolean | number | null | undefined;

export type RequesterProfileValues = {
  person_id?: string;
  full_name: string;
  department_id: string;
  location_id: string;
  phone: string;
  internal_extension: string;
  position: string;
  workplace_label: string;
  preferred_contact_method: string;
  custom_fields: Record<string, RequesterProfileValue>;
};

export type RequesterProfileValidationIssue = {
  code: string;
  message: string;
  path: string;
};

export type RequesterProfileSchemaValidation = {
  canPublish: boolean;
  issues: RequesterProfileValidationIssue[];
};

type NormalizedOption = {
  label: string;
  value: string;
};

export function normalizeProfileOption(option: string | { value: string; label: string }): NormalizedOption {
  if (typeof option === "string") {
    return { label: option, value: option };
  }
  return { label: option.label || option.value, value: option.value };
}

function trimText(value: unknown): string {
  return String(value ?? "").trim();
}

function isVisible(field: RequesterProfileSchemaField): boolean {
  return field.visible !== false;
}

function isEditable(field: RequesterProfileSchemaField): boolean {
  return field.editable !== false;
}

function isValuePresent(field: RequesterProfileSchemaField | { type?: string }, value: RequesterProfileValue): boolean {
  if (field.type === "checkbox") {
    return value === true;
  }
  return trimText(value).length > 0;
}

function builtInValue(values: RequesterProfileValues, key: string): RequesterProfileValue {
  if (key === "full_name") return values.full_name;
  if (key === "department_id") return values.department_id;
  if (key === "location_id") return values.location_id;
  if (key === "phone") return values.phone;
  if (key === "internal_extension") return values.internal_extension;
  if (key === "position") return values.position;
  if (key === "workplace_label") return values.workplace_label;
  if (key === "preferred_contact_method") return values.preferred_contact_method;
  return undefined;
}

export function buildProfileValues(profile?: RequesterProfile | null): RequesterProfileValues {
  return {
    person_id: profile?.person_id,
    full_name: profile?.full_name || profile?.display_name || "",
    department_id: profile?.department_id || "",
    location_id: profile?.location_id || "",
    phone: profile?.phone || "",
    internal_extension: profile?.internal_extension || "",
    position: profile?.position || "",
    workplace_label: profile?.workplace_label || "",
    preferred_contact_method: profile?.preferred_contact_method || "",
    custom_fields: { ...(profile?.custom_fields ?? {}) },
  };
}

export function profileFieldsFromSchema(schema?: RequesterProfileSchema | null): RequesterProfileSchemaField[] {
  const fields = schema?.fields ?? [];
  if (fields.length) {
    return fields.filter(isVisible);
  }
  return [
    { key: "full_name", label: "ФИО", type: "text", required: true, visible: true, system: true, editable: true },
    { key: "department_id", label: "Подразделение", type: "select", required: true, visible: true, system: true, editable: true },
    { key: "location_id", label: "Локация", type: "select", required: true, visible: true, system: true, editable: true },
    { key: "phone", label: "Телефон", type: "phone", required: true, visible: true, system: true, editable: true },
    { key: "internal_extension", label: "Внутренний номер", type: "phone", visible: true, editable: true },
    { key: "position", label: "Должность", type: "text", visible: true, editable: true },
    { key: "workplace_label", label: "Кабинет или рабочее место", type: "text", visible: true, editable: true },
    {
      key: "preferred_contact_method",
      label: "Предпочтительный способ связи",
      type: "select",
      visible: true,
      editable: true,
      options: [
        { value: "phone", label: "Телефон" },
        { value: "chat", label: "Чат в обращении" },
        { value: "email", label: "Email" },
      ],
    },
  ];
}

export function missingProfileFields(
  schema: RequesterProfileSchema | null | undefined,
  values: RequesterProfileValues,
): Array<{ key: string; label: string }> {
  const visibleFields = profileFieldsFromSchema(schema);
  const byKey = new Map(visibleFields.map((field) => [field.key, field]));
  const required = schema?.required_fields?.length
    ? schema.required_fields
    : [
        ...REQUIRED_PROFILE_FIELDS,
        ...visibleFields.filter((field) => field.required && field.custom).map((field) => ({
          key: field.key,
          label: field.label || field.key,
        })),
      ];
  return required.filter((item) => {
    if (item.key === "phone") {
      return !trimText(values.phone) && !trimText(values.internal_extension);
    }
    const field = byKey.get(item.key) ?? { key: item.key, label: item.label, type: "text" };
    if (field.custom) {
      return !isValuePresent(field, values.custom_fields[item.key]);
    }
    return !isValuePresent(field, builtInValue(values, item.key));
  });
}

export function buildProfilePayload(
  values: RequesterProfileValues,
  existingProfile: RequesterProfile | null | undefined,
  fields: RequesterProfileSchemaField[],
): RequesterProfileUpdatePayload {
  const visibleEditableFields = fields.filter((field) => isVisible(field) && isEditable(field));
  const visibleEditableBuiltIns = new Set(
    visibleEditableFields.filter((field) => !field.custom && EDITABLE_BUILT_IN_FIELDS.has(field.key)).map((field) => field.key),
  );
  const payload: RequesterProfileUpdatePayload = {
    person_id: existingProfile?.person_id ?? values.person_id,
    full_name: trimText(values.full_name),
    department_id: trimText(values.department_id),
    location_id: trimText(values.location_id),
    phone: trimText(values.phone),
  };

  if (visibleEditableBuiltIns.has("internal_extension") || trimText(values.internal_extension)) {
    payload.internal_extension = trimText(values.internal_extension);
  }
  for (const key of ["position", "workplace_label", "preferred_contact_method"] as const) {
    if (visibleEditableBuiltIns.has(key)) {
      payload[key] = trimText(values[key]);
    }
  }

  const customFields: NonNullable<RequesterProfileUpdatePayload["custom_fields"]> = {};
  for (const field of visibleEditableFields) {
    if (!field.custom) {
      continue;
    }
    const rawValue = values.custom_fields[field.key];
    customFields[field.key] = field.type === "checkbox" ? rawValue === true : trimText(rawValue);
  }
  if (Object.keys(customFields).length) {
    payload.custom_fields = customFields;
  }
  return payload;
}

export function validateRequesterProfileSchema(schema: RequesterProfileSchema): RequesterProfileSchemaValidation {
  const issues: RequesterProfileValidationIssue[] = [];
  const seen = new Set<string>();
  for (const field of schema.fields ?? []) {
    const path = `fields.${field.key || "<empty>"}`;
    if (!field.key || !/^[a-z][a-z0-9_]{1,63}$/.test(field.key)) {
      issues.push({ code: "invalid_profile_field_key", message: "Ключ поля должен быть безопасным латинским идентификатором.", path });
    }
    if (field.key && seen.has(field.key)) {
      issues.push({ code: "duplicate_profile_field_key", message: "Ключ поля повторяется.", path });
    }
    seen.add(field.key);
    if (!trimText(field.label)) {
      issues.push({ code: "empty_profile_field_label", message: "Название поля обязательно.", path });
    }
    if (!SUPPORTED_PROFILE_FIELD_TYPES.has(field.type)) {
      issues.push({ code: "unsupported_profile_field_type", message: "Тип поля не поддерживается профилем заявителя.", path });
    }
    if (field.required && field.visible === false) {
      issues.push({ code: "required_hidden_field", message: "Обязательное поле нельзя скрыть.", path });
    }
    if (field.type === "select" && !(field.options ?? []).length) {
      issues.push({ code: "empty_profile_select_options", message: "Для списка нужны варианты выбора.", path });
    }
    if (field.system && field.can_hide === false && field.visible === false) {
      issues.push({ code: "protected_profile_field_hidden", message: "Защищенное системное поле нельзя скрыть.", path });
    }
  }
  return { canPublish: issues.length === 0, issues };
}

export function RequesterProfileFieldControl({
  error,
  field,
  inputRef,
  managedText = "Значение управляется организацией",
  onChange,
  readOnly,
  value,
}: {
  error?: string | null;
  field: RequesterProfileSchemaField;
  inputRef?: (element: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement | null) => void;
  managedText?: string;
  onChange: (value: RequesterProfileValue) => void;
  readOnly?: boolean;
  value: RequesterProfileValue;
}) {
  const generatedId = useId();
  const safeLabel = requesterSafeFieldLabel(field.label, "Поле профиля");
  const label = `${safeLabel}${field.required ? " *" : ""}`;
  const helpId = `${generatedId}-help`;
  const errorId = `${generatedId}-error`;
  const describedBy = [field.help_text ? helpId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined;
  const helpText = field.help_text ? <span className="mt-1 block text-xs font-normal text-slate-500" id={helpId}>{field.help_text}</span> : null;
  const errorText = error ? (
    <span className="mt-1 block text-xs font-semibold text-rose-700" id={errorId}>
      {error}
    </span>
  ) : null;
  const disabled = readOnly || !isEditable(field);
  const commonInputProps: Pick<InputHTMLAttributes<HTMLInputElement>, "aria-describedby" | "aria-invalid" | "aria-label" | "disabled"> = {
    "aria-describedby": describedBy,
    "aria-invalid": error ? true : undefined,
    "aria-label": safeLabel,
    disabled,
  };

  if (disabled && !isEditable(field)) {
    return (
      <div className="rounded-panel border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
        <p className="font-semibold text-slate-700">{label}</p>
        <p className="mt-1 break-words text-slate-950">{formatProfileValue(field, value)}</p>
        <p className="mt-1 text-xs text-slate-500">{managedText}</p>
        {helpText}
        {errorText}
      </div>
    );
  }

  if (field.type === "textarea") {
    return (
      <label className="block text-sm font-semibold text-slate-700">
        {label}
        <textarea
          aria-describedby={describedBy}
          aria-invalid={error ? true : undefined}
          aria-label={safeLabel}
          className="mt-1 min-h-24 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          ref={(element) => inputRef?.(element)}
          value={String(value ?? "")}
        />
        {helpText}
        {errorText}
      </label>
    );
  }

  if (field.type === "select") {
    return (
      <label className="block text-sm font-semibold text-slate-700">
        {label}
        <select
          aria-describedby={describedBy}
          aria-invalid={error ? true : undefined}
          aria-label={safeLabel}
          className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
          disabled={disabled}
          onChange={(event: ChangeEvent<HTMLSelectElement>) => onChange(event.target.value)}
          ref={(element) => inputRef?.(element)}
          value={String(value ?? "")}
        >
          <option value="">Выберите...</option>
          {(field.options ?? []).map((option) => {
            const normalized = normalizeProfileOption(option);
            return (
              <option key={normalized.value} value={normalized.value}>
                {normalized.label}
              </option>
            );
          })}
        </select>
        {helpText}
        {errorText}
      </label>
    );
  }

  if (field.type === "checkbox") {
    return (
      <label className="flex items-start gap-2 rounded-panel border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700">
        <input
          {...commonInputProps}
          checked={value === true}
          className="mt-1"
          onChange={(event) => onChange(event.target.checked)}
          ref={(element) => inputRef?.(element)}
          type="checkbox"
        />
        <span>
          {label}
          {helpText}
          {errorText}
        </span>
      </label>
    );
  }

  const inputType =
    field.type === "number"
      ? "number"
      : field.type === "date"
        ? "date"
        : field.type === "email"
          ? "email"
          : field.type === "url"
            ? "url"
            : field.type === "phone"
              ? "tel"
              : "text";
  return (
    <label className="block text-sm font-semibold text-slate-700">
      {label}
      <input
        {...commonInputProps}
        className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
        onChange={(event) => onChange(event.target.value)}
        ref={(element) => inputRef?.(element)}
        type={inputType}
        value={String(value ?? "")}
      />
      {helpText}
      {errorText}
    </label>
  );
}

export function formatProfileValue(field: RequesterProfileSchemaField, value: RequesterProfileValue): string {
  if (field.type === "checkbox") {
    return value === true ? "Да" : "Нет";
  }
  if (field.type === "select") {
    const selected = (field.options ?? []).map(normalizeProfileOption).find((option) => option.value === value);
    return selected?.label || trimText(value) || "Не указано";
  }
  return trimText(value) || "Не указано";
}
