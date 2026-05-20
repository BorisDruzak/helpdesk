import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { fetchPolicyHealthDashboard, simulatePolicyHealth, type PolicyHealthTemplate, type PolicySimulationPayload } from "./api";
import {
  buildGuidedSimulationPayload,
  defaultGuidedSimulationDraft,
  POLICY_KIND_LABELS,
  type GuidedSimulationDraft,
} from "../request-template-studio/options";

const POLICY_COLUMNS = ["routing", "sla", "ola", "approval", "closure", "visibility", "notification", "diagnostic", "reporting"];

function statusTone(status: string) {
  if (status === "ok") {
    return "success" as const;
  }
  if (status === "warning" || status === "missing") {
    return "warning" as const;
  }
  if (status === "error") {
    return "danger" as const;
  }
  return "neutral" as const;
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", { dateStyle: "short", timeStyle: "short" }).format(date);
}

function offeringCodeFromContext(offeringContext: string | null, serviceCode: string | null): string | null {
  const normalized = offeringContext?.trim();
  if (!normalized) {
    return null;
  }
  if (serviceCode && normalized.startsWith(`${serviceCode}.`)) {
    return normalized.slice(serviceCode.length + 1) || normalized;
  }
  if (normalized.includes(".")) {
    return normalized.split(".").filter(Boolean).at(-1) ?? normalized;
  }
  return normalized;
}

function buildPolicyHealthSimulationRequest(
  templateCode: string,
  draft: GuidedSimulationDraft,
  searchParams: URLSearchParams,
): PolicySimulationPayload {
  const serviceCode = searchParams.get("service")?.trim() || draft.serviceCode.trim() || null;
  const offeringFullCode = searchParams.get("offering")?.trim() || null;
  const offeringCode = (offeringCodeFromContext(offeringFullCode, serviceCode) ?? draft.offeringCode.trim()) || null;
  const guidedPayload = buildGuidedSimulationPayload({
    ...draft,
    serviceCode: serviceCode ?? draft.serviceCode,
    offeringCode: offeringCode ?? draft.offeringCode,
  });
  return {
    template_code: templateCode,
    ...guidedPayload,
    service_code: serviceCode,
    offering_code: offeringCode,
    offering_full_code: offeringFullCode,
  };
}

function TemplateDetails({ template }: { template: PolicyHealthTemplate | null }) {
  if (!template) {
    return (
      <aside className="surface-panel p-5">
        <h2 className="text-base font-semibold text-slate-950">Детали</h2>
        <p className="mt-3 text-sm text-slate-500">Выберите шаблон в таблице.</p>
      </aside>
    );
  }
  const grouped = template.issues.reduce<Record<string, typeof template.issues>>((acc, issue) => {
    acc[issue.severity] = [...(acc[issue.severity] ?? []), issue];
    return acc;
  }, {});
  return (
    <aside className="surface-panel p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-950">{template.template_code}</h2>
          <p className="mt-1 text-sm text-slate-500">{template.template_name}</p>
        </div>
        <Badge tone={statusTone(template.health_status)}>{template.health_status}</Badge>
      </div>
      <Link
        className="mt-4 inline-flex h-9 items-center justify-center rounded-pill border border-border bg-white px-3 text-xs font-semibold text-slate-700 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800"
        to={`/app/admin/request-template-studio?template=${encodeURIComponent(template.template_code)}`}
      >
        Открыть в студии
      </Link>
      <dl className="mt-5 grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-slate-500">Оценка</dt>
          <dd className="font-semibold text-slate-950">{template.health_score}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Конфликты</dt>
          <dd className="font-semibold text-slate-950">{template.conflict_count}</dd>
        </div>
      </dl>
      <div className="mt-5 space-y-4">
        {Object.entries(grouped).length ? (
          Object.entries(grouped).map(([severity, issues]) => (
            <section key={severity}>
              <h3 className="text-sm font-semibold uppercase text-slate-600">{severity}</h3>
              <div className="mt-2 space-y-2">
                {issues.map((issue, index) => (
                  <article key={`${issue.policy_kind}:${issue.path}:${index}`} className="rounded-md border border-slate-200 p-3">
                    <div className="flex items-center gap-2">
                      <Badge tone={statusTone(issue.severity)}>{issue.policy_kind}</Badge>
                      <span className="text-xs font-semibold text-slate-500">{issue.kind}</span>
                    </div>
                    <p className="mt-2 text-sm text-slate-800">{issue.message}</p>
                    {issue.path || issue.reference ? (
                      <p className="mt-1 text-xs text-slate-500">{[issue.path, issue.reference].filter(Boolean).join(" / ")}</p>
                    ) : null}
                    {issue.suggested_fix ? <p className="mt-2 text-xs text-slate-600">{issue.suggested_fix}</p> : null}
                  </article>
                ))}
              </div>
            </section>
          ))
        ) : (
          <p className="text-sm text-slate-500">Проблемы не найдены.</p>
        )}
      </div>
    </aside>
  );
}

export function PolicyHealthPanel() {
  const [searchParams] = useSearchParams();
  const [healthFilter, setHealthFilter] = useState("all");
  const [kindFilter, setKindFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [simulationDraft, setSimulationDraft] = useState<GuidedSimulationDraft>(defaultGuidedSimulationDraft);

  const dashboardQuery = useQuery({
    queryKey: ["policy-health-dashboard"],
    queryFn: fetchPolicyHealthDashboard,
  });

  const templates = dashboardQuery.data?.templates ?? [];
  const selectedTemplate = templates.find((template) => template.template_code === selectedCode) ?? templates[0] ?? null;
  useEffect(() => {
    const template = searchParams.get("template");
    if (template && templates.some((item) => item.template_code === template)) {
      setSelectedCode(template);
    }
  }, [searchParams, templates]);
  const visibleTemplates = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return templates.filter((template) => {
      if (healthFilter !== "all" && template.health_status !== healthFilter) {
        return false;
      }
      if (statusFilter !== "all" && template.status !== statusFilter) {
        return false;
      }
      if (kindFilter !== "all" && !template.issues.some((issue) => issue.policy_kind === kindFilter)) {
        return false;
      }
      if (!normalizedQuery) {
        return true;
      }
      return `${template.template_code} ${template.template_name}`.toLowerCase().includes(normalizedQuery);
    });
  }, [healthFilter, kindFilter, query, statusFilter, templates]);

  const simulationMutation = useMutation({
    mutationFn: () => {
      if (!selectedTemplate) {
        throw new Error("Шаблон не выбран");
      }
      return simulatePolicyHealth(buildPolicyHealthSimulationRequest(selectedTemplate.template_code, simulationDraft, searchParams));
    },
  });

  if (dashboardQuery.isLoading) {
    return <section className="workspace-page p-6 text-sm text-slate-500">Загрузка проверки политик...</section>;
  }

  if (dashboardQuery.isError || !dashboardQuery.data) {
    return <section className="workspace-page p-6 text-sm text-rose-700">Не удалось загрузить проверку политик.</section>;
  }

  return (
    <section className="workspace-page space-y-5 p-6">
      <header className="workspace-page__header">
        <div className="workspace-page__copy">
          <p className="workspace-boot__eyebrow">Управление обращениями</p>
          <h1>Проверка политик</h1>
        </div>
        <dl className="workspace-page__stats">
          <div>
            <dt>Всего</dt>
            <dd>{dashboardQuery.data.summary.total}</dd>
          </div>
          <div>
            <dt>Предупреждения</dt>
            <dd>{dashboardQuery.data.summary.warning}</dd>
          </div>
          <div>
            <dt>Ошибки</dt>
            <dd>{dashboardQuery.data.summary.error}</dd>
          </div>
        </dl>
      </header>

      <div className="rounded-[1rem] border border-brand-100 bg-brand-50 px-4 py-3 text-sm text-brand-900">
        Основная настройка шаблонов доступна в{" "}
        <Link
          className="font-semibold underline-offset-4 hover:underline"
          to={`/app/admin/request-template-studio${selectedTemplate ? `?template=${encodeURIComponent(selectedTemplate.template_code)}` : ""}`}
        >
          Студии шаблонов
        </Link>
        . Проверка политик остаётся экспертным разделом для диагностики проблем и dry-run деталей.
      </div>

      <section className="surface-panel p-4">
        <div className="grid gap-3 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <label className="text-sm font-medium text-slate-700">
            Поиск
            <input className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2" value={query} onChange={(event) => setQuery(event.currentTarget.value)} />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Состояние
            <select className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2" value={healthFilter} onChange={(event) => setHealthFilter(event.currentTarget.value)}>
              <option value="all">Все</option>
              <option value="ok">В норме</option>
              <option value="warning">Предупреждение</option>
              <option value="error">Ошибка</option>
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Тип политики
            <select className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2" value={kindFilter} onChange={(event) => setKindFilter(event.currentTarget.value)}>
              <option value="all">Все</option>
              {POLICY_COLUMNS.map((kind) => <option key={kind} value={kind}>{POLICY_KIND_LABELS[kind] ?? kind}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Статус шаблона
            <select className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2" value={statusFilter} onChange={(event) => setStatusFilter(event.currentTarget.value)}>
              <option value="all">Все</option>
              <option value="published">Опубликован</option>
              <option value="draft">Черновик</option>
              <option value="archived">Архив</option>
            </select>
          </label>
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="surface-panel overflow-hidden">
          <div className="overflow-auto">
            <table className="w-full min-w-[1120px] text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3">Шаблон</th>
                  <th className="px-4 py-3">Состояние</th>
                  <th className="px-4 py-3">Проблемы</th>
                  {POLICY_COLUMNS.map((kind) => <th key={kind} className="px-3 py-3">{POLICY_KIND_LABELS[kind] ?? kind}</th>)}
                  <th className="px-4 py-3">Проверен</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {visibleTemplates.map((template) => (
                  <tr key={`${template.template_code}:${template.version}`} className="cursor-pointer hover:bg-slate-50" onClick={() => setSelectedCode(template.template_code)}>
                    <td className="px-4 py-3">
                      <p className="font-semibold text-slate-950">{template.template_code}</p>
                      <p className="text-xs text-slate-500">{template.template_name} / {template.version}</p>
                    </td>
                    <td className="px-4 py-3"><Badge tone={statusTone(template.health_status)}>{template.health_status}</Badge></td>
                    <td className="px-4 py-3">{template.issue_count} / conflicts {template.conflict_count}</td>
                    {POLICY_COLUMNS.map((kind) => (
                      <td key={kind} className="px-3 py-3">
                        <Badge tone={statusTone(template.checks[kind]?.status)}>{template.checks[kind]?.status ?? "n/a"}</Badge>
                      </td>
                    ))}
                    <td className="px-4 py-3 text-xs text-slate-500">{formatDateTime(template.last_checked_at)}</td>
                  </tr>
                ))}
                {!visibleTemplates.length ? (
                  <tr>
                    <td className="px-4 py-8 text-center text-sm text-slate-500" colSpan={13}>Нет шаблонов под текущий фильтр.</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>
        <TemplateDetails template={selectedTemplate} />
      </section>

      <section className="surface-panel p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-slate-950">Симуляция выполнения</h2>
            <p className="mt-1 text-sm text-slate-500">{selectedTemplate?.template_code ?? "шаблон не выбран"}</p>
          </div>
          <Button disabled={!selectedTemplate || simulationMutation.isPending} onClick={() => simulationMutation.mutate()}>
            Запустить тестовый прогон
          </Button>
        </div>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <div className="grid gap-3">
            <label className="text-sm font-medium text-slate-700">
              Инициатор
              <input className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2" value={simulationDraft.requester} onChange={(event) => setSimulationDraft((current) => ({ ...current, requester: event.currentTarget.value }))} />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Устройство
              <input className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2" value={simulationDraft.device} onChange={(event) => setSimulationDraft((current) => ({ ...current, device: event.currentTarget.value }))} />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Локация
              <input className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2" value={simulationDraft.location} onChange={(event) => setSimulationDraft((current) => ({ ...current, location: event.currentTarget.value }))} />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Ожидаемый приоритет
              <select className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2" value={simulationDraft.expectedPriority} onChange={(event) => setSimulationDraft((current) => ({ ...current, expectedPriority: event.currentTarget.value }))}>
                <option value="">Не проверять</option>
                <option value="P0">P0</option>
                <option value="P1">P1</option>
                <option value="P2">P2</option>
                <option value="P3">P3</option>
              </select>
            </label>
            <label className="text-sm font-medium text-slate-700">
              Ответы формы и ожидания
              <textarea
                className="mt-1 min-h-24 w-full rounded-md border border-slate-200 px-3 py-2"
                value={simulationDraft.answerSummary}
                onChange={(event) => setSimulationDraft((current) => ({ ...current, answerSummary: event.currentTarget.value }))}
              />
            </label>
            <details className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <summary className="cursor-pointer text-sm font-semibold text-slate-700">Экспертный JSON</summary>
              <pre className="mt-3 max-h-48 overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-50">
                {JSON.stringify(buildPolicyHealthSimulationRequest(selectedTemplate?.template_code ?? "", simulationDraft, searchParams), null, 2)}
              </pre>
            </details>
          </div>
          <pre className="min-h-56 overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-50">
            {simulationMutation.isError
              ? String(simulationMutation.error instanceof Error ? simulationMutation.error.message : simulationMutation.error)
              : JSON.stringify(simulationMutation.data ?? {}, null, 2)}
          </pre>
        </div>
      </section>
    </section>
  );
}
