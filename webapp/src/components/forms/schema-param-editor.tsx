import { useEffect, useMemo, useState } from "react";

import { Input } from "../ui/input";
import { Select } from "../ui/select";
import { cn } from "../../shared/ui/cn";

export type SchemaParamOption = {
  value: string;
  label: string;
};

export type SchemaParamField = {
  name: string;
  label?: string | null;
  description?: string | null;
  type: string;
  required?: boolean;
  default?: unknown;
  options?: SchemaParamOption[];
};

type SchemaParamEditorProps = {
  className?: string;
  fields: SchemaParamField[];
  onChange: (params: Record<string, unknown>) => void;
  value: Record<string, unknown>;
};

function fieldLabel(field: SchemaParamField) {
  return field.label || field.name;
}

function stringifyValue(value: unknown, type: string) {
  if (value == null) {
    return "";
  }
  if (type === "object" || type === "array") {
    return JSON.stringify(value, null, 2);
  }
  return String(value);
}

function coerceValue(rawValue: string | boolean, type: string) {
  if (type === "boolean") {
    return Boolean(rawValue);
  }
  if (type === "integer") {
    return Number.parseInt(String(rawValue || "0"), 10);
  }
  if (type === "number") {
    return Number.parseFloat(String(rawValue || "0"));
  }
  if (type === "object" || type === "array") {
    return JSON.parse(String(rawValue || (type === "array" ? "[]" : "{}"))) as unknown;
  }
  return String(rawValue);
}

function buildInitialValues(fields: SchemaParamField[], value: Record<string, unknown>) {
  const nextValues: Record<string, unknown> = {};
  for (const field of fields) {
    if (Object.prototype.hasOwnProperty.call(value, field.name)) {
      nextValues[field.name] = value[field.name];
      continue;
    }
    if (field.default !== undefined) {
      nextValues[field.name] = field.default;
    }
  }
  return nextValues;
}

export function SchemaParamEditor({ className, fields, onChange, value }: SchemaParamEditorProps) {
  const initialValues = useMemo(() => buildInitialValues(fields, value), [fields, value]);
  const [params, setParams] = useState<Record<string, unknown>>(initialValues);
  const [jsonDrafts, setJsonDrafts] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      fields
        .filter((field) => field.type === "object" || field.type === "array")
        .map((field) => [field.name, stringifyValue(initialValues[field.name] ?? field.default, field.type)]),
    ),
  );
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    setParams(initialValues);
    setJsonDrafts(
      Object.fromEntries(
        fields
          .filter((field) => field.type === "object" || field.type === "array")
          .map((field) => [field.name, stringifyValue(initialValues[field.name] ?? field.default, field.type)]),
      ),
    );
    setFieldErrors({});
  }, [fields, initialValues]);

  function updateField(field: SchemaParamField, rawValue: string | boolean) {
    try {
      const nextValue = coerceValue(rawValue, field.type);
      const nextParams = {
        ...params,
        [field.name]: nextValue,
      };
      setParams(nextParams);
      setFieldErrors((current) => {
        const { [field.name]: _removed, ...rest } = current;
        return rest;
      });
      onChange(nextParams);
    } catch {
      setFieldErrors((current) => ({
        ...current,
        [field.name]: `${fieldLabel(field)}: некорректный JSON.`,
      }));
    }
  }

  if (!fields.length) {
    return (
      <div className={cn("rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-4 text-sm text-slate-500", className)}>
        Для команды не объявлены настраиваемые параметры.
      </div>
    );
  }

  return (
    <div className={cn("grid gap-4", className)}>
      {fields.map((field) => {
        const label = fieldLabel(field);
        const valueText = stringifyValue(params[field.name] ?? field.default, field.type);
        const error = fieldErrors[field.name];

        if (field.type === "boolean") {
          return (
            <label
              className="flex items-start gap-3 rounded-[1rem] border border-border bg-white px-4 py-3 text-sm"
              key={field.name}
            >
              <input
                aria-label={label}
                checked={Boolean(params[field.name] ?? field.default)}
                className="mt-1 h-4 w-4"
                onChange={(event) => updateField(field, event.target.checked)}
                type="checkbox"
              />
              <span>
                <span className="font-medium text-slate-900">
                  {label}
                  {field.required ? " *" : ""}
                </span>
                {field.description ? <span className="mt-1 block text-xs leading-5 text-slate-500">{field.description}</span> : null}
              </span>
            </label>
          );
        }

        if (field.options?.length) {
          return (
            <label className="space-y-2 text-sm font-medium text-slate-800" key={field.name}>
              <span>
                {label}
                {field.required ? " *" : ""}
              </span>
              <Select aria-label={label} onChange={(event) => updateField(field, event.target.value)} value={valueText}>
                <option value="">Не выбрано</option>
                {field.options.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
              {field.description ? <span className="block text-xs leading-5 text-slate-500">{field.description}</span> : null}
            </label>
          );
        }

        if (field.type === "object" || field.type === "array") {
          return (
            <label className="space-y-2 text-sm font-medium text-slate-800" key={field.name}>
              <span>
                {label} JSON
                {field.required ? " *" : ""}
              </span>
              <textarea
                aria-label={`${label} JSON`}
                className={cn(
                  "field-base min-h-[112px] w-full resize-y px-4 py-3 font-mono text-xs",
                  error ? "border-rose-300 bg-rose-50" : "",
                )}
                onChange={(event) => {
                  const nextText = event.target.value;
                  setJsonDrafts((current) => ({ ...current, [field.name]: nextText }));
                  updateField(field, nextText);
                }}
                value={jsonDrafts[field.name] ?? valueText}
              />
              <span className="block text-xs leading-5 text-slate-500">
                Advanced field: schema does not expose a safer structured editor for this value yet.
              </span>
              {error ? <span className="block text-xs text-rose-600">{error}</span> : null}
            </label>
          );
        }

        return (
          <label className="space-y-2 text-sm font-medium text-slate-800" key={field.name}>
            <span>
              {label}
              {field.required ? " *" : ""}
            </span>
            <Input
              aria-label={label}
              onChange={(event) => updateField(field, event.target.value)}
              type={field.type === "integer" || field.type === "number" ? "number" : "text"}
              value={valueText}
            />
            {field.description ? <span className="block text-xs leading-5 text-slate-500">{field.description}</span> : null}
          </label>
        );
      })}
    </div>
  );
}
