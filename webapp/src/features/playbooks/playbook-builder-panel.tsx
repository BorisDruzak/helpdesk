import { useEffect, useMemo, useRef, useState } from "react";
import type { DragEvent, ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  CheckCircle2,
  ChevronDown,
  Code2,
  GitBranch,
  GripVertical,
  ListFilter,
  MousePointer2,
  Play,
  Save,
  Search,
  Settings2,
  Trash2,
  Workflow,
} from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { SchemaParamEditor, type SchemaParamField, type SchemaParamOption } from "../../components/forms/schema-param-editor";
import { requirePermission, type PermissionDecision } from "../auth/permissions";
import { cn } from "../../shared/ui/cn";
import {
  type AdminPlaybookBlockCatalogItem,
  type AdminPlaybookDraftBlock,
  type AdminPlaybookDraftRequest,
  type AdminScenarioTemplateItem,
  fetchAdminPlaybooksCatalog,
  saveAdminPlaybook,
} from "./api";

type Feedback = { tone: "success" | "error"; text: string } | null;
type Point = { x: number; y: number };
type CanvasPositions = Record<string, Point>;

const CANVAS_WIDTH = 980;
const CANVAS_HEIGHT = 760;
const BLOCK_WIDTH = 304;
const BLOCK_HEIGHT = 92;
const START_NODE = { id: "start", x: 338, y: 28, width: 260, height: 76 };

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 48);
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => String(item ?? "").trim()).filter(Boolean)
    : [];
}

function uniqueBlockId(base: string, blocks: AdminPlaybookDraftBlock[]): string {
  const normalizedBase = slugify(base) || "step";
  const used = new Set(blocks.map((block) => block.id));
  if (!used.has(normalizedBase)) {
    return normalizedBase;
  }
  for (let index = 2; index < 200; index += 1) {
    const candidate = `${normalizedBase}_${index}`;
    if (!used.has(candidate)) {
      return candidate;
    }
  }
  return `${normalizedBase}_${Date.now()}`;
}

function blockFromCatalog(
  item: AdminPlaybookBlockCatalogItem,
  existingBlocks: AdminPlaybookDraftBlock[] = []
): AdminPlaybookDraftBlock {
  return {
    id: uniqueBlockId(item.id || item.tool || item.label, existingBlocks),
    type: "diagnostic",
    module_kind: "diagnostic",
    tool: item.tool,
    capability_id: item.capability_id ?? item.tool,
    execution_target: item.execution_target ?? null,
    provider_id: item.provider_id ?? null,
    label: item.label,
    preset_id: null,
    install_policy: item.install_policy ?? (item.install_required ? "lazy" : "preinstalled"),
    tool_manifest: item,
    params: { ...item.default_params },
    condition: null,
    timeout_sec: null,
    continue_on_error: false,
    parallel_group: null,
  };
}

function decisionBlock(existingBlocks: AdminPlaybookDraftBlock[] = []): AdminPlaybookDraftBlock {
  return {
    id: uniqueBlockId("decision", existingBlocks),
    type: "decision",
    module_kind: "diagnostic",
    tool: null,
    label: "Проверка результата",
    params: {},
    condition: "",
    timeout_sec: null,
    continue_on_error: false,
    parallel_group: null,
  };
}

function buildDraftFromTemplate(
  template: AdminScenarioTemplateItem,
  catalog: AdminPlaybookBlockCatalogItem[]
): AdminPlaybookDraftRequest {
  const byId = new Map(catalog.map((item) => [item.id, item]));
  const blocks = template.block_ids.reduce<AdminPlaybookDraftBlock[]>((acc, blockId) => {
    const item = byId.get(blockId);
    if (item) {
      acc.push(blockFromCatalog(item, acc));
    }
    return acc;
  }, []);
  return {
    key: slugify(template.key) || "diagnostic_playbook",
    name: template.title,
    domain: "diagnostics",
    blocks,
  };
}

function defaultPositions(blocks: AdminPlaybookDraftBlock[]): CanvasPositions {
  return Object.fromEntries(
    blocks.map((block, index) => [
      block.id,
      {
        x: index % 2 === 0 ? 316 : 520,
        y: 150 + index * 118,
      },
    ])
  );
}

function sortedBlocks(
  blocks: AdminPlaybookDraftBlock[],
  positions: CanvasPositions
): AdminPlaybookDraftBlock[] {
  return [...blocks].sort((left, right) => {
    const leftPoint = positions[left.id] ?? { x: 0, y: 0 };
    const rightPoint = positions[right.id] ?? { x: 0, y: 0 };
    if (Math.abs(leftPoint.y - rightPoint.y) > 12) {
      return leftPoint.y - rightPoint.y;
    }
    return leftPoint.x - rightPoint.x;
  });
}

function outputContractSummary(item: AdminPlaybookBlockCatalogItem | null | undefined) {
  const contract = item?.output_contract ?? {};
  const statusPath = String(contract.status_path ?? item?.condition_hints?.status_path ?? "result.status");
  const statusValues = stringList(contract.status_values ?? item?.condition_hints?.status_values);
  const summaryPath = String(contract.summary_path ?? item?.condition_hints?.summary_path ?? "result.output.summary");
  const errorCodePath = String(contract.error_code_path ?? item?.condition_hints?.error_code_path ?? "result.error.code");
  const errorCodes = stringList(item?.error_codes ?? item?.condition_hints?.error_codes);
  return {
    statusPath,
    statusValues: statusValues.length ? statusValues : ["ok", "error"],
    summaryPath,
    errorCodePath,
    errorCodes,
  };
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
  if (value && typeof value === "object") {
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
      .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item))
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
  const rawSchema = typeof rawField === "object" && rawField && !Array.isArray(rawField)
    ? rawField as Record<string, unknown>
    : {};
  const defaultValue = rawSchema.default ?? params[name];
  const fieldRequired = required.has(name) || Boolean(rawSchema.required);
  const propertyRequired = new Set(
    Array.isArray(rawSchema.required)
      ? rawSchema.required.map((item) => String(item ?? "")).filter(Boolean)
      : [],
  );
  const childProperties =
    typeof rawSchema.properties === "object" && rawSchema.properties && !Array.isArray(rawSchema.properties)
      ? rawSchema.properties as Record<string, unknown>
      : null;
  const itemSchema =
    typeof rawSchema.items === "object" && rawSchema.items && !Array.isArray(rawSchema.items)
      ? rawSchema.items as Record<string, unknown>
      : null;
  const childParams = defaultValue && typeof defaultValue === "object" && !Array.isArray(defaultValue)
    ? defaultValue as Record<string, unknown>
    : {};

  return {
    name,
    label: String(rawSchema.title ?? rawSchema.label ?? name),
    description: rawSchema.description ? String(rawSchema.description) : null,
    type: String(rawSchema.type ?? inferParamType(defaultValue)),
    required: fieldRequired,
    default: defaultValue,
    options: normalizeSchemaOptions(rawSchema),
    properties: childProperties
      ? Object.entries(childProperties).map(([childName, childSchema]) =>
          normalizeSchemaField(childName, childSchema, propertyRequired, childParams),
        )
      : undefined,
    items: itemSchema
      ? normalizeSchemaField("item", itemSchema, new Set(), {})
      : undefined,
  };
}

function normalizeParamSchema(
  paramsSchema: Record<string, unknown> | undefined,
  params: Record<string, unknown>
): SchemaParamField[] {
  const required = new Set(
    Array.isArray(paramsSchema?.required)
      ? paramsSchema.required.map((item) => String(item ?? "")).filter(Boolean)
      : []
  );
  const properties =
    paramsSchema && typeof paramsSchema.properties === "object" && paramsSchema.properties && !Array.isArray(paramsSchema.properties)
      ? paramsSchema.properties as Record<string, unknown>
      : paramsSchema;

  const fields = Object.entries(properties ?? {})
    .filter(([name, rawField]) => name !== "required" && name !== "properties" && Boolean(rawField))
    .map(([name, rawField]) => normalizeSchemaField(name, rawField, required, params));

  if (fields.length) {
    return fields;
  }

  return Object.entries(params).map(([name, value]) => ({
    name,
    label: name,
    type: inferParamType(value),
    default: value,
  }));
}

function quickConditionOptions(blocks: AdminPlaybookDraftBlock[], decisionIndex: number) {
  return blocks.slice(0, decisionIndex).flatMap((block) => {
    const templates = block.tool_manifest?.condition_hints?.condition_templates ?? [];
    return templates
      .filter((template) => template?.expression)
      .map((template) => ({
        label: `${block.label}: ${template.label}`,
        value: template.expression.replaceAll("{step}", `steps.${block.id}`),
      }));
  });
}

function sampleResult(block: AdminPlaybookDraftBlock | null): Record<string, unknown> {
  if (!block) {
    return { status: "idle", facts: [] };
  }
  if (block.type === "decision") {
    return {
      block: block.id,
      decision: block.condition || "steps.previous.output.result.status == 'ok'",
      branch: "yes",
    };
  }
  const summary = outputContractSummary(block.tool_manifest);
  return {
    block: block.id,
    tool: block.tool,
    result: {
      status: summary.statusValues[0] ?? "ok",
      output: {
        summary: `${block.label}: демо-результат`,
      },
      error: null,
    },
    contract: {
      status_path: summary.statusPath,
      summary_path: summary.summaryPath,
      error_code_path: summary.errorCodePath,
    },
  };
}

function IconTile({ block }: { block: AdminPlaybookDraftBlock }) {
  if (block.type === "decision") {
    return (
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
        <GitBranch className="h-5 w-5" />
      </span>
    );
  }
  return (
    <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
      <Box className="h-5 w-5" />
    </span>
  );
}

function PaletteItem({
  item,
  onAdd,
}: {
  item: AdminPlaybookBlockCatalogItem;
  onAdd: (item: AdminPlaybookBlockCatalogItem) => void;
}) {
  return (
    <button
      className="group grid w-full grid-cols-[34px_minmax(0,1fr)] gap-3 rounded-lg border border-slate-200 bg-white px-3 py-3 text-left shadow-sm transition hover:border-blue-300 hover:bg-blue-50/40"
      draggable
      onClick={() => onAdd(item)}
      onDragStart={(event) => {
        event.dataTransfer.setData("application/x-playbook-palette", item.id);
        event.dataTransfer.effectAllowed = "copy";
      }}
      type="button"
    >
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-blue-600 group-hover:bg-blue-100">
        <Box className="h-4 w-4" />
      </span>
      <span className="min-w-0">
        <span className="block truncate text-sm font-semibold text-slate-900">{item.label}</span>
        <span className="mt-0.5 block truncate text-xs text-slate-500">{item.tool ?? item.module_name ?? "local"}</span>
      </span>
    </button>
  );
}

function ConnectorLayer({
  blocks,
  positions,
}: {
  blocks: AdminPlaybookDraftBlock[];
  positions: CanvasPositions;
}) {
  const ordered = sortedBlocks(blocks, positions);
  const points = [
    { x: START_NODE.x + START_NODE.width / 2, y: START_NODE.y + START_NODE.height },
    ...ordered.map((block) => {
      const point = positions[block.id] ?? { x: 0, y: 0 };
      return { x: point.x + BLOCK_WIDTH / 2, y: point.y };
    }),
  ];
  return (
    <svg className="pointer-events-none absolute inset-0 h-full w-full" role="presentation">
      {points.slice(0, -1).map((point, index) => {
        const next = points[index + 1];
        const midY = point.y + Math.max(28, (next.y - point.y) / 2);
        return (
          <path
            className="stroke-slate-400"
            d={`M ${point.x} ${point.y} L ${point.x} ${midY} L ${next.x} ${midY} L ${next.x} ${next.y - 10}`}
            fill="none"
            key={`${point.x}-${point.y}-${index}`}
            markerEnd="url(#playbook-arrow)"
            strokeDasharray="0"
            strokeWidth="1.5"
          />
        );
      })}
      <defs>
        <marker id="playbook-arrow" markerHeight="8" markerWidth="8" orient="auto" refX="4" refY="4">
          <path d="M 0 0 L 8 4 L 0 8 z" fill="#94a3b8" />
        </marker>
      </defs>
    </svg>
  );
}

function PlaybookBlockNode({
  block,
  catalog,
  isSelected,
  position,
  onSelect,
  onStartDrag,
  onToolChange,
}: {
  block: AdminPlaybookDraftBlock;
  catalog: AdminPlaybookBlockCatalogItem[];
  isSelected: boolean;
  position: Point;
  onSelect: () => void;
  onStartDrag: (blockId: string) => void;
  onToolChange: (item: AdminPlaybookBlockCatalogItem) => void;
}) {
  const contract = outputContractSummary(block.tool_manifest);
  return (
    <article
      aria-label={`Блок ${block.label}`}
      className={cn(
        "absolute rounded-lg border bg-white shadow-sm transition",
        isSelected ? "border-blue-500 shadow-[0_12px_34px_rgba(37,99,235,0.16)]" : "border-slate-200 hover:border-blue-300"
      )}
      draggable
      onClick={onSelect}
      onDragStart={(event) => {
        event.dataTransfer.setData("application/x-playbook-block", block.id);
        event.dataTransfer.effectAllowed = "move";
        onStartDrag(block.id);
      }}
      style={{ left: position.x, top: position.y, width: BLOCK_WIDTH }}
    >
      <div className="flex items-start gap-3 px-3 py-3">
        <IconTile block={block} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <strong className="truncate text-sm font-semibold text-slate-950">{block.label}</strong>
            <GripVertical className="h-4 w-4 shrink-0 text-slate-400" />
          </div>
          {block.type === "diagnostic" ? (
            <select
              aria-label={`Команда блока ${block.label}`}
              className="mt-2 h-8 w-full rounded-md border border-slate-200 bg-slate-50 px-2 text-xs text-slate-700 outline-none focus:border-blue-400"
              onChange={(event) => {
                const item = catalog.find((candidate) => candidate.id === event.currentTarget.value);
                if (item) {
                  onToolChange(item);
                }
              }}
              onClick={(event) => event.stopPropagation()}
              value={block.tool_manifest?.id ?? ""}
            >
              {catalog.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.tool ?? item.label}
                </option>
              ))}
            </select>
          ) : (
            <p className="mt-2 truncate text-xs text-slate-500">{block.condition || "Условие по результатам предыдущих шагов"}</p>
          )}
        </div>
      </div>
      <div className="border-t border-slate-100 px-3 py-2 text-xs text-slate-500">
        <span className="font-medium text-slate-700">Выход:</span>{" "}
        {block.type === "decision" ? "yes / no" : `${contract.statusPath} = ${contract.statusValues.join(" | ")}`}
      </div>
    </article>
  );
}

function FieldLabel({ children }: { children: ReactNode }) {
  return <span className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">{children}</span>;
}

function resolveOptionalAccess(permissions: string[] | undefined, permission: string): PermissionDecision {
  return permissions === undefined ? { allowed: true, reason: null } : requirePermission({ permissions }, permission);
}

export function PlaybookBuilderPanel({ permissions }: { permissions?: string[] } = {}) {
  const queryClient = useQueryClient();
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const [draft, setDraft] = useState<AdminPlaybookDraftRequest | null>(null);
  const [positions, setPositions] = useState<CanvasPositions>({});
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null);
  const [draggedBlockId, setDraggedBlockId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [moduleSearch, setModuleSearch] = useState("");
  const [showGrid, setShowGrid] = useState(true);
  const publishAccess = resolveOptionalAccess(permissions, "admin.playbooks.publish");

  const catalogQuery = useQuery({
    queryKey: ["admin-playbooks-catalog"],
    queryFn: fetchAdminPlaybooksCatalog,
    retry: false,
  });

  const saveMutation = useMutation({
    mutationFn: saveAdminPlaybook,
    onSuccess: async (result) => {
      setFeedback({ tone: "success", text: result.message });
      await queryClient.invalidateQueries({ queryKey: ["admin-playbooks-catalog"] });
    },
    onError: (error) => {
      setFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось опубликовать плейбук.",
      });
    },
  });

  const blockCatalog = catalogQuery.data?.block_catalog ?? [];
  const templates = catalogQuery.data?.scenario_templates ?? [];
  const diagnosticModules = useMemo(
    () => blockCatalog.filter((item) => item.module_kind === "diagnostic"),
    [blockCatalog]
  );
  const filteredModules = useMemo(() => {
    const needle = moduleSearch.trim().toLowerCase();
    if (!needle) {
      return diagnosticModules;
    }
    return diagnosticModules.filter((item) =>
      [item.label, item.tool, item.module_name, item.description].some((value) =>
        String(value ?? "").toLowerCase().includes(needle)
      )
    );
  }, [diagnosticModules, moduleSearch]);

  useEffect(() => {
    if (draft || !catalogQuery.data?.scenario_templates.length) {
      return;
    }
    const nextDraft = buildDraftFromTemplate(
      catalogQuery.data.scenario_templates[0],
      catalogQuery.data.block_catalog
    );
    setDraft(nextDraft);
    setPositions(defaultPositions(nextDraft.blocks));
    setSelectedBlockId(nextDraft.blocks[0]?.id ?? null);
  }, [catalogQuery.data, draft]);

  const selectedBlock = useMemo(
    () => draft?.blocks.find((block) => block.id === selectedBlockId) ?? draft?.blocks[0] ?? null,
    [draft?.blocks, selectedBlockId]
  );
  const canSave = Boolean(publishAccess.allowed && draft?.key.trim() && draft?.name.trim() && draft.blocks.length);
  const orderedBlocks = useMemo(
    () => (draft ? sortedBlocks(draft.blocks, positions) : []),
    [draft, positions]
  );
  const selectedOrderedIndex = orderedBlocks.findIndex((block) => block.id === selectedBlock?.id);

  const selectedParamFields = useMemo(
    () =>
      selectedBlock?.type === "diagnostic"
        ? normalizeParamSchema(selectedBlock.tool_manifest?.params_schema, selectedBlock.params)
        : [],
    [selectedBlock?.params, selectedBlock?.tool_manifest?.params_schema, selectedBlock?.type]
  );

  function updateBlock(blockId: string, patch: Partial<AdminPlaybookDraftBlock>) {
    setDraft((current) =>
      current
        ? {
            ...current,
            blocks: current.blocks.map((block) => block.id === blockId ? { ...block, ...patch } : block),
          }
        : current
    );
  }

  function setDraftFromTemplate(template: AdminScenarioTemplateItem) {
    const nextDraft = buildDraftFromTemplate(template, blockCatalog);
    setFeedback(null);
    setDraft(nextDraft);
    setPositions(defaultPositions(nextDraft.blocks));
    setSelectedBlockId(nextDraft.blocks[0]?.id ?? null);
  }

  function addBlockFromCatalog(item: AdminPlaybookBlockCatalogItem, point?: Point) {
    setDraft((current) => {
      if (!current) {
        return current;
      }
      const block = blockFromCatalog(item, current.blocks);
      setPositions((currentPositions) => ({
        ...currentPositions,
        [block.id]: point ?? { x: 338, y: 154 + current.blocks.length * 118 },
      }));
      setSelectedBlockId(block.id);
      return { ...current, blocks: [...current.blocks, block] };
    });
  }

  function addDecisionBlock(point?: Point) {
    setDraft((current) => {
      if (!current) {
        return current;
      }
      const block = decisionBlock(current.blocks);
      setPositions((currentPositions) => ({
        ...currentPositions,
        [block.id]: point ?? { x: 338, y: 154 + current.blocks.length * 118 },
      }));
      setSelectedBlockId(block.id);
      return { ...current, blocks: [...current.blocks, block] };
    });
  }

  function canvasPoint(event: DragEvent<HTMLDivElement>): Point {
    const rect = canvasRef.current?.getBoundingClientRect();
    const x = rect ? event.clientX - rect.left - BLOCK_WIDTH / 2 : 338;
    const y = rect ? event.clientY - rect.top - 32 : 180;
    return {
      x: clamp(x, 24, CANVAS_WIDTH - BLOCK_WIDTH - 24),
      y: clamp(y, 126, CANVAS_HEIGHT - BLOCK_HEIGHT - 24),
    };
  }

  function handleCanvasDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    const paletteId = event.dataTransfer.getData("application/x-playbook-palette");
    const blockId = event.dataTransfer.getData("application/x-playbook-block") || draggedBlockId;
    const point = canvasPoint(event);
    if (paletteId) {
      const item = diagnosticModules.find((candidate) => candidate.id === paletteId);
      if (item) {
        addBlockFromCatalog(item, point);
      }
      return;
    }
    if (blockId) {
      setPositions((current) => ({ ...current, [blockId]: point }));
      setSelectedBlockId(blockId);
      setDraggedBlockId(null);
    }
  }

  function updateBlockTool(blockId: string, item: AdminPlaybookBlockCatalogItem) {
    updateBlock(blockId, {
      tool: item.tool,
      capability_id: item.capability_id ?? item.tool,
      execution_target: item.execution_target ?? null,
      provider_id: item.provider_id ?? null,
      label: item.label,
      preset_id: null,
      install_policy: item.install_policy ?? (item.install_required ? "lazy" : "preinstalled"),
      tool_manifest: item,
      params: { ...item.default_params },
    });
  }

  function saveOrderedDraft() {
    if (!publishAccess.allowed) {
      setFeedback({ tone: "error", text: publishAccess.reason });
      return;
    }
    if (!draft) {
      return;
    }
    saveMutation.mutate({ ...draft, blocks: orderedBlocks });
  }

  const selectedContract = outputContractSummary(selectedBlock?.tool_manifest);
  const sampleJson = JSON.stringify(sampleResult(selectedBlock), null, 2);

  return (
    <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="flex min-h-[720px] flex-col xl:flex-row">
        <aside className="w-full border-b border-slate-200 bg-slate-50/80 xl:w-[284px] xl:border-b-0 xl:border-r">
          <div className="border-b border-slate-200 px-4 py-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-950">Playbook Builder</p>
                <p className="mt-1 text-xs text-slate-500">Модули и атомарные команды</p>
              </div>
              <Badge>diagnostic</Badge>
            </div>
            <div className="mt-4 grid grid-cols-2 rounded-lg bg-white p-1 text-sm shadow-sm">
              <button className="rounded-md bg-blue-50 px-3 py-2 font-medium text-blue-700" type="button">
                Модули
              </button>
              <button className="rounded-md px-3 py-2 text-slate-500" type="button">
                Переменные
              </button>
            </div>
            <label className="mt-4 flex h-10 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-500">
              <Search className="h-4 w-4" />
              <input
                className="min-w-0 flex-1 bg-transparent text-slate-800 outline-none placeholder:text-slate-400"
                onChange={(event) => setModuleSearch(event.currentTarget.value)}
                placeholder="Поиск модулей..."
                value={moduleSearch}
              />
            </label>
          </div>
          <div className="max-h-[640px] space-y-5 overflow-y-auto px-4 py-4">
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Шаблоны</p>
              <div className="space-y-2">
                {templates.map((template) => (
                  <button
                    aria-label={template.title}
                    className={cn(
                      "w-full rounded-lg border border-slate-200 bg-white px-3 py-3 text-left text-sm transition hover:border-blue-300 hover:bg-blue-50/40",
                      draft?.key === template.key ? "border-blue-300 bg-blue-50" : ""
                    )}
                    key={template.key}
                    onClick={() => setDraftFromTemplate(template)}
                    type="button"
                  >
                    <span className="block font-semibold text-slate-900">{template.title}</span>
                    <span className="mt-1 block text-xs leading-5 text-slate-500">{template.problem}</span>
                  </button>
                ))}
              </div>
            </div>
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Команды</p>
              <div className="space-y-2">
                {filteredModules.map((item) => (
                  <PaletteItem item={item} key={item.id} onAdd={addBlockFromCatalog} />
                ))}
              </div>
            </div>
            <button
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-blue-300 bg-white px-3 py-3 text-sm font-medium text-blue-700 hover:bg-blue-50"
              onClick={() => addDecisionBlock()}
              type="button"
            >
              <GitBranch className="h-4 w-4" />
              Блок условия
            </button>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
            <div className="flex min-w-0 flex-wrap items-center gap-3">
              <label className="min-w-[220px] space-y-1">
                <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Ключ</span>
                <input
                  aria-label="Ключ"
                  className="h-9 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-blue-400"
                  onChange={(event) => {
                    const value = event.currentTarget.value;
                    setDraft((current) => current ? { ...current, key: slugify(value) } : current);
                  }}
                  value={draft?.key ?? ""}
                />
              </label>
              <label className="min-w-[260px] flex-1 space-y-1">
                <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Название</span>
                <input
                  aria-label="Название плейбука"
                  className="h-9 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-blue-400"
                  onChange={(event) => {
                    const value = event.currentTarget.value;
                    setDraft((current) => current ? { ...current, name: value } : current);
                  }}
                  value={draft?.name ?? ""}
                />
              </label>
            </div>
            <div className="flex items-center gap-2">
              <Button onClick={() => setPositions(defaultPositions(draft?.blocks ?? []))} variant="outline">
                <Workflow className="h-4 w-4" />
                Автолэйаут
              </Button>
              <Button onClick={() => setShowGrid((value) => !value)} variant="outline">
                <ListFilter className="h-4 w-4" />
                Сетка
              </Button>
              <Button disabled={!canSave || saveMutation.isPending} onClick={saveOrderedDraft}>
                <Save className="h-4 w-4" />
                {saveMutation.isPending ? "Сохраняем..." : "Опубликовать"}
              </Button>
            </div>
          </header>

          {!publishAccess.allowed ? (
            <div className="mx-4 mt-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              {publishAccess.reason}
            </div>
          ) : null}

          {feedback ? (
            <div
              className={cn(
                "mx-4 mt-3 rounded-lg border px-4 py-3 text-sm",
                feedback.tone === "success"
                  ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                  : "border-rose-200 bg-rose-50 text-rose-700"
              )}
            >
              {feedback.text}
            </div>
          ) : null}

          <div className="grid min-h-0 flex-1 grid-cols-1 xl:grid-cols-[minmax(0,1fr)_336px]">
            <main className="min-w-0 bg-slate-50">
              <div className="border-b border-slate-200 bg-white px-4 py-2">
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <MousePointer2 className="h-4 w-4 text-blue-600" />
                  Перетащите команду из палитры на сетку или перемещайте блоки внутри canvas.
                </div>
              </div>
              <div className="overflow-auto p-4">
                <div
                  className={cn(
                    "relative rounded-lg border border-slate-200 bg-white shadow-inner",
                    showGrid ? "playbook-canvas-grid" : ""
                  )}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={handleCanvasDrop}
                  ref={canvasRef}
                  style={{ height: CANVAS_HEIGHT, width: CANVAS_WIDTH }}
                >
                  <ConnectorLayer blocks={draft?.blocks ?? []} positions={positions} />
                  <div
                    className="absolute rounded-lg border border-emerald-200 bg-white px-4 py-3 shadow-sm"
                    style={{ left: START_NODE.x, top: START_NODE.y, width: START_NODE.width }}
                  >
                    <div className="flex items-center gap-3">
                      <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
                        <Play className="h-5 w-5" />
                      </span>
                      <div>
                        <p className="text-sm font-semibold text-slate-950">Старт</p>
                        <p className="text-xs text-slate-500">Начало выполнения плейбука</p>
                      </div>
                    </div>
                  </div>
                  {draft?.blocks.map((block) => (
                    <PlaybookBlockNode
                      block={block}
                      catalog={diagnosticModules}
                      isSelected={selectedBlock?.id === block.id}
                      key={block.id}
                      onSelect={() => setSelectedBlockId(block.id)}
                      onStartDrag={setDraggedBlockId}
                      onToolChange={(item) => updateBlockTool(block.id, item)}
                      position={positions[block.id] ?? { x: 338, y: 160 }}
                    />
                  ))}
                </div>
              </div>
              <div className="border-t border-slate-200 bg-white px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Результат выполнения</p>
                    <p className="text-sm text-slate-600">Preview нормализованного результата выбранного блока</p>
                  </div>
                  <div className="flex rounded-lg bg-slate-100 p-1 text-xs">
                    <span className="rounded-md bg-white px-3 py-1 font-medium text-blue-700 shadow-sm">JSON</span>
                    <span className="px-3 py-1 text-slate-500">Переменные</span>
                    <span className="px-3 py-1 text-slate-500">Логи</span>
                  </div>
                </div>
                <pre className="mt-3 max-h-[180px] overflow-auto rounded-lg bg-slate-950 p-4 text-xs leading-5 text-emerald-100">
                  {sampleJson}
                </pre>
              </div>
            </main>

            <aside className="border-l border-slate-200 bg-white">
              <div className="border-b border-slate-200 px-4 py-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
                      <Settings2 className="h-5 w-5" />
                    </span>
                    <div>
                      <p className="text-sm font-semibold text-slate-950">Свойства блока</p>
                      <p className="text-xs text-slate-500">{selectedBlock?.id ?? "Выберите блок"}</p>
                    </div>
                  </div>
                  <ChevronDown className="h-4 w-4 text-slate-400" />
                </div>
              </div>
              {selectedBlock ? (
                <div className="max-h-[820px] space-y-5 overflow-y-auto px-4 py-4">
                  <div className="grid grid-cols-3 gap-2 rounded-lg bg-slate-100 p-1 text-xs">
                    <button className="rounded-md bg-white px-2 py-2 font-medium text-blue-700 shadow-sm" type="button">
                      Настройки
                    </button>
                    <button className="rounded-md px-2 py-2 text-slate-500" type="button">
                      Выходы
                    </button>
                    <button className="rounded-md px-2 py-2 text-slate-500" type="button">
                      Ошибки
                    </button>
                  </div>

                  <label className="block space-y-2">
                    <FieldLabel>Название</FieldLabel>
                    <input
                      className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-blue-400"
                      onChange={(event) => updateBlock(selectedBlock.id, { label: event.currentTarget.value })}
                      value={selectedBlock.label}
                    />
                  </label>

                  {selectedBlock.type === "diagnostic" ? (
                    <label className="block space-y-2">
                      <FieldLabel>Команда модуля</FieldLabel>
                      <select
                        aria-label="Команда модуля"
                        className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-blue-400"
                        onChange={(event) => {
                          const item = diagnosticModules.find((candidate) => candidate.id === event.currentTarget.value);
                          if (item) {
                            updateBlockTool(selectedBlock.id, item);
                          }
                        }}
                        value={selectedBlock.tool_manifest?.id ?? ""}
                      >
                        {diagnosticModules.map((item) => (
                          <option key={item.id} value={item.id}>
                            {item.tool ?? item.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  ) : null}

                  {selectedBlock.tool_manifest?.presets?.length ? (
                    <label className="block space-y-2">
                      <FieldLabel>Preset</FieldLabel>
                      <select
                        className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-blue-400"
                        onChange={(event) => {
                          const value = event.currentTarget.value;
                          const preset = selectedBlock.tool_manifest?.presets?.find(
                            (item) => (item.preset_id ?? item.id) === value
                          );
                          updateBlock(selectedBlock.id, {
                            preset_id: value || null,
                            params: preset?.params ? { ...preset.params } : {},
                          });
                        }}
                        value={selectedBlock.preset_id ?? ""}
                      >
                        <option value="">Manual params</option>
                        {selectedBlock.tool_manifest.presets.map((preset) => {
                          const presetId = preset.preset_id ?? preset.id ?? "";
                          return (
                            <option key={presetId} value={presetId}>
                              {preset.label ?? presetId}
                            </option>
                          );
                        })}
                      </select>
                    </label>
                  ) : null}

                  {selectedBlock.type === "decision" ? (
                    <>
                      <label className="block space-y-2">
                        <FieldLabel>Условие</FieldLabel>
                        <input
                          className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-blue-400"
                          onChange={(event) => updateBlock(selectedBlock.id, { condition: event.currentTarget.value })}
                          value={selectedBlock.condition ?? ""}
                        />
                      </label>
                      <label className="block space-y-2">
                        <FieldLabel>Быстрый шаблон</FieldLabel>
                        <select
                          aria-label="Quick condition template"
                          className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-blue-400"
                          onChange={(event) => {
                            const value = event.currentTarget.value;
                            if (value) {
                              updateBlock(selectedBlock.id, { condition: value });
                            }
                          }}
                          value=""
                        >
                          <option value="">Выбрать вывод...</option>
                          {quickConditionOptions(orderedBlocks, selectedOrderedIndex).map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                    </>
                  ) : (
                    <div className="space-y-3">
                      <div>
                        <FieldLabel>Параметры команды</FieldLabel>
                        <p className="mt-1 text-xs leading-5 text-slate-500">
                          Настройки формируются из manifest schema и будут сохранены как params payload.
                        </p>
                      </div>
                      <SchemaParamEditor
                        fields={selectedParamFields}
                        onChange={(params) => updateBlock(selectedBlock.id, { params })}
                        value={selectedBlock.params}
                      />
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-3">
                    <label className="block space-y-2">
                      <FieldLabel>Таймаут</FieldLabel>
                      <input
                        className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-blue-400"
                        min={0}
                        onChange={(event) => {
                          const value = event.currentTarget.value;
                          updateBlock(selectedBlock.id, {
                            timeout_sec: value ? Number(value) : null,
                          });
                        }}
                        type="number"
                        value={selectedBlock.timeout_sec ?? ""}
                      />
                    </label>
                    <label className="flex items-end gap-2 pb-2 text-sm text-slate-700">
                      <input
                        checked={Boolean(selectedBlock.continue_on_error)}
                        className="h-4 w-4"
                        onChange={(event) =>
                          updateBlock(selectedBlock.id, { continue_on_error: event.currentTarget.checked })
                        }
                        type="checkbox"
                      />
                      Продолжать при ошибке
                    </label>
                  </div>

                  <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
                    <div className="flex items-center gap-2">
                      <Code2 className="h-4 w-4 text-blue-600" />
                      <p className="text-sm font-semibold text-slate-900">Output contract</p>
                    </div>
                    <dl className="mt-3 space-y-2 text-xs text-slate-600">
                      <div className="flex justify-between gap-3">
                        <dt>Status path</dt>
                        <dd className="font-mono text-slate-900">{selectedContract.statusPath}</dd>
                      </div>
                      <div className="flex justify-between gap-3">
                        <dt>Values</dt>
                        <dd className="font-mono text-slate-900">{selectedContract.statusValues.join(", ")}</dd>
                      </div>
                      <div className="flex justify-between gap-3">
                        <dt>Summary</dt>
                        <dd className="font-mono text-slate-900">{selectedContract.summaryPath}</dd>
                      </div>
                    </dl>
                    {selectedContract.errorCodes.length ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {selectedContract.errorCodes.map((code) => (
                          <Badge key={code}>{code}</Badge>
                        ))}
                      </div>
                    ) : null}
                  </div>

                  <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-3 text-sm text-emerald-800">
                    <div className="flex items-center gap-2 font-semibold">
                      <CheckCircle2 className="h-4 w-4" />
                      Только диагностика
                    </div>
                    <p className="mt-2 leading-5">
                      Эти блоки собирают факты. Исправляющие действия останутся отдельным подтверждаемым flow.
                    </p>
                  </div>

                  <Button
                    className="w-full border-rose-200 text-rose-600 hover:bg-rose-50"
                    disabled={!publishAccess.allowed}
                    onClick={() => {
                      if (!publishAccess.allowed) {
                        return;
                      }
                      setDraft((current) =>
                        current
                          ? { ...current, blocks: current.blocks.filter((block) => block.id !== selectedBlock.id) }
                          : current
                      );
                      setPositions((current) => {
                        const next = { ...current };
                        delete next[selectedBlock.id];
                        return next;
                      });
                      setSelectedBlockId(null);
                    }}
                    variant="outline"
                  >
                    <Trash2 className="h-4 w-4" />
                    Удалить блок
                  </Button>
                </div>
              ) : (
                <div className="px-4 py-10 text-center text-sm text-slate-500">
                  Выберите блок на canvas, чтобы настроить команду, параметры и выходы.
                </div>
              )}
            </aside>
          </div>
        </div>
      </div>

      <style>{`
        .playbook-canvas-grid {
          background-image: radial-gradient(circle, rgba(148, 163, 184, 0.45) 1px, transparent 1px);
          background-size: 18px 18px;
        }
      `}</style>
    </section>
  );
}
