import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, CheckCircle2, GitBranch, Plus, Save } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
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

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 48);
}

function blockFromCatalog(item: AdminPlaybookBlockCatalogItem): AdminPlaybookDraftBlock {
  return {
    id: item.id.replace(/[^a-z0-9_]+/gi, "_"),
    type: "diagnostic",
    module_kind: "diagnostic",
    tool: item.tool,
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

function decisionBlock(index: number): AdminPlaybookDraftBlock {
  return {
    id: `decision_${index}`,
    type: "decision",
    module_kind: "diagnostic",
    tool: null,
    label: "Проверка результата",
    params: {},
    condition: "steps.system_collect.status == 'success'",
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
  return {
    key: slugify(template.key) || "diagnostic_playbook",
    name: template.title,
    domain: "diagnostics",
    blocks: template.block_ids
      .map((blockId) => byId.get(blockId))
      .filter((item): item is AdminPlaybookBlockCatalogItem => Boolean(item))
      .map(blockFromCatalog),
  };
}

function moveBlock(blocks: AdminPlaybookDraftBlock[], index: number, direction: -1 | 1) {
  const nextIndex = index + direction;
  if (nextIndex < 0 || nextIndex >= blocks.length) {
    return blocks;
  }
  const next = [...blocks];
  const [item] = next.splice(index, 1);
  next.splice(nextIndex, 0, item);
  return next;
}

function stringifyParams(params: Record<string, unknown>): string {
  return JSON.stringify(params ?? {}, null, 2);
}

function parseParamsJson(value: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(value || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed as Record<string, unknown> : null;
  } catch {
    return null;
  }
}

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => String(item ?? "").trim()).filter(Boolean)
    : [];
}

function outputContractSummary(item: AdminPlaybookBlockCatalogItem) {
  const contract = item.output_contract ?? {};
  const statusPath = String(contract.status_path ?? item.condition_hints?.status_path ?? "result.status");
  const statusValues = stringList(contract.status_values ?? item.condition_hints?.status_values);
  const summaryPath = String(contract.summary_path ?? item.condition_hints?.summary_path ?? "result.output.summary");
  const errorCodes = stringList(item.error_codes ?? item.condition_hints?.error_codes);
  return {
    statusPath,
    statusValues: statusValues.length ? statusValues : ["ok", "error"],
    summaryPath,
    errorCodes,
  };
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

function OutputContractPreview({ item }: { item: AdminPlaybookBlockCatalogItem }) {
  const summary = outputContractSummary(item);
  return (
    <div className="mt-3 grid gap-2 rounded-[0.7rem] border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 md:grid-cols-3">
      <div>
        <span className="block font-semibold text-slate-800">Status path</span>
        <code>{summary.statusPath}</code>
      </div>
      <div>
        <span className="block font-semibold text-slate-800">Values</span>
        <code>{summary.statusValues.join(", ")}</code>
      </div>
      <div>
        <span className="block font-semibold text-slate-800">Summary path</span>
        <code>{summary.summaryPath}</code>
      </div>
      {summary.errorCodes.length ? (
        <div className="md:col-span-3">
          <span className="block font-semibold text-slate-800">Error codes</span>
          <code>{summary.errorCodes.join(", ")}</code>
        </div>
      ) : null}
    </div>
  );
}

export function PlaybookBuilderPanel() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<AdminPlaybookDraftRequest | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);

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

  useEffect(() => {
    if (draft || !catalogQuery.data?.scenario_templates.length) {
      return;
    }
    setDraft(
      buildDraftFromTemplate(
        catalogQuery.data.scenario_templates[0],
        catalogQuery.data.block_catalog
      )
    );
  }, [catalogQuery.data, draft]);

  const blockCatalog = catalogQuery.data?.block_catalog ?? [];
  const templates = catalogQuery.data?.scenario_templates ?? [];
  const existingPlaybooks = catalogQuery.data?.playbooks ?? [];
  const canSave = Boolean(draft?.key.trim() && draft?.name.trim() && draft.blocks.length);

  const diagnosticModules = useMemo(
    () => blockCatalog.filter((item) => item.module_kind === "diagnostic"),
    [blockCatalog]
  );

  return (
    <section className="space-y-6">
      <Card>
        <CardHeader className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <CardTitle>Конструктор плейбуков</CardTitle>
            <CardDescription>
              Диагностические сценарии собираются из безопасных модулей, условий и отчётных блоков.
            </CardDescription>
          </div>
          <Button
            disabled={!canSave || saveMutation.isPending}
            onClick={() => draft && saveMutation.mutate(draft)}
          >
            <Save className="h-4 w-4" />
            {saveMutation.isPending ? "Сохраняем..." : "Сохранить плейбук"}
          </Button>
        </CardHeader>
        <CardContent className="space-y-5">
          {feedback ? (
            <div
              className={cn(
                "rounded-[0.8rem] border px-4 py-3 text-sm",
                feedback.tone === "success"
                  ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                  : "border-rose-200 bg-rose-50 text-rose-700"
              )}
            >
              {feedback.text}
            </div>
          ) : null}

          {catalogQuery.isLoading ? (
            <div className="rounded-[0.8rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
              Загружаем каталог диагностических модулей.
            </div>
          ) : null}

          <div className="grid gap-4 xl:grid-cols-[300px_minmax(0,1fr)_280px]">
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-700">Сценарии</p>
              {templates.map((template) => (
                <button
                  aria-label={template.title}
                  className={cn(
                    "w-full rounded-[0.8rem] border border-border bg-white px-4 py-3 text-left transition hover:border-brand-300 hover:bg-brand-50/40",
                    draft?.key === template.key ? "border-brand-300 bg-brand-50/60" : ""
                  )}
                  key={template.key}
                  onClick={() => {
                    setFeedback(null);
                    setDraft(buildDraftFromTemplate(template, blockCatalog));
                  }}
                  type="button"
                >
                  <span className="block text-sm font-semibold text-slate-950">{template.title}</span>
                  <span className="mt-1 block text-xs leading-5 text-slate-500">{template.problem}</span>
                </button>
              ))}
            </div>

            <div className="space-y-4">
              <div className="grid gap-3 md:grid-cols-2">
                <label className="space-y-2 text-sm font-medium text-slate-800">
                  <span>Ключ</span>
                  <input
                    className="field-base h-11 w-full px-4 text-sm"
                    onChange={(event) =>
                      setDraft((current) =>
                        current ? { ...current, key: slugify(event.currentTarget.value) } : current
                      )
                    }
                    value={draft?.key ?? ""}
                  />
                </label>
                <label className="space-y-2 text-sm font-medium text-slate-800">
                  <span>Название</span>
                  <input
                    className="field-base h-11 w-full px-4 text-sm"
                    onChange={(event) =>
                      setDraft((current) =>
                        current ? { ...current, name: event.currentTarget.value } : current
                      )
                    }
                    value={draft?.name ?? ""}
                  />
                </label>
              </div>

              <div className="space-y-3">
                {draft?.blocks.map((block, index) => (
                  <article
                    className="rounded-[0.8rem] border border-border bg-white px-4 py-4"
                    draggable
                    key={`${block.id}-${index}`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <strong className="text-sm text-slate-950">{block.label}</strong>
                          <Badge>{block.type === "decision" ? "Условие" : "Диагностика"}</Badge>
                        </div>
                        <p className="mt-1 text-xs text-slate-500">
                          {block.tool ?? "Локальный блок"} · {block.module_kind}
                        </p>
                        {block.tool_manifest ? (
                          <>
                            <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-500">
                              <Badge>{block.tool_manifest.module_name ?? "builtin"}</Badge>
                              <Badge>{block.install_policy ?? "preinstalled"}</Badge>
                              {block.tool_manifest.supported_platforms?.length ? (
                                <Badge>{block.tool_manifest.supported_platforms.join(", ")}</Badge>
                              ) : null}
                              {block.tool_manifest.min_agent_version ? (
                                <Badge>{`agent >= ${block.tool_manifest.min_agent_version}`}</Badge>
                              ) : null}
                            </div>
                            <OutputContractPreview item={block.tool_manifest} />
                          </>
                        ) : null}
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          aria-label={`Поднять блок ${block.label}`}
                          disabled={index === 0}
                          onClick={() =>
                            setDraft((current) =>
                              current ? { ...current, blocks: moveBlock(current.blocks, index, -1) } : current
                            )
                          }
                          size="icon"
                          variant="outline"
                        >
                          <ArrowUp className="h-4 w-4" />
                        </Button>
                        <Button
                          aria-label={`Опустить блок ${block.label}`}
                          disabled={index === draft.blocks.length - 1}
                          onClick={() =>
                            setDraft((current) =>
                              current ? { ...current, blocks: moveBlock(current.blocks, index, 1) } : current
                            )
                          }
                          size="icon"
                          variant="outline"
                        >
                          <ArrowDown className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                    {block.tool_manifest?.presets?.length ? (
                      <label className="mt-4 block space-y-2 text-sm font-medium text-slate-800">
                        <span>Preset</span>
                        <select
                          className="field-base h-11 w-full px-4 text-sm"
                          onChange={(event) => {
                            const value = event.currentTarget.value;
                            const preset = block.tool_manifest?.presets?.find(
                              (item) => (item.preset_id ?? item.id) === value
                            );
                            setDraft((current) =>
                              current
                                ? {
                                    ...current,
                                    blocks: current.blocks.map((item, itemIndex) =>
                                      itemIndex === index
                                        ? {
                                            ...item,
                                            preset_id: value || null,
                                            params: preset?.params ? { ...preset.params } : {},
                                          }
                                        : item
                                    ),
                                  }
                                : current
                            );
                          }}
                          value={block.preset_id ?? ""}
                        >
                          <option value="">Manual params</option>
                          {block.tool_manifest.presets.map((preset) => {
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
                    {block.tool ? (
                      <label className="mt-4 block space-y-2 text-sm font-medium text-slate-800">
                        <span>Params JSON</span>
                        <textarea
                          className="field-base min-h-[110px] w-full resize-y px-4 py-3 font-mono text-xs"
                          onChange={(event) => {
                            const parsed = parseParamsJson(event.currentTarget.value);
                            if (parsed === null) {
                              return;
                            }
                            setDraft((current) =>
                              current
                                ? {
                                    ...current,
                                    blocks: current.blocks.map((item, itemIndex) =>
                                      itemIndex === index ? { ...item, params: parsed } : item
                                    ),
                                  }
                                : current
                            );
                          }}
                          value={stringifyParams(block.params)}
                        />
                      </label>
                    ) : null}
                    {block.type === "decision" ? (
                      <label className="mt-4 block space-y-2 text-sm font-medium text-slate-800">
                        <span>Условие продолжения</span>
                        <input
                          className="field-base h-11 w-full px-4 text-sm"
                          onChange={(event) => {
                            const value = event.currentTarget.value;
                            setDraft((current) =>
                              current
                                ? {
                                    ...current,
                                    blocks: current.blocks.map((item, itemIndex) =>
                                      itemIndex === index ? { ...item, condition: value } : item
                                    ),
                                  }
                                : current
                            );
                          }}
                          value={block.condition ?? ""}
                        />
                      </label>
                    ) : null}
                    {block.type === "decision" ? (
                      <label className="mt-3 block space-y-2 text-sm font-medium text-slate-800">
                        <span>Quick condition</span>
                        <select
                          aria-label="Quick condition template"
                          className="field-base h-11 w-full px-4 text-sm"
                          onChange={(event) => {
                            const value = event.currentTarget.value;
                            if (!value) {
                              return;
                            }
                            setDraft((current) =>
                              current
                                ? {
                                    ...current,
                                    blocks: current.blocks.map((item, itemIndex) =>
                                      itemIndex === index ? { ...item, condition: value } : item
                                    ),
                                  }
                                : current
                            );
                          }}
                          value=""
                        >
                          <option value="">Select output...</option>
                          {quickConditionOptions(draft.blocks, index).map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                    ) : null}
                  </article>
                ))}
              </div>

              <div className="flex flex-wrap gap-3">
                <Button
                  onClick={() =>
                    setDraft((current) =>
                      current
                        ? {
                            ...current,
                            blocks: [...current.blocks, decisionBlock(current.blocks.length + 1)],
                          }
                        : current
                    )
                  }
                  variant="outline"
                >
                  <GitBranch className="h-4 w-4" />
                  Добавить условие
                </Button>
                {diagnosticModules.map((item) => (
                  <Button
                    aria-label={`Добавить блок ${item.label}`}
                    key={item.id}
                    onClick={() =>
                      setDraft((current) =>
                        current
                          ? { ...current, blocks: [...current.blocks, blockFromCatalog(item)] }
                          : current
                      )
                    }
                    variant="outline"
                  >
                    <Plus className="h-4 w-4" />
                    Добавить: {item.label}
                  </Button>
                ))}
              </div>
            </div>

            <aside className="space-y-4">
              <div className="rounded-[0.8rem] border border-border bg-surface-subtle px-4 py-4">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  <p className="font-semibold text-slate-900">Только диагностика</p>
                </div>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  Блоки не меняют устройство. Модули с логами могут запросить согласие агента.
                </p>
              </div>
              <div className="rounded-[0.8rem] border border-border bg-white px-4 py-4">
                <p className="font-semibold text-slate-900">Опубликованные</p>
                <div className="mt-3 space-y-3 text-sm">
                  {existingPlaybooks.length ? (
                    existingPlaybooks.map((item) => (
                      <div key={item.key} className="flex items-center justify-between gap-3">
                        <span className="text-slate-600">{item.name}</span>
                        <code className="text-xs text-slate-500">{item.version ?? "draft"}</code>
                      </div>
                    ))
                  ) : (
                    <p className="text-slate-500">Пока нет опубликованных плейбуков.</p>
                  )}
                </div>
              </div>
            </aside>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
