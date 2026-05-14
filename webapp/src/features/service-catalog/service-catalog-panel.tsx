import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, ShieldCheck } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import {
  fetchServiceCatalogDashboard,
  publishServiceCatalogObject,
  retireServiceCatalogObject,
  saveOfferingDraft,
  saveServiceDraft,
  simulateServiceCatalog,
  validateServiceCatalogObject,
  type AdminServiceCatalogOffering,
  type AdminServiceCatalogService,
} from "./api";

function tone(status: string) {
  if (status === "published" || status === "ok") {
    return "success" as const;
  }
  if (status === "draft" || status === "warning") {
    return "warning" as const;
  }
  if (status === "retired" || status === "error") {
    return "danger" as const;
  }
  return "neutral" as const;
}

function policySummary(service: AdminServiceCatalogService, offering?: AdminServiceCatalogOffering | null) {
  const entries = [
    ["routing", offering?.routing_policy_code ?? service.default_routing_policy_code],
    ["sla", offering?.sla_policy_code ?? service.default_sla_policy_code],
    ["ola", offering?.ola_policy_code],
    ["approval", offering?.approval_policy_code],
    ["closure", offering?.closure_policy_code],
    ["visibility", offering?.visibility_policy_code],
    ["diagnostic", offering?.diagnostic_policy_code ?? service.default_diagnostic_policy_code],
    ["notification", offering?.notification_policy_code],
    ["reporting", offering?.reporting_policy_code],
  ].filter(([, value]) => Boolean(value));
  return entries.length ? entries.map(([key, value]) => `${key}: ${value}`).join(" · ") : "Политики наследуются или не заданы";
}

function emptyToNull(value: string | null | undefined): string | null {
  const trimmed = String(value ?? "").trim();
  return trimmed ? trimmed : null;
}

function numberOrNull(value: string | number | null | undefined): number | null {
  const trimmed = String(value ?? "").trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

const fieldClass = "mt-1 w-full rounded-md border border-slate-200 px-3 py-2";

function ServiceDetails({
  offerings,
  service,
}: {
  offerings: AdminServiceCatalogOffering[];
  service: AdminServiceCatalogService | null;
}) {
  const [selectedOfferingCode, setSelectedOfferingCode] = useState("");
  const [simulationInput, setSimulationInput] = useState('{"request_form_data":{},"custom_fields":{},"device_metadata":{},"requester_context":{}}');
  const [draftJson, setDraftJson] = useState("");
  const queryClient = useQueryClient();
  const selectedOffering =
    offerings.find((offering) => offering.full_code === selectedOfferingCode) ?? offerings[0] ?? null;
  const [serviceDraft, setServiceDraft] = useState<Partial<AdminServiceCatalogService>>({});
  const [offeringDraft, setOfferingDraft] = useState<Partial<AdminServiceCatalogOffering>>({});

  useEffect(() => {
    setServiceDraft(service ?? {});
    setDraftJson("");
  }, [service?.code]);

  useEffect(() => {
    setSelectedOfferingCode("");
  }, [service?.code]);

  useEffect(() => {
    setOfferingDraft(
      selectedOffering ?? {
        service_code: service?.code ?? "",
        code: "",
        full_code: "",
        public_title: "",
        lifecycle_status: "draft",
        visibility: "public",
        request_type: "service_request",
      },
    );
  }, [selectedOffering?.full_code, service?.code]);

  const validationQuery = useQuery({
    enabled: Boolean(service?.code),
    queryKey: ["service-catalog-validation", service?.code],
    queryFn: () => validateServiceCatalogObject("service", service?.code ?? ""),
  });
  const offeringValidationQuery = useQuery({
    enabled: Boolean(selectedOffering?.full_code),
    queryKey: ["service-catalog-validation", "offering", selectedOffering?.full_code],
    queryFn: () => validateServiceCatalogObject("offering", selectedOffering?.full_code ?? ""),
  });

  const simulationMutation = useMutation({
    mutationFn: () => {
      const parsed = JSON.parse(simulationInput) as Record<string, unknown>;
      return simulateServiceCatalog({
        service_code: service?.code,
        offering_code: selectedOffering?.code,
        offering_full_code: selectedOffering?.full_code,
        request_form_data: (parsed.request_form_data as Record<string, unknown>) ?? {},
        custom_fields: (parsed.custom_fields as Record<string, unknown>) ?? {},
        device_metadata: (parsed.device_metadata as Record<string, unknown>) ?? {},
        requester_context: (parsed.requester_context as Record<string, unknown>) ?? {},
      });
    },
  });
  const saveServiceMutation = useMutation({
    mutationFn: () =>
      saveServiceDraft({
        ...serviceDraft,
        code: String(serviceDraft.code ?? service?.code ?? "").trim(),
        public_title: String(serviceDraft.public_title ?? service?.public_title ?? "").trim(),
        short_description: emptyToNull(serviceDraft.short_description),
        description: emptyToNull(serviceDraft.description),
        owner_queue_id: numberOrNull(serviceDraft.owner_queue_id),
        default_queue_id: numberOrNull(serviceDraft.default_queue_id),
        default_sla_policy_code: emptyToNull(serviceDraft.default_sla_policy_code),
        default_routing_policy_code: emptyToNull(serviceDraft.default_routing_policy_code),
        default_diagnostic_policy_code: emptyToNull(serviceDraft.default_diagnostic_policy_code),
        business_criticality: emptyToNull(serviceDraft.business_criticality),
        reporting_category: emptyToNull(serviceDraft.reporting_category),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["service-catalog-dashboard"] }),
  });
  const publishServiceMutation = useMutation({
    mutationFn: () => publishServiceCatalogObject("service", service?.code ?? ""),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["service-catalog-dashboard"] }),
  });
  const retireServiceMutation = useMutation({
    mutationFn: () => retireServiceCatalogObject("service", service?.code ?? ""),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["service-catalog-dashboard"] }),
  });
  const publishOfferingMutation = useMutation({
    mutationFn: () => publishServiceCatalogObject("offering", selectedOffering?.full_code ?? ""),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["service-catalog-dashboard"] }),
  });
  const saveOfferingMutation = useMutation({
    mutationFn: () =>
      saveOfferingDraft({
        ...offeringDraft,
        service_code: String(offeringDraft.service_code ?? service?.code ?? "").trim(),
        code: String(offeringDraft.code ?? selectedOffering?.code ?? "").trim(),
        public_title: String(offeringDraft.public_title ?? selectedOffering?.public_title ?? "").trim(),
        short_description: emptyToNull(offeringDraft.short_description),
        request_type: emptyToNull(offeringDraft.request_type),
        request_template_key: emptyToNull(offeringDraft.request_template_key),
        routing_policy_code: emptyToNull(offeringDraft.routing_policy_code),
        sla_policy_code: emptyToNull(offeringDraft.sla_policy_code),
        ola_policy_code: emptyToNull(offeringDraft.ola_policy_code),
        approval_policy_code: emptyToNull(offeringDraft.approval_policy_code),
        closure_policy_code: emptyToNull(offeringDraft.closure_policy_code),
        visibility_policy_code: emptyToNull(offeringDraft.visibility_policy_code),
        diagnostic_policy_code: emptyToNull(offeringDraft.diagnostic_policy_code),
        notification_policy_code: emptyToNull(offeringDraft.notification_policy_code),
        reporting_policy_code: emptyToNull(offeringDraft.reporting_policy_code),
        reporting_category: emptyToNull(offeringDraft.reporting_category),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["service-catalog-dashboard"] }),
  });

  if (!service) {
    return (
      <aside className="surface-panel p-5 text-sm text-slate-500">
        Выберите услугу, чтобы увидеть offerings, publication gates и runtime simulation.
      </aside>
    );
  }

  return (
    <aside className="surface-panel space-y-5 p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">{service.public_title || service.code}</h2>
          <p className="mt-1 text-sm text-slate-500">{service.short_description || service.description || service.code}</p>
        </div>
        <Badge tone={tone(service.lifecycle_status)}>{service.lifecycle_status}</Badge>
      </div>

      <section>
        <h3 className="text-sm font-semibold text-slate-800">Publication gates</h3>
        {validationQuery.data ? (
          <div className="mt-2 space-y-2">
            <Badge tone={tone(validationQuery.data.status)}>{validationQuery.data.status}</Badge>
            {validationQuery.data.issues.length ? (
              validationQuery.data.issues.map((issue) => (
                <div key={`${issue.path}:${issue.kind}`} className="rounded-md border border-slate-200 p-3 text-sm">
                  <div className="flex items-center gap-2">
                    <Badge tone={tone(issue.severity)}>{issue.severity}</Badge>
                    <span className="font-semibold text-slate-700">{issue.kind}</span>
                  </div>
                  <p className="mt-1 text-slate-600">{issue.message}</p>
                </div>
              ))
            ) : (
              <p className="mt-2 text-sm text-slate-500">Blocking issues не найдены.</p>
            )}
          </div>
        ) : (
          <p className="mt-2 text-sm text-slate-500">Проверка publication gates...</p>
        )}
        {selectedOffering && offeringValidationQuery.data ? (
          <div className="mt-4 space-y-2 border-t border-slate-200 pt-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase text-slate-500">Selected offering</span>
              <Badge tone={tone(offeringValidationQuery.data.status)}>{offeringValidationQuery.data.status}</Badge>
            </div>
            {offeringValidationQuery.data.issues.length ? (
              offeringValidationQuery.data.issues.map((issue) => (
                <div key={`offering:${issue.path}:${issue.kind}`} className="rounded-md border border-slate-200 p-3 text-sm">
                  <div className="flex items-center gap-2">
                    <Badge tone={tone(issue.severity)}>{issue.severity}</Badge>
                    <span className="font-semibold text-slate-700">{issue.kind}</span>
                  </div>
                  <p className="mt-1 text-slate-600">{issue.message}</p>
                  {issue.suggested_fix ? <p className="mt-1 text-xs text-slate-500">{issue.suggested_fix}</p> : null}
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-500">Blocking issues не найдены.</p>
            )}
          </div>
        ) : null}
      </section>

      <section>
        <h3 className="text-sm font-semibold text-slate-800">Offerings</h3>
        <div className="mt-2 space-y-2">
          {offerings.length ? (
            offerings.map((offering) => (
              <button
                className="w-full rounded-md border border-slate-200 bg-white p-3 text-left text-sm transition hover:border-brand-200 hover:bg-brand-50"
                key={offering.full_code}
                onClick={() => setSelectedOfferingCode(offering.full_code)}
                type="button"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-slate-900">{offering.public_title || offering.full_code}</span>
                  <Badge tone={tone(offering.lifecycle_status)}>{offering.lifecycle_status}</Badge>
                </div>
                <p className="mt-1 text-xs text-slate-500">{offering.request_template_key || "request template не указан"}</p>
              </button>
            ))
          ) : (
            <p className="text-sm text-slate-500">Offerings пока не заведены.</p>
          )}
        </div>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-slate-800">Policy inheritance</h3>
        <p className="mt-2 text-sm text-slate-600">{policySummary(service, selectedOffering)}</p>
      </section>

      <section className="space-y-4">
        <h3 className="text-sm font-semibold text-slate-800">Structured service editor</h3>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-sm font-medium text-slate-700">
            Code
            <input
              className={fieldClass}
              onChange={(event) => setServiceDraft((current) => ({ ...current, code: event.currentTarget.value }))}
              value={serviceDraft.code ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Public title
            <input
              className={fieldClass}
              onChange={(event) => setServiceDraft((current) => ({ ...current, public_title: event.currentTarget.value }))}
              value={serviceDraft.public_title ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700 md:col-span-2">
            Short description
            <input
              className={fieldClass}
              onChange={(event) => setServiceDraft((current) => ({ ...current, short_description: event.currentTarget.value }))}
              value={serviceDraft.short_description ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Lifecycle
            <select
              className={fieldClass}
              onChange={(event) =>
                setServiceDraft((current) => ({
                  ...current,
                  lifecycle_status: event.currentTarget.value as AdminServiceCatalogService["lifecycle_status"],
                }))
              }
              value={serviceDraft.lifecycle_status ?? "draft"}
            >
              <option value="draft">draft</option>
              <option value="published">published</option>
              <option value="retired">retired</option>
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Visibility
            <select
              className={fieldClass}
              onChange={(event) =>
                setServiceDraft((current) => ({
                  ...current,
                  visibility: event.currentTarget.value as AdminServiceCatalogService["visibility"],
                }))
              }
              value={serviceDraft.visibility ?? "public"}
            >
              <option value="public">public</option>
              <option value="internal">internal</option>
              <option value="restricted">restricted</option>
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Owner queue
            <input
              className={fieldClass}
              inputMode="numeric"
              onChange={(event) => setServiceDraft((current) => ({ ...current, owner_queue_id: numberOrNull(event.currentTarget.value) }))}
              value={serviceDraft.owner_queue_id ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Default queue
            <input
              className={fieldClass}
              inputMode="numeric"
              onChange={(event) => setServiceDraft((current) => ({ ...current, default_queue_id: numberOrNull(event.currentTarget.value) }))}
              value={serviceDraft.default_queue_id ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Default routing policy
            <input
              className={fieldClass}
              onChange={(event) => setServiceDraft((current) => ({ ...current, default_routing_policy_code: event.currentTarget.value }))}
              value={serviceDraft.default_routing_policy_code ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Default SLA policy
            <input
              className={fieldClass}
              onChange={(event) => setServiceDraft((current) => ({ ...current, default_sla_policy_code: event.currentTarget.value }))}
              value={serviceDraft.default_sla_policy_code ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Default diagnostics
            <input
              className={fieldClass}
              onChange={(event) => setServiceDraft((current) => ({ ...current, default_diagnostic_policy_code: event.currentTarget.value }))}
              value={serviceDraft.default_diagnostic_policy_code ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Reporting category
            <input
              className={fieldClass}
              onChange={(event) => setServiceDraft((current) => ({ ...current, reporting_category: event.currentTarget.value }))}
              value={serviceDraft.reporting_category ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Business criticality
            <select
              className={fieldClass}
              onChange={(event) => setServiceDraft((current) => ({ ...current, business_criticality: event.currentTarget.value }))}
              value={serviceDraft.business_criticality ?? "medium"}
            >
              <option value="low">low</option>
              <option value="medium">medium</option>
              <option value="high">high</option>
              <option value="critical">critical</option>
            </select>
          </label>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button disabled={saveServiceMutation.isPending} onClick={() => saveServiceMutation.mutate()} type="button" variant="secondary">
            Save service draft
          </Button>
          <Button disabled={publishServiceMutation.isPending || validationQuery.data?.blocking} onClick={() => publishServiceMutation.mutate()} type="button" variant="secondary">
            Publish service
          </Button>
          <Button disabled={retireServiceMutation.isPending} onClick={() => retireServiceMutation.mutate()} type="button" variant="secondary">
            Retire service
          </Button>
        </div>
      </section>

      <section className="space-y-4">
        <h3 className="text-sm font-semibold text-slate-800">Structured offering editor</h3>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-sm font-medium text-slate-700">
            Parent service
            <input
              className={fieldClass}
              onChange={(event) => setOfferingDraft((current) => ({ ...current, service_code: event.currentTarget.value }))}
              value={offeringDraft.service_code ?? service.code}
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Offering code
            <input
              className={fieldClass}
              onChange={(event) => setOfferingDraft((current) => ({ ...current, code: event.currentTarget.value }))}
              value={offeringDraft.code ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700 md:col-span-2">
            Public title
            <input
              className={fieldClass}
              onChange={(event) => setOfferingDraft((current) => ({ ...current, public_title: event.currentTarget.value }))}
              value={offeringDraft.public_title ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700 md:col-span-2">
            Short description
            <input
              className={fieldClass}
              onChange={(event) => setOfferingDraft((current) => ({ ...current, short_description: event.currentTarget.value }))}
              value={offeringDraft.short_description ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Lifecycle
            <select
              className={fieldClass}
              onChange={(event) =>
                setOfferingDraft((current) => ({
                  ...current,
                  lifecycle_status: event.currentTarget.value as AdminServiceCatalogOffering["lifecycle_status"],
                }))
              }
              value={offeringDraft.lifecycle_status ?? "draft"}
            >
              <option value="draft">draft</option>
              <option value="published">published</option>
              <option value="retired">retired</option>
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Visibility
            <select
              className={fieldClass}
              onChange={(event) =>
                setOfferingDraft((current) => ({
                  ...current,
                  visibility: event.currentTarget.value as AdminServiceCatalogOffering["visibility"],
                }))
              }
              value={offeringDraft.visibility ?? "public"}
            >
              <option value="public">public</option>
              <option value="internal">internal</option>
              <option value="restricted">restricted</option>
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Request type
            <input
              className={fieldClass}
              onChange={(event) => setOfferingDraft((current) => ({ ...current, request_type: event.currentTarget.value }))}
              value={offeringDraft.request_type ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Request template key
            <input
              className={fieldClass}
              onChange={(event) => setOfferingDraft((current) => ({ ...current, request_template_key: event.currentTarget.value }))}
              value={offeringDraft.request_template_key ?? ""}
            />
          </label>
          {[
            ["routing_policy_code", "Routing"],
            ["sla_policy_code", "SLA"],
            ["ola_policy_code", "OLA"],
            ["approval_policy_code", "Approval"],
            ["closure_policy_code", "Closure"],
            ["visibility_policy_code", "Visibility"],
            ["diagnostic_policy_code", "Diagnostic"],
            ["notification_policy_code", "Notification"],
            ["reporting_policy_code", "Reporting"],
          ].map(([key, label]) => (
            <label className="text-sm font-medium text-slate-700" key={key}>
              {label} policy override
              <input
                className={fieldClass}
                onChange={(event) => setOfferingDraft((current) => ({ ...current, [key]: event.currentTarget.value }))}
                value={String(offeringDraft[key as keyof AdminServiceCatalogOffering] ?? "")}
              />
            </label>
          ))}
          <label className="text-sm font-medium text-slate-700 md:col-span-2">
            Reporting category
            <input
              className={fieldClass}
              onChange={(event) => setOfferingDraft((current) => ({ ...current, reporting_category: event.currentTarget.value }))}
              value={offeringDraft.reporting_category ?? ""}
            />
          </label>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button disabled={saveOfferingMutation.isPending} onClick={() => saveOfferingMutation.mutate()} type="button" variant="secondary">
            Save offering draft
          </Button>
          <Button
            disabled={publishOfferingMutation.isPending || !selectedOffering || offeringValidationQuery.data?.blocking}
            onClick={() => publishOfferingMutation.mutate()}
            type="button"
            variant="secondary"
          >
            Publish offering
          </Button>
        </div>
        <details className="rounded-md border border-slate-200 bg-slate-50 p-3">
          <summary className="cursor-pointer text-sm font-semibold text-slate-700">Advanced JSON</summary>
          <textarea
            className="field-base mt-3 min-h-28 w-full px-3 py-2 font-mono text-xs"
            onChange={(event) => setDraftJson(event.currentTarget.value)}
            placeholder={JSON.stringify(selectedOffering ?? service, null, 2)}
            value={draftJson}
          />
          <div className="mt-2 flex flex-wrap gap-2">
            <Button
              disabled={saveServiceMutation.isPending || !draftJson.trim()}
              onClick={() => {
                setServiceDraft((current) => ({ ...current, ...(JSON.parse(draftJson) as Partial<AdminServiceCatalogService>) }));
              }}
              type="button"
              variant="outline"
            >
              Load JSON into service form
            </Button>
            <Button
              disabled={saveOfferingMutation.isPending || !draftJson.trim()}
              onClick={() => {
                setOfferingDraft((current) => ({ ...current, ...(JSON.parse(draftJson) as Partial<AdminServiceCatalogOffering>) }));
              }}
              type="button"
              variant="outline"
            >
              Load JSON into offering form
            </Button>
          </div>
        </details>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-slate-800">Runtime simulation</h3>
          <Button
            disabled={simulationMutation.isPending || !selectedOffering}
            leadingIcon={<Play className="h-4 w-4" />}
            onClick={() => simulationMutation.mutate()}
            type="button"
            variant="secondary"
          >
            Run
          </Button>
        </div>
        <textarea
          className="field-base min-h-28 w-full px-3 py-2 font-mono text-xs"
          onChange={(event) => setSimulationInput(event.currentTarget.value)}
          value={simulationInput}
        />
        {simulationMutation.data ? (
          <pre className="max-h-80 overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-100">
            {JSON.stringify(simulationMutation.data, null, 2)}
          </pre>
        ) : null}
        {simulationMutation.isError ? <p className="text-sm text-rose-700">Simulation failed.</p> : null}
      </section>
    </aside>
  );
}

export function ServiceCatalogPanel() {
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [visibilityFilter, setVisibilityFilter] = useState("all");
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const dashboardQuery = useQuery({
    queryKey: ["service-catalog-dashboard"],
    queryFn: fetchServiceCatalogDashboard,
  });

  const services = dashboardQuery.data?.services ?? [];
  const offerings = dashboardQuery.data?.offerings ?? [];
  const selectedService = services.find((service) => service.code === selectedCode) ?? services[0] ?? null;
  const selectedOfferings = offerings.filter((offering) => offering.service_code === selectedService?.code);
  const visibleServices = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return services.filter((service) => {
      if (statusFilter !== "all" && service.lifecycle_status !== statusFilter) {
        return false;
      }
      if (visibilityFilter !== "all" && service.visibility !== visibilityFilter) {
        return false;
      }
      return !normalizedQuery || `${service.code} ${service.public_title} ${service.short_description ?? ""}`.toLowerCase().includes(normalizedQuery);
    });
  }, [query, services, statusFilter, visibilityFilter]);

  if (dashboardQuery.isLoading) {
    return <section className="workspace-page p-6 text-sm text-slate-500">Загружаем Service Catalog...</section>;
  }

  if (dashboardQuery.isError || !dashboardQuery.data) {
    return <section className="workspace-page p-6 text-sm text-rose-700">Не удалось загрузить Service Catalog.</section>;
  }

  return (
    <section className="workspace-page space-y-5 p-6">
      <header className="workspace-page__header">
        <div className="workspace-page__copy">
          <p className="workspace-boot__eyebrow">Service desk governance</p>
          <h1>Service Catalog</h1>
          <p>Услуги, offerings, publication gates и runtime-equivalent simulation.</p>
        </div>
        <dl className="workspace-page__stats">
          <div>
            <dt>Services</dt>
            <dd>{services.length}</dd>
          </div>
          <div>
            <dt>Offerings</dt>
            <dd>{offerings.length}</dd>
          </div>
        </dl>
      </header>

      <section className="surface-panel p-4">
        <div className="grid gap-3 md:grid-cols-[1.4fr_1fr_1fr]">
          <label className="text-sm font-medium text-slate-700">
            Search
            <input className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2" value={query} onChange={(event) => setQuery(event.currentTarget.value)} />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Lifecycle
            <select className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2" value={statusFilter} onChange={(event) => setStatusFilter(event.currentTarget.value)}>
              <option value="all">all</option>
              <option value="draft">draft</option>
              <option value="published">published</option>
              <option value="retired">retired</option>
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Visibility
            <select className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2" value={visibilityFilter} onChange={(event) => setVisibilityFilter(event.currentTarget.value)}>
              <option value="all">all</option>
              <option value="public">public</option>
              <option value="internal">internal</option>
              <option value="restricted">restricted</option>
            </select>
          </label>
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="surface-panel overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Service</th>
                <th className="px-4 py-3">Lifecycle</th>
                <th className="px-4 py-3">Visibility</th>
                <th className="px-4 py-3">Offerings</th>
                <th className="px-4 py-3">Policies</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {visibleServices.map((service) => {
                const count = offerings.filter((offering) => offering.service_code === service.code).length;
                return (
                  <tr className="cursor-pointer hover:bg-brand-50/40" key={service.code} onClick={() => setSelectedCode(service.code)}>
                    <td className="px-4 py-3">
                      <div className="font-semibold text-slate-950">{service.public_title || service.code}</div>
                      <div className="text-xs text-slate-500">{service.code}</div>
                    </td>
                    <td className="px-4 py-3"><Badge tone={tone(service.lifecycle_status)}>{service.lifecycle_status}</Badge></td>
                    <td className="px-4 py-3"><Badge tone="neutral">{service.visibility}</Badge></td>
                    <td className="px-4 py-3">{count}</td>
                    <td className="px-4 py-3 text-xs text-slate-500">{policySummary(service)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {!visibleServices.length ? (
            <div className="flex items-center gap-2 p-6 text-sm text-slate-500">
              <ShieldCheck className="h-4 w-4" />
              Services по текущим фильтрам не найдены.
            </div>
          ) : null}
        </div>
        <ServiceDetails offerings={selectedOfferings} service={selectedService} />
      </section>
    </section>
  );
}
