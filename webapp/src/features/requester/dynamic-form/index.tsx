import type { ChangeEvent } from "react";

import type {
  RequestFormDefinition,
  RequestFormField,
  RequestFormFieldOption,
  RequesterDevice,
  RequesterRegistryOption,
  ServiceCatalogCurrent,
} from "../types";
import { requesterDeviceLabel, requesterSafeFieldLabel } from "../labels";

export type DynamicFieldValue = string | number | boolean | string[] | null | undefined;
export type DynamicFormValues = Record<string, DynamicFieldValue>;

export type DynamicFormValidationIssue = {
  code: string;
  message: string;
  path: string;
  severity: "error" | "warning";
};

export type DynamicFormValidationResult = {
  canPublish: boolean;
  issues: DynamicFormValidationIssue[];
};

export const ALL_DYNAMIC_REQUEST_FIELD_TYPES = [
  "text",
  "textarea",
  "select",
  "multi_select",
  "radio",
  "checkbox",
  "number",
  "date",
  "datetime",
  "file",
  "user_picker",
  "department_picker",
  "location_picker",
  "device_picker",
  "service_picker",
  "url",
  "phone",
  "email",
] as const satisfies readonly RequestFormField["type"][];

export type PublishableDynamicRequestFieldType = Exclude<RequestFormField["type"], "file">;

export const PUBLISHABLE_DYNAMIC_REQUEST_FIELD_TYPES = ALL_DYNAMIC_REQUEST_FIELD_TYPES.filter(
  (type): type is PublishableDynamicRequestFieldType => type !== "file",
);

const DYNAMIC_REQUEST_FIELD_TYPE_SET = new Set<string>(ALL_DYNAMIC_REQUEST_FIELD_TYPES);
const PICKER_TYPES = new Set<RequestFormField["type"]>([
  "user_picker",
  "department_picker",
  "location_picker",
  "device_picker",
  "service_picker",
]);
const OPTION_TYPES = new Set<RequestFormField["type"]>([
  "select",
  "multi_select",
  "radio",
  "user_picker",
  "department_picker",
  "location_picker",
  "device_picker",
  "service_picker",
]);

export function isDynamicFieldVisible(field: RequestFormField, values: DynamicFormValues): boolean {
  const rule = field.visible_when as
    | {
        field?: string;
        equals?: string | boolean | number | null;
        in?: Array<string | boolean | number | null>;
        values?: Array<string | boolean | number | null>;
      }
    | null
    | undefined;
  if (!rule?.field) {
    return true;
  }
  const currentValue = values[rule.field];
  if (Object.prototype.hasOwnProperty.call(rule, "equals") && rule.equals !== undefined && rule.equals !== null) {
    return valuesMatch(currentValue, rule.equals);
  }
  const allowed = Array.isArray(rule.in) ? rule.in : Array.isArray(rule.values) ? rule.values : [];
  if (allowed.length) {
    return allowed.some((item) => valuesMatch(currentValue, item));
  }
  return true;
}

export function buildDefaultFieldValues(
  form: Pick<RequestFormDefinition, "fields"> | null | undefined,
  prefill: DynamicFormValues = {},
): DynamicFormValues {
  const nextValues: DynamicFormValues = {};
  for (const field of form?.fields ?? []) {
    const prefilled = prefillValueForField(field, prefill);
    nextValues[field.key] = normalizeDynamicFieldValue(field, prefilled ?? defaultValueForField(field));
  }
  return nextValues;
}

export function mergeContextPrefillValues(
  form: Pick<RequestFormDefinition, "fields"> | null | undefined,
  current: DynamicFormValues,
  previousPrefill: DynamicFormValues,
  nextPrefill: DynamicFormValues,
): DynamicFormValues {
  const defaults = buildDefaultFieldValues(form, nextPrefill);
  const next: DynamicFormValues = {};
  for (const field of form?.fields ?? []) {
    const currentValue = normalizeDynamicFieldValue(field, current[field.key]);
    const previousValue = normalizeDynamicFieldValue(field, previousPrefill[field.key]);
    const defaultValue = normalizeDynamicFieldValue(field, defaults[field.key] ?? defaultValueForField(field));
    const isEmpty = isEmptyDynamicValue(field, currentValue);
    const stillPrevious =
      current[field.key] !== undefined && dynamicValuesEqual(field, currentValue, previousValue);
    next[field.key] = isEmpty || stillPrevious ? defaultValue : currentValue;
  }
  return next;
}

export function fieldWithRequesterContextOptions(
  field: RequestFormField,
  context: {
    departments?: RequesterRegistryOption[];
    locations?: RequesterRegistryOption[];
    devices?: Array<Partial<RequesterDevice> & { device_id: string }>;
    services?: ServiceCatalogCurrent["services"];
  },
): RequestFormField {
  if (field.type === "department_picker") {
    return { ...field, options: uniqueOptions([...(field.options ?? []), ...(context.departments ?? [])]) };
  }
  if (field.type === "location_picker") {
    return { ...field, options: uniqueOptions([...(field.options ?? []), ...(context.locations ?? [])]) };
  }
  if (field.type === "device_picker") {
    return {
      ...field,
      options: uniqueOptions([
        ...(field.options ?? []),
        ...(context.devices ?? []).map((device) => ({
          value: device.device_id,
          label: dynamicDeviceLabel(device),
        })),
      ]),
    };
  }
  if (field.type === "service_picker") {
    return {
      ...field,
      options: uniqueOptions([
        ...(field.options ?? []),
        ...(context.services ?? []).map((service) => ({
          value: service.service_code,
          label: service.title || service.service_code,
        })),
      ]),
    };
  }
  return field;
}

export function collectVisiblePayload(
  form: Pick<RequestFormDefinition, "fields"> | null | undefined,
  values: DynamicFormValues,
): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  for (const field of form?.fields ?? []) {
    if (isDynamicFieldVisible(field, values)) {
      payload[field.key] = normalizeDynamicFieldValue(field, values[field.key]);
    }
  }
  return payload;
}

export function missingRequiredFields(
  form: Pick<RequestFormDefinition, "fields"> | null | undefined,
  values: DynamicFormValues,
): string[] {
  return missingRequiredFieldDetails(form, values).map((field) => field.label);
}

export function missingRequiredFieldDetails(
  form: Pick<RequestFormDefinition, "fields"> | null | undefined,
  values: DynamicFormValues,
): Array<{ key: string; label: string }> {
  return (form?.fields ?? [])
    .filter((field) => field.required && isDynamicFieldVisible(field, values))
    .filter((field) => isEmptyDynamicValue(field, normalizeDynamicFieldValue(field, values[field.key])))
    .map((field) => ({ key: field.key, label: requesterSafeFieldLabel(field.label, "Поле обращения") }));
}

export function formatDynamicFieldReviewValue(field: RequestFormField, value: DynamicFieldValue): string {
  const normalized = normalizeDynamicFieldValue(field, value);
  if (field.type === "checkbox") {
    return normalized === true ? "Да" : "Нет";
  }
  if (Array.isArray(normalized)) {
    const labels = normalized.map((item) => optionLabelForValue(field, item)).filter(Boolean);
    return labels.length ? labels.join(", ") : "Не выбрано";
  }
  if (normalized === null || normalized === undefined || normalized === "") {
    return "Не указано";
  }
  const label = optionLabelForValue(field, String(normalized));
  if (label) {
    return label;
  }
  return PICKER_TYPES.has(field.type) ? "Выбрано значение" : String(normalized);
}

export function validateDynamicFormSchema(
  form: Pick<RequestFormDefinition, "key" | "title" | "fields">,
): DynamicFormValidationResult {
  const issues: DynamicFormValidationIssue[] = [];
  const seenKeys = new Set<string>();
  const fieldKeys = new Set((form.fields ?? []).map((field) => field.key).filter(Boolean));

  if (!String(form.key ?? "").trim()) {
    issues.push(issue("missing_form_key", "Ключ формы обязателен.", "key"));
  }
  if (!String(form.title ?? "").trim()) {
    issues.push(issue("missing_form_title", "Название формы обязательно.", "title"));
  }

  (form.fields ?? []).forEach((field, index) => {
    const path = field.key ? `fields.${field.key}` : `fields.${index}`;
    const key = String(field.key ?? "").trim();
    const fieldType = String(field.type ?? "");
    if (!key) {
      issues.push(issue("missing_field_key", "Ключ поля обязателен.", `${path}.key`));
    } else if (seenKeys.has(key)) {
      issues.push(issue("duplicate_field_key", "Ключ поля должен быть уникальным.", path));
    }
    seenKeys.add(key);
    if (!String(field.label ?? "").trim()) {
      issues.push(issue("missing_field_label", "Название поля обязательно.", `${path}.label`));
    }
    if (!DYNAMIC_REQUEST_FIELD_TYPE_SET.has(fieldType)) {
      issues.push(issue("unsupported_field_type", `Тип поля ${fieldType || "unknown"} не поддерживается.`, path));
    }
    if (field.type === "file") {
      issues.push(
        issue(
          "requester_file_upload_disabled",
          "Поле файла нельзя публиковать, пока загрузка вложений не включена в динамической форме.",
          path,
        ),
      );
    }
    if (field.visible_when?.field) {
      const dependencyKey = String(field.visible_when.field).trim();
      if (!fieldKeys.has(dependencyKey)) {
        issues.push(issue("invalid_visible_when_field", "Условие ссылается на отсутствующее поле.", `${path}.visible_when.field`));
      }
      if (dependencyKey === key) {
        issues.push(issue("invalid_visible_when_self_reference", "Поле не может зависеть от самого себя.", `${path}.visible_when.field`));
      }
    }
    if (
      (field.type === "select" || field.type === "multi_select" || field.type === "radio") &&
      !uniqueOptions(field.options ?? []).length
    ) {
      issues.push(issue("missing_field_options", "Для поля нужны варианты выбора.", `${path}.options`));
    }
  });

  return {
    canPublish: !issues.some((item) => item.severity === "error"),
    issues,
  };
}

export function normalizeDynamicFieldValue(field: RequestFormField, value: DynamicFieldValue): DynamicFieldValue {
  if (field.type === "checkbox") {
    if (typeof value === "string") {
      return value === "true" || value === "1" || value.toLowerCase() === "yes";
    }
    return value === true;
  }
  if (field.type === "multi_select") {
    if (Array.isArray(value)) {
      return value.map((item) => String(item ?? "").trim()).filter(Boolean);
    }
    const text = String(value ?? "").trim();
    return text ? [text] : [];
  }
  if (field.type === "number") {
    if (value === null || value === undefined || value === "") {
      return null;
    }
    const next = typeof value === "number" ? value : Number(String(value).replace(",", "."));
    return Number.isFinite(next) ? next : null;
  }
  if (field.type === "file") {
    return null;
  }
  if (typeof value === "boolean" || Array.isArray(value)) {
    return "";
  }
  const text = String(value ?? "").trim();
  return text;
}

export function RequestFormFieldControl({
  error,
  field,
  inputRef,
  onChange,
  userPickerAllowed = true,
  value,
}: {
  error?: string | null;
  field: RequestFormField;
  inputRef?: (element: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement | null) => void;
  onChange: (value: DynamicFieldValue) => void;
  userPickerAllowed?: boolean;
  value: DynamicFieldValue;
}) {
  if (field.type === "user_picker" && !userPickerAllowed) {
    return null;
  }

  const safeLabel = requesterSafeFieldLabel(field.label, "Поле обращения");
  const label = `${safeLabel}${field.required ? " *" : ""}`;
  const normalizedValue = normalizeDynamicFieldValue(field, value);
  const helpText = field.help_text ? <p className="mt-1 text-xs font-normal text-slate-500">{field.help_text}</p> : null;
  const errorText = error ? <p className="mt-1 text-xs font-semibold text-rose-700">{error}</p> : null;
  const invalidProps = {
    "aria-invalid": error ? true : undefined,
  };

  if (field.type === "textarea") {
    return (
      <label className="block text-sm font-semibold text-slate-700">
        {label}
        <textarea
          {...invalidProps}
          aria-label={safeLabel}
          className="mt-1 min-h-24 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
          onChange={(event) => onChange(event.currentTarget.value)}
          placeholder={field.placeholder ?? ""}
          ref={(element) => inputRef?.(element)}
          value={String(normalizedValue ?? "")}
        />
        {helpText}
        {errorText}
      </label>
    );
  }

  if (field.type === "radio") {
    return (
      <fieldset {...invalidProps} aria-label={safeLabel} className="rounded-panel border border-slate-200 px-3 py-2">
        <legend className="text-sm font-semibold text-slate-700">{label}</legend>
        <div className="mt-2 grid gap-2">
          {(field.options ?? []).map((option, index) => (
            <label className="flex items-center gap-2 text-sm text-slate-700" key={option.value}>
              <input
                checked={String(normalizedValue ?? "") === option.value}
                name={`request-form-${field.key}`}
                onChange={() => onChange(option.value)}
                ref={index === 0 ? (element) => inputRef?.(element) : undefined}
                type="radio"
                value={option.value}
              />
              <span>{option.label || option.value}</span>
            </label>
          ))}
        </div>
        {helpText}
        {errorText}
      </fieldset>
    );
  }

  if (field.type === "multi_select") {
    const currentValues = new Set(Array.isArray(normalizedValue) ? normalizedValue : []);
    return (
      <fieldset {...invalidProps} aria-label={safeLabel} className="rounded-panel border border-slate-200 px-3 py-2">
        <legend className="text-sm font-semibold text-slate-700">{label}</legend>
        <div className="mt-2 grid gap-2">
          {(field.options ?? []).map((option, index) => (
            <label className="flex items-center gap-2 text-sm text-slate-700" key={option.value}>
              <input
                checked={currentValues.has(option.value)}
                onChange={(event) => {
                  const nextValues = new Set(currentValues);
                  if (event.currentTarget.checked) {
                    nextValues.add(option.value);
                  } else {
                    nextValues.delete(option.value);
                  }
                  onChange(Array.from(nextValues));
                }}
                ref={index === 0 ? (element) => inputRef?.(element) : undefined}
                type="checkbox"
              />
              <span>{option.label || option.value}</span>
            </label>
          ))}
        </div>
        {helpText}
        {errorText}
      </fieldset>
    );
  }

  if (isSelectLike(field)) {
    return (
      <label className="block text-sm font-semibold text-slate-700">
        {label}
        <select
          {...invalidProps}
          aria-label={safeLabel}
          className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
          onChange={(event) => onChange(event.currentTarget.value)}
          ref={(element) => inputRef?.(element)}
          value={String(normalizedValue ?? "")}
        >
          <option value="">Выберите...</option>
          {(field.options ?? []).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label || option.value}
            </option>
          ))}
        </select>
        {helpText}
        {errorText}
      </label>
    );
  }

  if (field.type === "checkbox") {
    return (
      <label className="flex items-center gap-2 rounded-panel border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700">
        <input
          {...invalidProps}
          aria-label={safeLabel}
          checked={normalizedValue === true}
          onChange={(event) => onChange(event.currentTarget.checked)}
          ref={(element) => inputRef?.(element)}
          type="checkbox"
        />
        <span>{label}</span>
        {helpText}
        {errorText}
      </label>
    );
  }

  if (field.type === "file") {
    return (
      <label className="block text-sm font-semibold text-slate-700">
        {label}
        <input
          {...invalidProps}
          aria-label={safeLabel}
          className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
          disabled
          onChange={() => onChange(null)}
          ref={(element) => inputRef?.(element)}
          type="file"
        />
        <p className="mt-1 text-xs font-normal text-amber-700">
          Вложения добавляются после создания обращения. Поле файла нельзя публиковать до включения загрузки в динамической форме.
        </p>
        {errorText}
      </label>
    );
  }

  return (
    <label className="block text-sm font-semibold text-slate-700">
      {label}
      <input
        {...invalidProps}
        aria-label={safeLabel}
        className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
        onChange={(event) => onChange(inputValueForField(field, event))}
        placeholder={field.placeholder ?? ""}
        ref={(element) => inputRef?.(element)}
        type={inputTypeForField(field)}
        value={String(normalizedValue ?? "")}
      />
      {helpText}
      {errorText}
    </label>
  );
}

function inputValueForField(field: RequestFormField, event: ChangeEvent<HTMLInputElement>): DynamicFieldValue {
  if (field.type === "number") {
    return event.currentTarget.value === "" ? null : Number(event.currentTarget.value);
  }
  return event.currentTarget.value;
}

function inputTypeForField(field: RequestFormField): string {
  if (field.type === "number") {
    return "number";
  }
  if (field.type === "date") {
    return "date";
  }
  if (field.type === "datetime") {
    return "datetime-local";
  }
  if (field.type === "email") {
    return "email";
  }
  if (field.type === "url") {
    return "url";
  }
  if (field.type === "phone") {
    return "tel";
  }
  return "text";
}

function isSelectLike(field: RequestFormField): boolean {
  return (
    field.type === "select" ||
    field.type === "department_picker" ||
    field.type === "location_picker" ||
    field.type === "device_picker" ||
    field.type === "service_picker" ||
    field.type === "user_picker"
  );
}

function defaultValueForField(field: RequestFormField): DynamicFieldValue {
  if (field.type === "checkbox") {
    return false;
  }
  if (field.type === "multi_select") {
    return [];
  }
  if (field.type === "number" || field.type === "file") {
    return null;
  }
  return "";
}

function prefillKeysForField(field: RequestFormField): string[] {
  const key = field.key.toLowerCase();
  const candidates = [field.key];
  if (field.type === "department_picker" || key.includes("department")) {
    candidates.push(key.endsWith("_id") ? "department_id" : "department", "department_id", "department_code");
  }
  if (field.type === "location_picker" || key.includes("location") || key === "building" || key === "room") {
    candidates.push(key.endsWith("_id") ? "location_id" : "location", "location_id", "building", "room");
  }
  if (field.type === "device_picker" || key.includes("device") || key === "hostname") {
    candidates.push(key.endsWith("_id") ? "device_id" : "device", "device_id", "device_hostname", "hostname");
  }
  if (field.type === "service_picker" || key.includes("service") || key.includes("offering")) {
    candidates.push(key.includes("offering") ? "offering_full_code" : "service_code", "service", "offering");
  }
  if (key.includes("phone")) {
    candidates.push("phone");
  }
  if (key.includes("email")) {
    candidates.push("email");
  }
  if (key.includes("name") || key.includes("requester")) {
    candidates.push("requester_name", "full_name");
  }
  return Array.from(new Set(candidates));
}

function prefillValueForField(field: RequestFormField, prefill: DynamicFormValues): DynamicFieldValue {
  for (const key of prefillKeysForField(field)) {
    const value = prefill[key];
    if (!isEmptyDynamicValue(field, value)) {
      return value;
    }
  }
  return undefined;
}

function isEmptyDynamicValue(field: RequestFormField, value: DynamicFieldValue): boolean {
  if (field.type === "checkbox") {
    return value !== true;
  }
  if (field.type === "multi_select") {
    return !Array.isArray(value) || value.length === 0;
  }
  if (field.type === "number") {
    return value === null || value === undefined || value === "";
  }
  return !String(value ?? "").trim();
}

function dynamicValuesEqual(field: RequestFormField, left: DynamicFieldValue, right: DynamicFieldValue): boolean {
  const normalizedLeft = normalizeDynamicFieldValue(field, left);
  const normalizedRight = normalizeDynamicFieldValue(field, right);
  if (Array.isArray(normalizedLeft) || Array.isArray(normalizedRight)) {
    return JSON.stringify(normalizedLeft ?? []) === JSON.stringify(normalizedRight ?? []);
  }
  return String(normalizedLeft ?? "") === String(normalizedRight ?? "");
}

function valuesMatch(currentValue: DynamicFieldValue, expected: string | boolean | number | null): boolean {
  if (Array.isArray(currentValue)) {
    return currentValue.some((item) => String(item ?? "").trim() === String(expected ?? "").trim());
  }
  return String(currentValue ?? "").trim() === String(expected ?? "").trim();
}

function uniqueOptions(options: RequesterRegistryOption[]): RequestFormFieldOption[] {
  const seen = new Set<string>();
  const result: RequestFormFieldOption[] = [];
  for (const option of options) {
    const value = String(option.value || "").trim();
    if (!value || seen.has(value)) {
      continue;
    }
    seen.add(value);
    result.push({ value, label: option.label || value });
  }
  return result;
}

function dynamicDeviceLabel(device: Partial<RequesterDevice> & { device_id: string }): string {
  return requesterDeviceLabel(device, "Устройство");
}

function optionLabelForValue(field: RequestFormField, value: string): string | null {
  const option = (field.options ?? []).find((item) => item.value === value);
  return option?.label || null;
}

function issue(code: string, message: string, path: string): DynamicFormValidationIssue {
  return { code, message, path, severity: "error" };
}
