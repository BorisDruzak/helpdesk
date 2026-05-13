import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { fetchPolicyHealthDashboard, simulatePolicyHealth, type PolicyHealthTemplate } from "./api";

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
      <dl className="mt-5 grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-slate-500">Score</dt>
          <dd className="font-semibold text-slate-950">{template.health_score}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Conflicts</dt>
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
          <p className="text-sm text-slate-500">Issues не найдены.</p>
        )}
      </div>
    </aside>
  );
}

export function PolicyHealthPanel() {
  const [healthFilter, setHealthFilter] = useState("all");
  const [kindFilter, setKindFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [simulationInput, setSimulationInput] = useState('{"request_form_data":{},"custom_fields":{},"device_metadata":{},"requester_context":{}}');

  const dashboardQuery = useQuery({
    queryKey: ["policy-health-dashboard"],
    queryFn: fetchPolicyHealthDashboard,
  });

  const templates = dashboardQuery.data?.templates ?? [];
  const selectedTemplate = templates.find((template) => template.template_code === selectedCode) ?? templates[0] ?? null;
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
      const parsed = JSON.parse(simulationInput) as Record<string, unknown>;
      return simulatePolicyHealth({
        template_code: selectedTemplate.template_code,
        request_form_data: (parsed.request_form_data as Record<string, unknown>) ?? {},
        custom_fields: (parsed.custom_fields as Record<string, unknown>) ?? {},
        device_metadata: (parsed.device_metadata as Record<string, unknown>) ?? {},
        requester_context: (parsed.requester_context as Record<string, unknown>) ?? {},
      });
    },
  });

  if (dashboardQuery.isLoading) {
    return <section className="workspace-page p-6 text-sm text-slate-500">Загрузка Policy Health...</section>;
  }

  if (dashboardQuery.isError || !dashboardQuery.data) {
    return <section className="workspace-page p-6 text-sm text-rose-700">Не удалось загрузить Policy Health.</section>;
  }

  return (
    <section className="workspace-page space-y-5 p-6">
      <header className="workspace-page__header">
        <div className="workspace-page__copy">
          <p className="workspace-boot__eyebrow">Helpdesk governance</p>
          <h1>Policy Health</h1>
        </div>
        <dl className="workspace-page__stats">
          <div>
            <dt>Total</dt>
            <dd>{dashboardQuery.data.summary.total}</dd>
          </div>
          <div>
            <dt>Warnings</dt>
            <dd>{dashboardQuery.data.summary.warning}</dd>
          </div>
          <div>
            <dt>Errors</dt>
            <dd>{dashboardQuery.data.summary.error}</dd>
          </div>
        </dl>
      </header>

      <section className="surface-panel p-4">
        <div className="grid gap-3 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <label className="text-sm font-medium text-slate-700">
            Search
            <input className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2" value={query} onChange={(event) => setQuery(event.currentTarget.value)} />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Health
            <select className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2" value={healthFilter} onChange={(event) => setHealthFilter(event.currentTarget.value)}>
              <option value="all">all</option>
              <option value="ok">ok</option>
              <option value="warning">warning</option>
              <option value="error">error</option>
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Policy kind
            <select className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2" value={kindFilter} onChange={(event) => setKindFilter(event.currentTarget.value)}>
              <option value="all">all</option>
              {POLICY_COLUMNS.map((kind) => <option key={kind} value={kind}>{kind}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Template status
            <select className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2" value={statusFilter} onChange={(event) => setStatusFilter(event.currentTarget.value)}>
              <option value="all">all</option>
              <option value="published">published</option>
              <option value="draft">draft</option>
              <option value="archived">archived</option>
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
                  <th className="px-4 py-3">Template</th>
                  <th className="px-4 py-3">Health</th>
                  <th className="px-4 py-3">Issues</th>
                  {POLICY_COLUMNS.map((kind) => <th key={kind} className="px-3 py-3">{kind}</th>)}
                  <th className="px-4 py-3">Checked</th>
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
            <h2 className="text-base font-semibold text-slate-950">Dry-run simulation</h2>
            <p className="mt-1 text-sm text-slate-500">{selectedTemplate?.template_code ?? "template not selected"}</p>
          </div>
          <Button disabled={!selectedTemplate || simulationMutation.isPending} onClick={() => simulationMutation.mutate()}>
            Run preview
          </Button>
        </div>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <textarea
            className="min-h-56 rounded-md border border-slate-200 p-3 font-mono text-xs"
            value={simulationInput}
            onChange={(event) => setSimulationInput(event.currentTarget.value)}
          />
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
