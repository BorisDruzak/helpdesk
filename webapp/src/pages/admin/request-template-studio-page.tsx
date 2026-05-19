import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, ClipboardCheck, FileText, Play, Route, Settings2 } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { fetchHelpdeskModelRegistry } from "../../features/forms-builder/api";
import { fetchPolicyHealthDashboard, simulatePolicyHealth } from "../../features/policy-health/api";
import {
  buildGuidedSimulationPayload,
  defaultGuidedSimulationDraft,
  offeringOptions,
  policyOptions,
  requestTemplateOptions,
  serviceOptions,
  type GuidedSimulationDraft,
} from "../../features/request-template-studio/options";
import { fetchServiceCatalogDashboard } from "../../features/service-catalog/api";

const stepLabels = [
  "Услуга",
  "Вариант услуги",
  "Шаблон обращения",
  "Форма",
  "Политики",
  "Симуляция",
  "Публикация",
];

function statusTone(status: string | null | undefined) {
  if (status === "ok" || status === "published" || status === "active") {
    return "success" as const;
  }
  if (status === "warning" || status === "draft") {
    return "warning" as const;
  }
  if (status === "error" || status === "retired" || status === "inactive") {
    return "danger" as const;
  }
  return "neutral" as const;
}

export function AdminRequestTemplateStudioPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const catalogQuery = useQuery({ queryKey: ["request-template-studio", "catalog"], queryFn: fetchServiceCatalogDashboard });
  const registryQuery = useQuery({ queryKey: ["request-template-studio", "registry"], queryFn: fetchHelpdeskModelRegistry });
  const healthQuery = useQuery({ queryKey: ["request-template-studio", "policy-health"], queryFn: fetchPolicyHealthDashboard });
  const [simulationDraft, setSimulationDraft] = useState<GuidedSimulationDraft>(defaultGuidedSimulationDraft);

  const services = catalogQuery.data?.services ?? [];
  const offerings = catalogQuery.data?.offerings ?? [];
  const templates = requestTemplateOptions(registryQuery.data);
  const selectedServiceCode = searchParams.get("service") ?? services[0]?.code ?? "";
  const selectedOfferingCode = searchParams.get("offering") ?? "";
  const selectedTemplateCode = searchParams.get("template") ?? templates[0]?.value ?? "";
  const selectedService = services.find((service) => service.code === selectedServiceCode) ?? services[0] ?? null;
  const selectedOffering =
    offerings.find((offering) => (offering.full_code || offering.code) === selectedOfferingCode) ??
    offerings.find((offering) => offering.service_code === selectedService?.code) ??
    null;
  const selectedTemplate = registryQuery.data?.request_templates.find((template) => template.template_code === selectedTemplateCode) ?? null;
  const selectedHealth = healthQuery.data?.templates.find((template) => template.template_code === selectedTemplateCode) ?? null;
  const servicePickerOptions = serviceOptions(services);
  const offeringPickerOptions = offeringOptions(offerings, selectedService?.code);

  const selectedPolicies = useMemo(
    () => [
      ["priority", selectedTemplate?.priority_policy_code],
      ["routing", selectedTemplate?.routing_policy_code],
      ["sla", selectedTemplate?.sla_policy_code],
      ["ola", selectedTemplate?.ola_policy_code],
      ["approval", selectedTemplate?.approval_policy_code],
      ["diagnostic", selectedTemplate?.diagnostic_policy_code],
      ["closure", selectedTemplate?.closure_policy_code],
      ["visibility", selectedTemplate?.visibility_policy_code],
      ["notification", selectedTemplate?.notification_policy_code],
      ["reporting", selectedTemplate?.reporting_policy_code],
    ],
    [selectedTemplate],
  );

  const simulationMutation = useMutation({
    mutationFn: () => {
      if (!selectedTemplateCode) {
        throw new Error("Шаблон обращения не выбран");
      }
      return simulatePolicyHealth({
        template_code: selectedTemplateCode,
        ...buildGuidedSimulationPayload({
          ...simulationDraft,
          serviceCode: selectedService?.code ?? "",
          offeringCode: selectedOffering?.code ?? "",
        }),
      });
    },
  });

  function setParam(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) {
      next.set(key, value);
    } else {
      next.delete(key);
    }
    if (key === "service") {
      next.delete("offering");
    }
    setSearchParams(next);
  }

  return (
    <section className="workspace-page space-y-5 p-6">
      <header className="workspace-page__header">
        <div className="workspace-page__copy">
          <p className="workspace-boot__eyebrow">Service → Offering → Template → Policies</p>
          <h1>Студия шаблонов</h1>
          <p>Единый workflow от услуги и варианта услуги до формы, политик, симуляции и публикации.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link className="inline-flex h-11 items-center justify-center rounded-pill border border-border bg-white px-4 text-sm font-semibold text-slate-700 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800" to="/app/admin/forms">Открыть конструктор форм</Link>
          <Link className="inline-flex h-11 items-center justify-center rounded-pill border border-border bg-white px-4 text-sm font-semibold text-slate-700 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800" to="/app/admin/service-catalog">Открыть каталог услуг</Link>
        </div>
      </header>

      <section className="surface-panel p-4">
        <div className="grid gap-2 md:grid-cols-7">
          {stepLabels.map((label, index) => (
            <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm" key={label}>
              <p className="text-xs font-semibold text-slate-500">Шаг {index + 1}</p>
              <p className="font-semibold text-slate-900">{label}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-5">
          <section className="surface-panel p-5">
            <div className="flex items-center gap-2">
              <Route className="h-5 w-5 text-brand-700" />
              <h2 className="text-lg font-semibold text-slate-950">Услуга и вариант услуги</h2>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <label className="text-sm font-medium text-slate-700">
                Услуга
                <select className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2" value={selectedService?.code ?? ""} onChange={(event) => setParam("service", event.currentTarget.value)}>
                  {servicePickerOptions.map((option) => <option disabled={option.disabled} key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </label>
              <label className="text-sm font-medium text-slate-700">
                Вариант услуги
                <select className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2" value={selectedOffering?.full_code ?? ""} onChange={(event) => setParam("offering", event.currentTarget.value)}>
                  <option value="">Не выбран</option>
                  {offeringPickerOptions.map((option) => <option disabled={option.disabled} key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </label>
            </div>
          </section>

          <section className="surface-panel p-5">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-brand-700" />
              <h2 className="text-lg font-semibold text-slate-950">Шаблон обращения и форма</h2>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto]">
              <label className="text-sm font-medium text-slate-700">
                Шаблон обращения
                <select className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2" value={selectedTemplateCode} onChange={(event) => setParam("template", event.currentTarget.value)}>
                  {templates.map((option) => <option disabled={option.disabled} key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </label>
              <Link className="inline-flex h-11 items-center justify-center self-end rounded-pill bg-surface-subtle px-4 text-sm font-semibold text-slate-900 shadow-soft hover:bg-brand-50 hover:text-brand-800" to={`/app/admin/forms?template=${encodeURIComponent(selectedTemplateCode)}`}>Открыть форму</Link>
            </div>
          </section>

          <section className="surface-panel p-5">
            <div className="flex items-center gap-2">
              <Settings2 className="h-5 w-5 text-brand-700" />
              <h2 className="text-lg font-semibold text-slate-950">Политики</h2>
            </div>
            <div className="mt-4 grid gap-2 md:grid-cols-2">
              {selectedPolicies.map(([kind, code]) => (
                <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm" key={kind}>
                  <p className="text-xs font-semibold text-slate-500">{kind}</p>
                  <p className="font-semibold text-slate-900">{code || "Не задана"}</p>
                  <p className="text-xs text-slate-500">{policyOptions(registryQuery.data, kind ?? "").length} доступно в реестре</p>
                </div>
              ))}
            </div>
          </section>

          <section className="surface-panel p-5">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Play className="h-5 w-5 text-brand-700" />
                <h2 className="text-lg font-semibold text-slate-950">Симуляция выполнения</h2>
              </div>
              <Button disabled={!selectedTemplateCode || simulationMutation.isPending} onClick={() => simulationMutation.mutate()} type="button">
                Запустить
              </Button>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <input className="field-base px-3 py-2" placeholder="Инициатор" value={simulationDraft.requester} onChange={(event) => setSimulationDraft((current) => ({ ...current, requester: event.currentTarget.value }))} />
              <input className="field-base px-3 py-2" placeholder="Устройство" value={simulationDraft.device} onChange={(event) => setSimulationDraft((current) => ({ ...current, device: event.currentTarget.value }))} />
              <input className="field-base px-3 py-2" placeholder="Локация" value={simulationDraft.location} onChange={(event) => setSimulationDraft((current) => ({ ...current, location: event.currentTarget.value }))} />
              <select className="field-base px-3 py-2" value={simulationDraft.expectedPriority} onChange={(event) => setSimulationDraft((current) => ({ ...current, expectedPriority: event.currentTarget.value }))}>
                <option value="">Ожидаемый приоритет не задан</option>
                <option value="P0">P0</option>
                <option value="P1">P1</option>
                <option value="P2">P2</option>
                <option value="P3">P3</option>
              </select>
              <textarea className="field-base min-h-24 px-3 py-2 md:col-span-2" placeholder="Ответы формы и ожидаемые проверки" value={simulationDraft.answerSummary} onChange={(event) => setSimulationDraft((current) => ({ ...current, answerSummary: event.currentTarget.value }))} />
            </div>
            <details className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3">
              <summary className="cursor-pointer text-sm font-semibold text-slate-700">Экспертный JSON</summary>
              <pre className="mt-3 max-h-56 overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-50">
                {JSON.stringify(buildGuidedSimulationPayload(simulationDraft), null, 2)}
              </pre>
            </details>
            {simulationMutation.data || simulationMutation.isError ? (
              <pre className="mt-4 max-h-80 overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-50">
                {simulationMutation.isError ? String(simulationMutation.error) : JSON.stringify(simulationMutation.data, null, 2)}
              </pre>
            ) : null}
          </section>
        </div>

        <aside className="surface-panel p-5">
          <div className="flex items-center gap-2">
            <ClipboardCheck className="h-5 w-5 text-brand-700" />
            <h2 className="text-lg font-semibold text-slate-950">Готовность публикации</h2>
          </div>
          <div className="mt-4 space-y-3">
            <Badge tone={statusTone(selectedHealth?.health_status)}>{selectedHealth?.health_status ?? "нет данных"}</Badge>
            <p className="text-sm text-slate-600">Проверка берётся из реального Policy Health для выбранного шаблона.</p>
            {(selectedHealth?.issues ?? []).slice(0, 8).map((issue) => (
              <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm" key={`${issue.policy_kind}:${issue.path}:${issue.message}`}>
                <div className="flex items-center gap-2">
                  <Badge tone={statusTone(issue.severity)}>{issue.policy_kind}</Badge>
                  <span className="font-semibold text-slate-700">{issue.kind}</span>
                </div>
                <p className="mt-1 text-slate-600">{issue.message}</p>
              </div>
            ))}
            {selectedHealth && selectedHealth.issues.length === 0 ? (
              <p className="flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
                <CheckCircle2 className="h-4 w-4" />
                Блокирующие проблемы не найдены.
              </p>
            ) : null}
            <Link className="inline-flex h-11 w-full items-center justify-center rounded-pill bg-surface-subtle px-4 text-sm font-semibold text-slate-900 shadow-soft hover:bg-brand-50 hover:text-brand-800" to={`/app/admin/policy-health?template=${encodeURIComponent(selectedTemplateCode)}`}>Открыть проверку политик</Link>
          </div>
        </aside>
      </section>
    </section>
  );
}
