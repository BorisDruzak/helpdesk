export type SchemaPathKind = "object" | "array" | "scalar";

export type SchemaPathItem = {
  path: string;
  label: string;
  type: string;
  kind: SchemaPathKind;
};

type JsonRecord = Record<string, unknown>;

const MAX_DEPTH = 8;

function isRecord(value: unknown): value is JsonRecord {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function schemaType(schema: JsonRecord): string {
  const rawType = schema.type;
  if (typeof rawType === "string") {
    return rawType;
  }
  if (Array.isArray(rawType)) {
    return rawType.filter((item): item is string => typeof item === "string").join(" | ") || "unknown";
  }
  if (isRecord(schema.properties)) {
    return "object";
  }
  if (isRecord(schema.items)) {
    return "array";
  }
  return "unknown";
}

function labelFor(propertyName: string, schema: JsonRecord): string {
  const title = schema.title;
  if (typeof title === "string" && title.trim()) {
    return title.trim();
  }
  return propertyName.replaceAll("_", " ");
}

function pushPath(
  result: SchemaPathItem[],
  item: {
    path: string;
    label: string;
    type: string;
    kind: SchemaPathKind;
  },
): void {
  const { path, label, type, kind } = item;
  if (!path || result.some((item) => item.path === path)) {
    return;
  }
  result.push({ path, label, type, kind });
}

function walk(
  schema: unknown,
  path: string,
  propertyName: string,
  result: SchemaPathItem[],
  seen: WeakSet<object>,
  depth: number,
): void {
  if (!isRecord(schema) || depth > MAX_DEPTH) {
    return;
  }
  const type = schemaType(schema);
  const properties = isRecord(schema.properties) ? schema.properties : null;
  const label = labelFor(propertyName || path, schema);
  if (path && type === "object") {
    pushPath(result, { path, label, type: "object", kind: "object" });
  }
  if (seen.has(schema)) {
    return;
  }
  seen.add(schema);

  if (type === "object" && properties) {
    for (const [name, child] of Object.entries(properties)) {
      walk(child, path ? `${path}.${name}` : name, name, result, seen, depth + 1);
    }
    return;
  }

  if (type === "array") {
    const items = schema.items;
    if (isRecord(items) && isRecord(items.properties)) {
      pushPath(result, { path, label, type: "array<object>", kind: "array" });
      for (const [name, child] of Object.entries(items.properties)) {
        walk(child, `${path}[].${name}`, name, result, seen, depth + 1);
      }
      return;
    }
    const itemType = isRecord(items) ? schemaType(items) : "unknown";
    pushPath(result, { path, label, type: `array<${itemType}>`, kind: "scalar" });
    return;
  }

  if (path) {
    pushPath(result, { path, label, type, kind: "scalar" });
  }
}

export function extractSchemaPaths(outputSchema: unknown, maxItems = 300): SchemaPathItem[] {
  const result: SchemaPathItem[] = [];
  walk(outputSchema, "", "", result, new WeakSet<object>(), 0);
  return result.slice(0, maxItems);
}

export function generateMockSampleFromSchema(schema: unknown, depth = 0, seen = new WeakSet<object>()): unknown {
  if (!isRecord(schema) || depth > MAX_DEPTH || seen.has(schema)) {
    return {};
  }
  seen.add(schema);
  const type = schemaType(schema);
  if (type === "string") {
    return "example";
  }
  if (type === "number" || type === "integer") {
    return 42;
  }
  if (type === "boolean") {
    return true;
  }
  if (type === "array") {
    const items = schema.items;
    if (!isRecord(items)) {
      return [];
    }
    return [generateMockSampleFromSchema(items, depth + 1, seen)];
  }
  const properties = isRecord(schema.properties) ? schema.properties : null;
  if (type === "object" || properties) {
    const item: Record<string, unknown> = {};
    for (const [name, child] of Object.entries(properties ?? {})) {
      item[name] = generateMockSampleFromSchema(child, depth + 1, seen);
    }
    return item;
  }
  return "example";
}
