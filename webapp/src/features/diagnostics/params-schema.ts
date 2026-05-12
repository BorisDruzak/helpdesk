import type { SchemaParamField, SchemaParamOption } from "../../components/forms/schema-param-editor";

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function inferParamType(value: unknown): string {
  if (typeof value === "boolean") {
    return "boolean";
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? "integer" : "number";
  }
  if (Array.isArray(value)) {
    return "array";
  }
  if (isRecord(value)) {
    return "object";
  }
  return "string";
}

function normalizeSchemaOptions(rawSchema: Record<string, unknown>): SchemaParamOption[] | undefined {
  const enumValues = Array.isArray(rawSchema.enum) ? rawSchema.enum : null;
  if (enumValues?.length) {
    return enumValues.map((item) => {
      const value = String(item ?? "");
      return { value, label: value };
    });
  }

  const oneOf = Array.isArray(rawSchema.oneOf) ? rawSchema.oneOf : null;
  if (oneOf?.length) {
    return oneOf
      .filter(isRecord)
      .map((item) => {
        const value = String(item.const ?? item.value ?? "");
        return {
          value,
          label: String(item.title ?? item.label ?? value),
        };
      })
      .filter((item) => item.value);
  }

  return undefined;
}

function normalizeSchemaField(
  name: string,
  rawField: unknown,
  required: Set<string>,
  params: Record<string, unknown>,
): SchemaParamField {
  const rawSchema = isRecord(rawField) ? rawField : {};
  const defaultValue = rawSchema.default ?? params[name];
  const propertyRequired = new Set(
    Array.isArray(rawSchema.required)
      ? rawSchema.required.map((item) => String(item ?? "")).filter(Boolean)
      : [],
  );
  const childProperties = isRecord(rawSchema.properties) ? rawSchema.properties : null;
  const itemSchema = isRecord(rawSchema.items) ? rawSchema.items : null;
  const childParams = isRecord(defaultValue) ? defaultValue : {};

  return {
    name,
    label: String(rawSchema.title ?? rawSchema.label ?? name),
    description: rawSchema.description ? String(rawSchema.description) : null,
    type: String(rawSchema.type ?? inferParamType(defaultValue)),
    required: required.has(name) || Boolean(rawSchema.required === true),
    default: defaultValue,
    options: normalizeSchemaOptions(rawSchema),
    properties: childProperties
      ? Object.entries(childProperties).map(([childName, childSchema]) =>
          normalizeSchemaField(childName, childSchema, propertyRequired, childParams),
        )
      : undefined,
    items: itemSchema ? normalizeSchemaField("item", itemSchema, new Set(), {}) : undefined,
  };
}

export function normalizeCapabilityParamSchema(
  paramsSchema: Record<string, unknown> | undefined,
  params: Record<string, unknown>,
): SchemaParamField[] {
  if (!paramsSchema || !isRecord(paramsSchema)) {
    return Object.entries(params).map(([name, value]) => ({
      name,
      label: name,
      type: inferParamType(value),
      default: value,
    }));
  }

  const required = new Set(
    Array.isArray(paramsSchema.required)
      ? paramsSchema.required.map((item) => String(item ?? "")).filter(Boolean)
      : [],
  );
  const properties = isRecord(paramsSchema.properties) ? paramsSchema.properties : paramsSchema;

  return Object.entries(properties)
    .filter(([name, rawField]) => name !== "required" && name !== "properties" && Boolean(rawField))
    .map(([name, rawField]) => normalizeSchemaField(name, rawField, required, params));
}
