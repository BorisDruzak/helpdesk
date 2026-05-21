import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  ExternalLink,
  FileText,
  Play,
  Route,
  Save,
  Settings2,
} from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import {
  fetchAdminFormsCatalog,
  fetchHelpdeskModelRegistry,
  type AdminFormsFieldItem,
  type AdminFormsFormItem,
  type AdminHelpdeskFormSchemaItem,
  type AdminHelpdeskModelPayload,
  type AdminHelpdeskRequestTemplateItem,
} from "../../features/forms-builder/api";
import {
  fetchPolicyHealthDashboard,
  simulatePolicyHealth,
  type PolicyHealthIssue,
  type PolicyHealthSimulationResult,
  type PolicyHealthTemplate,
} from "../../features/policy-health/api";
import {
  buildStudioSimulationPayload,
  defaultGuidedSimulationDraft,
  offeringOptions,
  POLICY_KIND_LABELS,
  POLICY_KINDS,
  policyOptions,
  requestTemplateOptions,
  serviceOptions,
  type GuidedSimulationDraft,
  type StudioPolicyKind,
} from "../../features/request-template-studio/options";
import { fetchServiceCatalogDashboard, type AdminServiceCatalogOffering, type AdminServiceCatalogService } from "../../features/service-catalog/api";

type StepStatus = "ok" | "warning" | "error" | "not_configured";

type FormPreviewModel = {
  title: string;
  description: string | null;
  fields: Array<{
    key: string;
    label: string;
    type: string;
    required: boolean;
    options?: Array<Record<string, unknown>>;
    visibility?: Record<string, unknown> | null;
    visibleWhen?: AdminFormsFieldItem["visible_when"];
    processMapping?: Record<string, unknown>;
  }>;
  source: "registry" | "forms-builder";
};

type PublicationGate = {
  key: string;
  label: string;
  status: StepStatus;
  explanation: string;
  actionLabel?: string;
  href?: string;
};

const STEP_LABELS = [
  { key: "service", label: "Услуга" },
  { key: "offering", label: "Вариант услуги" },
  { key: "template", label: "Шаблон обращения" },
  { key: "form", label: "Форма" },
  { key: "policies", label: "Политики" },
  { key: "simulation", label: "Симуляция" },
  { key: "publication", label: "Публикация" },
] as const;

const POLICY_REF_KEYS: Record<StudioPolicyKind, keyof AdminHelpdeskRequestTemplateItem> = {
  priority: "priority_policy_code",
  routing: "routing_policy_code",
  sla: "sla_policy_code",
  ola: "ola_policy_code",
  approval: "approval_policy_code",
  diagnostic: "diagnostic_policy_code",
  closure: "closure_policy_code",
  visibility: "visibility_policy_code",
  notification: "notification_policy_code",
  reporting: "reporting_policy_code",
};

const SIMULATION_CARDS: Array<{ key: keyof PolicyHealthSimulationResult | "notification" | "reporting"; title: string }> = [
  { key: "routing", title: "Маршрутизация" },
  { key: "priority", title: "Приоритет" },
  { key: "sla", title: "SLA" },
  { key: "ola", title: "OLA" },
  { key: "approval", title: "Согласование" },
  { key: "diagnostic", title: "Диагностика" },
  { key: "closure", title: "Закрытие" },
  { key: "visibility", title: "Видимость" },
  { key: "notification", title: "Уведомления" },
  { key: "reporting", title: "Отчётность" },
];

function statusTone(status: string | null | undefined) {
  if (status === "ok" || status === "published" || status === "active") {
    return "success" as const;
  }
  if (status === "warning" || status === "draft" || status === "not_configured") {
    return "warning" as const;
  }
  if (status === "error" || status === "retired" || status === "inactive" || status === "critical") {
    return "danger" as const;
  }
  return "neutral" as const;
}

function formatStatus(status: string | null | undefined): string {
  const labels: Record<string, string> = {
    ok: "В норме",
    warning: "Предупреждение",
    error: "Ошибка",
    critical: "Критично",
    not_configured: "Не настроено",
    published: "Опубликовано",
    draft: "Черновик",
    active: "Активно",
    inactive: "Неактивно",
    retired: "Выведено",
  };
  return status ? labels[status] ?? status : "Нет данных";
}

function issueTone(issue: PolicyHealthIssue) {
  return issue.severity === "critical" || issue.severity === "error" ? "danger" : issue.severity === "warning" ? "warning" : "info";
}

function tech(value: string | number | null | undefined) {
  return value === null || value === undefined || value === "" ? "не задано" : String(value);
}

function buildStudioUrl(params: { service?: string | null; offering?: string | null; template?: string | null }) {
  const search = new URLSearchParams();
  if (params.service) {
    search.set("service", params.service);
  }
  if (params.offering) {
    search.set("offering", params.offering);
  }
  if (params.template) {
    search.set("template", params.template);
  }
  const suffix = search.toString();
  return `/app/admin/request-template-studio${suffix ? `?${suffix}` : ""}`;
}

function buildDeepLink(base: string, params: { service?: string | null; offering?: string | null; template?: string | null }) {
  const search = new URLSearchParams();
  if (params.service) {
    search.set("service", params.service);
  }
  if (params.offering) {
    search.set("offering", params.offering);
  }
  if (params.template) {
    search.set("template", params.template);
  }
  const suffix = search.toString();
  return `${base}${suffix ? `?${suffix}` : ""}`;
}

function selectedTemplatePolicy(template: AdminHelpdeskRequestTemplateItem | null, kind: StudioPolicyKind) {
  const key = POLICY_REF_KEYS[kind];
  const value = template?.[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function offeringPolicy(offering: AdminServiceCatalogOffering | null, kind: StudioPolicyKind) {
  const key = `${kind}_policy_code` as keyof AdminServiceCatalogOffering;
  const value = offering?.[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function servicePolicy(service: AdminServiceCatalogService | null, kind: StudioPolicyKind) {
  if (kind === "routing") {
    return service?.default_routing_policy_code ?? null;
  }
  if (kind === "sla") {
    return service?.default_sla_policy_code ?? null;
  }
  if (kind === "diagnostic") {
    return service?.default_diagnostic_policy_code ?? null;
  }
  return null;
}

function policyBindingCode(
  template: AdminHelpdeskRequestTemplateItem | null,
  offering: AdminServiceCatalogOffering | null,
  service: AdminServiceCatalogService | null,
  kind: StudioPolicyKind,
) {
  return selectedTemplatePolicy(template, kind) ?? offeringPolicy(offering, kind) ?? servicePolicy(service, kind);
}

function findFormPreview(
  registry: AdminHelpdeskModelPayload | null | undefined,
  forms: AdminFormsFormItem[],
  template: AdminHelpdeskRequestTemplateItem | null,
): FormPreviewModel | null {
  if (!template) {
    return null;
  }
  const schema =
    registry?.form_schemas.find((item) => item.schema_id === template.form_schema_id) ??
    registry?.form_schemas.find((item) => item.request_template_code === template.template_code) ??
    registry?.form_schemas.find((item) => item.form_key === template.template_code);
  if (schema) {
    return fromRegistrySchema(schema);
  }
  const form = forms.find((item) => item.key === template.template_code);
  return form ? fromFormsBuilder(form) : null;
}

function fromRegistrySchema(schema: AdminHelpdeskFormSchemaItem): FormPreviewModel {
  return {
    title: schema.title || schema.schema_id,
    description: schema.description,
    source: "registry",
    fields: schema.fields.map((field) => ({
      key: field.key,
      label: field.label || field.key,
      type: field.type,
      required: field.required,
      options: field.options,
      visibility: field.visibility,
      processMapping: field.process_mapping,
    })),
  };
}

function fromFormsBuilder(form: AdminFormsFormItem): FormPreviewModel {
  return {
    title: form.title || form.key,
    description: form.description,
    source: "forms-builder",
    fields: form.fields.map((field) => ({
      key: field.key,
      label: field.label || field.key,
      type: field.type_label || field.type,
      required: field.required,
      options: field.options as Array<Record<string, unknown>>,
      visibleWhen: field.visible_when,
      processMapping: field.process_mapping,
    })),
  };
}

function countConditionalFields(form: FormPreviewModel | null) {
  return form?.fields.filter((field) => field.visibleWhen || (field.visibility && Object.keys(field.visibility).length > 0)).length ?? 0;
}

function hasBlockingIssue(issue: PolicyHealthIssue) {
  return issue.severity === "critical" || issue.severity === "error";
}

function getResultRecord(result: PolicyHealthSimulationResult | undefined, key: string): Record<string, unknown> | null {
  if (!result) {
    return null;
  }
  const value = (result as unknown as Record<string, unknown>)[key];
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function firstString(record: Record<string, unknown> | null, keys: string[]) {
  if (!record) {
    return null;
  }
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) {
      return value;
    }
    if (typeof value === "number") {
      return String(value);
    }
  }
  return null;
}

function summarizeSimulationRecord(record: Record<string, unknown> | null, key: string) {
  if (!record) {
    return { status: "not_configured", policy: "нет данных", decision: "Симуляция не вернула этот блок" };
  }
  const status = firstString(record, ["status", "state", "result", "decision_status"]) ?? "ok";
  const policy = firstString(record, ["policy_code", "reference", "policy", "selected_policy", "policy_ref"]) ?? "не указана";
  const decision =
    firstString(record, [
      "target_queue_name",
      "target_queue",
      "queue",
      "priority",
      "sla_target",
      "ola_target",
      "required",
      "mode",
      "profile_code",
      "public_status",
    ]) ?? (key === "approval" ? "Согласование не требуется или не определено" : "Решение см. в деталях");
  return { status, policy, decision };
}

function buildPublicationGates({
  selectedService,
  selectedOffering,
  selectedTemplate,
  formPreview,
  selectedHealth,
  simulationResult,
  links,
}: {
  selectedService: AdminServiceCatalogService | null;
  selectedOffering: AdminServiceCatalogOffering | null;
  selectedTemplate: AdminHelpdeskRequestTemplateItem | null;
  formPreview: FormPreviewModel | null;
  selectedHealth: PolicyHealthTemplate | null;
  simulationResult: PolicyHealthSimulationResult | undefined;
  links: { forms: string; serviceCatalog: string; policyHealth: string };
}): PublicationGate[] {
  const policyGate = (kind: StudioPolicyKind, required = true): PublicationGate => {
    const code = selectedTemplatePolicy(selectedTemplate, kind);
    if (code) {
      return {
        key: `policy-${kind}`,
        label: `${POLICY_KIND_LABELS[kind]} настроена`,
        status: "ok",
        explanation: `Привязана политика ${code}.`,
        actionLabel: "Открыть Policy Health",
        href: links.policyHealth,
      };
    }
    return {
      key: `policy-${kind}`,
      label: `${POLICY_KIND_LABELS[kind]} настроена`,
      status: required ? "error" : "warning",
      explanation: required ? "Политика не привязана к шаблону." : "Политика не привязана; проверьте, нужна ли она для этого шаблона.",
      actionLabel: "Открыть редактор формы",
      href: links.forms,
    };
  };
  const blockingHealth = selectedHealth?.issues.some(hasBlockingIssue) ?? false;
  return [
    {
      key: "service",
      label: "Услуга выбрана",
      status: selectedService ? "ok" : "error",
      explanation: selectedService ? `Выбрана услуга ${selectedService.public_title || selectedService.code}.` : "Выберите услугу из каталога.",
      actionLabel: "Открыть каталог услуг",
      href: links.serviceCatalog,
    },
    {
      key: "offering",
      label: "Вариант услуги выбран",
      status: selectedOffering ? "ok" : "warning",
      explanation: selectedOffering ? `Выбран вариант ${selectedOffering.public_title || selectedOffering.full_code}.` : "Вариант услуги не выбран.",
      actionLabel: "Открыть каталог услуг",
      href: links.serviceCatalog,
    },
    {
      key: "template",
      label: "Шаблон обращения выбран",
      status: selectedTemplate ? "ok" : "error",
      explanation: selectedTemplate ? `Шаблон ${selectedTemplate.template_code} активен: ${selectedTemplate.is_active ? "да" : "нет"}.` : "Выберите шаблон обращения.",
    },
    {
      key: "form",
      label: "Форма содержит поля",
      status: formPreview?.fields.length ? "ok" : "error",
      explanation: formPreview?.fields.length ? `Полей: ${formPreview.fields.length}, обязательных: ${formPreview.fields.filter((field) => field.required).length}.` : "Форма для шаблона не найдена.",
      actionLabel: "Редактировать форму",
      href: links.forms,
    },
    policyGate("priority"),
    policyGate("routing"),
    policyGate("sla"),
    policyGate("ola", false),
    policyGate("approval", false),
    policyGate("diagnostic", false),
    policyGate("closure"),
    policyGate("visibility"),
    policyGate("notification", false),
    {
      key: "simulation",
      label: "Симуляция выполнена",
      status: simulationResult ? "ok" : "warning",
      explanation: simulationResult ? "Последний тестовый прогон выполнен для выбранного контекста." : "Запустите симуляцию перед публикацией.",
    },
    {
      key: "policy-health",
      label: "Нет блокирующих проблем Policy Health",
      status: !selectedHealth ? "warning" : blockingHealth || selectedHealth.health_status === "error" ? "error" : selectedHealth.health_status === "warning" ? "warning" : "ok",
      explanation: !selectedHealth
        ? "Для шаблона нет данных Policy Health."
        : blockingHealth
          ? "Найдены ошибки, которые могут блокировать публикацию."
          : `Состояние Policy Health: ${formatStatus(selectedHealth.health_status)}.`,
      actionLabel: "Открыть Policy Health",
      href: links.policyHealth,
    },
  ];
}

export function AdminRequestTemplateStudioPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const catalogQuery = useQuery({ queryKey: ["request-template-studio", "catalog"], queryFn: fetchServiceCatalogDashboard });
  const registryQuery = useQuery({ queryKey: ["request-template-studio", "registry"], queryFn: fetchHelpdeskModelRegistry });
  const healthQuery = useQuery({ queryKey: ["request-template-studio", "policy-health"], queryFn: fetchPolicyHealthDashboard });
  const formsQuery = useQuery({ queryKey: ["request-template-studio", "forms"], queryFn: fetchAdminFormsCatalog });
  const [simulationDraft, setSimulationDraft] = useState<GuidedSimulationDraft>(defaultGuidedSimulationDraft);
  const [offeringResetNotice, setOfferingResetNotice] = useState(false);

  const services = catalogQuery.data?.services ?? [];
  const offerings = catalogQuery.data?.offerings ?? [];
  const templates = requestTemplateOptions(registryQuery.data);
  const selectedServiceCode = searchParams.get("service") ?? services[0]?.code ?? "";
  const selectedService = services.find((service) => service.code === selectedServiceCode) ?? services[0] ?? null;
  const selectedOfferingCode = searchParams.get("offering") ?? "";
  const selectedOfferingCandidate =
    offerings.find((offering) => offering.full_code === selectedOfferingCode || offering.code === selectedOfferingCode) ?? null;
  const selectedOffering = selectedOfferingCandidate?.service_code === selectedService?.code ? selectedOfferingCandidate : null;
  const selectedTemplateCode = searchParams.get("template") ?? selectedOffering?.request_template_key ?? templates[0]?.value ?? "";
  const selectedTemplate = registryQuery.data?.request_templates.find((template) => template.template_code === selectedTemplateCode) ?? null;
  const selectedHealth = healthQuery.data?.templates.find((template) => template.template_code === selectedTemplateCode) ?? null;
  const servicePickerOptions = serviceOptions(services);
  const offeringPickerOptions = offeringOptions(offerings, selectedService?.code);
  const formPreview = findFormPreview(registryQuery.data, formsQuery.data?.forms ?? [], selectedTemplate);
  const deepParams = {
    service: selectedService?.code ?? null,
    offering: selectedOffering?.full_code ?? null,
    template: selectedTemplateCode || null,
  };
  const links = {
    forms: buildDeepLink("/app/admin/forms", deepParams),
    serviceCatalog: buildDeepLink("/app/admin/service-catalog", deepParams),
    policyHealth: buildDeepLink("/app/admin/policy-health", deepParams),
    studio: buildStudioUrl(deepParams),
  };
  const studioSimulationPayload = buildStudioSimulationPayload({
    selectedTemplateCode,
    selectedService,
    selectedOffering,
    simulationDraft,
  });
  const selectedPolicies = useMemo(
    () => POLICY_KINDS.map((kind) => ({ kind, code: policyBindingCode(selectedTemplate, selectedOffering, selectedService, kind) })),
    [selectedOffering, selectedService, selectedTemplate],
  );
  const blockingIssues = selectedHealth?.issues.filter(hasBlockingIssue) ?? [];
  const simulationMutation = useMutation({
    mutationFn: () => {
      if (!selectedTemplateCode) {
        throw new Error("Шаблон обращения не выбран");
      }
      return simulatePolicyHealth(studioSimulationPayload);
    },
  });
  const gatesWithSimulation = buildPublicationGates({
    selectedService,
    selectedOffering,
    selectedTemplate,
    formPreview,
    selectedHealth,
    simulationResult: simulationMutation.data,
    links,
  });
  const overallGateStatus: StepStatus = gatesWithSimulation.some((gate) => gate.status === "error")
    ? "error"
    : gatesWithSimulation.some((gate) => gate.status === "warning")
      ? "warning"
      : "ok";
  const stepStatuses = {
    service: selectedService ? "ok" : "error",
    offering: selectedOffering ? "ok" : "warning",
    template: selectedTemplate ? "ok" : "error",
    form: formPreview?.fields.length ? "ok" : "error",
    policies: selectedPolicies.some((policy) => !policy.code) ? "warning" : "ok",
    simulation: simulationMutation.data ? "ok" : "not_configured",
    publication: overallGateStatus,
  } satisfies Record<string, StepStatus>;

  useEffect(() => {
    if (!selectedOfferingCode || !selectedOfferingCandidate || !selectedService) {
      return;
    }
    if (selectedOfferingCandidate.service_code === selectedService.code) {
      return;
    }
    const next = new URLSearchParams(searchParams);
    next.delete("offering");
    setSearchParams(next, { replace: true });
    setOfferingResetNotice(true);
  }, [searchParams, selectedOfferingCandidate, selectedOfferingCode, selectedService, setSearchParams]);

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

  function updateSimulationDraft(key: keyof GuidedSimulationDraft, value: string) {
    setSimulationDraft((current) => ({ ...current, [key]: value }));
  }

  const serviceOfferingsCount = selectedService ? offerings.filter((offering) => offering.service_code === selectedService.code).length : 0;
  const requiredFieldCount = formPreview?.fields.filter((field) => field.required).length ?? 0;
  const conditionalFieldCount = countConditionalFields(formPreview);

  return (
    <section className="workspace-page space-y-5 p-6">
      <header className="workspace-page__header">
        <div className="workspace-page__copy">
          <p className="workspace-boot__eyebrow">Услуга → Вариант услуги → Шаблон → Публикация</p>
          <h1>Студия шаблонов</h1>
          <p>Единый workflow от услуги и варианта услуги до формы, политик, симуляции и публикации.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button disabled type="button" variant="secondary" leadingIcon={<Save className="h-4 w-4" />}>
            Сохранить изменения
          </Button>
          <Button disabled={!selectedTemplateCode || simulationMutation.isPending} onClick={() => simulationMutation.mutate()} type="button" leadingIcon={<Play className="h-4 w-4" />}>
            Запустить симуляцию
          </Button>
          <a className="inline-flex h-11 items-center justify-center gap-2 rounded-pill border border-border bg-white px-4 text-sm font-semibold text-slate-700 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800" href="#publication-gates">
            <ClipboardCheck className="h-4 w-4" />
            Проверить публикацию
          </a>
        </div>
      </header>

      <section className="surface-panel p-4">
        <div className="grid gap-2 md:grid-cols-7">
          {STEP_LABELS.map((step, index) => (
            <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm" key={step.key}>
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-semibold text-slate-500">Шаг {index + 1}</p>
                <Badge tone={statusTone(stepStatuses[step.key])}>{formatStatus(stepStatuses[step.key])}</Badge>
              </div>
              <p className="mt-2 font-semibold text-slate-900">{step.label}</p>
            </div>
          ))}
        </div>
      </section>

      {offeringResetNotice ? (
        <div className="rounded-[1rem] border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Вариант услуги не относится к выбранной услуге и был сброшен.
        </div>
      ) : null}

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_390px]">
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
                <select className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2" value={selectedOffering?.full_code ?? selectedOffering?.code ?? ""} onChange={(event) => setParam("offering", event.currentTarget.value)}>
                  <option value="">Не выбран</option>
                  {offeringPickerOptions.map((option) => <option disabled={option.disabled} key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </label>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <ObjectSummary
                title={selectedService?.public_title || selectedService?.name || "Услуга не выбрана"}
                rows={[
                  ["Код", tech(selectedService?.code)],
                  ["Статус", formatStatus(selectedService?.lifecycle_status)],
                  ["Видимость", tech(selectedService?.visibility)],
                  ["Вариантов", String(serviceOfferingsCount)],
                  ["Owner/default queue", tech(selectedService?.owner_queue_id ?? selectedService?.default_queue_id)],
                ]}
              />
              <ObjectSummary
                title={selectedOffering?.public_title || "Вариант услуги не выбран"}
                rows={[
                  ["Код", tech(selectedOffering?.full_code ?? selectedOffering?.code)],
                  ["Статус", formatStatus(selectedOffering?.lifecycle_status)],
                  ["Request type", tech(selectedOffering?.request_type)],
                  ["Шаблон", tech(selectedOffering?.request_template_key)],
                  ["Видимость", tech(selectedOffering?.visibility)],
                ]}
              />
            </div>
          </section>

          <section className="surface-panel p-5">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-brand-700" />
              <h2 className="text-lg font-semibold text-slate-950">Шаблон обращения</h2>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto]">
              <label className="text-sm font-medium text-slate-700">
                Шаблон обращения
                <select className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2" value={selectedTemplateCode} onChange={(event) => setParam("template", event.currentTarget.value)}>
                  {templates.map((option) => <option disabled={option.disabled} key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </label>
              <Link className="inline-flex h-11 items-center justify-center self-end rounded-pill bg-surface-subtle px-4 text-sm font-semibold text-slate-900 shadow-soft hover:bg-brand-50 hover:text-brand-800" to={links.forms}>Редактировать форму</Link>
            </div>
            <div className="mt-4">
              <TemplateBindingSummary
                selectedService={selectedService}
                selectedOffering={selectedOffering}
                selectedTemplate={selectedTemplate}
                formPreview={formPreview}
                selectedPolicies={selectedPolicies}
              />
            </div>
            {selectedTemplate && selectedOffering?.request_template_key && selectedOffering.request_template_key !== selectedTemplate.template_code ? (
              <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                Шаблон выбран, но его связь с услугой/вариантом услуги не подтверждена.
              </div>
            ) : null}
          </section>

          <section className="surface-panel p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <FileText className="h-5 w-5 text-brand-700" />
                  <h2 className="text-lg font-semibold text-slate-950">Форма обращения</h2>
                </div>
                <p className="mt-1 text-sm text-slate-500">Preview строится из реального registry form schema или текущего Forms Builder каталога.</p>
              </div>
              <Link className="inline-flex h-9 items-center justify-center gap-2 rounded-pill border border-border bg-white px-3 text-xs font-semibold text-slate-700 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800" to={links.forms}>
                Редактировать форму
                <ExternalLink className="h-3.5 w-3.5" />
              </Link>
            </div>
            {formPreview ? (
              <>
                <dl className="mt-4 grid gap-3 md:grid-cols-4">
                  <MetricCard label="Полей" value={String(formPreview.fields.length)} />
                  <MetricCard label="Обязательных" value={String(requiredFieldCount)} />
                  <MetricCard label="Условных" value={String(conditionalFieldCount)} />
                  <MetricCard label="Источник" value={formPreview.source === "registry" ? "Registry" : "Forms Builder"} />
                </dl>
                <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-4">
                  <h3 className="font-semibold text-slate-950">{formPreview.title}</h3>
                  {formPreview.description ? <p className="mt-1 text-sm text-slate-600">{formPreview.description}</p> : null}
                  <RequestTemplateFieldList form={formPreview} />
                </div>
              </>
            ) : (
              <EmptyPanel title="Форма не найдена" description="Для выбранного шаблона нет form_schema_id или legacy формы. Откройте Forms Builder и привяжите форму." />
            )}
          </section>

          <section className="surface-panel p-5">
            <div className="flex items-center gap-2">
              <Settings2 className="h-5 w-5 text-brand-700" />
              <h2 className="text-lg font-semibold text-slate-950">Политики шаблона</h2>
            </div>
            <p className="mt-1 text-sm text-slate-500">Привязки показаны из шаблона, затем из варианта услуги и услуги. Изменение через Studio пока read-only.</p>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {POLICY_KINDS.map((kind) => (
                <PolicyCard
                  key={kind}
                  kind={kind}
                  code={policyBindingCode(selectedTemplate, selectedOffering, selectedService, kind)}
                  registry={registryQuery.data}
                  health={selectedHealth}
                  href={buildDeepLink("/app/admin/policy-health", { ...deepParams, template: selectedTemplateCode, service: selectedService?.code })}
                />
              ))}
            </div>
          </section>

          <section className="surface-panel p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Play className="h-5 w-5 text-brand-700" />
                <h2 className="text-lg font-semibold text-slate-950">Симуляция выполнения</h2>
              </div>
              <Button disabled={!selectedTemplateCode || simulationMutation.isPending} onClick={() => simulationMutation.mutate()} type="button">
                Запустить симуляцию
              </Button>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge tone="brand">Услуга: {tech(studioSimulationPayload.service_code)}</Badge>
              <Badge tone="brand">Вариант: {tech(studioSimulationPayload.offering_full_code)}</Badge>
              <Badge tone="brand">Шаблон: {tech(studioSimulationPayload.template_code)}</Badge>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <input className="field-base px-3 py-2" placeholder="Инициатор" value={simulationDraft.requester} onChange={(event) => updateSimulationDraft("requester", event.currentTarget.value)} />
              <input className="field-base px-3 py-2" placeholder="Устройство" value={simulationDraft.device} onChange={(event) => updateSimulationDraft("device", event.currentTarget.value)} />
              <input className="field-base px-3 py-2" placeholder="Локация" value={simulationDraft.location} onChange={(event) => updateSimulationDraft("location", event.currentTarget.value)} />
              <select className="field-base px-3 py-2" value={simulationDraft.expectedPriority} onChange={(event) => updateSimulationDraft("expectedPriority", event.currentTarget.value)}>
                <option value="">Ожидаемый приоритет не задан</option>
                <option value="P0">P0</option>
                <option value="P1">P1</option>
                <option value="P2">P2</option>
                <option value="P3">P3</option>
              </select>
              <textarea className="field-base min-h-24 px-3 py-2 md:col-span-2" placeholder="Краткое содержание ответов формы" value={simulationDraft.answerSummary} onChange={(event) => updateSimulationDraft("answerSummary", event.currentTarget.value)} />
            </div>
            <SimulationResult result={simulationMutation.data} error={simulationMutation.error} />
            <details className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3">
              <summary className="cursor-pointer text-sm font-semibold text-slate-700">Экспертный JSON запроса</summary>
              <pre data-testid="studio-simulation-payload" className="mt-3 max-h-56 overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-50">
                {JSON.stringify(studioSimulationPayload, null, 2)}
              </pre>
            </details>
          </section>
        </div>

        <aside className="space-y-5">
          <section id="publication-gates" className="surface-panel p-5">
            <div className="flex items-center gap-2">
              <ClipboardCheck className="h-5 w-5 text-brand-700" />
              <h2 className="text-lg font-semibold text-slate-950">Готовность публикации</h2>
            </div>
            <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
              <Badge tone={statusTone(overallGateStatus)}>{overallGateStatus === "ok" ? "Можно публиковать" : overallGateStatus === "warning" ? "Есть предупреждения" : "Есть блокирующие проблемы"}</Badge>
              <p className="mt-2 text-sm text-slate-600">Публикация через Studio пока недоступна: endpoint для safe publish из Studio не найден в текущем frontend contract.</p>
              <Button className="mt-3 w-full" disabled type="button" variant="secondary">Публикация через Studio пока недоступна</Button>
            </div>
            <div className="mt-4 space-y-2">
              {gatesWithSimulation.map((gate) => (
                <div className="rounded-md border border-slate-200 bg-white p-3 text-sm" key={gate.key}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-slate-900">{gate.label}</span>
                    <Badge tone={statusTone(gate.status)}>{formatStatus(gate.status)}</Badge>
                  </div>
                  <p className="mt-1 text-slate-600">{gate.explanation}</p>
                  {gate.href && gate.actionLabel ? (
                    <Link className="mt-2 inline-flex text-xs font-semibold text-brand-700 hover:text-brand-900" to={gate.href}>{gate.actionLabel}</Link>
                  ) : null}
                </div>
              ))}
            </div>
          </section>

          <section className="surface-panel p-5">
            <h2 className="text-lg font-semibold text-slate-950">Выбранный контекст</h2>
            <dl className="mt-3 space-y-2 text-sm">
              <ContextRow label="Услуга" value={selectedService?.public_title || selectedService?.code} />
              <ContextRow label="Вариант услуги" value={selectedOffering?.public_title || selectedOffering?.full_code} />
              <ContextRow label="Шаблон" value={selectedTemplate?.public_title || selectedTemplate?.template_code} />
              <ContextRow label="Форма" value={formPreview?.title} />
              <ContextRow label="Policy Health" value={selectedHealth ? formatStatus(selectedHealth.health_status) : "нет данных"} />
            </dl>
          </section>

          <section className="surface-panel p-5">
            <h2 className="text-lg font-semibold text-slate-950">Блокеры</h2>
            {blockingIssues.length ? (
              <div className="mt-3 space-y-2">
                {blockingIssues.slice(0, 6).map((issue, index) => (
                  <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" key={`${issue.policy_kind}:${issue.path}:${index}`}>
                    <Badge tone={issueTone(issue)}>{POLICY_KIND_LABELS[issue.policy_kind] ?? issue.policy_kind}</Badge>
                    <p className="mt-2">{issue.message}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-3 flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
                <CheckCircle2 className="h-4 w-4" />
                Блокирующие проблемы не найдены.
              </p>
            )}
          </section>

          <section className="surface-panel p-5">
            <h2 className="text-lg font-semibold text-slate-950">Экспертные разделы</h2>
            <div className="mt-3 space-y-2">
              <DeepLink href={links.forms} label="Открыть конструктор форм" />
              <DeepLink href={links.serviceCatalog} label="Открыть каталог услуг" />
              <DeepLink href={links.policyHealth} label="Открыть проверку политик" />
            </div>
            <details className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
              <summary className="cursor-pointer text-sm font-semibold text-slate-700">Открыть JSON/экспертный режим</summary>
              <pre className="mt-3 max-h-64 overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-50">
                {JSON.stringify({ service: selectedService, offering: selectedOffering, template: selectedTemplate, health: selectedHealth }, null, 2)}
              </pre>
            </details>
          </section>
        </aside>
      </section>
    </section>
  );
}

function ObjectSummary({ title, rows }: { title: string; rows: Array<[string, string]> }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <h3 className="font-semibold text-slate-950">{title}</h3>
      <dl className="mt-2 space-y-1 text-xs text-slate-600">
        {rows.map(([label, value]) => (
          <div className="flex min-w-0 items-center justify-between gap-3" key={label}>
            <dt>{label}</dt>
            <dd className="min-w-0 truncate font-medium text-slate-900">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function TemplateBindingSummary({
  selectedService,
  selectedOffering,
  selectedTemplate,
  formPreview,
  selectedPolicies,
}: {
  selectedService: AdminServiceCatalogService | null;
  selectedOffering: AdminServiceCatalogOffering | null;
  selectedTemplate: AdminHelpdeskRequestTemplateItem | null;
  formPreview: FormPreviewModel | null;
  selectedPolicies: Array<{ kind: StudioPolicyKind; code: string | null }>;
}) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
      <h3 className="font-semibold text-slate-950">Связка шаблона</h3>
      <div className="mt-3 grid gap-2 md:grid-cols-3">
        <MiniFact label="Услуга" value={selectedService?.public_title || selectedService?.code} />
        <MiniFact label="Вариант услуги" value={selectedOffering?.public_title || selectedOffering?.full_code} />
        <MiniFact label="Шаблон" value={selectedTemplate?.public_title || selectedTemplate?.template_code} />
        <MiniFact label="Form schema" value={selectedTemplate?.form_schema_id || formPreview?.title} />
        {selectedPolicies.map((policy) => (
          <MiniFact key={policy.kind} label={POLICY_KIND_LABELS[policy.kind] ?? policy.kind} value={policy.code} />
        ))}
      </div>
    </div>
  );
}

function MiniFact({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div className="min-w-0 rounded-md border border-slate-200 bg-white px-3 py-2">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-slate-900">{tech(value)}</p>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-3">
      <dt className="text-xs font-semibold text-slate-500">{label}</dt>
      <dd className="mt-1 text-xl font-semibold text-slate-950">{value}</dd>
    </div>
  );
}

function EmptyPanel({ title, description }: { title: string; description: string }) {
  return (
    <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-4 text-sm">
      <p className="font-semibold text-slate-900">{title}</p>
      <p className="mt-1 text-slate-600">{description}</p>
    </div>
  );
}

function RequestTemplateFieldList({ form }: { form: FormPreviewModel }) {
  return (
    <div className="mt-4 grid gap-2">
      {form.fields.map((field) => (
        <div className="rounded-md border border-slate-200 bg-white p-3" key={field.key}>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-slate-900">{field.label}</span>
            <Badge tone="neutral">{field.type}</Badge>
            {field.required ? <Badge tone="warning">обязательное</Badge> : <Badge tone="neutral">необязательное</Badge>}
            {field.visibleWhen || field.visibility ? <Badge tone="info">условная видимость</Badge> : null}
          </div>
          <p className="mt-1 text-xs text-slate-500">Ключ: {field.key}</p>
          {field.visibleWhen ? (
            <p className="mt-1 text-xs text-slate-600">
              Показывать, если {field.visibleWhen.field} = {field.visibleWhen.equals ?? field.visibleWhen.values.join(", ")}
            </p>
          ) : null}
          {field.processMapping && Object.keys(field.processMapping).length > 0 ? (
            <p className="mt-1 text-xs text-slate-600">Есть process mapping</p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function PolicyCard({
  kind,
  code,
  registry,
  health,
  href,
}: {
  kind: StudioPolicyKind;
  code: string | null;
  registry: AdminHelpdeskModelPayload | undefined;
  health: PolicyHealthTemplate | null;
  href: string;
}) {
  const options = policyOptions(registry, kind);
  const selectedOption = options.find((option) => option.value === code);
  const check = health?.checks[kind];
  const issues = health?.issues.filter((issue) => issue.policy_kind === kind) ?? [];
  const blockingCount = issues.filter(hasBlockingIssue).length;
  const status = blockingCount ? "error" : check?.status ?? (code ? "ok" : "not_configured");
  return (
    <article className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold text-slate-950">{POLICY_KIND_LABELS[kind]}</h3>
          <p className="mt-1 truncate text-xs text-slate-500">{code ?? "Политика не привязана"}</p>
        </div>
        <Badge tone={statusTone(status)}>{formatStatus(status)}</Badge>
      </div>
      <p className="mt-2 text-xs text-slate-600">{selectedOption?.subtitle ?? `${options.length} доступно в реестре`}</p>
      <label className="mt-3 block text-xs font-semibold text-slate-600">
        Изменить
        <select className="mt-1 w-full rounded-md border border-slate-200 bg-white px-2 py-2 text-sm" disabled value={code ?? ""}>
          <option value="">Не выбрана</option>
          {options.map((option) => <option disabled={option.disabled} key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </label>
      <p className="mt-2 text-xs text-slate-500">Редактирование привязок пока доступно через Forms Builder / expert policy editor.</p>
      {issues.length ? (
        <div className="mt-3 space-y-2">
          {issues.slice(0, 2).map((issue, index) => (
            <div className="rounded-md border border-slate-200 bg-white p-2" key={`${issue.path}:${index}`}>
              <Badge tone={issueTone(issue)}>{issue.severity}</Badge>
              <p className="mt-1 text-xs text-slate-700">{issue.message}</p>
            </div>
          ))}
          <p className="text-xs text-slate-500">Проблем: {issues.length}, блокирующих: {blockingCount}</p>
        </div>
      ) : null}
      <Link className="mt-3 inline-flex text-xs font-semibold text-brand-700 hover:text-brand-900" to={href}>Открыть в Policy Health</Link>
    </article>
  );
}

function SimulationResult({ result, error }: { result: PolicyHealthSimulationResult | undefined; error: unknown }) {
  if (error) {
    return (
      <div className="mt-4 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
        {error instanceof Error ? error.message : "Симуляция завершилась ошибкой."}
      </div>
    );
  }
  if (!result) {
    return null;
  }
  return (
    <div className="mt-4">
      <h3 className="font-semibold text-slate-950">Результат симуляции</h3>
      {result.warnings?.length ? (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          <div className="flex items-center gap-2 font-semibold">
            <AlertTriangle className="h-4 w-4" />
            Предупреждения
          </div>
          <ul className="mt-2 list-disc pl-5">
            {result.warnings.map((warning) => <li key={warning}>{warning}</li>)}
          </ul>
        </div>
      ) : null}
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {SIMULATION_CARDS.map((card) => {
          const record = getResultRecord(result, card.key);
          const summary = summarizeSimulationRecord(record, card.key);
          return (
            <article className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm" key={card.key}>
              <div className="flex items-center justify-between gap-2">
                <h4 className="font-semibold text-slate-950">{card.title}</h4>
                <Badge tone={statusTone(summary.status)}>{formatStatus(summary.status)}</Badge>
              </div>
              <dl className="mt-2 space-y-1 text-xs text-slate-600">
                <ContextRow label="Политика" value={summary.policy} />
                <ContextRow label="Решение" value={summary.decision} />
              </dl>
              {record ? (
                <details className="mt-2">
                  <summary className="cursor-pointer text-xs font-semibold text-slate-600">Raw details</summary>
                  <pre className="mt-2 max-h-40 overflow-auto rounded-md bg-slate-950 p-2 text-xs text-slate-50">{JSON.stringify(record, null, 2)}</pre>
                </details>
              ) : null}
            </article>
          );
        })}
      </div>
      <details className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3">
        <summary className="cursor-pointer text-sm font-semibold text-slate-700">Экспертный результат JSON</summary>
        <pre className="mt-3 max-h-80 overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-50">{JSON.stringify(result, null, 2)}</pre>
      </details>
    </div>
  );
}

function ContextRow({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div className="flex min-w-0 items-start justify-between gap-3">
      <dt className="shrink-0 text-slate-500">{label}</dt>
      <dd className="min-w-0 text-right font-medium text-slate-900">{tech(value)}</dd>
    </div>
  );
}

function DeepLink({ href, label }: { href: string; label: string }) {
  return (
    <Link className="flex h-10 items-center justify-between gap-3 rounded-md border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800" to={href}>
      <span>{label}</span>
      <ExternalLink className="h-4 w-4" />
    </Link>
  );
}
