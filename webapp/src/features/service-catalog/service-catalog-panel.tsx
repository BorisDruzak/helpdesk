import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { fetchHelpdeskModelRegistry } from "../forms-builder/api";
import {
  buildGuidedSimulationPayload,
  defaultGuidedSimulationDraft,
  policyOptions,
  requestTemplateOptions,
  serviceOptions,
  type GuidedSimulationDraft,
} from "../request-template-studio/options";
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
  registry,
  service,
  services,
}: {
  offerings: AdminServiceCatalogOffering[];
  registry: Awaited<ReturnType<typeof fetchHelpdeskModelRegistry>> | undefined;
  service: AdminServiceCatalogService | null;
  services: AdminServiceCatalogService[];
}) {
  const [selectedOfferingCode, setSelectedOfferingCode] = useState("");
  const [simulationDraft, setSimulationDraft] = useState<GuidedSimulationDraft>(defaultGuidedSimulationDraft);
  const [draftJson, setDraftJson] = useState("");
  const queryClient = useQueryClient();
  const selectedOffering =
    offerings.find((offering) => offering.full_code === selectedOfferingCode) ?? offerings[0] ?? null;
  const templatePickerOptions = requestTemplateOptions(registry);
  const parentServiceOptions = serviceOptions(services);
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
      const guidedPayload = buildGuidedSimulationPayload({
        ...simulationDraft,
        serviceCode: service?.code ?? simulationDraft.serviceCode,
        offeringCode: selectedOffering?.code ?? simulationDraft.offeringCode,
      });
      return simulateServiceCatalog({
        service_code: service?.code,
        offering_code: selectedOffering?.code,
        offering_full_code: selectedOffering?.full_code,
        ...guidedPayload,
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
        Выберите услугу, чтобы увидеть варианты услуги, проверки публикации и симуляцию выполнения.
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
      <Link
        className="inline-flex h-9 items-center justify-center rounded-pill border border-border bg-white px-3 text-xs font-semibold text-slate-700 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800"
        to={`/app/admin/request-template-studio?service=${encodeURIComponent(service.code)}${selectedOffering?.full_code ? `&offering=${encodeURIComponent(selectedOffering.full_code)}` : ""}${selectedOffering?.request_template_key ? `&template=${encodeURIComponent(selectedOffering.request_template_key)}` : ""}`}
      >
        Открыть в студии
      </Link>

      <section>
        <h3 className="text-sm font-semibold text-slate-800">Проверки публикации</h3>
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
              <p className="mt-2 text-sm text-slate-500">Блокирующие проблемы не найдены.</p>
            )}
          </div>
        ) : (
          <p className="mt-2 text-sm text-slate-500">Проверяем готовность публикации...</p>
        )}
        {selectedOffering && offeringValidationQuery.data ? (
          <div className="mt-4 space-y-2 border-t border-slate-200 pt-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase text-slate-500">Выбранный вариант услуги</span>
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
              <p className="text-sm text-slate-500">Блокирующие проблемы не найдены.</p>
            )}
          </div>
        ) : null}
      </section>

      <section>
        <h3 className="text-sm font-semibold text-slate-800">Варианты услуги</h3>
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
                <p className="mt-1 text-xs text-slate-500">{offering.request_template_key ? `Шаблон: ${offering.request_template_key}` : "Шаблон обращения не указан"}</p>
              </button>
            ))
          ) : (
            <p className="text-sm text-slate-500">Варианты услуги пока не заведены.</p>
          )}
        </div>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-slate-800">Наследование политик</h3>
        <p className="mt-2 text-sm text-slate-600">{policySummary(service, selectedOffering)}</p>
      </section>

      <section className="space-y-4">
        <h3 className="text-sm font-semibold text-slate-800">Редактор услуги</h3>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-sm font-medium text-slate-700">
            Код услуги
            <input
              className={fieldClass}
              onChange={(event) => setServiceDraft((current) => ({ ...current, code: event.currentTarget.value }))}
              value={serviceDraft.code ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Название для пользователей
            <input
              className={fieldClass}
              onChange={(event) => setServiceDraft((current) => ({ ...current, public_title: event.currentTarget.value }))}
              value={serviceDraft.public_title ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700 md:col-span-2">
            Краткое описание
            <input
              className={fieldClass}
              onChange={(event) => setServiceDraft((current) => ({ ...current, short_description: event.currentTarget.value }))}
              value={serviceDraft.short_description ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Жизненный цикл
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
              <option value="draft">Черновик</option>
              <option value="published">Опубликована</option>
              <option value="retired">Выведена</option>
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Видимость
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
              <option value="public">Публичная</option>
              <option value="internal">Внутренняя</option>
              <option value="restricted">Ограниченная</option>
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Очередь-владелец
            <input
              className={fieldClass}
              inputMode="numeric"
              onChange={(event) => setServiceDraft((current) => ({ ...current, owner_queue_id: numberOrNull(event.currentTarget.value) }))}
              value={serviceDraft.owner_queue_id ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Очередь по умолчанию
            <input
              className={fieldClass}
              inputMode="numeric"
              onChange={(event) => setServiceDraft((current) => ({ ...current, default_queue_id: numberOrNull(event.currentTarget.value) }))}
              value={serviceDraft.default_queue_id ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Политика маршрутизации по умолчанию
            <select
              className={fieldClass}
              onChange={(event) => setServiceDraft((current) => ({ ...current, default_routing_policy_code: event.currentTarget.value }))}
              value={serviceDraft.default_routing_policy_code ?? ""}
            >
              <option value="">Наследовать</option>
              {policyOptions(registry, "routing").map((option) => <option disabled={option.disabled} key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            SLA по умолчанию
            <select
              className={fieldClass}
              onChange={(event) => setServiceDraft((current) => ({ ...current, default_sla_policy_code: event.currentTarget.value }))}
              value={serviceDraft.default_sla_policy_code ?? ""}
            >
              <option value="">Наследовать</option>
              {policyOptions(registry, "sla").map((option) => <option disabled={option.disabled} key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Диагностика по умолчанию
            <select
              className={fieldClass}
              onChange={(event) => setServiceDraft((current) => ({ ...current, default_diagnostic_policy_code: event.currentTarget.value }))}
              value={serviceDraft.default_diagnostic_policy_code ?? ""}
            >
              <option value="">Наследовать</option>
              {policyOptions(registry, "diagnostic").map((option) => <option disabled={option.disabled} key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Категория отчётности
            <input
              className={fieldClass}
              onChange={(event) => setServiceDraft((current) => ({ ...current, reporting_category: event.currentTarget.value }))}
              value={serviceDraft.reporting_category ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Критичность для бизнеса
            <select
              className={fieldClass}
              onChange={(event) => setServiceDraft((current) => ({ ...current, business_criticality: event.currentTarget.value }))}
              value={serviceDraft.business_criticality ?? "medium"}
            >
              <option value="low">Низкая</option>
              <option value="medium">Средняя</option>
              <option value="high">Высокая</option>
              <option value="critical">Критичная</option>
            </select>
          </label>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button disabled={saveServiceMutation.isPending} onClick={() => saveServiceMutation.mutate()} type="button" variant="secondary">
            Сохранить черновик услуги
          </Button>
          <Button disabled={publishServiceMutation.isPending || validationQuery.data?.blocking} onClick={() => publishServiceMutation.mutate()} type="button" variant="secondary">
            Опубликовать услугу
          </Button>
          <Button disabled={retireServiceMutation.isPending} onClick={() => retireServiceMutation.mutate()} type="button" variant="secondary">
            Вывести услугу
          </Button>
        </div>
      </section>

      <section className="space-y-4">
        <h3 className="text-sm font-semibold text-slate-800">Редактор варианта услуги</h3>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-sm font-medium text-slate-700">
            Родительская услуга
            <select
              className={fieldClass}
              onChange={(event) => setOfferingDraft((current) => ({ ...current, service_code: event.currentTarget.value }))}
              value={offeringDraft.service_code ?? service.code}
            >
              {parentServiceOptions.map((option) => <option disabled={option.disabled} key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Технический код варианта
            <input
              className={fieldClass}
              placeholder="Будет использован как technical id"
              onChange={(event) => setOfferingDraft((current) => ({ ...current, code: event.currentTarget.value }))}
              value={offeringDraft.code ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700 md:col-span-2">
            Название для пользователей
            <input
              className={fieldClass}
              onChange={(event) => setOfferingDraft((current) => ({ ...current, public_title: event.currentTarget.value }))}
              value={offeringDraft.public_title ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700 md:col-span-2">
            Краткое описание
            <input
              className={fieldClass}
              onChange={(event) => setOfferingDraft((current) => ({ ...current, short_description: event.currentTarget.value }))}
              value={offeringDraft.short_description ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Жизненный цикл
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
              <option value="draft">Черновик</option>
              <option value="published">Опубликован</option>
              <option value="retired">Выведен</option>
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Видимость
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
              <option value="public">Публичный</option>
              <option value="internal">Внутренний</option>
              <option value="restricted">Ограниченный</option>
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Тип обращения
            <input
              className={fieldClass}
              onChange={(event) => setOfferingDraft((current) => ({ ...current, request_type: event.currentTarget.value }))}
              value={offeringDraft.request_type ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Шаблон обращения
            <select
              className={fieldClass}
              onChange={(event) => setOfferingDraft((current) => ({ ...current, request_template_key: event.currentTarget.value }))}
              value={offeringDraft.request_template_key ?? ""}
            >
              <option value="">Не выбран</option>
              {templatePickerOptions.map((option) => <option disabled={option.disabled} key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
          {[
            ["routing_policy_code", "Маршрутизация", "routing"],
            ["sla_policy_code", "SLA", "sla"],
            ["ola_policy_code", "OLA", "ola"],
            ["approval_policy_code", "Согласование", "approval"],
            ["closure_policy_code", "Закрытие", "closure"],
            ["visibility_policy_code", "Видимость", "visibility"],
            ["diagnostic_policy_code", "Диагностика", "diagnostic"],
            ["notification_policy_code", "Уведомления", "notification"],
            ["reporting_policy_code", "Отчётность", "reporting"],
          ].map(([key, label, kind]) => (
            <label className="text-sm font-medium text-slate-700" key={key}>
              {label}
              <select
                className={fieldClass}
                onChange={(event) => setOfferingDraft((current) => ({ ...current, [key]: event.currentTarget.value }))}
                value={String(offeringDraft[key as keyof AdminServiceCatalogOffering] ?? "")}
              >
                <option value="">Наследовать</option>
                {policyOptions(registry, kind).map((option) => <option disabled={option.disabled} key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
          ))}
          <label className="text-sm font-medium text-slate-700 md:col-span-2">
            Категория отчётности
            <input
              className={fieldClass}
              onChange={(event) => setOfferingDraft((current) => ({ ...current, reporting_category: event.currentTarget.value }))}
              value={offeringDraft.reporting_category ?? ""}
            />
          </label>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button disabled={saveOfferingMutation.isPending} onClick={() => saveOfferingMutation.mutate()} type="button" variant="secondary">
            Сохранить черновик варианта
          </Button>
          <Button
            disabled={publishOfferingMutation.isPending || !selectedOffering || offeringValidationQuery.data?.blocking}
            onClick={() => publishOfferingMutation.mutate()}
            type="button"
            variant="secondary"
          >
            Опубликовать вариант
          </Button>
        </div>
        <details className="rounded-md border border-slate-200 bg-slate-50 p-3">
          <summary className="cursor-pointer text-sm font-semibold text-slate-700">Экспертный JSON</summary>
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
              Загрузить JSON в форму услуги
            </Button>
            <Button
              disabled={saveOfferingMutation.isPending || !draftJson.trim()}
              onClick={() => {
                setOfferingDraft((current) => ({ ...current, ...(JSON.parse(draftJson) as Partial<AdminServiceCatalogOffering>) }));
              }}
              type="button"
              variant="outline"
            >
              Загрузить JSON в форму варианта
            </Button>
          </div>
        </details>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-slate-800">Симуляция выполнения</h3>
          <Button
            disabled={simulationMutation.isPending || !selectedOffering}
            leadingIcon={<Play className="h-4 w-4" />}
            onClick={() => simulationMutation.mutate()}
            type="button"
            variant="secondary"
          >
            Запустить тестовый прогон
          </Button>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-sm font-medium text-slate-700">
            Инициатор
            <input className={fieldClass} onChange={(event) => setSimulationDraft((current) => ({ ...current, requester: event.currentTarget.value }))} value={simulationDraft.requester} />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Устройство
            <input className={fieldClass} onChange={(event) => setSimulationDraft((current) => ({ ...current, device: event.currentTarget.value }))} value={simulationDraft.device} />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Локация
            <input className={fieldClass} onChange={(event) => setSimulationDraft((current) => ({ ...current, location: event.currentTarget.value }))} value={simulationDraft.location} />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Ожидаемый приоритет
            <select className={fieldClass} onChange={(event) => setSimulationDraft((current) => ({ ...current, expectedPriority: event.currentTarget.value }))} value={simulationDraft.expectedPriority}>
              <option value="">Не проверять</option>
              <option value="P0">P0</option>
              <option value="P1">P1</option>
              <option value="P2">P2</option>
              <option value="P3">P3</option>
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700 md:col-span-2">
            Ответы формы / контекст проверки
            <textarea
              className="field-base mt-1 min-h-24 w-full px-3 py-2"
              onChange={(event) => setSimulationDraft((current) => ({ ...current, answerSummary: event.currentTarget.value }))}
              placeholder="Опишите данные формы, которые должны повлиять на маршрут, SLA, согласования и закрытие."
              value={simulationDraft.answerSummary}
            />
          </label>
        </div>
        <details className="rounded-md border border-slate-200 bg-slate-50 p-3">
          <summary className="cursor-pointer text-sm font-semibold text-slate-700">Экспертный JSON payload</summary>
          <pre className="mt-3 overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-100">
            {JSON.stringify(buildGuidedSimulationPayload({ ...simulationDraft, serviceCode: service.code, offeringCode: selectedOffering?.code ?? "" }), null, 2)}
          </pre>
        </details>
        {simulationMutation.data ? (
          <pre className="max-h-80 overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-100">
            {JSON.stringify(simulationMutation.data, null, 2)}
          </pre>
        ) : null}
        {simulationMutation.isError ? <p className="text-sm text-rose-700">Симуляция не выполнена.</p> : null}
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
  const registryQuery = useQuery({
    queryKey: ["service-catalog-helpdesk-model-registry"],
    queryFn: fetchHelpdeskModelRegistry,
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
          <p className="workspace-boot__eyebrow">Управление обращениями</p>
          <h1>Каталог услуг</h1>
          <p>Услуги, варианты услуги, проверки публикации и симуляция выполнения.</p>
        </div>
        <dl className="workspace-page__stats">
          <div>
            <dt>Услуги</dt>
            <dd>{services.length}</dd>
          </div>
          <div>
            <dt>Варианты</dt>
            <dd>{offerings.length}</dd>
          </div>
        </dl>
      </header>

      <section className="surface-panel p-4">
        <div className="grid gap-3 md:grid-cols-[1.4fr_1fr_1fr]">
          <label className="text-sm font-medium text-slate-700">
            Поиск
            <input className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2" value={query} onChange={(event) => setQuery(event.currentTarget.value)} />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Жизненный цикл
            <select className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2" value={statusFilter} onChange={(event) => setStatusFilter(event.currentTarget.value)}>
              <option value="all">all</option>
              <option value="draft">draft</option>
              <option value="published">published</option>
              <option value="retired">retired</option>
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Видимость
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
        <ServiceDetails offerings={selectedOfferings} registry={registryQuery.data} service={selectedService} services={services} />
      </section>
    </section>
  );
}
