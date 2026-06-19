import { ArrowRight, CheckCircle2, Search, Send } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  createRequesterTicket,
  previewRequesterTicket,
  recordKnowledgeFeedback,
  searchRequesterOnBehalfPeople,
  suggestKnowledge,
  RequesterApiError,
} from "../../features/requester/api";
import {
  requesterInvalidations,
  useRequesterBootstrapQuery,
  useRequesterFormPackQuery,
  useRequesterRegistryOptionsQuery,
  useRequesterServiceCatalogQuery,
} from "../../features/requester/queries";
import {
  RequestFormFieldControl,
  buildDefaultFieldValues,
  collectVisiblePayload,
  fieldWithRequesterContextOptions,
  isDynamicFieldVisible,
  mergeContextPrefillValues,
  missingRequiredFieldDetails,
  missingRequiredFields,
  type DynamicFormValues,
} from "../../features/requester/dynamic-form";
import { requesterDeviceLabel } from "../../features/requester/labels";
import type {
  KnowledgeAttempt,
  KnowledgeSuggestResult,
  KnowledgeSuggestionItem,
  RequestFormDefinition,
  RequesterContextPreview,
  RequesterDevice,
  RequesterOnBehalfPerson,
  RequesterTicketCreatePayload,
  ServiceCatalogCurrent,
  ServiceCatalogSafePreview,
} from "../../features/requester/types";
import { useQueryClient } from "@tanstack/react-query";

type WizardStep = "problem" | "quick_help" | "details" | "review";
type KnowledgeFeedbackEvent = Parameters<typeof recordKnowledgeFeedback>[0]["event_type"];

const ASK_TICKET_CONTEXT_STORAGE_KEY = "pc_client.knowledge_ask.ticket_context";
const ASK_TICKET_CONTEXT_MAX_AGE_MS = 30 * 60 * 1000;

type AskTicketContext = {
  query?: string | null;
  created_at?: string | null;
  primary_item?: { item_id?: string | null; version_id?: string | null } | null;
  retrieval_results?: Array<{ item_id?: string | null; version_id?: string | null }>;
};

export function RequesterNewRequestPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const bootstrapQuery = useRequesterBootstrapQuery();
  const formPackQuery = useRequesterFormPackQuery();
  const catalogQuery = useRequesterServiceCatalogQuery();
  const bootstrap = bootstrapQuery.data ?? null;
  const forms = formPackQuery.data?.forms ?? [];
  const services = catalogQuery.data?.services ?? [];
  const profileComplete = bootstrap?.profile_completion ? bootstrap.profile_completion.complete !== false : Boolean(bootstrap?.profile);
  const canCreateWithoutDevice = bootstrap?.feature_flags?.requester_no_device_create === true;
  const devices = bootstrap?.devices ?? [];
  const primaryDevice = devices[0] ?? null;
  const hasAgentContext = Boolean(primaryDevice || canCreateWithoutDevice);
  const [step, setStep] = useState<WizardStep>("problem");
  const [problem, setProblem] = useState("");
  const [fieldValues, setFieldValues] = useState<DynamicFormValues>({});
  const [previousPrefill, setPreviousPrefill] = useState<DynamicFormValues>({});
  const [knowledgeResult, setKnowledgeResult] = useState<KnowledgeSuggestResult | null>(null);
  const [knowledgeLoading, setKnowledgeLoading] = useState(false);
  const [knowledgeAttempts, setKnowledgeAttempts] = useState<KnowledgeAttempt[]>([]);
  const [previewResult, setPreviewResult] = useState<ServiceCatalogSafePreview | null>(null);
  const [previewSubmitting, setPreviewSubmitting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [onBehalfEnabled, setOnBehalfEnabled] = useState(false);
  const [onBehalfQuery, setOnBehalfQuery] = useState("");
  const [onBehalfPeople, setOnBehalfPeople] = useState<RequesterOnBehalfPerson[]>([]);
  const [selectedOnBehalfPerson, setSelectedOnBehalfPerson] = useState<RequesterOnBehalfPerson | null>(null);
  const [onBehalfReason, setOnBehalfReason] = useState("");
  const loadedAskContextRef = useRef(false);
  const fieldRefs = useRef<Record<string, HTMLElement | null>>({});
  const [validationAttempted, setValidationAttempted] = useState(false);

  const selectedOffering = useMemo(() => firstAvailableOffering(services), [services]);
  const selectedService = useMemo(
    () => services.find((service) => service.service_code === selectedOffering?.service_code) ?? null,
    [selectedOffering?.service_code, services],
  );
  const selectedForm = useMemo(
    () => resolveSelectedForm(forms, selectedOffering, profileComplete, hasAgentContext),
    [forms, hasAgentContext, profileComplete, selectedOffering],
  );
  const needsRegistryOptions = useMemo(
    () => (selectedForm?.fields ?? []).some((field) => field.type === "department_picker" || field.type === "location_picker"),
    [selectedForm],
  );
  const registryOptionsQuery = useRequesterRegistryOptionsQuery({ enabled: needsRegistryOptions });
  const requestFormPrefill = useMemo(
    () => requesterFormPrefillFromContext(bootstrap?.requester_context, bootstrap?.profile, primaryDevice, selectedService, selectedOffering),
    [bootstrap?.profile, bootstrap?.requester_context, primaryDevice, selectedOffering, selectedService],
  );
  const contextualFields = useMemo(
    () =>
      (selectedForm?.fields ?? [])
        .filter((field) => isDynamicFieldVisible(field, fieldValues))
        .map((field) =>
          fieldWithRequesterContextOptions(field, {
            departments: registryOptionsQuery.data?.departments ?? [],
            locations: registryOptionsQuery.data?.locations ?? [],
            devices,
            services,
          }),
        ),
    [devices, fieldValues, registryOptionsQuery.data?.departments, registryOptionsQuery.data?.locations, selectedForm, services],
  );
  const visiblePayload = useMemo(() => collectVisiblePayload(selectedForm, fieldValues), [fieldValues, selectedForm]);
  const missingFieldDetails = useMemo(() => missingRequiredFieldDetails(selectedForm, fieldValues), [fieldValues, selectedForm]);
  const missingFields = useMemo(() => missingRequiredFields(selectedForm, fieldValues), [fieldValues, selectedForm]);
  const onBehalfPolicy = selectedForm?.on_behalf_policy ?? null;
  const onBehalfMissingRequired =
    Boolean(onBehalfPolicy?.allowed && onBehalfEnabled && onBehalfPolicy.affected_person_required && !selectedOnBehalfPerson) ||
    Boolean(onBehalfPolicy?.allowed && onBehalfEnabled && onBehalfPolicy.reason_required && !onBehalfReason.trim());
  const canPreview = Boolean(problem.trim() && selectedForm && !missingFields.length && !onBehalfMissingRequired);
  const canCreate = Boolean(previewResult?.ok && !(previewResult.blockers ?? []).length && !submitting && !previewSubmitting);

  useEffect(() => {
    if (loadedAskContextRef.current) {
      return;
    }
    loadedAskContextRef.current = true;
    const context = readAskContext();
    if (!context) {
      return;
    }
    if (context.query) {
      setProblem(context.query);
    }
    setKnowledgeAttempts((current) => [...current, ...askContextAttempts(context)]);
  }, []);

  useEffect(() => {
    setFieldValues((current) => {
      const next = mergeContextPrefillValues(selectedForm, current, previousPrefill, requestFormPrefill);
      setPreviousPrefill(buildDefaultFieldValues(selectedForm, requestFormPrefill));
      return next;
    });
  }, [requestFormPrefill, selectedForm]);

  useEffect(() => {
    setPreviewResult(null);
  }, [fieldValues, problem, selectedForm?.key, selectedOffering?.full_code, selectedService?.service_code, onBehalfReason, selectedOnBehalfPerson?.person_id]);

  async function loadKnowledgeSuggestions() {
    if (!problem.trim()) {
      setKnowledgeResult(null);
      return;
    }
    setKnowledgeLoading(true);
    setError(null);
    try {
      const result = await suggestKnowledge({
        service_code: selectedService?.service_code,
        offering_code: selectedOffering?.full_code,
        request_template_key: selectedOffering?.request_template_key ?? selectedForm?.key,
        query: problem,
        form_payload: visiblePayload,
        requester_context: bootstrap?.requester_context,
        device_metadata: primaryDevice ? deviceMetadata(primaryDevice) : undefined,
        surface: "requester_portal",
      });
      setKnowledgeResult(result);
    } catch {
      setKnowledgeResult({ suggestions: [], rollout: { enabled: true } });
    } finally {
      setKnowledgeLoading(false);
    }
  }

  async function goToQuickHelp() {
    await loadKnowledgeSuggestions();
    setStep("quick_help");
  }

  async function markKnowledge(item: KnowledgeSuggestionItem, result: Extract<KnowledgeAttempt["result"], KnowledgeFeedbackEvent>) {
    const attempt: KnowledgeAttempt = {
      item_id: item.item_id,
      version_id: item.version_id ?? null,
      result,
      surface: "requester_portal",
      timestamp: new Date().toISOString(),
    };
    setKnowledgeAttempts((current) => [...current, attempt]);
    try {
      await recordKnowledgeFeedback({
        item_id: item.item_id,
        version_id: item.version_id ?? null,
        event_type: result,
        surface: "requester_portal",
        request_template_key: selectedForm?.key,
      });
    } catch {
      // Feedback is non-blocking for request creation.
    }
  }

  async function runOnBehalfSearch() {
    if (!selectedForm || !onBehalfQuery.trim()) {
      return;
    }
    setError(null);
    try {
      const result = await searchRequesterOnBehalfPeople({
        form_key: selectedForm.key,
        q: onBehalfQuery.trim(),
        request_template_key: selectedOffering?.request_template_key ?? selectedForm.key,
        form_pack_key: formPackQuery.data?.pack_key,
        form_pack_version: formPackQuery.data?.version,
      });
      setOnBehalfPeople(result.people ?? []);
    } catch (exc) {
      setError(exc instanceof RequesterApiError || exc instanceof Error ? exc.message : "Не удалось найти сотрудника");
    }
  }

  async function runPreview() {
    if (!canPreview) {
      return;
    }
    setPreviewSubmitting(true);
    setError(null);
    try {
      const result = await previewRequesterTicket(buildCreatePayload());
      setPreviewResult(result);
    } catch (exc) {
      setPreviewResult(null);
      setError(exc instanceof RequesterApiError || exc instanceof Error ? exc.message : "Не удалось проверить заявку");
    } finally {
      setPreviewSubmitting(false);
    }
  }

  function goToReview() {
    setValidationAttempted(true);
    if (missingFieldDetails.length || onBehalfMissingRequired) {
      setError(`Заполните: ${[...missingFields, onBehalfMissingRequired ? "данные сотрудника" : ""].filter(Boolean).join(", ")}.`);
      window.requestAnimationFrame(() => {
        const firstMissingKey = missingFieldDetails[0]?.key;
        if (firstMissingKey) {
          fieldRefs.current[firstMissingKey]?.focus();
        }
      });
      return;
    }
    setError(null);
    setStep("review");
  }

  async function createTicket() {
    if (!canCreate) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const result = await createRequesterTicket(buildCreatePayload());
      window.sessionStorage.removeItem(ASK_TICKET_CONTEXT_STORAGE_KEY);
      await requesterInvalidations.afterTicketMutation(queryClient, result.ticket_id);
      navigate(`/app/requester/tickets/${encodeURIComponent(result.ticket_id)}`);
    } catch (exc) {
      setError(exc instanceof RequesterApiError || exc instanceof Error ? exc.message : "Не удалось создать обращение");
    } finally {
      setSubmitting(false);
    }
  }

  function buildCreatePayload(): RequesterTicketCreatePayload {
    const ticketContext =
      onBehalfPolicy?.allowed && onBehalfEnabled && selectedOnBehalfPerson
        ? {
            affected_person_id: selectedOnBehalfPerson.person_id,
            on_behalf_reason: onBehalfReason.trim() || undefined,
            affected_person_lookup: onBehalfQuery.trim() || undefined,
          }
        : undefined;
    const title = problem.trim().split(/\r?\n/)[0]?.slice(0, 140) || selectedForm?.title || "Новое обращение";
    return {
      ...(primaryDevice?.device_id ? { device_id: primaryDevice.device_id } : {}),
      title,
      description: problem.trim(),
      form_key: selectedForm?.key,
      form_pack_key: formPackQuery.data?.pack_key,
      form_pack_version: formPackQuery.data?.version,
      form_payload: visiblePayload,
      ticket_type: selectedForm?.request_kind ?? undefined,
      service_code: selectedService?.service_code,
      offering_code: selectedOffering?.offering_code,
      offering_full_code: selectedOffering?.full_code,
      request_template_key: selectedOffering?.request_template_key ?? selectedForm?.key,
      ticket_context: ticketContext,
      knowledge_attempts: knowledgeAttempts,
    };
  }

  if (bootstrapQuery.isLoading || formPackQuery.isLoading) {
    return <main className="mx-auto max-w-4xl px-4 py-8 text-sm text-slate-600">Загружаем форму...</main>;
  }

  if (!selectedForm) {
    if (!profileComplete) {
      return (
        <main className="mx-auto max-w-4xl px-4 py-8">
          <h1 className="text-2xl font-semibold text-slate-950">Сначала заполните профиль</h1>
          <p className="mt-2 text-sm text-slate-600">После этого можно будет создать обычное обращение.</p>
          <a className="mt-4 inline-flex rounded-panel bg-brand-700 px-4 py-2 text-sm font-semibold text-white" href={bootstrap?.profile_completion?.setup_path || "/app/requester/profile/setup"}>
            Заполнить профиль
          </a>
        </main>
      );
    }
    return (
      <main className="mx-auto max-w-4xl px-4 py-8">
        <h1 className="text-2xl font-semibold text-slate-950">Нет доступной формы</h1>
        <p className="mt-2 text-sm text-slate-600">Для вашего профиля пока нет подходящего типа обращения.</p>
      </main>
    );
  }

  return (
    <main className="mx-auto grid max-w-5xl gap-5 px-4 py-6 lg:grid-cols-[minmax(0,1fr)_280px]">
      <section className="space-y-4">
        <div>
          <p className="text-sm font-semibold text-brand-700">Новое обращение</p>
          <h1 className="mt-1 text-2xl font-semibold text-slate-950">{stepTitle(step)}</h1>
        </div>
        <StepRail step={step} />
        {error ? <div aria-live="assertive" className="rounded-panel border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800" role="alert">{error}</div> : null}
        {step === "problem" ? (
          <section className="rounded-panel border border-slate-200 bg-white p-4">
            <label className="block text-sm font-semibold text-slate-800">
              Что случилось или что нужно?
              <textarea
                aria-label="Что случилось или что нужно?"
                className="mt-2 min-h-36 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                onChange={(event) => setProblem(event.currentTarget.value)}
                value={problem}
              />
            </label>
            <button
              className="mt-4 inline-flex items-center gap-2 rounded-panel bg-brand-700 px-4 py-2 text-sm font-semibold text-white disabled:bg-slate-300"
              disabled={!problem.trim() || knowledgeLoading}
              onClick={goToQuickHelp}
              type="button"
            >
              <Search className="h-4 w-4" />
              Продолжить
            </button>
          </section>
        ) : null}
        {step === "quick_help" ? (
          <section className="rounded-panel border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-slate-950">Возможно, поможет</h2>
              {knowledgeLoading ? <span className="text-xs text-slate-500">Ищем...</span> : null}
            </div>
            <div className="mt-3 grid gap-2">
              {(knowledgeResult?.suggestions ?? []).length ? (
                (knowledgeResult?.suggestions ?? []).map((item) => (
                  <article className="rounded-panel border border-slate-200 bg-slate-50 px-3 py-2" key={item.item_id}>
                    <p className="font-semibold text-slate-950">{item.title}</p>
                    {item.summary ? <p className="mt-1 text-sm text-slate-600">{item.summary}</p> : null}
                    <button className="mt-2 rounded-panel border border-slate-300 bg-white px-3 py-1 text-xs font-semibold" onClick={() => markKnowledge(item, "not_helpful")} type="button">
                      Не помогло
                    </button>
                  </article>
                ))
              ) : (
                <p className="text-sm text-slate-600">Подходящих подсказок пока нет.</p>
              )}
            </div>
            <button className="mt-4 inline-flex items-center gap-2 rounded-panel bg-brand-700 px-4 py-2 text-sm font-semibold text-white" onClick={() => setStep("details")} type="button">
              <ArrowRight className="h-4 w-4" />
              Продолжить оформление
            </button>
          </section>
        ) : null}
        {step === "details" ? (
          <section className="rounded-panel border border-slate-200 bg-white p-4">
            <h2 className="text-lg font-semibold text-slate-950">{selectedForm.title}</h2>
            {onBehalfPolicy?.allowed ? (
              <OnBehalfPanel
                enabled={onBehalfEnabled}
                onQueryChange={setOnBehalfQuery}
                onReasonChange={setOnBehalfReason}
                onSearch={runOnBehalfSearch}
                onSelect={setSelectedOnBehalfPerson}
                people={onBehalfPeople}
                policy={onBehalfPolicy}
                query={onBehalfQuery}
                reason={onBehalfReason}
                selectedPerson={selectedOnBehalfPerson}
                setEnabled={setOnBehalfEnabled}
              />
            ) : null}
            <div className="mt-4 grid gap-3">
              {contextualFields.map((field) => (
                <RequestFormFieldControl
                  error={validationAttempted && missingFieldDetails.some((item) => item.key === field.key) ? `Заполните поле: ${field.label}.` : null}
                  field={field}
                  inputRef={(element) => {
                    fieldRefs.current[field.key] = element;
                  }}
                  key={field.key}
                  onChange={(value) => {
                    setFieldValues((current) => ({ ...current, [field.key]: value }));
                    setError(null);
                  }}
                  userPickerAllowed={Boolean(onBehalfPolicy?.allowed)}
                  value={fieldValues[field.key]}
                />
              ))}
            </div>
            {missingFields.length || onBehalfMissingRequired ? (
              <p aria-live="polite" className="mt-3 text-sm text-rose-700" role="status">
                Заполните: {[...missingFields, onBehalfMissingRequired ? "данные сотрудника" : ""].filter(Boolean).join(", ")}.
              </p>
            ) : null}
            <button
              className="mt-4 inline-flex items-center gap-2 rounded-panel bg-brand-700 px-4 py-2 text-sm font-semibold text-white disabled:bg-slate-300"
              disabled={!problem.trim() || !selectedForm}
              onClick={goToReview}
              type="button"
            >
              <CheckCircle2 className="h-4 w-4" />
              К проверке
            </button>
          </section>
        ) : null}
        {step === "review" ? (
          <section className="rounded-panel border border-slate-200 bg-white p-4">
            <h2 className="text-lg font-semibold text-slate-950">Проверка перед отправкой</h2>
            <dl className="mt-3 grid gap-2 text-sm">
              <div><dt className="font-semibold text-slate-500">Тема</dt><dd>{problem.trim().split(/\r?\n/)[0]}</dd></div>
              <div><dt className="font-semibold text-slate-500">Тип</dt><dd>{selectedOffering?.title || selectedForm.title}</dd></div>
              {primaryDevice ? <div><dt className="font-semibold text-slate-500">Устройство</dt><dd>{requesterDeviceLabel(primaryDevice, "Основное устройство")}</dd></div> : null}
            </dl>
            {previewResult ? (
              <div className="mt-3 rounded-panel border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                <p className="font-semibold text-slate-950">Безопасный preview</p>
                {previewResult.request_type_label ? <p>Тип: {previewResult.request_type_label}</p> : null}
                {previewResult.diagnostics?.text ? <p>{previewResult.diagnostics.text}</p> : null}
                {(previewResult.blockers ?? []).map((blocker) => <p className="text-rose-700" key={blocker}>{blocker}</p>)}
              </div>
            ) : null}
            <div className="mt-4 flex flex-wrap gap-2">
              <button className="rounded-panel border border-slate-300 bg-white px-4 py-2 text-sm font-semibold disabled:opacity-60" disabled={previewSubmitting} onClick={runPreview} type="button">
                {previewSubmitting ? "Проверяем..." : "Проверить заявку"}
              </button>
              <button className="inline-flex items-center gap-2 rounded-panel bg-brand-700 px-4 py-2 text-sm font-semibold text-white disabled:bg-slate-300" disabled={!canCreate} onClick={createTicket} type="button">
                <Send className="h-4 w-4" />
                {submitting ? "Создаем..." : "Создать обращение"}
              </button>
            </div>
          </section>
        ) : null}
      </section>
      <aside className="space-y-3 lg:sticky lg:top-20 lg:self-start">
        <div className="rounded-panel border border-slate-200 bg-white p-4 text-sm">
          <p className="font-semibold text-slate-950">Подобранный вариант</p>
          <p className="mt-2 text-slate-700">{selectedOffering?.title || selectedForm.title}</p>
          <p className="mt-1 text-slate-500">{selectedService?.title || "Каталог заявок"}</p>
        </div>
        <div className="rounded-panel border border-slate-200 bg-white p-4 text-sm">
          <p className="font-semibold text-slate-950">Контекст</p>
          <p className="mt-2 text-slate-700">{bootstrap?.profile?.display_name || bootstrap?.profile?.full_name || "Заявитель"}</p>
          {primaryDevice ? <p className="mt-1 text-slate-500">{requesterDeviceLabel(primaryDevice, "Основное устройство")}</p> : <p className="mt-1 text-amber-700">Устройство не выбрано</p>}
        </div>
      </aside>
    </main>
  );
}

function StepRail({ step }: { step: WizardStep }) {
  const items: Array<{ key: WizardStep; label: string }> = [
    { key: "problem", label: "Описание" },
    { key: "quick_help", label: "Подсказки" },
    { key: "details", label: "Детали" },
    { key: "review", label: "Проверка" },
  ];
  return (
    <div className="grid gap-2 sm:grid-cols-4">
      {items.map((item) => (
        <div className={`rounded-panel border px-3 py-2 text-sm ${item.key === step ? "border-brand-300 bg-brand-50 text-brand-800" : "border-slate-200 bg-white text-slate-600"}`} key={item.key}>
          {item.label}
        </div>
      ))}
    </div>
  );
}

function OnBehalfPanel({
  enabled,
  onQueryChange,
  onReasonChange,
  onSearch,
  onSelect,
  people,
  policy,
  query,
  reason,
  selectedPerson,
  setEnabled,
}: {
  enabled: boolean;
  onQueryChange: (value: string) => void;
  onReasonChange: (value: string) => void;
  onSearch: () => void;
  onSelect: (person: RequesterOnBehalfPerson) => void;
  people: RequesterOnBehalfPerson[];
  policy: NonNullable<RequestFormDefinition["on_behalf_policy"]>;
  query: string;
  reason: string;
  selectedPerson: RequesterOnBehalfPerson | null;
  setEnabled: (value: boolean) => void;
}) {
  return (
    <div className="mt-4 rounded-panel border border-slate-200 bg-slate-50 p-3">
      <label className="flex items-center gap-2 text-sm font-semibold text-slate-800">
        <input checked={enabled} onChange={(event) => setEnabled(event.currentTarget.checked)} type="checkbox" />
        {policy.label || "Обращение за другого сотрудника"}
      </label>
      {enabled ? (
        <div className="mt-3 grid gap-3">
          <label className="block text-sm font-semibold text-slate-800">
            Найти сотрудника
            <input className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal" onChange={(event) => onQueryChange(event.currentTarget.value)} value={query} />
          </label>
          <button className="w-fit rounded-panel border border-slate-300 bg-white px-3 py-1 text-sm font-semibold" onClick={onSearch} type="button">Найти</button>
          {people.map((person) => (
            <button className="rounded-panel border border-slate-200 bg-white px-3 py-2 text-left text-sm" key={person.person_id} onClick={() => onSelect(person)} type="button">
              <span className="font-semibold">{person.display_name || person.full_name || person.email}</span>
              {selectedPerson?.person_id === person.person_id ? <span className="ml-2 text-brand-700">выбран</span> : null}
            </button>
          ))}
          {policy.reason_required ? (
            <label className="block text-sm font-semibold text-slate-800">
              Причина
              <textarea className="mt-1 min-h-20 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal" onChange={(event) => onReasonChange(event.currentTarget.value)} value={reason} />
            </label>
          ) : null}
          {selectedPerson?.primary_agent?.status === "missing" || selectedPerson?.primary_agent?.status === "ambiguous" ? (
            <p className="text-sm text-amber-700">У выбранного сотрудника нет однозначного основного устройства. Диагностика может быть недоступна.</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function firstAvailableOffering(services: ServiceCatalogCurrent["services"]) {
  for (const service of services) {
    const offering = service.offerings?.[0];
    if (offering) {
      return { ...offering, service_code: service.service_code };
    }
  }
  return null;
}

function resolveSelectedForm(
  forms: RequestFormDefinition[],
  offering: (ServiceCatalogCurrent["services"][number]["offerings"][number] & { service_code: string }) | null,
  profileComplete: boolean,
  hasAgentContext: boolean,
) {
  const visible = forms.filter((form) => formVisibleForRequester(form, profileComplete, hasAgentContext));
  return visible.find((form) => form.key === offering?.request_template_key) ?? visible[0] ?? null;
}

function formVisibleForRequester(form: RequestFormDefinition, profileComplete: boolean, hasAgentContext: boolean): boolean {
  const policy = form.availability_policy ?? {};
  if (!profileComplete && !policy.available_without_completed_profile && !form.available_without_completed_profile) {
    return false;
  }
  if (!hasAgentContext && !policy.available_without_agent_binding && !form.available_without_agent_binding && !form.on_behalf_policy?.allowed) {
    return false;
  }
  return true;
}

function requesterFormPrefillFromContext(
  context: RequesterContextPreview | null | undefined,
  profile: { display_name?: string | null; full_name?: string | null; department_id?: string | null; location_id?: string | null; email?: string | null; phone?: string | null } | null | undefined,
  device: RequesterDevice | null,
  service: ServiceCatalogCurrent["services"][number] | null,
  offering: (ServiceCatalogCurrent["services"][number]["offerings"][number] & { service_code: string }) | null,
): DynamicFormValues {
  const values: DynamicFormValues = {};
  Object.entries(context?.form_prefill ?? {}).forEach(([key, value]) => {
    values[key] = Array.isArray(value) ? value.map((item) => String(item)) : typeof value === "boolean" ? value : String(value ?? "");
  });
  if (profile?.department_id) values.department_id = profile.department_id;
  if (profile?.location_id) values.location_id = profile.location_id;
  if (profile?.phone) values.phone = profile.phone;
  if (profile?.email) values.email = profile.email;
  if (profile?.display_name || profile?.full_name) values.requester_name = profile.display_name || profile.full_name || "";
  if (device) {
    values.device_id = device.device_id;
    values.device = requesterDeviceLabel(device, "Основное устройство");
  }
  if (service) {
    values.service_code = service.service_code;
    values.service = service.title || service.service_code;
  }
  if (offering) {
    values.offering_code = offering.offering_code;
    values.offering_full_code = offering.full_code;
    values.offering = offering.title || offering.full_code;
  }
  return values;
}

function deviceMetadata(device: RequesterDevice): Record<string, unknown> {
  return {
    device_id: device.device_id,
    hostname: device.hostname,
    os: device.os,
    agent_version: device.agent_version,
    asset_id: device.asset_id,
    asset_name: device.asset_name,
  };
}

function stepTitle(step: WizardStep): string {
  return {
    problem: "Опишите проблему",
    quick_help: "Быстрые подсказки",
    details: "Детали заявки",
    review: "Проверка",
  }[step];
}

function readAskContext(): AskTicketContext | null {
  try {
    const raw = window.sessionStorage.getItem(ASK_TICKET_CONTEXT_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AskTicketContext;
    const createdAt = parsed.created_at ? Date.parse(parsed.created_at) : 0;
    if (createdAt && Date.now() - createdAt > ASK_TICKET_CONTEXT_MAX_AGE_MS) {
      window.sessionStorage.removeItem(ASK_TICKET_CONTEXT_STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function askContextAttempts(context: AskTicketContext): KnowledgeAttempt[] {
  const now = new Date().toISOString();
  const items = context.primary_item?.item_id ? [context.primary_item, ...(context.retrieval_results ?? [])] : context.retrieval_results ?? [];
  const seen = new Set<string>();
  return items
    .map((item) => ({ item_id: item?.item_id ?? "", version_id: item?.version_id ?? null }))
    .filter((item) => {
      if (!item.item_id || seen.has(item.item_id)) return false;
      seen.add(item.item_id);
      return true;
    })
    .slice(0, 5)
    .map((item) => ({ ...item, result: "ticket_created_after_view" as const, surface: "requester_portal" as const, timestamp: now }));
}
