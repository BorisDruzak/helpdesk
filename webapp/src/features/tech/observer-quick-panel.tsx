import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  GitBranchPlus,
  RefreshCcw,
} from "lucide-react";
import { startTransition, useDeferredValue, useEffect, useMemo, useState } from "react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { SearchField } from "../../components/ui/search-field";
import { Select } from "../../components/ui/select";
import { Tabs } from "../../components/ui/tabs";
import { cn } from "../../shared/ui/cn";
import {
  fetchObserverDegradations,
  fetchObserverDiagnosticsBundle,
  fetchObserverRuntime,
  fetchObserverSettings,
  fetchObserverSignatureDetail,
  fetchObserverSignatures,
  fetchObserverWorkbenchQuick,
  fetchObserverWorkbenchTraceDetail,
  fetchObserverWorkbenchTraces,
  rebuildObserverTraces,
  saveObserverSettings,
  type ObserverAgentActionItem,
  type ObserverDegradationItem,
  type ObserverDiagnosticsBundlePayload,
  type ObserverSignatureListItem,
  type ObserverTraceDetailPayload,
} from "./observer-workbench-api";
import {
  type AdminObserverRootKindFilter,
  type AdminObserverTraceItem,
  type AdminObserverTraceStatusFilter,
} from "./api";

const LOOKBACK_OPTIONS = [
  { hours: 6, label: "6 часов" },
  { hours: 24, label: "24 часа" },
  { hours: 72, label: "72 часа" },
] as const;

const OBSERVER_TABS = [
  { value: "quick", label: "Обзор" },
  { value: "traces", label: "Трассы" },
  { value: "signatures", label: "Сигнатуры" },
  { value: "degradations", label: "Деградации" },
  { value: "runtime", label: "Runtime" },
] as const;

type ObserverTab = (typeof OBSERVER_TABS)[number]["value"];

type ObserverSettingsDraft = {
  successTraceSampleRate: string;
  okTraceRetentionHours: string;
  errorTraceRetentionHours: string;
  historicalBackfillEnabled: boolean;
  actionSyncEnabled: boolean;
  actionSyncLimit: string;
  alwaysKeepRootKinds: string;
};

type ActionFeedback =
  | {
      tone: "success" | "error";
      text: string;
    }
  | null;

type ObserverQuickPanelProps = {
  deviceId: string | null;
  deviceLabel: string;
};

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "Нет данных";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatDuration(value: number | null | undefined): string {
  if (value == null || value <= 0) {
    return "Нет данных";
  }
  if (value < 1000) {
    return `${Math.round(value)} мс`;
  }
  return `${(value / 1000).toFixed(1)} с`;
}

function formatPercent(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) {
    return "0%";
  }
  const normalized = value > 1 ? value : value * 100;
  return `${Math.round(normalized)}%`;
}

function formatRuntimeStatValue(value: unknown): string {
  if (value == null) {
    return "Нет данных";
  }
  if (typeof value === "boolean") {
    return value ? "Да" : "Нет";
  }
  return String(value);
}

function compactActionValue(value: unknown): string {
  if (value == null) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function getStatusTone(status: string | null | undefined) {
  switch (String(status ?? "").trim().toLowerCase()) {
    case "healthy":
    case "up":
    case "ok":
    case "succeeded":
    case "success":
      return "success" as const;
    case "running":
    case "queued":
    case "accepted":
      return "brand" as const;
    case "warning":
    case "degraded":
      return "warning" as const;
    case "timed_out":
    case "failed":
    case "error":
    case "down":
      return "danger" as const;
    default:
      return "neutral" as const;
  }
}

function traceMatchesSearch(trace: AdminObserverTraceItem, query: string): boolean {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return [
    trace.trace_id,
    trace.root_kind_label,
    trace.status_label,
    trace.ticket_id ?? "",
    trace.operation_id ?? "",
    trace.device_id ?? "",
    trace.job_id ?? "",
  ].some((value) => value.toLowerCase().includes(normalized));
}

function signatureMatchesSearch(signature: ObserverSignatureListItem, query: string): boolean {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return [
    signature.error_signature,
    signature.title ?? "",
    signature.component ?? "",
    signature.module_name ?? "",
    signature.tool_name ?? "",
  ].some((value) => value.toLowerCase().includes(normalized));
}

function degradationMatchesSearch(item: ObserverDegradationItem, query: string): boolean {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return [
    item.operation_kind ?? "",
    item.operation_kind_label ?? "",
    item.module_name ?? "",
    item.tool_name ?? "",
  ].some((value) => value.toLowerCase().includes(normalized));
}

function degradationKey(item: ObserverDegradationItem): string {
  return `${item.operation_kind ?? "unknown"}:${item.tool_name ?? item.module_name ?? "item"}`;
}

function settingsToDraft(settings: Record<string, unknown>): ObserverSettingsDraft {
  return {
    successTraceSampleRate: String(settings.success_trace_sample_rate ?? 0.35),
    okTraceRetentionHours: String(settings.ok_trace_retention_hours ?? 24),
    errorTraceRetentionHours: String(settings.error_trace_retention_hours ?? 168),
    historicalBackfillEnabled: Boolean(settings.historical_backfill_enabled ?? true),
    actionSyncEnabled: Boolean(settings.action_sync_enabled ?? true),
    actionSyncLimit: String(settings.action_sync_limit ?? 120),
    alwaysKeepRootKinds: Array.isArray(settings.always_keep_root_kinds)
      ? settings.always_keep_root_kinds.map((item) => String(item)).join(", ")
      : String(settings.always_keep_root_kinds ?? "ticket, agent_update, module_install, consent"),
  };
}

function draftToSettings(draft: ObserverSettingsDraft): Record<string, unknown> {
  return {
    success_trace_sample_rate: Number.parseFloat(draft.successTraceSampleRate) || 0,
    ok_trace_retention_hours: Number.parseInt(draft.okTraceRetentionHours, 10) || 1,
    error_trace_retention_hours: Number.parseInt(draft.errorTraceRetentionHours, 10) || 1,
    historical_backfill_enabled: draft.historicalBackfillEnabled,
    action_sync_enabled: draft.actionSyncEnabled,
    action_sync_limit: Number.parseInt(draft.actionSyncLimit, 10) || 1,
    always_keep_root_kinds: draft.alwaysKeepRootKinds
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  };
}

function buildSettingsFingerprint(draft: ObserverSettingsDraft | null): string {
  return JSON.stringify(draftToSettings(draft ?? settingsToDraft({})));
}

function ActionFeedbackBanner({ feedback }: { feedback: ActionFeedback }) {
  if (!feedback) {
    return null;
  }
  return (
    <div
      className={cn(
        "rounded-[1.1rem] border px-4 py-3 text-sm shadow-soft",
        feedback.tone === "success"
          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
          : "border-rose-200 bg-rose-50 text-rose-700",
      )}
    >
      {feedback.text}
    </div>
  );
}

function TraceList({
  emptyText,
  items,
  loading,
  selectedTraceId,
  onSelect,
}: {
  emptyText: string;
  items: AdminObserverTraceItem[];
  loading?: boolean;
  selectedTraceId: string | null;
  onSelect: (traceId: string) => void;
}) {
  if (loading) {
    return (
      <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
        Загружаем трассы...
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
        {emptyText}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {items.map((trace) => {
        const active = trace.trace_id === selectedTraceId;

        return (
          <button
            key={trace.trace_id}
            className={cn(
              "w-full rounded-[1.1rem] border px-4 py-4 text-left transition-colors",
              active
                ? "border-brand-200 bg-brand-50"
                : "border-border bg-white hover:border-brand-100 hover:bg-surface-subtle",
            )}
            onClick={() => onSelect(trace.trace_id)}
            type="button"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-semibold text-slate-950">{trace.root_kind_label}</p>
                <p className="mt-1 truncate text-xs text-slate-500">{trace.trace_id}</p>
              </div>
              <Badge tone={getStatusTone(trace.status)}>{trace.status_label}</Badge>
            </div>
            <p className="mt-3 text-sm text-slate-600">
              Ошибок: {trace.error_count} • spans: {trace.span_count} • длительность:{" "}
              {formatDuration(trace.duration_ms)}
            </p>
            <p className="mt-2 text-xs text-slate-500">
              {trace.ticket_id ? `Тикет ${trace.ticket_id}` : "Без тикета"}
              {trace.operation_id ? ` • операция ${trace.operation_id}` : ""}
            </p>
            <p className="mt-1 text-xs text-slate-400">
              Завершена: {formatDateTime(trace.finished_at ?? trace.started_at)}
            </p>
          </button>
        );
      })}
    </div>
  );
}

function TraceDetailCard({
  bundle,
  bundleError,
  detail,
  error,
  isBundleLoading,
  isLoading,
}: {
  bundle: ObserverDiagnosticsBundlePayload | undefined;
  bundleError?: unknown;
  detail: ObserverTraceDetailPayload | undefined;
  error?: unknown;
  isBundleLoading: boolean;
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-sm text-slate-500">
        Загружаем детали выбранной трассы...
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-[1.1rem] border border-rose-200 bg-rose-50 px-5 py-10 text-sm text-rose-700">
        Не удалось загрузить детали трассы: {error instanceof Error ? error.message : "неизвестная ошибка"}.
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-sm text-slate-500">
        Выберите трассу слева, чтобы открыть spans, ошибки, связи и agent actions.
      </div>
    );
  }

  const agentActions =
    Array.isArray(bundle?.agent_actions) && bundle.agent_actions.length
      ? bundle.agent_actions
      : Array.isArray(detail.agent_actions)
        ? (detail.agent_actions as ObserverAgentActionItem[])
        : [];
  const agentActionsError = bundle?.agent_actions_error ?? detail.agent_actions_error;

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
          <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Статус</p>
          <div className="mt-3 flex items-center gap-3">
            <Badge tone={getStatusTone(detail.trace.status)}>{detail.trace.status_label}</Badge>
            <span className="text-sm text-slate-500">{detail.trace.root_kind_label}</span>
          </div>
        </div>
        <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
          <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Спаны и ошибки</p>
          <p className="mt-3 text-xl font-semibold text-slate-950">
            {detail.summary.span_count} / {detail.summary.error_count}
          </p>
          <p className="mt-2 text-sm text-slate-500">
            Связанных трасс: {detail.summary.linked_trace_count}
          </p>
        </div>
        <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
          <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Длительность</p>
          <p className="mt-3 text-xl font-semibold text-slate-950">
            {formatDuration(detail.trace.duration_ms)}
          </p>
          <p className="mt-2 text-sm text-slate-500">
            Завершена: {formatDateTime(detail.trace.finished_at ?? detail.trace.started_at)}
          </p>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Card className="overflow-hidden">
          <CardHeader>
            <CardTitle>Span timeline</CardTitle>
            <CardDescription>
              Видим реальные spans, их источники, длительность и контекст текущей трассы.
            </CardDescription>
          </CardHeader>
          <CardContent className="max-h-[min(56vh,44rem)] space-y-3 overflow-y-auto pr-2">
            {detail.spans.length ? (
              detail.spans.map((span) => (
                <article key={span.span_id} className="rounded-[1rem] border border-border bg-white px-4 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-semibold text-slate-950">{span.name}</p>
                      <p className="mt-1 text-xs text-slate-500">{span.span_id}</p>
                    </div>
                    <Badge tone={getStatusTone(span.status)}>{span.status_label ?? span.status ?? "unknown"}</Badge>
                  </div>
                  <p className="mt-3 text-sm text-slate-600">
                    {span.component ?? "Компонент не указан"}
                    {span.tool_name ? ` • ${span.tool_name}` : ""}
                    {span.module_name ? ` • ${span.module_name}` : ""}
                  </p>
                  <p className="mt-2 text-sm text-slate-500">
                    Источник: {span.source_type ?? "unknown"}
                    {span.source_ref ? ` • ${span.source_ref}` : ""}
                  </p>
                  <p className="mt-2 text-sm text-slate-500">
                    Длительность: {formatDuration(span.duration_ms)}
                  </p>
                </article>
              ))
            ) : (
              <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
                Внутри трассы пока нет spans.
              </div>
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card className="overflow-hidden">
            <CardHeader>
              <CardTitle>Diagnostic bundle</CardTitle>
              <CardDescription>
                Trace, ticket, device, logs, audit and next checks in one payload for production debugging.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {isBundleLoading ? (
                <div className="rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-6 text-sm text-slate-500">
                  Собираем bundle...
                </div>
              ) : null}
              {bundleError ? (
                <div className="rounded-[1rem] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                  Bundle не собран: {bundleError instanceof Error ? bundleError.message : "неизвестная ошибка"}.
                </div>
              ) : null}

              {bundle ? (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-[1rem] border border-border bg-surface-subtle px-3 py-3">
                      <p className="text-xs uppercase tracking-[0.16em] text-brand-700">Logs</p>
                      <p className="mt-2 text-lg font-semibold text-slate-950">{bundle.summary.recent_log_count ?? 0}</p>
                    </div>
                    <div className="rounded-[1rem] border border-border bg-surface-subtle px-3 py-3">
                      <p className="text-xs uppercase tracking-[0.16em] text-brand-700">Audit</p>
                      <p className="mt-2 text-lg font-semibold text-slate-950">{bundle.summary.agent_audit_count ?? 0}</p>
                    </div>
                  </div>
                  <div className="space-y-2">
                    {(bundle.recommended_next_checks ?? []).slice(0, 4).map((item) => (
                      <p key={item} className="rounded-[1rem] border border-border bg-white px-3 py-2 text-sm text-slate-600">
                        {item}
                      </p>
                    ))}
                  </div>
                  {bundle.links?.trace_detail ? (
                    <p className="break-all text-xs text-slate-400">{bundle.links.trace_detail}</p>
                  ) : null}
                </>
              ) : (
                <div className="rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-6 text-sm text-slate-500">
                  Bundle появится после выбора трассы.
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="overflow-hidden">
            <CardHeader>
              <CardTitle>Ошибки и связи</CardTitle>
              <CardDescription>
                Сигнатуры, severity и связанные span links для быстрого расследования.
              </CardDescription>
            </CardHeader>
            <CardContent className="max-h-[min(28vh,18rem)] space-y-3 overflow-y-auto pr-2">
              {detail.error_occurrences.length ? (
                detail.error_occurrences.map((occurrence) => (
                  <article key={occurrence.occurrence_id} className="rounded-[1rem] border border-border bg-white px-4 py-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-semibold text-slate-950">{occurrence.error_signature}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          {occurrence.exception_type ?? occurrence.error_kind ?? "Ошибка"}
                        </p>
                      </div>
                      <Badge tone={getStatusTone(occurrence.severity)}>{occurrence.severity_label ?? occurrence.severity ?? "info"}</Badge>
                    </div>
                    <p className="mt-3 text-sm text-slate-600">
                      {occurrence.message_norm ?? "Сообщение ошибки недоступно"}
                    </p>
                    <p className="mt-2 text-xs text-slate-400">
                      {formatDateTime(occurrence.created_at)}
                      {occurrence.failure_stage ? ` • ${occurrence.failure_stage}` : ""}
                    </p>
                  </article>
                ))
              ) : (
                <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
                  Отдельные error occurrence для этой трассы не зафиксированы.
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="overflow-hidden">
            <CardHeader>
              <CardTitle>Связанные trace links</CardTitle>
              <CardDescription>
                Показываем cross-trace связи и причины линковки прямо в workbench.
              </CardDescription>
            </CardHeader>
            <CardContent className="max-h-[min(22vh,16rem)] space-y-3 overflow-y-auto pr-2">
              {detail.span_links.length ? (
                detail.span_links.map((link) => (
                  <article key={link.id} className="rounded-[1rem] border border-border bg-white px-4 py-4">
                    <p className="font-semibold text-slate-950">
                      {link.linked_trace_id ?? "Связанная трасса"}
                    </p>
                    <p className="mt-2 text-sm text-slate-600">{link.reason ?? "Связь"}</p>
                    <p className="mt-2 text-xs text-slate-400">
                      Span: {link.span_id} • {formatDateTime(link.created_at)}
                    </p>
                  </article>
                ))
              ) : (
                <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
                  Для этой трассы пока нет связанных links.
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="overflow-hidden">
            <CardHeader>
              <CardTitle>Agent actions</CardTitle>
              <CardDescription>
                Делаем sync с agent action trace и показываем живые события без отдельного legacy-экрана.
              </CardDescription>
            </CardHeader>
            <CardContent className="max-h-[min(28vh,18rem)] space-y-3 overflow-y-auto pr-2">
              {agentActionsError ? (
                <div className="rounded-[1rem] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                  {agentActionsError}
                </div>
              ) : null}

              {agentActions.length ? (
                agentActions.map((item, index) => (
                  <article key={`${item.action ?? "action"}-${index}`} className="rounded-[1rem] border border-border bg-white px-4 py-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-semibold text-slate-950">{item.action ?? "agent.action"}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          {[item.source, item.stage, item.tool_name].filter(Boolean).join(" / ") || "agent trace"}
                        </p>
                      </div>
                      <Badge tone={getStatusTone(item.status)}>{item.status ?? "ok"}</Badge>
                    </div>
                    {item.summary ? <p className="mt-3 text-sm text-slate-600">{item.summary}</p> : null}
                    <div className="mt-3 grid gap-2 text-xs text-slate-500">
                      {item.operation_id ? <p className="break-all">operation: {item.operation_id}</p> : null}
                      {item.trace_id ? <p className="break-all">trace: {item.trace_id}</p> : null}
                      {item.ts ? <p>{formatDateTime(item.ts)}</p> : null}
                    </div>
                    {item.details && Object.keys(item.details).length ? (
                      <p className="mt-3 break-words rounded-[0.8rem] bg-surface-subtle px-3 py-2 text-xs text-slate-500">
                        {Object.entries(item.details)
                          .slice(0, 4)
                          .map(([key, value]) => `${key}: ${compactActionValue(value)}`)
                          .join(" / ")}
                      </p>
                    ) : null}
                  </article>
                ))
              ) : (
                <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
                  Agent actions по этой трассе пока не синхронизированы.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

export function ObserverQuickPanel({ deviceId, deviceLabel }: ObserverQuickPanelProps) {
  const queryClient = useQueryClient();
  const [lookbackHours, setLookbackHours] = useState<number>(24);
  const [activeTab, setActiveTab] = useState<ObserverTab>("quick");
  const [statusFilter, setStatusFilter] = useState<AdminObserverTraceStatusFilter>("all");
  const [rootKindFilter, setRootKindFilter] = useState<AdminObserverRootKindFilter>("all");
  const [search, setSearch] = useState("");
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [selectedSignatureId, setSelectedSignatureId] = useState<string | null>(null);
  const [selectedDegradationKey, setSelectedDegradationKey] = useState<string | null>(null);
  const [settingsDraft, setSettingsDraft] = useState<ObserverSettingsDraft | null>(null);
  const [settingsBaseline, setSettingsBaseline] = useState("");
  const [actionFeedback, setActionFeedback] = useState<ActionFeedback>(null);
  const deferredSearch = useDeferredValue(search);

  const quickQuery = useQuery({
    queryKey: ["observer-workbench-quick", deviceId, lookbackHours],
    queryFn: () => fetchObserverWorkbenchQuick({ deviceId, lookbackHours }),
    retry: false,
  });

  const tracesQuery = useQuery({
    queryKey: ["observer-workbench-traces", deviceId, lookbackHours, statusFilter, rootKindFilter, deferredSearch],
    queryFn: () =>
      fetchObserverWorkbenchTraces({
        deviceId,
        lookbackHours,
        statusFilter,
        rootKindFilter,
        limit: 40,
        query: deferredSearch || null,
      }),
    retry: false,
  });

  const signaturesQuery = useQuery({
    queryKey: ["observer-workbench-signatures", deviceId, lookbackHours, rootKindFilter],
    queryFn: () =>
      fetchObserverSignatures({
        deviceId,
        lookbackHours,
        rootKindFilter,
        limit: 40,
      }),
    retry: false,
  });

  const degradationsQuery = useQuery({
    queryKey: ["observer-workbench-degradations", deviceId, lookbackHours, rootKindFilter],
    queryFn: () =>
      fetchObserverDegradations({
        deviceId,
        lookbackHours,
        rootKindFilter,
        limit: 40,
      }),
    retry: false,
  });

  const runtimeQuery = useQuery({
    queryKey: ["observer-workbench-runtime"],
    queryFn: fetchObserverRuntime,
    retry: false,
  });

  const settingsQuery = useQuery({
    queryKey: ["observer-workbench-settings"],
    queryFn: fetchObserverSettings,
    retry: false,
  });

  useEffect(() => {
    if (!settingsQuery.data || settingsDraft) {
      return;
    }
    const nextDraft = settingsToDraft(settingsQuery.data);
    setSettingsDraft(nextDraft);
    setSettingsBaseline(buildSettingsFingerprint(nextDraft));
  }, [settingsDraft, settingsQuery.data]);

  const visibleTraces = useMemo(
    () => (tracesQuery.data?.traces ?? []).filter((trace) => traceMatchesSearch(trace, deferredSearch)),
    [deferredSearch, tracesQuery.data?.traces],
  );

  const visibleSignatures = useMemo(
    () =>
      (signaturesQuery.data ?? []).filter((signature) => signatureMatchesSearch(signature, deferredSearch)),
    [deferredSearch, signaturesQuery.data],
  );

  const visibleDegradations = useMemo(
    () => (degradationsQuery.data ?? []).filter((item) => degradationMatchesSearch(item, deferredSearch)),
    [deferredSearch, degradationsQuery.data],
  );

  useEffect(() => {
    if (!visibleTraces.length) {
      setSelectedTraceId(null);
      return;
    }
    if (!selectedTraceId || !visibleTraces.some((trace) => trace.trace_id === selectedTraceId)) {
      setSelectedTraceId(visibleTraces[0].trace_id);
    }
  }, [selectedTraceId, visibleTraces]);

  useEffect(() => {
    if (!visibleSignatures.length) {
      setSelectedSignatureId(null);
      return;
    }
    if (!selectedSignatureId || !visibleSignatures.some((signature) => signature.error_signature === selectedSignatureId)) {
      setSelectedSignatureId(visibleSignatures[0].error_signature);
    }
  }, [selectedSignatureId, visibleSignatures]);

  useEffect(() => {
    if (!visibleDegradations.length) {
      setSelectedDegradationKey(null);
      return;
    }
    if (
      !selectedDegradationKey ||
      !visibleDegradations.some((item) => degradationKey(item) === selectedDegradationKey)
    ) {
      setSelectedDegradationKey(degradationKey(visibleDegradations[0]));
    }
  }, [selectedDegradationKey, visibleDegradations]);

  const selectedDegradation =
    visibleDegradations.find((item) => degradationKey(item) === selectedDegradationKey) ?? null;

  const traceDetailQuery = useQuery({
    queryKey: ["observer-workbench-trace-detail", selectedTraceId],
    queryFn: () =>
      fetchObserverWorkbenchTraceDetail(selectedTraceId!, {
        includeAgentActions: false,
      }),
    enabled: Boolean(selectedTraceId),
    retry: false,
  });

  const diagnosticsBundleQuery = useQuery({
    queryKey: ["observer-workbench-diagnostics-bundle", selectedTraceId, lookbackHours],
    queryFn: () =>
      fetchObserverDiagnosticsBundle({
        traceId: selectedTraceId,
        lookbackHours,
        includeAgentActions: true,
        actionLimit: 80,
      }),
    enabled: Boolean(selectedTraceId),
    retry: false,
  });

  const signatureDetailQuery = useQuery({
    queryKey: ["observer-workbench-signature-detail", selectedSignatureId],
    queryFn: () => fetchObserverSignatureDetail(selectedSignatureId!),
    enabled: Boolean(selectedSignatureId),
    retry: false,
  });

  const saveSettingsMutation = useMutation({
    mutationFn: async () => {
      if (!settingsDraft) {
        throw new Error("Настройки observer ещё не загружены.");
      }
      return saveObserverSettings(draftToSettings(settingsDraft));
    },
    onSuccess: async (savedSettings) => {
      const nextDraft = settingsToDraft(savedSettings);
      setSettingsDraft(nextDraft);
      setSettingsBaseline(buildSettingsFingerprint(nextDraft));
      setActionFeedback({
        tone: "success",
        text: "Observer settings сохранены и уже применены к runtime.",
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["observer-workbench-settings"] }),
        queryClient.invalidateQueries({ queryKey: ["observer-workbench-runtime"] }),
        queryClient.invalidateQueries({ queryKey: ["observer-workbench-trace-detail"] }),
      ]);
    },
    onError: (error) => {
      setActionFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось сохранить observer settings.",
      });
    },
  });

  const rebuildMutation = useMutation({
    mutationFn: () =>
      rebuildObserverTraces({
        deviceId,
        lookbackHours,
        limit: 50,
      }),
    onSuccess: async (payload) => {
      setActionFeedback({
        tone: "success",
        text: `Пересобрано observer traces: ${payload.projected_count}.`,
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["observer-workbench-quick"] }),
        queryClient.invalidateQueries({ queryKey: ["observer-workbench-traces"] }),
        queryClient.invalidateQueries({ queryKey: ["observer-workbench-degradations"] }),
        queryClient.invalidateQueries({ queryKey: ["observer-workbench-signatures"] }),
        queryClient.invalidateQueries({ queryKey: ["observer-workbench-runtime"] }),
      ]);
    },
    onError: (error) => {
      setActionFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось пересобрать observer traces.",
      });
    },
  });

  const settingsDirty = settingsDraft ? buildSettingsFingerprint(settingsDraft) !== settingsBaseline : false;

  const runtime = runtimeQuery.data;
  const runtimeStats = Object.entries(runtime?.stats ?? {});

  const mainSearchPlaceholder =
    activeTab === "signatures"
      ? "Поиск по signature, component или tool"
      : activeTab === "degradations"
        ? "Поиск по tool, module или operation kind"
        : "Поиск по trace id, ticket или operation";

  function openTrace(traceId: string) {
    startTransition(() => {
      setActiveTab("traces");
      setSelectedTraceId(traceId);
    });
  }

  function openSignature(signatureId: string) {
    startTransition(() => {
      setActiveTab("signatures");
      setSelectedSignatureId(signatureId);
    });
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div className="max-w-3xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-brand-700">
            Observability
          </p>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-slate-950">
            Observer для {deviceLabel}
          </h2>
          <p className="mt-3 text-sm leading-7 text-slate-500 md:text-base">
            Переносим быстрый observer-срез, поиск трасс, signatures, degradations и runtime settings
            в единый SaaS workbench без legacy-техпанели.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 rounded-pill border border-border bg-white px-4 py-2.5 text-sm text-slate-600 shadow-soft">
            <Activity className="h-4 w-4 text-brand-600" />
            <span>Runtime: {runtime?.health?.status ?? "unknown"}</span>
          </div>
          <Button
            leadingIcon={<GitBranchPlus className="h-4 w-4" />}
            onClick={() => rebuildMutation.mutate()}
            variant="outline"
          >
            {rebuildMutation.isPending ? "Пересобираем..." : "Пересобрать traces"}
          </Button>
          <Button
            leadingIcon={<RefreshCcw className="h-4 w-4" />}
            onClick={() => {
              void Promise.all([
                quickQuery.refetch(),
                tracesQuery.refetch(),
                signaturesQuery.refetch(),
                degradationsQuery.refetch(),
                runtimeQuery.refetch(),
                settingsQuery.refetch(),
              ]);
            }}
            variant="outline"
          >
            Обновить
          </Button>
        </div>
      </div>

      <ActionFeedbackBanner feedback={actionFeedback} />

      <div className="grid gap-4 lg:grid-cols-4">
        <div className="rounded-[1.3rem] border border-border bg-white px-5 py-5 shadow-soft">
          <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Горячие traces</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
            {quickQuery.data?.summary.hot_trace_count ?? 0}
          </p>
          <p className="mt-2 text-sm text-slate-500">
            Всего recent traces: {quickQuery.data?.summary.recent_trace_count ?? 0}
          </p>
        </div>
        <div className="rounded-[1.3rem] border border-border bg-white px-5 py-5 shadow-soft">
          <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Signatures</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
            {quickQuery.data?.summary.signature_count ?? 0}
          </p>
          <p className="mt-2 text-sm text-slate-500">
            Degradation groups: {quickQuery.data?.summary.degradation_group_count ?? 0}
          </p>
        </div>
        <div className="rounded-[1.3rem] border border-border bg-white px-5 py-5 shadow-soft">
          <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Dangerous flows</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
            {quickQuery.data?.summary.dangerous_flow_count ?? 0}
          </p>
          <p className="mt-2 text-sm text-slate-500">
            Pending traces: {quickQuery.data?.runtime.pending_trace_count ?? 0}
          </p>
        </div>
        <div className="rounded-[1.3rem] border border-border bg-white px-5 py-5 shadow-soft">
          <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Runtime health</p>
          <div className="mt-3 flex items-center gap-3">
            <Badge tone={getStatusTone(quickQuery.data?.runtime.health_status)} withDot>
              {quickQuery.data?.runtime.health_status_label ?? runtime?.health?.status ?? "unknown"}
            </Badge>
          </div>
          <p className="mt-2 text-sm text-slate-500">
            Last projection: {formatDateTime(quickQuery.data?.runtime.last_projected_at)}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {LOOKBACK_OPTIONS.map((option) => (
          <button
            key={option.hours}
            className={cn(
              "rounded-pill px-4 py-2 text-sm font-medium transition-colors",
              lookbackHours === option.hours
                ? "bg-brand-600 text-white"
                : "bg-white text-slate-600 shadow-soft hover:bg-brand-50 hover:text-brand-800",
            )}
            onClick={() => {
              startTransition(() => {
                setLookbackHours(option.hours);
              });
            }}
            type="button"
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <Tabs
          items={OBSERVER_TABS.map((item) => ({
            value: item.value,
            label: item.label,
            count:
              item.value === "traces"
                ? tracesQuery.data?.summary.visible_count ?? 0
                : item.value === "signatures"
                  ? visibleSignatures.length
                  : item.value === "degradations"
                    ? visibleDegradations.length
                    : undefined,
          }))}
          onValueChange={(value) => setActiveTab(value as ObserverTab)}
          value={activeTab}
        />

        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          {activeTab === "runtime" ? null : (
            <SearchField
              className="flex-1"
              onChange={(event) => setSearch(event.target.value)}
              placeholder={mainSearchPlaceholder}
              value={search}
            />
          )}
          <div className="grid grid-cols-2 gap-3 md:flex">
            <Select
              className="min-w-[160px]"
              onChange={(event) => setRootKindFilter(event.target.value as AdminObserverRootKindFilter)}
              value={rootKindFilter}
            >
              {(tracesQuery.data?.filters.root_kind_options ?? []).map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
            <Select
              className="min-w-[160px]"
              disabled={activeTab === "signatures" || activeTab === "degradations" || activeTab === "quick"}
              onChange={(event) => setStatusFilter(event.target.value as AdminObserverTraceStatusFilter)}
              value={statusFilter}
            >
              {(tracesQuery.data?.filters.status_options ?? []).map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>
        </div>
      </div>

      {activeTab === "quick" ? (
        <div className="grid gap-6 xl:grid-cols-2">
          <Card className="overflow-hidden">
            <CardHeader>
              <CardTitle>Горячие traces</CardTitle>
              <CardDescription>
                Берём реальные hot traces из observer quick и даём быстрый вход в trace drilldown.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {(quickQuery.data?.hot_traces ?? []).length ? (
                quickQuery.data!.hot_traces.map((trace) => (
                  <article key={trace.trace_id} className="rounded-[1rem] border border-border bg-white px-4 py-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-semibold text-slate-950">{trace.root_kind_label}</p>
                        <p className="mt-1 truncate text-xs text-slate-500">{trace.trace_id}</p>
                      </div>
                      <Badge tone={getStatusTone(trace.status)}>{trace.status_label}</Badge>
                    </div>
                    <p className="mt-3 text-sm text-slate-600">
                      Ошибок: {trace.error_count} • spans: {trace.span_count} • {formatDuration(trace.duration_ms)}
                    </p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <Button onClick={() => openTrace(trace.trace_id)} size="sm" variant="outline">
                        Открыть trace
                      </Button>
                    </div>
                  </article>
                ))
              ) : (
                <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
                  За выбранное окно горячих traces пока нет.
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="overflow-hidden">
            <CardHeader>
              <CardTitle>Mass signatures и dangerous flows</CardTitle>
              <CardDescription>
                Держим массовые сбои, деградации и опасные потоки в одном обзорном слое.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-3">
                {(quickQuery.data?.top_signatures ?? []).map((item) => (
                  <article key={item.error_signature} className="rounded-[1rem] border border-border bg-white px-4 py-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-semibold text-slate-950">{item.title}</p>
                        <p className="mt-1 truncate text-xs text-slate-500">{item.error_signature}</p>
                      </div>
                      <Badge tone="danger">{item.occurrences_count}</Badge>
                    </div>
                    <p className="mt-3 text-sm text-slate-600">
                      {[item.component, item.tool_name].filter(Boolean).join(" • ") || "Без component/tool"}
                    </p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <Button onClick={() => openSignature(item.error_signature)} size="sm" variant="outline">
                        Открыть signature
                      </Button>
                    </div>
                  </article>
                ))}
              </div>

              <div className="grid gap-3 lg:grid-cols-2">
                {(quickQuery.data?.dangerous_flows ?? []).map((item) => (
                  <div key={item.root_kind} className="rounded-[1rem] border border-border bg-surface-subtle px-4 py-4">
                    <p className="font-semibold text-slate-950">{item.root_kind_label}</p>
                    <p className="mt-2 text-sm text-slate-600">
                      error {item.error_count} • timeout {item.timeout_count} • retry {item.retried_count}
                    </p>
                    <p className="mt-2 text-xs text-slate-500">
                      Active now: {item.active_count} • {formatDateTime(item.latest_operation_at)}
                    </p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      ) : null}

      {activeTab === "traces" ? (
        <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
          <Card className="overflow-hidden xl:sticky xl:top-[8.5rem] xl:self-start">
            <CardHeader>
              <CardTitle>Список traces</CardTitle>
              <CardDescription>
                Полный поиск по трассам, статусы и связка с ticket / operation.
              </CardDescription>
            </CardHeader>
            <CardContent className="max-h-[min(68vh,52rem)] overflow-y-auto pr-2">
              <TraceList
                emptyText="Для текущих фильтров traces не найдены."
                items={visibleTraces}
                loading={tracesQuery.isLoading}
                onSelect={setSelectedTraceId}
                selectedTraceId={selectedTraceId}
              />
            </CardContent>
          </Card>

          <TraceDetailCard
            bundle={diagnosticsBundleQuery.data}
            bundleError={diagnosticsBundleQuery.error}
            detail={traceDetailQuery.data}
            error={traceDetailQuery.error}
            isBundleLoading={diagnosticsBundleQuery.isLoading}
            isLoading={traceDetailQuery.isLoading}
          />
        </div>
      ) : null}

      {activeTab === "signatures" ? (
        <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
          <Card className="overflow-hidden xl:sticky xl:top-[8.5rem] xl:self-start">
            <CardHeader>
              <CardTitle>Сигнатуры ошибок</CardTitle>
              <CardDescription>
                Реальные error signatures, affected devices и вход в occurrence detail.
              </CardDescription>
            </CardHeader>
            <CardContent className="max-h-[min(68vh,52rem)] space-y-3 overflow-y-auto pr-2">
              {signaturesQuery.isLoading ? (
                <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
                  Загружаем signatures...
                </div>
              ) : null}

              {visibleSignatures.length ? (
                visibleSignatures.map((signature) => {
                  const active = signature.error_signature === selectedSignatureId;
                  return (
                    <button
                      key={signature.error_signature}
                      className={cn(
                        "w-full rounded-[1.1rem] border px-4 py-4 text-left transition-colors",
                        active
                          ? "border-brand-200 bg-brand-50"
                          : "border-border bg-white hover:border-brand-100 hover:bg-surface-subtle",
                      )}
                      onClick={() => setSelectedSignatureId(signature.error_signature)}
                      type="button"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="font-semibold text-slate-950">{signature.title ?? signature.error_signature}</p>
                          <p className="mt-1 truncate text-xs text-slate-500">{signature.error_signature}</p>
                        </div>
                        <Badge tone="danger">{signature.occurrences_count ?? 0}</Badge>
                      </div>
                      <p className="mt-3 text-sm text-slate-600">
                        {[signature.component, signature.module_name, signature.tool_name]
                          .filter(Boolean)
                          .join(" • ") || "Без component/module/tool"}
                      </p>
                      <p className="mt-2 text-xs text-slate-400">
                        Последний случай: {formatDateTime(signature.last_seen_at)}
                      </p>
                    </button>
                  );
                })
              ) : (
                <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
                  Под текущий фильтр signatures не найдены.
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="overflow-hidden">
            <CardHeader>
              <CardTitle>Signature detail</CardTitle>
              <CardDescription>
                Occurrence list, severity и affected devices из реального observer backend.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {signatureDetailQuery.isLoading ? (
                <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-sm text-slate-500">
                  Загружаем детали signature...
                </div>
              ) : null}

              {signatureDetailQuery.data ? (
                <>
                  <div className="grid gap-4 lg:grid-cols-4">
                    <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                      <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Occurrences</p>
                      <p className="mt-3 text-2xl font-semibold text-slate-950">
                        {signatureDetailQuery.data.signature.occurrences_count ?? 0}
                      </p>
                    </div>
                    <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                      <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Affected devices</p>
                      <p className="mt-3 text-2xl font-semibold text-slate-950">
                        {signatureDetailQuery.data.signature.affected_devices_count ?? 0}
                      </p>
                    </div>
                    <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                      <p className="text-xs uppercase tracking-[0.22em] text-brand-700">First seen</p>
                      <p className="mt-3 text-sm font-semibold text-slate-950">
                        {formatDateTime(signatureDetailQuery.data.signature.first_seen_at)}
                      </p>
                    </div>
                    <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                      <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Last seen</p>
                      <p className="mt-3 text-sm font-semibold text-slate-950">
                        {formatDateTime(signatureDetailQuery.data.signature.last_seen_at)}
                      </p>
                    </div>
                  </div>

                  <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                    <p className="font-semibold text-slate-950">
                      {signatureDetailQuery.data.signature.title ?? signatureDetailQuery.data.signature.error_signature}
                    </p>
                    <p className="mt-2 text-sm text-slate-500">
                      {[signatureDetailQuery.data.signature.component, signatureDetailQuery.data.signature.module_name, signatureDetailQuery.data.signature.tool_name]
                        .filter(Boolean)
                        .join(" • ") || "Без component/module/tool"}
                    </p>
                    <code className="mt-3 block rounded-panel bg-slate-950 px-4 py-3 text-xs text-slate-100">
                      {signatureDetailQuery.data.signature.error_signature}
                    </code>
                  </div>

                  <div className="max-h-[min(46vh,34rem)] space-y-3 overflow-y-auto pr-2">
                    {signatureDetailQuery.data.occurrences.map((occurrence) => (
                      <article key={occurrence.occurrence_id} className="rounded-[1rem] border border-border bg-white px-4 py-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="font-semibold text-slate-950">
                              {occurrence.message_norm ?? occurrence.exception_type ?? occurrence.error_kind ?? "Ошибка"}
                            </p>
                            <p className="mt-1 text-xs text-slate-500">
                              Trace {occurrence.trace_id}
                              {occurrence.span_id ? ` • span ${occurrence.span_id}` : ""}
                            </p>
                          </div>
                          <Badge tone={getStatusTone(occurrence.severity)}>{occurrence.severity_label ?? occurrence.severity ?? "info"}</Badge>
                        </div>
                        <p className="mt-3 text-sm text-slate-600">
                          {[occurrence.component, occurrence.module_name, occurrence.tool_name]
                            .filter(Boolean)
                            .join(" • ") || "Без component/module/tool"}
                        </p>
                        <div className="mt-4 flex flex-wrap gap-2">
                          <Button onClick={() => openTrace(occurrence.trace_id)} size="sm" variant="outline">
                            Открыть trace
                          </Button>
                        </div>
                      </article>
                    ))}
                  </div>
                </>
              ) : (
                <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-sm text-slate-500">
                  Выберите signature слева, чтобы открыть occurrences.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      ) : null}

      {activeTab === "degradations" ? (
        <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
          <Card className="overflow-hidden xl:sticky xl:top-[8.5rem] xl:self-start">
            <CardHeader>
              <CardTitle>Группы деградаций</CardTitle>
              <CardDescription>
                Slow / timeout / retry паттерны с поиском и быстрым переходом в sample trace.
              </CardDescription>
            </CardHeader>
            <CardContent className="max-h-[min(68vh,52rem)] space-y-3 overflow-y-auto pr-2">
              {degradationsQuery.isLoading ? (
                <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
                  Загружаем degradations...
                </div>
              ) : null}

              {visibleDegradations.length ? (
                visibleDegradations.map((item) => {
                  const active = degradationKey(item) === selectedDegradationKey;
                  return (
                    <button
                      key={degradationKey(item)}
                      className={cn(
                        "w-full rounded-[1.1rem] border px-4 py-4 text-left transition-colors",
                        active
                          ? "border-brand-200 bg-brand-50"
                          : "border-border bg-white hover:border-brand-100 hover:bg-surface-subtle",
                      )}
                      onClick={() => setSelectedDegradationKey(degradationKey(item))}
                      type="button"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="font-semibold text-slate-950">{item.tool_name ?? item.operation_kind_label}</p>
                          <p className="mt-1 text-xs text-slate-500">
                            {[item.operation_kind_label, item.module_name].filter(Boolean).join(" • ")}
                          </p>
                        </div>
                        <Badge tone="warning">{item.operations_count ?? 0}</Badge>
                      </div>
                      <p className="mt-3 text-sm text-slate-600">
                        timeout {formatPercent(item.timeout_rate)} • retry {formatPercent(item.retry_rate)} • slow {formatPercent(item.slow_rate)}
                      </p>
                    </button>
                  );
                })
              ) : (
                <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
                  Под текущий фильтр деградации не найдены.
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="overflow-hidden">
            <CardHeader>
              <CardTitle>Degradation detail</CardTitle>
              <CardDescription>
                Видим rates, среднюю длительность и sample traces для точечного разбора.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {selectedDegradation ? (
                <>
                  <div className="grid gap-4 lg:grid-cols-4">
                    <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                      <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Operations</p>
                      <p className="mt-3 text-2xl font-semibold text-slate-950">
                        {selectedDegradation.operations_count ?? 0}
                      </p>
                    </div>
                    <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                      <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Timeout / Retry</p>
                      <p className="mt-3 text-2xl font-semibold text-slate-950">
                        {formatPercent(selectedDegradation.timeout_rate)} / {formatPercent(selectedDegradation.retry_rate)}
                      </p>
                    </div>
                    <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                      <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Slow rate</p>
                      <p className="mt-3 text-2xl font-semibold text-slate-950">
                        {formatPercent(selectedDegradation.slow_rate)}
                      </p>
                    </div>
                    <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                      <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Avg / Max</p>
                      <p className="mt-3 text-sm font-semibold text-slate-950">
                        {formatDuration(selectedDegradation.avg_duration_ms)} / {formatDuration(selectedDegradation.max_duration_ms)}
                      </p>
                    </div>
                  </div>

                  <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                    <p className="font-semibold text-slate-950">
                      {selectedDegradation.tool_name ?? selectedDegradation.operation_kind_label}
                    </p>
                    <p className="mt-2 text-sm text-slate-600">
                      {[selectedDegradation.module_name, selectedDegradation.operation_kind_label]
                        .filter(Boolean)
                        .join(" • ") || "Без module/operation kind"}
                    </p>
                    <p className="mt-2 text-sm text-slate-500">
                      Последняя активность: {formatDateTime(selectedDegradation.latest_operation_at)}
                    </p>
                  </div>

                  <div className="space-y-3">
                    <p className="text-sm font-semibold text-slate-900">Sample traces</p>
                    {selectedDegradation.sample_trace_ids?.length ? (
                      <div className="flex flex-wrap gap-2">
                        {selectedDegradation.sample_trace_ids.map((traceId) => (
                          <Button key={traceId} onClick={() => openTrace(traceId)} size="sm" variant="outline">
                            {traceId}
                          </Button>
                        ))}
                      </div>
                    ) : (
                      <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
                        Для этой деградации sample trace пока не сохранён.
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-sm text-slate-500">
                  Выберите деградацию слева, чтобы открыть детали и sample traces.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      ) : null}

      {activeTab === "runtime" ? (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Runtime и health</CardTitle>
                <CardDescription>
                  Смотрим, жив ли observer runtime, какие у него issues и что лежит в stats.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4 lg:grid-cols-3">
                  <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Health</p>
                    <div className="mt-3">
                      <Badge tone={getStatusTone(runtime?.health?.status)} withDot>
                        {runtime?.health?.status ?? "unknown"}
                      </Badge>
                    </div>
                  </div>
                  <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Enabled / running</p>
                    <p className="mt-3 text-xl font-semibold text-slate-950">
                      {runtime?.enabled ? "enabled" : "disabled"} / {runtime?.running ? "running" : "stopped"}
                    </p>
                  </div>
                  <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Trace sampling</p>
                    <p className="mt-3 text-xl font-semibold text-slate-950">
                      {settingsDraft ? formatPercent(Number.parseFloat(settingsDraft.successTraceSampleRate) || 0) : "—"}
                    </p>
                  </div>
                </div>

                {runtime?.health?.issues?.length ? (
                  <div className="space-y-3">
                    {runtime.health.issues.map((issue) => (
                      <div key={issue} className="rounded-[1rem] border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
                        {issue}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-[1rem] border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                    Runtime issues сейчас не зафиксированы.
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Runtime stats</CardTitle>
                <CardDescription>
                  Прямой срез полей из observer runtime без скрытия технических значений.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {runtimeStats.length ? (
                  runtimeStats.map(([key, value]) => (
                    <div key={key} className="rounded-[1rem] border border-border bg-white px-4 py-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{key}</p>
                      <p className="mt-2 font-semibold text-slate-950">{formatRuntimeStatValue(value)}</p>
                    </div>
                  ))
                ) : (
                  <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
                    Runtime stats пока не вернул значения.
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <Card className="xl:sticky xl:top-[8.5rem] xl:self-start">
            <CardHeader>
              <CardTitle>Observer settings</CardTitle>
              <CardDescription>
                Настраиваем sampling, retention, action sync и список root kinds, которые всегда надо хранить.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {settingsDraft ? (
                <>
                  <label className="space-y-2 text-sm font-medium text-slate-800">
                    <span>Success trace sample rate</span>
                    <Input
                      onChange={(event) =>
                        setSettingsDraft((current) =>
                          current
                            ? {
                                ...current,
                                successTraceSampleRate: event.target.value,
                              }
                            : current,
                        )
                      }
                      value={settingsDraft.successTraceSampleRate}
                    />
                  </label>

                  <div className="grid gap-4 md:grid-cols-2">
                    <label className="space-y-2 text-sm font-medium text-slate-800">
                      <span>OK retention hours</span>
                      <Input
                        onChange={(event) =>
                          setSettingsDraft((current) =>
                            current
                              ? {
                                  ...current,
                                  okTraceRetentionHours: event.target.value,
                                }
                              : current,
                          )
                        }
                        value={settingsDraft.okTraceRetentionHours}
                      />
                    </label>

                    <label className="space-y-2 text-sm font-medium text-slate-800">
                      <span>Error retention hours</span>
                      <Input
                        onChange={(event) =>
                          setSettingsDraft((current) =>
                            current
                              ? {
                                  ...current,
                                  errorTraceRetentionHours: event.target.value,
                                }
                              : current,
                          )
                        }
                        value={settingsDraft.errorTraceRetentionHours}
                      />
                    </label>
                  </div>

                  <label className="space-y-2 text-sm font-medium text-slate-800">
                    <span>Action sync limit</span>
                    <Input
                      onChange={(event) =>
                        setSettingsDraft((current) =>
                          current
                            ? {
                                ...current,
                                actionSyncLimit: event.target.value,
                              }
                            : current,
                        )
                      }
                      value={settingsDraft.actionSyncLimit}
                    />
                  </label>

                  <label className="space-y-2 text-sm font-medium text-slate-800">
                    <span>Always keep root kinds</span>
                    <Input
                      onChange={(event) =>
                        setSettingsDraft((current) =>
                          current
                            ? {
                                ...current,
                                alwaysKeepRootKinds: event.target.value,
                              }
                            : current,
                        )
                      }
                      value={settingsDraft.alwaysKeepRootKinds}
                    />
                  </label>

                  <label className="flex items-center justify-between gap-3 rounded-[1rem] border border-border bg-surface-subtle px-4 py-3">
                    <span className="text-sm font-medium text-slate-800">Historical backfill enabled</span>
                    <input
                      checked={settingsDraft.historicalBackfillEnabled}
                      className="h-4 w-4 rounded border-border text-brand-600"
                      onChange={(event) =>
                        setSettingsDraft((current) =>
                          current
                            ? {
                                ...current,
                                historicalBackfillEnabled: event.target.checked,
                              }
                            : current,
                        )
                      }
                      type="checkbox"
                    />
                  </label>

                  <label className="flex items-center justify-between gap-3 rounded-[1rem] border border-border bg-surface-subtle px-4 py-3">
                    <span className="text-sm font-medium text-slate-800">Action sync enabled</span>
                    <input
                      checked={settingsDraft.actionSyncEnabled}
                      className="h-4 w-4 rounded border-border text-brand-600"
                      onChange={(event) =>
                        setSettingsDraft((current) =>
                          current
                            ? {
                                ...current,
                                actionSyncEnabled: event.target.checked,
                              }
                            : current,
                        )
                      }
                      type="checkbox"
                    />
                  </label>

                  <div className="flex flex-wrap gap-3">
                    <Button
                      disabled={!settingsDirty || saveSettingsMutation.isPending}
                      onClick={() => saveSettingsMutation.mutate()}
                    >
                      {saveSettingsMutation.isPending ? "Сохраняем..." : "Сохранить settings"}
                    </Button>
                    <Button
                      onClick={() => {
                        const nextDraft = settingsToDraft(settingsQuery.data ?? {});
                        setSettingsDraft(nextDraft);
                        setSettingsBaseline(buildSettingsFingerprint(nextDraft));
                        setActionFeedback(null);
                      }}
                      variant="outline"
                    >
                      Сбросить
                    </Button>
                  </div>
                </>
              ) : (
                <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
                  Загружаем observer settings...
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      ) : null}
    </section>
  );
}
