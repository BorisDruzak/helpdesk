import { ArrowRight, CheckCircle2, Search, Send } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import {
  createRequesterTicket,
  previewRequesterTicket,
  recordKnowledgeFeedback,
  searchRequesterOnBehalfPeople,
  suggestKnowledge,
} from "../../features/requester/api";
import {
  requesterInvalidations,
  requesterTicketRouteParam,
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
  validateDynamicFormValues,
  type DynamicFormValues,
} from "../../features/requester/dynamic-form";
import { requesterDeviceLabel, requesterErrorMessage } from "../../features/requester/labels";
import { Button, FieldShell, FormActions, InlineAlert, Textarea } from "../../features/requester/ui/form-controls";
import {
  ASK_TICKET_CONTEXT_STORAGE_KEY,
  CategorySelector,
  OWNER_CHANGE_INTENT,
  OWNER_CHANGE_PROBLEM,
  OnBehalfPanel,
  StepRail,
  askContextAttempts,
  buildCategoryOptions,
  deviceMetadata,
  isResolvedPrimaryDeviceStatus,
  primaryDeviceResolutionText,
  readAskContext,
  recommendOffering,
  requesterFormPrefillFromContext,
  resolveRecommendedCategoryKey,
  stepTitle,
  type WizardStep,
} from "./new-request-workflow";
import type {
  KnowledgeAttempt,
  KnowledgeSuggestResult,
  KnowledgeSuggestionItem,
  RequesterOnBehalfPerson,
  RequesterTicketCreatePayload,
  ServiceCatalogSafePreview,
} from "../../features/requester/types";
import { useQueryClient } from "@tanstack/react-query";

type KnowledgeFeedbackEvent = Parameters<typeof recordKnowledgeFeedback>[0]["event_type"];

export function RequesterNewRequestPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const requestIntent = useMemo(() => new URLSearchParams(location.search).get("intent") || "", [location.search]);
  const bootstrapQuery = useRequesterBootstrapQuery();
  const formPackQuery = useRequesterFormPackQuery();
  const catalogQuery = useRequesterServiceCatalogQuery();
  const bootstrap = bootstrapQuery.data ?? null;
  const forms = formPackQuery.data?.forms ?? [];
  const services = catalogQuery.data?.services ?? [];
  const profileComplete = bootstrap?.profile_completion ? bootstrap.profile_completion.complete !== false : Boolean(bootstrap?.profile);
  const devices = bootstrap?.devices ?? [];
  const primaryResolutionStatus = String(bootstrap?.primary_device_resolution?.status ?? "").trim().toLowerCase();
  const primaryDevice =
    bootstrap?.primary_device && isResolvedPrimaryDeviceStatus(primaryResolutionStatus)
      ? bootstrap.primary_device
      : null;
  const hasAgentContext = Boolean(primaryDevice);
  const [step, setStep] = useState<WizardStep>("problem");
  const [problem, setProblem] = useState(() => (requestIntent === OWNER_CHANGE_INTENT ? OWNER_CHANGE_PROBLEM : ""));
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
  const [selectedCategoryKey, setSelectedCategoryKey] = useState("");
  const [showAllCategoryOptions, setShowAllCategoryOptions] = useState(false);

  const categoryOptions = useMemo(
    () => buildCategoryOptions(services, forms, profileComplete, hasAgentContext),
    [forms, hasAgentContext, profileComplete, services],
  );
  const recommendation = useMemo(() => recommendOffering(services, problem, forms, requestIntent), [forms, problem, requestIntent, services]);
  const recommendedOffering = recommendation?.offering ?? null;
  const recommendedCategoryKey = useMemo(
    () => resolveRecommendedCategoryKey(categoryOptions, recommendedOffering, requestIntent),
    [categoryOptions, recommendedOffering, requestIntent],
  );
  const shouldAutoSelectRecommendedCategory = Boolean(recommendedCategoryKey && recommendation?.confident);
  const autoSelectCategoryKey =
    requestIntent === OWNER_CHANGE_INTENT ? recommendedCategoryKey : shouldAutoSelectRecommendedCategory ? recommendedCategoryKey : null;
  const selectedCategory = useMemo(
    () => categoryOptions.find((option) => option.key === selectedCategoryKey) ?? null,
    [categoryOptions, selectedCategoryKey],
  );
  const categorySelectorOptions = useMemo(() => {
    if (
      !showAllCategoryOptions &&
      shouldAutoSelectRecommendedCategory &&
      selectedCategory &&
      selectedCategory.key === recommendedCategoryKey
    ) {
      return [selectedCategory];
    }
    return categoryOptions;
  }, [categoryOptions, recommendedCategoryKey, selectedCategory, shouldAutoSelectRecommendedCategory, showAllCategoryOptions]);
  const selectedOffering = selectedCategory?.offering ?? null;
  const selectedService = selectedCategory?.service ?? null;
  const selectedForm = selectedCategory?.form ?? null;
  const selectedFormAvailability = selectedCategory?.availability ?? null;
  const requiresOnBehalfForAvailability = selectedFormAvailability?.requiresOnBehalfForAvailability === true;
  const needsRegistryOptions = useMemo(
    () => (selectedForm?.fields ?? []).some((field) => field.type === "department_picker" || field.type === "location_picker"),
    [selectedForm],
  );
  const registryOptionsQuery = useRequesterRegistryOptionsQuery({ enabled: needsRegistryOptions });
  const requestFormPrefill = useMemo(
    () => requesterFormPrefillFromContext(bootstrap?.requester_context, bootstrap?.profile, primaryDevice, selectedService, selectedOffering),
    [bootstrap?.profile, bootstrap?.requester_context, primaryDevice, selectedOffering, selectedService],
  );
  const onBehalfPolicy = selectedForm?.on_behalf_policy ?? null;
  const onBehalfActive = Boolean(onBehalfPolicy?.allowed && (onBehalfEnabled || requiresOnBehalfForAvailability));
  const activeDynamicForm = selectedForm && (!requiresOnBehalfForAvailability || selectedOnBehalfPerson) ? selectedForm : null;
  const contextualFields = useMemo(
    () =>
      (activeDynamicForm?.fields ?? [])
        .filter((field) => isDynamicFieldVisible(field, fieldValues))
        .map((field) =>
          fieldWithRequesterContextOptions(field, {
            departments: registryOptionsQuery.data?.departments ?? [],
            locations: registryOptionsQuery.data?.locations ?? [],
            devices,
            services,
          }),
        ),
    [activeDynamicForm, devices, fieldValues, registryOptionsQuery.data?.departments, registryOptionsQuery.data?.locations, services],
  );
  const visiblePayload = useMemo(() => collectVisiblePayload(activeDynamicForm, fieldValues), [activeDynamicForm, fieldValues]);
  const missingFieldDetails = useMemo(() => missingRequiredFieldDetails(activeDynamicForm, fieldValues), [activeDynamicForm, fieldValues]);
  const missingFields = useMemo(() => missingRequiredFields(activeDynamicForm, fieldValues), [activeDynamicForm, fieldValues]);
  const valueValidation = useMemo(() => validateDynamicFormValues(activeDynamicForm, fieldValues), [activeDynamicForm, fieldValues]);
  const onBehalfMissingRequired =
    Boolean(onBehalfActive && onBehalfPolicy?.affected_person_required && !selectedOnBehalfPerson) ||
    Boolean(onBehalfActive && onBehalfPolicy?.reason_required && !onBehalfReason.trim());
  const canPreview = Boolean(
    problem.trim() &&
      selectedForm &&
      (selectedFormAvailability?.availableForSelf || onBehalfActive) &&
      !missingFields.length &&
      !valueValidation.issues.length &&
      !onBehalfMissingRequired,
  );
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
    setSelectedCategoryKey((current) => {
      if (current && categoryOptions.some((option) => option.key === current)) {
        return current;
      }
      return autoSelectCategoryKey ?? "";
    });
  }, [autoSelectCategoryKey, categoryOptions]);

  useEffect(() => {
    setShowAllCategoryOptions(false);
  }, [recommendedCategoryKey]);

  useEffect(() => {
    setFieldValues((current) => {
      const next = mergeContextPrefillValues(selectedForm, current, previousPrefill, requestFormPrefill);
      setPreviousPrefill(buildDefaultFieldValues(selectedForm, requestFormPrefill));
      return next;
    });
  }, [requestFormPrefill, selectedForm]);

  useEffect(() => {
    setPreviewResult(null);
  }, [fieldValues, problem, selectedCategoryKey, selectedForm?.key, selectedOffering?.full_code, selectedService?.service_code, onBehalfReason, selectedOnBehalfPerson?.person_id]);

  useEffect(() => {
    setOnBehalfEnabled(false);
    setOnBehalfQuery("");
    setOnBehalfPeople([]);
    setSelectedOnBehalfPerson(null);
    setOnBehalfReason("");
  }, [selectedForm?.key]);

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
      setError(requesterErrorMessage(exc, "Не удалось найти сотрудника", { domain: "profile" }));
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
      setError(requesterErrorMessage(exc, "Не удалось проверить обращение", { operation: "preview" }));
    } finally {
      setPreviewSubmitting(false);
    }
  }

  function goToReview() {
    setValidationAttempted(true);
    if (missingFieldDetails.length || valueValidation.issues.length || onBehalfMissingRequired) {
      setError(
        valueValidation.issues[0]?.message ||
          `Заполните: ${[...missingFields, onBehalfMissingRequired ? "данные сотрудника" : ""].filter(Boolean).join(", ")}.`,
      );
      window.requestAnimationFrame(() => {
        const firstMissingKey = missingFieldDetails[0]?.key ?? valueValidation.issues[0]?.path.replace(/^fields\./, "");
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
      const ticketRouteParam = requesterTicketRouteParam({
        ticket_id: result.ticket?.ticket_id ?? result.ticket_id,
        ticket_code: result.ticket?.ticket_code ?? result.ticket_code,
      });
      await requesterInvalidations.afterTicketMutation(queryClient, ticketRouteParam);
      if (!ticketRouteParam) {
        navigate("/app/requester/tickets");
        return;
      }
      navigate(`/app/requester/tickets/${encodeURIComponent(ticketRouteParam)}`);
    } catch (exc) {
      setError(requesterErrorMessage(exc, "Не удалось создать обращение", { operation: "create" }));
    } finally {
      setSubmitting(false);
    }
  }

  function buildCreatePayload(): RequesterTicketCreatePayload {
    const ticketContext =
      onBehalfActive && selectedOnBehalfPerson
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
    return <div className="mx-auto max-w-4xl px-4 py-8 text-sm text-slate-600">Загружаем форму...</div>;
  }

  if (!categoryOptions.length) {
    if (!profileComplete) {
      return (
        <div className="mx-auto max-w-4xl px-4 py-8">
          <h1 className="text-2xl font-semibold text-slate-950">Сначала заполните профиль</h1>
          <p className="mt-2 text-sm text-slate-600">После этого можно будет создать обычное обращение.</p>
          <a className="mt-4 inline-flex rounded-panel bg-brand-700 px-4 py-2 text-sm font-semibold text-white" href={bootstrap?.profile_completion?.setup_path || "/app/requester/profile/setup"}>
            Заполнить профиль
          </a>
        </div>
      );
    }
    return (
      <div className="mx-auto max-w-4xl px-4 py-8">
        <h1 className="text-2xl font-semibold text-slate-950">Нет доступной формы</h1>
        <p className="mt-2 text-sm text-slate-600">Для вашего профиля пока нет подходящего типа обращения.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto grid max-w-5xl gap-5 px-4 py-6 lg:grid-cols-[minmax(0,1fr)_280px]">
      <section className="space-y-4">
        <div>
          <p className="text-sm font-semibold text-brand-700">Новое обращение</p>
          <h1 className="mt-1 text-2xl font-semibold text-slate-950">{stepTitle(step)}</h1>
        </div>
        <StepRail step={step} />
        {error ? <InlineAlert aria-live="assertive" role="alert" tone="danger">{error}</InlineAlert> : null}
        {step === "problem" ? (
          <section className="rounded-panel border border-slate-200 bg-white p-4">
            <FieldShell label="Что случилось или что нужно?">
              <Textarea
                aria-label="Что случилось или что нужно?"
                className="mt-2 min-h-36 font-normal"
                onChange={(event) => setProblem(event.currentTarget.value)}
                value={problem}
              />
            </FieldShell>
            <Button
              className="mt-4"
              disabled={!problem.trim() || knowledgeLoading}
              leadingIcon={<Search className="h-4 w-4" />}
              onClick={goToQuickHelp}
              type="button"
            >
              Продолжить
            </Button>
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
                    <Button className="mt-2" onClick={() => markKnowledge(item, "not_helpful")} size="sm" type="button" variant="outline">
                      Не помогло
                    </Button>
                  </article>
                ))
              ) : (
                <p className="text-sm text-slate-600">Подходящих подсказок пока нет.</p>
              )}
            </div>
            <Button className="mt-4" leadingIcon={<ArrowRight className="h-4 w-4" />} onClick={() => setStep("details")} type="button">
              Продолжить оформление
            </Button>
          </section>
        ) : null}
        {step === "details" ? (
          <section className="rounded-panel border border-slate-200 bg-white p-4">
            <CategorySelector
              canShowAll={categorySelectorOptions.length < categoryOptions.length}
              onShowAll={() => setShowAllCategoryOptions(true)}
              options={categorySelectorOptions}
              recommendedKey={recommendedCategoryKey}
              selectedKey={selectedCategoryKey}
              onChange={(key) => {
                setSelectedCategoryKey(key);
                setError(null);
              }}
            />
            {!selectedForm ? (
              <p className="mt-3 text-sm text-slate-600">Выберите категорию, чтобы увидеть нужные поля и безопасную проверку.</p>
            ) : null}
            {selectedForm ? <h2 className="mt-4 text-lg font-semibold text-slate-950">{selectedForm.title}</h2> : null}
            {requiresOnBehalfForAvailability ? (
              <InlineAlert className="mt-3" tone="warning">
                Для обращения за себя нужно основное устройство.
              </InlineAlert>
            ) : null}
            {selectedForm && onBehalfPolicy?.allowed ? (
              <OnBehalfPanel
                enabled={onBehalfActive}
                onQueryChange={setOnBehalfQuery}
                onReasonChange={setOnBehalfReason}
                onSearch={runOnBehalfSearch}
                onSelect={setSelectedOnBehalfPerson}
                people={onBehalfPeople}
                policy={onBehalfPolicy}
                query={onBehalfQuery}
                reason={onBehalfReason}
                required={requiresOnBehalfForAvailability}
                selectedPerson={selectedOnBehalfPerson}
                setEnabled={setOnBehalfEnabled}
              />
            ) : null}
            <div className="mt-4 grid gap-3">
              {contextualFields.map((field) => (
                <RequestFormFieldControl
                  error={
                    validationAttempted
                      ? missingFieldDetails.some((item) => item.key === field.key)
                        ? `Заполните поле: ${field.label}.`
                        : valueValidation.issues.find((item) => item.path === `fields.${field.key}`)?.message ?? null
                      : null
                  }
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
            {selectedForm && (missingFields.length || valueValidation.issues.length || onBehalfMissingRequired) ? (
              <p aria-live="polite" className="mt-3 text-sm text-rose-700" role="status">
                {valueValidation.issues[0]?.message ||
                  `Заполните: ${[...missingFields, onBehalfMissingRequired ? "данные сотрудника" : ""].filter(Boolean).join(", ")}.`}
              </p>
            ) : null}
            <Button
              className="mt-4"
              disabled={!problem.trim() || !selectedForm}
              leadingIcon={<CheckCircle2 className="h-4 w-4" />}
              onClick={goToReview}
              type="button"
            >
              К проверке
            </Button>
          </section>
        ) : null}
        {step === "review" ? (
          <section className="rounded-panel border border-slate-200 bg-white p-4">
            <h2 className="text-lg font-semibold text-slate-950">Проверка перед отправкой</h2>
            <dl className="mt-3 grid gap-2 text-sm">
              <div><dt className="font-semibold text-slate-500">Тема</dt><dd>{problem.trim().split(/\r?\n/)[0]}</dd></div>
              <div><dt className="font-semibold text-slate-500">Тип</dt><dd>{selectedOffering?.title || selectedForm?.title}</dd></div>
              {primaryDevice ? <div><dt className="font-semibold text-slate-500">Устройство</dt><dd>{requesterDeviceLabel(primaryDevice, "Основное устройство")}</dd></div> : null}
            </dl>
            {previewResult ? (
              <div className="mt-3 rounded-panel border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                <p className="font-semibold text-slate-950">Безопасная проверка</p>
                {previewResult.request_type_label ? <p>Тип: {previewResult.request_type_label}</p> : null}
                {previewResult.diagnostics?.text ? <p>{previewResult.diagnostics.text}</p> : null}
                {(previewResult.blockers ?? []).map((blocker) => <p className="text-rose-700" key={blocker}>{blocker}</p>)}
              </div>
            ) : null}
            <FormActions className="mt-4">
              <Button disabled={previewSubmitting} onClick={runPreview} type="button" variant="outline">
                {previewSubmitting ? "Проверяем..." : "Проверить обращение"}
              </Button>
              <Button disabled={!canCreate} leadingIcon={<Send className="h-4 w-4" />} onClick={createTicket} type="button">
                {submitting ? "Создаем..." : "Создать обращение"}
              </Button>
            </FormActions>
          </section>
        ) : null}
      </section>
      <aside className="space-y-3 lg:sticky lg:top-20 lg:self-start">
        <div className="rounded-panel border border-slate-200 bg-white p-4 text-sm">
          <p className="font-semibold text-slate-950">Категория обращения</p>
          <p className="mt-2 text-slate-700">{selectedCategory?.label || "Выберите категорию"}</p>
          <p className="mt-1 text-slate-500">{selectedService?.title || "Каталог обращений"}</p>
        </div>
        <div className="rounded-panel border border-slate-200 bg-white p-4 text-sm">
          <p className="font-semibold text-slate-950">Контекст</p>
          <p className="mt-2 text-slate-700">{bootstrap?.profile?.display_name || bootstrap?.profile?.full_name || "Заявитель"}</p>
          {primaryDevice ? (
            <p className="mt-1 text-slate-500">{requesterDeviceLabel(primaryDevice, "Основное устройство")}</p>
          ) : (
            <p className="mt-1 text-amber-700">{primaryDeviceResolutionText(bootstrap?.primary_device_resolution)}</p>
          )}
        </div>
      </aside>
    </div>
  );
}
