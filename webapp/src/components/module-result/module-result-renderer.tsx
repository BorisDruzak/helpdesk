import { CheckCircle2, Circle, Clock3, Copy, FileArchive } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "../ui/badge";
import { cn } from "../../shared/ui/cn";

type JsonRecord = Record<string, unknown>;

export type PresentationTone = "neutral" | "brand" | "success" | "warning" | "danger" | "info";

export type PresentationField = {
  path?: string;
  label?: string;
  unit?: string;
  format?: string;
  empty_text?: string;
  copyable?: boolean;
  tone_rules?: Array<{ equals?: unknown; includes?: string; tone?: PresentationTone }>;
};

type BaseBlock = {
  type: string;
  id?: string;
  title?: string;
  collapsed?: boolean;
};

export type FieldGridBlock = BaseBlock & { type: "field_grid"; fields?: PresentationField[] };
export type MetricCardsBlock = BaseBlock & { type: "metric_cards"; metrics?: PresentationField[] };
export type TableBlock = BaseBlock & { type: "table"; rows_path?: string; columns?: PresentationField[] };
export type ChecklistBlock = BaseBlock & {
  type: "checklist";
  items_path?: string;
  label_path?: string;
  status_path?: string;
  detail_path?: string;
};
export type TimelineBlock = BaseBlock & {
  type: "timeline";
  items_path?: string;
  title_path?: string;
  status_path?: string;
  time_path?: string;
  detail_path?: string;
};
export type ArtifactListBlock = BaseBlock & {
  type: "artifact_list";
  items_path?: string;
  name_path?: string;
  kind_path?: string;
  size_path?: string;
};
export type RawJsonBlock = BaseBlock & { type: "raw_json" };

export type PresentationBlock =
  | FieldGridBlock
  | MetricCardsBlock
  | TableBlock
  | ChecklistBlock
  | TimelineBlock
  | ArtifactListBlock
  | RawJsonBlock
  | BaseBlock;

export type PresentationSchema = {
  version?: string;
  kind?: "tool_result" | "composite_recipe" | string;
  title?: string;
  summary?: {
    title_path?: string;
    subtitle_template?: string;
    message_path?: string;
    status_path?: string;
  };
  blocks?: PresentationBlock[];
  steps?: {
    path?: string;
    title_path?: string;
    status_path?: string;
    tool_id_path?: string;
    primitive_id_path?: string;
    result_path?: string;
    default_layout?: "timeline" | "checklist" | string;
  };
  fallback?: {
    show_raw_json?: boolean;
    show_step_raw_json?: boolean;
  };
};

const BLOCK_TYPES = new Set(["field_grid", "metric_cards", "table", "checklist", "timeline", "artifact_list", "raw_json"]);
const FORBIDDEN_PATH_SEGMENTS = new Set(["__proto__", "prototype", "constructor"]);

function isRecord(value: unknown): value is JsonRecord {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

export function normalizePresentationSchema(schema: unknown): PresentationSchema | null {
  if (!isRecord(schema)) {
    return null;
  }
  if (schema.blocks !== undefined && !Array.isArray(schema.blocks)) {
    return null;
  }
  if (schema.steps !== undefined && !isRecord(schema.steps)) {
    return null;
  }
  return schema as PresentationSchema;
}

export function getPathValue(result: unknown, path: string | undefined): unknown {
  if (!path || !path.trim()) {
    return undefined;
  }
  const parts = path.split(".").map((part) => part.trim()).filter(Boolean);
  let current: unknown = result;
  for (const part of parts) {
    if (FORBIDDEN_PATH_SEGMENTS.has(part)) {
      return undefined;
    }
    if (Array.isArray(current)) {
      const index = Number(part);
      if (!Number.isInteger(index) || index < 0) {
        return undefined;
      }
      current = current[index];
    } else if (isRecord(current)) {
      current = current[part];
    } else {
      return undefined;
    }
  }
  return current;
}

export function renderTemplate(template: string | undefined, result: unknown): string {
  if (!template) {
    return "";
  }
  return template.replace(/\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}/g, (_match, path: string) => formatValue(getPathValue(result, path)));
}

export function evaluateToneRules(value: unknown, rules: PresentationField["tone_rules"] = []): PresentationTone {
  for (const rule of rules) {
    if (!rule || !rule.tone) {
      continue;
    }
    if (rule.equals !== undefined && value === rule.equals) {
      return rule.tone;
    }
    if (rule.includes && String(value ?? "").includes(rule.includes)) {
      return rule.tone;
    }
  }
  const normalized = String(value ?? "").toLowerCase();
  if (["ok", "success", "true", "available", "running", "passed"].includes(normalized)) {
    return "success";
  }
  if (["warning", "pending", "install_required"].includes(normalized)) {
    return "warning";
  }
  if (["error", "failed", "false", "missing", "unavailable"].includes(normalized)) {
    return "danger";
  }
  return "neutral";
}

function formatValue(value: unknown, field?: PresentationField): string {
  if (value === undefined || value === null || value === "") {
    return field?.empty_text ?? "—";
  }
  if (field?.format === "datetime" && typeof value === "number") {
    return new Date(value * 1000).toLocaleString("ru-RU");
  }
  if (Array.isArray(value)) {
    return value.map((item) => formatValue(item)).join(", ");
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return `${String(value)}${field?.unit ?? ""}`;
}

function toRows(value: unknown): JsonRecord[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => (isRecord(item) ? item : { value: item }));
}

export function inferFallbackBlocks(result: unknown): PresentationBlock[] {
  if (!isRecord(result)) {
    return [{ type: "raw_json", collapsed: true }];
  }
  const fields: PresentationField[] = [];
  const blocks: PresentationBlock[] = [];
  for (const [key, value] of Object.entries(result)) {
    if (Array.isArray(value) && value.some(isRecord)) {
      blocks.push({
        type: "table",
        title: key,
        rows_path: key,
        columns: Object.keys((value.find(isRecord) as JsonRecord | undefined) ?? {}).slice(0, 6).map((path) => ({ path, label: path })),
      });
    } else if (!isRecord(value)) {
      fields.push({ path: key, label: key });
    }
  }
  if (fields.length) {
    blocks.unshift({ type: "field_grid", title: "Result", fields });
  }
  blocks.push({ type: "raw_json", collapsed: true });
  return blocks;
}

function BlockShell({ children, title }: { children: ReactNode; title?: string }) {
  return (
    <section className="rounded-lg border border-border bg-white p-4">
      {title ? <h4 className="mb-3 text-sm font-semibold text-slate-950">{title}</h4> : null}
      {children}
    </section>
  );
}

function FieldValue({ field, source }: { field: PresentationField; source: unknown }) {
  const value = getPathValue(source, field.path);
  const text = formatValue(value, field);
  const tone = evaluateToneRules(value, field.tone_rules);
  return (
    <div className="min-w-0 rounded-md bg-surface-subtle px-3 py-2">
      <p className="text-xs font-semibold uppercase text-slate-400">{field.label ?? field.path ?? "value"}</p>
      <div className="mt-1 flex min-w-0 items-center gap-2">
        <p className="min-w-0 break-words text-sm text-slate-800">{text}</p>
        {tone !== "neutral" ? <Badge tone={tone}>{tone}</Badge> : null}
        {field.copyable ? <Copy aria-label="Copyable" className="h-3.5 w-3.5 text-slate-400" /> : null}
      </div>
    </div>
  );
}

function RawJson({ collapsed, value }: { collapsed?: boolean; value: unknown }) {
  const content = (
    <pre className="max-h-72 overflow-auto rounded-lg bg-slate-950 p-4 text-xs leading-5 text-slate-100">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
  if (collapsed) {
    return (
      <details className="rounded-lg border border-border bg-white p-3">
        <summary className="cursor-pointer text-sm font-semibold text-slate-800">Raw JSON</summary>
        <div className="mt-3">{content}</div>
      </details>
    );
  }
  return <BlockShell title="Raw JSON">{content}</BlockShell>;
}

function renderBlock(block: PresentationBlock, result: unknown): ReactNode {
  if (!BLOCK_TYPES.has(block.type)) {
    return null;
  }
  if (block.type === "field_grid") {
    const fields = Array.isArray((block as FieldGridBlock).fields) ? (block as FieldGridBlock).fields ?? [] : [];
    return (
      <BlockShell title={block.title}>
        <div className="grid gap-3 md:grid-cols-2">{fields.map((field, index) => <FieldValue field={field} key={`${field.path ?? index}`} source={result} />)}</div>
      </BlockShell>
    );
  }
  if (block.type === "metric_cards") {
    const metrics = Array.isArray((block as MetricCardsBlock).metrics) ? (block as MetricCardsBlock).metrics ?? [] : [];
    return (
      <BlockShell title={block.title}>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {metrics.map((metric, index) => (
            <div className="rounded-lg border border-border bg-surface-subtle px-3 py-3" key={`${metric.path ?? index}`}>
              <p className="text-xs font-semibold uppercase text-slate-400">{metric.label ?? metric.path}</p>
              <p className="mt-2 text-xl font-semibold text-slate-950">{formatValue(getPathValue(result, metric.path), metric)}</p>
            </div>
          ))}
        </div>
      </BlockShell>
    );
  }
  if (block.type === "table") {
    const table = block as TableBlock;
    const rows = toRows(getPathValue(result, table.rows_path));
    const columns = table.columns?.length ? table.columns : Object.keys(rows[0] ?? {}).map((path) => ({ path, label: path }));
    return (
      <BlockShell title={block.title}>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-400">
              <tr>{columns.map((column) => <th className="px-3 py-2" key={column.path}>{column.label ?? column.path}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr className="border-t border-border" key={rowIndex}>
                  {columns.map((column) => <td className="px-3 py-2 text-slate-700" key={column.path}>{formatValue(getPathValue(row, column.path), column)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </BlockShell>
    );
  }
  if (block.type === "checklist" || block.type === "timeline") {
    const list = block as (ChecklistBlock | TimelineBlock) & {
      items_path?: string;
      label_path?: string;
      title_path?: string;
      status_path?: string;
      time_path?: string;
      detail_path?: string;
    };
    const items = toRows(getPathValue(result, list.items_path));
    return (
      <BlockShell title={block.title}>
        <div className="space-y-3">
          {items.map((item, index) => {
            const status = getPathValue(item, list.status_path);
            const title = formatValue(getPathValue(item, list.label_path ?? list.title_path) ?? `Step ${index + 1}`);
            const detail = formatValue(getPathValue(item, list.detail_path), { empty_text: "" });
            return (
              <div className={cn("flex gap-3", block.type === "timeline" ? "border-l border-border pl-4" : "")} key={index}>
                {evaluateToneRules(status) === "success" ? <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" /> : <Circle className="mt-0.5 h-4 w-4 text-slate-400" />}
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-medium text-slate-900">{title}</p>
                    <Badge tone={evaluateToneRules(status)}>{formatValue(status)}</Badge>
                  </div>
                  {list.time_path ? <p className="mt-1 text-xs text-slate-400"><Clock3 className="mr-1 inline h-3 w-3" />{formatValue(getPathValue(item, list.time_path))}</p> : null}
                  {detail ? <p className="mt-1 text-sm text-slate-600">{detail}</p> : null}
                </div>
              </div>
            );
          })}
        </div>
      </BlockShell>
    );
  }
  if (block.type === "artifact_list") {
    const artifactBlock = block as ArtifactListBlock;
    const items = toRows(getPathValue(result, artifactBlock.items_path));
    return (
      <BlockShell title={block.title}>
        <div className="space-y-2">
          {items.map((item, index) => (
            <div className="flex items-center gap-3 rounded-md bg-surface-subtle px-3 py-2" key={index}>
              <FileArchive className="h-4 w-4 text-slate-500" />
              <div className="min-w-0">
                <p className="break-words text-sm font-medium text-slate-900">{formatValue(getPathValue(item, artifactBlock.name_path ?? "name"))}</p>
                <p className="text-xs text-slate-500">
                  {formatValue(getPathValue(item, artifactBlock.kind_path ?? "kind"))}
                  {artifactBlock.size_path ? ` · ${formatValue(getPathValue(item, artifactBlock.size_path))}` : ""}
                </p>
              </div>
            </div>
          ))}
        </div>
      </BlockShell>
    );
  }
  if (block.type === "raw_json") {
    return <RawJson collapsed={(block as RawJsonBlock).collapsed} value={result} />;
  }
  return null;
}

export function ModuleResultRenderer({
  result,
  presentationSchema,
}: {
  result: unknown;
  presentationSchema?: unknown;
  primitiveSchemas?: Record<string, PresentationSchema>;
  artifacts?: unknown;
}) {
  const schema = normalizePresentationSchema(presentationSchema);
  const blocks = schema?.blocks?.length ? schema.blocks : inferFallbackBlocks(result);
  const rendered = blocks.map((block, index) => <div key={`${block.id ?? block.type}-${index}`}>{renderBlock(block, result)}</div>).filter(Boolean);
  const hasRawJsonBlock = blocks.some((block) => block.type === "raw_json");
  const shouldShowRawFallback = schema?.fallback?.show_raw_json && !hasRawJsonBlock;
  const title = schema?.title;
  const summaryTitle = formatValue(getPathValue(result, schema?.summary?.title_path), { empty_text: "" });
  const subtitle = renderTemplate(schema?.summary?.subtitle_template, result);
  const status = getPathValue(result, schema?.summary?.status_path);

  return (
    <div className="space-y-3">
      {title || summaryTitle || subtitle ? (
        <div className="rounded-lg border border-border bg-surface-subtle px-4 py-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              {title ? <p className="text-sm font-semibold text-slate-950">{title}</p> : null}
              {summaryTitle ? <p className="mt-1 text-sm text-slate-700">{summaryTitle}</p> : null}
              {subtitle ? <p className="mt-1 text-xs text-slate-500">{subtitle}</p> : null}
            </div>
            {status !== undefined ? <Badge tone={evaluateToneRules(status)}>{formatValue(status)}</Badge> : null}
          </div>
        </div>
      ) : null}
      {rendered}
      {shouldShowRawFallback ? <RawJson collapsed value={result} /> : null}
    </div>
  );
}

export function CompositeRecipeRenderer({
  result,
  presentationSchema,
  primitiveSchemas = {},
}: {
  result: unknown;
  presentationSchema?: unknown;
  primitiveSchemas?: Record<string, PresentationSchema>;
}) {
  const schema = normalizePresentationSchema(presentationSchema);
  const steps = schema?.steps;
  const stepRows = toRows(getPathValue(result, steps?.path ?? "steps"));
  const title = formatValue(getPathValue(result, schema?.summary?.title_path), { empty_text: schema?.title ?? "Recipe" });
  const message = formatValue(getPathValue(result, schema?.summary?.message_path), { empty_text: "" });
  const status = getPathValue(result, schema?.summary?.status_path);

  return (
    <div className="space-y-3">
      <BlockShell title={title}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          {message ? <p className="text-sm text-slate-600">{message}</p> : <p className="text-sm text-slate-500">Composite recipe result</p>}
          {status !== undefined ? <Badge tone={evaluateToneRules(status)}>{formatValue(status)}</Badge> : null}
        </div>
      </BlockShell>
      <div className="space-y-3">
        {stepRows.map((step, index) => {
          const primitiveId = formatValue(getPathValue(step, steps?.primitive_id_path), { empty_text: "" });
          const toolId = formatValue(getPathValue(step, steps?.tool_id_path), { empty_text: "" });
          const stepSchema = primitiveSchemas[primitiveId] ?? primitiveSchemas[toolId];
          const stepResult = getPathValue(step, steps?.result_path ?? "result") ?? step;
          return (
            <BlockShell key={index} title={formatValue(getPathValue(step, steps?.title_path) ?? `Step ${index + 1}`)}>
              <div className="mb-3 flex flex-wrap gap-2">
                <Badge tone={evaluateToneRules(getPathValue(step, steps?.status_path))}>{formatValue(getPathValue(step, steps?.status_path))}</Badge>
                {primitiveId ? <Badge tone="info">{primitiveId}</Badge> : null}
                {toolId ? <Badge tone="brand">{toolId}</Badge> : null}
              </div>
              <ModuleResultRenderer result={stepResult} presentationSchema={stepSchema} />
            </BlockShell>
          );
        })}
      </div>
    </div>
  );
}
