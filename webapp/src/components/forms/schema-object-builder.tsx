import { Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Select } from "../ui/select";

type SchemaFieldType = "string" | "number" | "integer" | "boolean" | "object" | "array";

type SchemaObjectBuilderProps = {
  label: string;
  onChange: (schema: Record<string, unknown>) => void;
  value: unknown;
};

type SchemaFieldRow = {
  id: string;
  name: string;
  type: SchemaFieldType;
  description: string;
  defaultValue: string;
  enumText: string;
  required: boolean;
};

const FIELD_TYPES: SchemaFieldType[] = ["string", "number", "integer", "boolean", "object", "array"];

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function normalizeFieldType(value: unknown): SchemaFieldType {
  return FIELD_TYPES.includes(value as SchemaFieldType) ? (value as SchemaFieldType) : "string";
}

function createRow(index: number, seed?: Partial<SchemaFieldRow>): SchemaFieldRow {
  return {
    id: `schema-field-${index}`,
    name: seed?.name ?? "",
    type: seed?.type ?? "string",
    description: seed?.description ?? "",
    defaultValue: seed?.defaultValue ?? "",
    enumText: seed?.enumText ?? "",
    required: seed?.required ?? false,
  };
}

function readSchemaRows(value: unknown): SchemaFieldRow[] {
  if (!isRecord(value) || !isRecord(value.properties)) {
    return [];
  }
  const required = Array.isArray(value.required) ? value.required.map((item) => String(item)) : [];
  return Object.entries(value.properties).map(([name, rawProperty], index) => {
    const property = isRecord(rawProperty) ? rawProperty : {};
    const enumText = Array.isArray(property.enum) ? property.enum.map((item) => String(item ?? "")).join("\n") : "";
    return createRow(index, {
      name,
      type: normalizeFieldType(property.type),
      description: typeof property.description === "string" ? property.description : "",
      defaultValue: property.default == null ? "" : String(property.default),
      enumText,
      required: required.includes(name),
    });
  });
}

function coerceSchemaValue(value: string, type: SchemaFieldType): unknown {
  if (!value.trim()) {
    return undefined;
  }
  if (type === "number") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : value;
  }
  if (type === "integer") {
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : value;
  }
  if (type === "boolean") {
    return value === "true" || value === "1" || value.toLowerCase() === "yes";
  }
  return value;
}

function enumValuesFromText(value: string, type: SchemaFieldType): unknown[] {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => coerceSchemaValue(item, type))
    .filter((item) => item !== undefined);
}

function buildSchema(rows: SchemaFieldRow[]): Record<string, unknown> {
  const cleanRows = rows.filter((row) => row.name.trim());
  const properties = Object.fromEntries(
    cleanRows.map((row) => {
      const property: Record<string, unknown> = {
        type: row.type,
      };
      if (row.description.trim()) {
        property.description = row.description.trim();
      }
      const defaultValue = coerceSchemaValue(row.defaultValue, row.type);
      if (defaultValue !== undefined) {
        property.default = defaultValue;
      }
      const enumValues = enumValuesFromText(row.enumText, row.type);
      if (enumValues.length) {
        property.enum = enumValues;
      }
      return [row.name.trim(), property];
    }),
  );
  return {
    type: "object",
    properties,
    required: cleanRows.filter((row) => row.required).map((row) => row.name.trim()),
  };
}

export function SchemaObjectBuilder({ label, onChange, value }: SchemaObjectBuilderProps) {
  const [rows, setRows] = useState<SchemaFieldRow[]>(() => readSchemaRows(value));

  useEffect(() => {
    setRows(readSchemaRows(value));
  }, [value]);

  function applyRows(nextRows: SchemaFieldRow[]) {
    setRows(nextRows);
    onChange(buildSchema(nextRows));
  }

  function updateRow(rowId: string, patch: Partial<SchemaFieldRow>) {
    applyRows(rows.map((row) => (row.id === rowId ? { ...row, ...patch } : row)));
  }

  const schemaPreview = buildSchema(rows);

  return (
    <div className="rounded-[1.2rem] border border-border bg-surface-subtle px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-slate-900">{label}</p>
          <p className="mt-1 text-sm text-slate-500">
            Поля схемы задаются строками; JSON Schema собирается автоматически.
          </p>
        </div>
        <Button
          leadingIcon={<Plus className="h-4 w-4" />}
          onClick={() => applyRows([...rows, createRow(rows.length, { name: `field_${rows.length + 1}` })])}
          size="sm"
          variant="outline"
        >
          Добавить поле
        </Button>
      </div>

      <div className="mt-4 grid gap-3">
        {rows.length ? (
          rows.map((row) => (
            <div key={row.id} className="rounded-[0.9rem] bg-white px-3 py-3">
              <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_11rem_auto]">
                <label className="space-y-2 text-sm font-medium text-slate-800">
                  <span>Field name</span>
                  <Input aria-label="Field name" onChange={(event) => updateRow(row.id, { name: event.target.value })} value={row.name} />
                </label>
                <label className="space-y-2 text-sm font-medium text-slate-800">
                  <span>Field type</span>
                  <Select
                    aria-label="Field type"
                    onChange={(event) => updateRow(row.id, { type: normalizeFieldType(event.target.value) })}
                    value={row.type}
                  >
                    {FIELD_TYPES.map((type) => (
                      <option key={type} value={type}>
                        {type}
                      </option>
                    ))}
                  </Select>
                </label>
                <Button
                  aria-label={`Удалить поле ${row.name || "schema"}`}
                  className="self-end"
                  leadingIcon={<Trash2 className="h-4 w-4" />}
                  onClick={() => applyRows(rows.filter((item) => item.id !== row.id))}
                  size="sm"
                  variant="outline"
                >
                  Удалить
                </Button>
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <label className="space-y-2 text-sm font-medium text-slate-800">
                  <span>Description</span>
                  <Input
                    aria-label="Description"
                    onChange={(event) => updateRow(row.id, { description: event.target.value })}
                    value={row.description}
                  />
                </label>
                <label className="space-y-2 text-sm font-medium text-slate-800">
                  <span>Default value</span>
                  <Input
                    aria-label="Default value"
                    onChange={(event) => updateRow(row.id, { defaultValue: event.target.value })}
                    value={row.defaultValue}
                  />
                </label>
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-[minmax(0,1fr)_10rem]">
                <label className="space-y-2 text-sm font-medium text-slate-800">
                  <span>Enum values, one per line</span>
                  <textarea
                    aria-label="Enum values, one per line"
                    className="field-base min-h-[82px] w-full resize-y px-4 py-3 text-sm"
                    onChange={(event) => updateRow(row.id, { enumText: event.target.value })}
                    value={row.enumText}
                  />
                </label>
                <label className="flex items-center gap-2 self-start rounded-[0.9rem] bg-surface-subtle px-3 py-3 text-sm font-medium text-slate-800 md:self-end">
                  <input
                    aria-label="Required"
                    checked={row.required}
                    onChange={(event) => updateRow(row.id, { required: event.target.checked })}
                    type="checkbox"
                  />
                  <span>Required</span>
                </label>
              </div>
            </div>
          ))
        ) : (
          <div className="rounded-[0.9rem] border border-dashed border-border bg-white px-4 py-5 text-sm text-slate-500">
            Полей пока нет. Добавьте поле, если команда принимает параметры или возвращает структурированный результат.
          </div>
        )}
      </div>

      <div className="mt-4 rounded-[0.9rem] bg-white px-3 py-3">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Schema preview</p>
        <pre className="mt-2 max-h-52 overflow-auto text-xs text-slate-600">{JSON.stringify(schemaPreview, null, 2)}</pre>
      </div>
    </div>
  );
}
