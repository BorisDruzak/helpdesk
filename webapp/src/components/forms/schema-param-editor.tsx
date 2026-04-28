import { useEffect, useMemo, useRef, useState } from "react";

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
  properties?: SchemaParamField[];
  items?: SchemaParamField;
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function primitiveValueText(value: unknown) {
  return value == null ? "" : String(value);
}

function coercePrimitiveValue(rawValue: string | boolean, type: string) {
  if (type === "boolean") {
    return Boolean(rawValue);
  }
  if (type === "integer") {
    return Number.parseInt(String(rawValue || "0"), 10);
  }
  if (type === "number") {
    return Number.parseFloat(String(rawValue || "0"));
  }
  return String(rawValue);
}

function normalizeFieldValue(field: SchemaParamField, value: unknown): unknown {
  if (field.type === "object") {
    const record = isRecord(value) ? value : {};
    if (!field.properties?.length) {
      return record;
    }
    return {
      ...record,
      ...buildInitialValues(field.properties, record),
    };
  }

  if (field.type === "array") {
    if (Array.isArray(value)) {
      return value.map((item) => (field.items ? normalizeFieldValue(field.items, item) : item));
    }
    return [];
  }

  return value;
}

function hasNestedDefaults(field: SchemaParamField): boolean {
  if (field.default !== undefined) {
    return true;
  }
  if (field.type === "object") {
    return Boolean(field.properties?.some(hasNestedDefaults));
  }
  return false;
}

function buildInitialValues(fields: SchemaParamField[], value: Record<string, unknown>) {
  const nextValues: Record<string, unknown> = {};
  for (const field of fields) {
    if (Object.prototype.hasOwnProperty.call(value, field.name)) {
      nextValues[field.name] = normalizeFieldValue(field, value[field.name]);
      continue;
    }
    if (field.default !== undefined) {
      nextValues[field.name] = normalizeFieldValue(field, field.default);
      continue;
    }
    if (field.type === "object" && hasNestedDefaults(field)) {
      nextValues[field.name] = normalizeFieldValue(field, {});
      continue;
    }
    if (field.type === "array" && Array.isArray(field.default)) {
      nextValues[field.name] = normalizeFieldValue(field, field.default);
    }
  }
  return nextValues;
}

function emptyArrayItem(field: SchemaParamField): unknown {
  const item = field.items;
  if (!item) {
    return "";
  }
  if (item.default !== undefined) {
    return normalizeFieldValue(item, item.default);
  }
  if (item.type === "object") {
    return normalizeFieldValue(item, {});
  }
  if (item.type === "array") {
    return [];
  }
  if (item.type === "boolean") {
    return false;
  }
  if (item.type === "integer" || item.type === "number") {
    return 0;
  }
  return "";
}

function nextUnknownObjectKey(value: Record<string, unknown>) {
  for (let index = 1; index < 200; index += 1) {
    const key = `field_${index}`;
    if (!Object.prototype.hasOwnProperty.call(value, key)) {
      return key;
    }
  }
  return `field_${Date.now()}`;
}

export function SchemaParamEditor({ className, fields, onChange, value }: SchemaParamEditorProps) {
  const initialValues = useMemo(() => buildInitialValues(fields, value), [fields, value]);
  const [params, setParams] = useState<Record<string, unknown>>(initialValues);
  const paramsRef = useRef<Record<string, unknown>>(initialValues);

  useEffect(() => {
    paramsRef.current = initialValues;
    setParams(initialValues);
  }, [initialValues]);

  function commitParams(nextParams: Record<string, unknown>) {
    paramsRef.current = nextParams;
    setParams(nextParams);
    onChange(nextParams);
  }

  function updateTopLevel(name: string, nextValue: unknown) {
    commitParams({
      ...paramsRef.current,
      [name]: nextValue,
    });
  }

  function renderPrimitiveField(
    field: SchemaParamField,
    currentValue: unknown,
    onValueChange: (nextValue: unknown) => void,
    labelOverride?: string,
  ) {
    const label = labelOverride ?? fieldLabel(field);
    const valueText = primitiveValueText(currentValue ?? field.default);

    if (field.type === "boolean") {
      return (
        <label className="flex items-start gap-3 rounded-[1rem] border border-border bg-white px-4 py-3 text-sm" key={label}>
          <input
            aria-label={label}
            checked={Boolean(currentValue ?? field.default)}
            className="mt-1 h-4 w-4"
            onChange={(event) => onValueChange(event.target.checked)}
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
        <label className="space-y-2 text-sm font-medium text-slate-800" key={label}>
          <span>
            {label}
            {field.required ? " *" : ""}
          </span>
          <Select
            aria-label={label}
            onChange={(event) => onValueChange(coercePrimitiveValue(event.target.value, field.type))}
            value={valueText}
          >
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

    return (
      <label className="space-y-2 text-sm font-medium text-slate-800" key={label}>
        <span>
          {label}
          {field.required ? " *" : ""}
        </span>
        <Input
          aria-label={label}
          onChange={(event) => onValueChange(coercePrimitiveValue(event.target.value, field.type))}
          type={field.type === "integer" || field.type === "number" ? "number" : "text"}
          value={valueText}
        />
        {field.description ? <span className="block text-xs leading-5 text-slate-500">{field.description}</span> : null}
      </label>
    );
  }

  function renderUnknownObjectEditor(field: SchemaParamField, currentObject: Record<string, unknown>) {
    const label = fieldLabel(field);
    const entries = Object.entries(currentObject);

    return (
      <div className="space-y-3">
        {entries.length ? (
          entries.map(([key, rawValue]) => (
            <div className="grid gap-2 rounded-lg border border-slate-200 bg-white p-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_auto]" key={key}>
              <Input
                aria-label={`${label} key ${key}`}
                onChange={(event) => {
                  const nextKey = event.target.value.trim();
                  if (!nextKey || nextKey === key) {
                    return;
                  }
                  const { [key]: removed, ...rest } = currentObject;
                  updateTopLevel(field.name, { ...rest, [nextKey]: removed });
                }}
                value={key}
              />
              <Input
                aria-label={`${label} value ${key}`}
                onChange={(event) => updateTopLevel(field.name, { ...currentObject, [key]: event.target.value })}
                value={primitiveValueText(rawValue)}
              />
              <button
                className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-rose-600 hover:bg-rose-50"
                onClick={() => {
                  const { [key]: _removed, ...rest } = currentObject;
                  updateTopLevel(field.name, rest);
                }}
                type="button"
              >
                Удалить
              </button>
            </div>
          ))
        ) : (
          <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-500">
            Полей пока нет. Добавьте ключ, если параметр принимает свободный объект.
          </p>
        )}
        <button
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-50"
          onClick={() => updateTopLevel(field.name, { ...currentObject, [nextUnknownObjectKey(currentObject)]: "" })}
          type="button"
        >
          Добавить поле
        </button>
      </div>
    );
  }

  function renderObjectField(field: SchemaParamField) {
    const label = fieldLabel(field);
    const currentObject = isRecord(params[field.name]) ? params[field.name] as Record<string, unknown> : {};

    return (
      <section className="rounded-[1rem] border border-slate-200 bg-slate-50/80 p-4" key={field.name}>
        <div className="mb-3">
          <p className="text-sm font-semibold text-slate-900">
            {label}
            {field.required ? " *" : ""}
          </p>
          {field.description ? <p className="mt-1 text-xs leading-5 text-slate-500">{field.description}</p> : null}
        </div>
        {field.properties?.length ? (
          <div className="grid gap-3">
            {field.properties.map((child) =>
              renderParamField(
                child,
                currentObject[child.name],
                (nextValue) => updateTopLevel(field.name, { ...currentObject, [child.name]: nextValue }),
              ),
            )}
          </div>
        ) : (
          renderUnknownObjectEditor(field, currentObject)
        )}
      </section>
    );
  }

  function renderArrayItemControl(
    field: SchemaParamField,
    itemSchema: SchemaParamField,
    itemValue: unknown,
    itemIndex: number,
    onItemChange: (nextValue: unknown) => void,
  ) {
    const itemLabel = `${fieldLabel(itemSchema)} ${itemIndex + 1}`;
    if (itemSchema.type === "object") {
      const currentObject = isRecord(itemValue) ? itemValue : {};
      return (
        <div className="grid gap-3">
          {itemSchema.properties?.length ? (
            itemSchema.properties.map((child) =>
              renderParamField(
                child,
                currentObject[child.name],
                (nextValue) => onItemChange({ ...currentObject, [child.name]: nextValue }),
              ),
            )
          ) : (
            <Input
              aria-label={itemLabel}
              onChange={(event) => onItemChange(event.target.value)}
              value={primitiveValueText(itemValue)}
            />
          )}
        </div>
      );
    }

    return renderPrimitiveField(itemSchema, itemValue, onItemChange, itemLabel);
  }

  function renderArrayField(
    field: SchemaParamField,
    currentValue: unknown = params[field.name],
    onArrayChange: (nextValue: unknown[]) => void = (nextValue) => updateTopLevel(field.name, nextValue),
  ) {
    const label = fieldLabel(field);
    const currentArray = Array.isArray(currentValue) ? currentValue : [];
    const itemSchema = field.items ?? { name: "item", label: "Item", type: "string" };
    const itemLabel = fieldLabel(itemSchema);

    return (
      <section className="rounded-[1rem] border border-slate-200 bg-slate-50/80 p-4" key={field.name}>
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-slate-900">
              {label}
              {field.required ? " *" : ""}
            </p>
            {field.description ? <p className="mt-1 text-xs leading-5 text-slate-500">{field.description}</p> : null}
          </div>
          <button
            className="shrink-0 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-50"
            onClick={() => onArrayChange([...currentArray, emptyArrayItem(field)])}
            type="button"
          >
            Добавить {itemLabel}
          </button>
        </div>
        <div className="grid gap-3">
          {currentArray.length ? (
            currentArray.map((item, index) => (
              <div className="rounded-lg border border-slate-200 bg-white p-3" key={index}>
                <div className="flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    {renderArrayItemControl(field, itemSchema, item, index, (nextValue) => {
                      const nextArray = [...currentArray];
                      nextArray[index] = nextValue;
                      onArrayChange(nextArray);
                    })}
                  </div>
                  <button
                    aria-label={`Удалить ${itemLabel} ${index + 1}`}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-rose-600 hover:bg-rose-50"
                    onClick={() => onArrayChange(currentArray.filter((_, itemIndex) => itemIndex !== index))}
                    type="button"
                  >
                    Удалить
                  </button>
                </div>
              </div>
            ))
          ) : (
            <p className="rounded-lg border border-dashed border-slate-200 bg-white px-3 py-3 text-xs text-slate-500">
              Строк пока нет. Добавьте значение, если параметр принимает список.
            </p>
          )}
        </div>
      </section>
    );
  }

  function renderParamField(
    field: SchemaParamField,
    currentValue: unknown,
    onValueChange: (nextValue: unknown) => void,
  ) {
    if (field.type === "object") {
      const currentObject = isRecord(currentValue) ? currentValue : {};
      const label = fieldLabel(field);
      return (
        <section className="rounded-lg border border-slate-200 bg-white p-3" key={field.name}>
          <p className="mb-3 text-sm font-semibold text-slate-900">
            {label}
            {field.required ? " *" : ""}
          </p>
          {field.properties?.length ? (
            <div className="grid gap-3">
              {field.properties.map((child) =>
                renderParamField(
                  child,
                  currentObject[child.name],
                  (nextValue) => onValueChange({ ...currentObject, [child.name]: nextValue }),
                ),
              )}
            </div>
          ) : (
            <Input
              aria-label={label}
              onChange={(event) => onValueChange(event.target.value)}
              value={primitiveValueText(currentValue)}
            />
          )}
        </section>
      );
    }

    if (field.type === "array") {
      return renderArrayField(field, currentValue, onValueChange);
    }

    return renderPrimitiveField(field, currentValue, onValueChange);
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
        if (field.type === "object") {
          return renderObjectField(field);
        }
        if (field.type === "array") {
          return renderArrayField(field);
        }
        return renderPrimitiveField(field, params[field.name], (nextValue) => updateTopLevel(field.name, nextValue), fieldLabel(field));
      })}
    </div>
  );
}
