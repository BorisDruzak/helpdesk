import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { createRequesterTicket, previewRequesterTicket, searchRequesterOnBehalfPeople } from "../../features/requester/api";
import {
  requesterInvalidations,
  requesterTicketRouteParam,
  useRequesterBootstrapQuery,
  useRequesterFormPackQuery,
  useRequesterRegistryOptionsQuery,
  useRequesterServiceCatalogQuery,
} from "../../features/requester/queries";
import {
  buildDefaultFieldValues,
  collectVisiblePayload,
  fieldWithRequesterContextOptions,
  formatDynamicFieldReviewValue,
  isDynamicFieldVisible,
  mergeContextPrefillValues,
  missingRequiredFieldDetails,
  missingRequiredFields,
  validateDynamicFormValues,
  type DynamicFormValues,
} from "../../features/requester/dynamic-form";
import { requesterErrorMessage } from "../../features/requester/labels";
import {
  DetailsStepPanel,
  RequestSummaryAside,
  RequestWizardShell,
  ReviewStepPanel,
} from "./new-request-panels";
import {
  ASK_TICKET_CONTEXT_STORAGE_KEY,
  OWNER_CHANGE_INTENT,
  OWNER_CHANGE_PROBLEM,
  askContextAttempts,
  buildCategoryOptions,
  isResolvedPrimaryDeviceStatus,
  readAskContext,
  recommendOffering,
  requesterFormPrefillFromContext,
  resolveRecommendedCategoryKey,
  type WizardStep,
} from "./new-request-workflow";
import type {
  KnowledgeAttempt,
  RequestFormDefinition,
  RequestFormField,
  RequesterOnBehalfPerson,
  RequesterTicketCreatePayload,
  ServiceCatalogSafePreview,
} from "../../features/requester/types";
import { useQueryClient } from "@tanstack/react-query";

const REQUEST_DRAFT_STORAGE_KEY_PREFIX = "pc_client.requester.new_request.draft.v1";

type NewRequestDraft = {
  fieldValues?: DynamicFormValues;
  formPackVersion?: string | null;
  intent?: string;
  onBehalfEnabled?: boolean;
  onBehalfQuery?: string;
  onBehalfReason?: string;
  selectedCategoryKey?: string;
  selectedOnBehalfPerson?: RequesterOnBehalfPerson | null;
  showAllCategoryOptions?: boolean;
  status: "draft";
  step?: WizardStep;
  updated_at?: string;
};

function draftStorageKey(personId: string | null | undefined, intent: string): string {
  return `${REQUEST_DRAFT_STORAGE_KEY_PREFIX}:${personId || "anonymous"}:${intent || "default"}`;
}

function readNewRequestDraft(key: string): NewRequestDraft | null {
  try {
    const raw = window.sessionStorage.getItem(key);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<NewRequestDraft>;
    return parsed.status === "draft" ? (parsed as NewRequestDraft) : null;
  } catch {
    return null;
  }
}

function writeNewRequestDraft(key: string, draft: NewRequestDraft): void {
  try {
    window.sessionStorage.setItem(key, JSON.stringify(draft));
  } catch {
    // Draft persistence is best-effort and must not block ticket creation.
  }
}

function removeNewRequestDraft(key: string | null): void {
  if (!key) {
    return;
  }
  try {
    window.sessionStorage.removeItem(key);
  } catch {
    // Ignore storage failures.
  }
}

function withRequestSeedPrefill(
  form: RequestFormDefinition | null,
  values: DynamicFormValues,
  requestSeed: string,
): DynamicFormValues {
  const seed = requestSeed.trim();
  if (!form || !seed) {
    return values;
  }
  const preferredKeys = ["summary", "description", "details", "owner_context", "problem", "subject", "title"];
  const field =
    preferredKeys
      .map((key) => form.fields.find((item) => item.key === key && isLongTextField(item)))
      .find(Boolean) ??
    form.fields.find((item) => item.required && isLongTextField(item)) ??
    form.fields.find(isLongTextField);
  if (!field || values[field.key]) {
    return values;
  }
  return { ...values, [field.key]: seed };
}

function isLongTextField(field: RequestFormField): boolean {
  return field.type === "text" || field.type === "textarea";
}

function fieldTextValue(fields: RequestFormField[], payload: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const field = fields.find((item) => item.key === key);
    if (!field) {
      continue;
    }
    const text = formatDynamicFieldReviewValue(field, payload[key] as never).trim();
    if (isMeaningfulFieldText(text)) {
      return text;
    }
  }
  return "";
}

function isMeaningfulFieldText(value: string): boolean {
  return Boolean(value && value !== "Не указано" && value !== "Не выбрано" && value !== "Выбрано значение");
}

function requestTitleFromForm(
  fields: RequestFormField[],
  payload: Record<string, unknown>,
  selectedForm: RequestFormDefinition | null,
  selectedOffering: { title?: string | null } | null,
): string {
  const title =
    fieldTextValue(fields, payload, ["summary", "title", "subject", "description", "details", "owner_context", "problem"]) ||
    selectedOffering?.title ||
    selectedForm?.title ||
    "Новое обращение";
  return title.split(/\r?\n/)[0]?.slice(0, 140) || "Новое обращение";
}

function requestDescriptionFromForm(
  fields: RequestFormField[],
  payload: Record<string, unknown>,
  title: string,
): string {
  const preferred = fieldTextValue(fields, payload, ["description", "details", "owner_context", "problem", "summary", "title", "subject"]);
  if (preferred) {
    return preferred;
  }
  const rows = fields
    .map((field) => {
      const text = formatDynamicFieldReviewValue(field, payload[field.key] as never).trim();
      return isMeaningfulFieldText(text) ? `${field.label}: ${text}` : "";
    })
    .filter(Boolean);
  return rows.length ? rows.join("\n") : title;
}

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
  const requestDraftStorageKey = bootstrap ? draftStorageKey(bootstrap.profile?.person_id, requestIntent) : null;
  const [step, setStep] = useState<WizardStep>("details");
  const [requestSeed, setRequestSeed] = useState(() => (requestIntent === OWNER_CHANGE_INTENT ? OWNER_CHANGE_PROBLEM : ""));
  const [fieldValues, setFieldValues] = useState<DynamicFormValues>({});
  const [previousPrefill, setPreviousPrefill] = useState<DynamicFormValues>({});
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
  const restoredDraftRef = useRef(false);

  const categoryOptions = useMemo(
    () => buildCategoryOptions(services, forms, profileComplete, hasAgentContext),
    [forms, hasAgentContext, profileComplete, services],
  );
  const recommendation = useMemo(
    () => recommendOffering(services, requestSeed, forms, requestIntent),
    [forms, requestIntent, requestSeed, services],
  );
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
  const requestFormPrefill = useMemo(() => {
    const contextPrefill = requesterFormPrefillFromContext(
      bootstrap?.requester_context,
      bootstrap?.profile,
      primaryDevice,
      selectedService,
      selectedOffering,
    );
    return withRequestSeedPrefill(selectedForm, contextPrefill, requestSeed);
  }, [bootstrap?.profile, bootstrap?.requester_context, primaryDevice, requestSeed, selectedForm, selectedOffering, selectedService]);
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
  const requestTitle = useMemo(
    () => requestTitleFromForm(contextualFields, visiblePayload, selectedForm, selectedOffering),
    [contextualFields, selectedForm, selectedOffering, visiblePayload],
  );
  const requestDescription = useMemo(
    () => requestDescriptionFromForm(contextualFields, visiblePayload, requestTitle),
    [contextualFields, requestTitle, visiblePayload],
  );
  const missingFieldDetails = useMemo(() => missingRequiredFieldDetails(activeDynamicForm, fieldValues), [activeDynamicForm, fieldValues]);
  const missingFields = useMemo(() => missingRequiredFields(activeDynamicForm, fieldValues), [activeDynamicForm, fieldValues]);
  const valueValidation = useMemo(() => validateDynamicFormValues(activeDynamicForm, fieldValues), [activeDynamicForm, fieldValues]);
  const onBehalfMissingRequired =
    Boolean(onBehalfActive && onBehalfPolicy?.affected_person_required && !selectedOnBehalfPerson) ||
    Boolean(onBehalfActive && onBehalfPolicy?.reason_required && !onBehalfReason.trim());
  const canPreview = Boolean(
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
      setRequestSeed(context.query);
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
  }, [
    fieldValues,
    selectedCategoryKey,
    selectedForm?.key,
    selectedOffering?.full_code,
    selectedService?.service_code,
    onBehalfReason,
    selectedOnBehalfPerson?.person_id,
  ]);

  useEffect(() => {
    if (!requestDraftStorageKey || restoredDraftRef.current || !formPackQuery.data || !categoryOptions.length) {
      return;
    }
    restoredDraftRef.current = true;
    const draft = readNewRequestDraft(requestDraftStorageKey);
    if (!draft || draft.intent !== requestIntent) {
      return;
    }
    if (draft.formPackVersion && draft.formPackVersion !== formPackQuery.data.version) {
      removeNewRequestDraft(requestDraftStorageKey);
      return;
    }
    if (draft.selectedCategoryKey && !categoryOptions.some((option) => option.key === draft.selectedCategoryKey)) {
      removeNewRequestDraft(requestDraftStorageKey);
      return;
    }
    setSelectedCategoryKey(draft.selectedCategoryKey ?? "");
    setShowAllCategoryOptions(Boolean(draft.showAllCategoryOptions));
    setFieldValues(draft.fieldValues ?? {});
    setOnBehalfEnabled(Boolean(draft.onBehalfEnabled));
    setOnBehalfQuery(draft.onBehalfQuery ?? "");
    setSelectedOnBehalfPerson(draft.selectedOnBehalfPerson ?? null);
    setOnBehalfReason(draft.onBehalfReason ?? "");
    setStep(draft.step === "review" ? "review" : "details");
    setPreviewResult(null);
    setError(null);
  }, [categoryOptions, formPackQuery.data, requestDraftStorageKey, requestIntent]);

  useEffect(() => {
    if (!requestDraftStorageKey || !formPackQuery.data || !restoredDraftRef.current) {
      return;
    }
    const hasDraftData =
      Boolean(selectedCategoryKey) ||
      Object.keys(fieldValues).length > 0 ||
      onBehalfEnabled ||
      Boolean(onBehalfQuery.trim()) ||
      Boolean(onBehalfReason.trim()) ||
      Boolean(selectedOnBehalfPerson) ||
      showAllCategoryOptions ||
      step !== "details";
    if (!hasDraftData) {
      removeNewRequestDraft(requestDraftStorageKey);
      return;
    }
    writeNewRequestDraft(requestDraftStorageKey, {
      fieldValues,
      formPackVersion: formPackQuery.data.version,
      intent: requestIntent,
      onBehalfEnabled,
      onBehalfQuery,
      onBehalfReason,
      selectedCategoryKey,
      selectedOnBehalfPerson,
      showAllCategoryOptions,
      status: "draft",
      step,
      updated_at: new Date().toISOString(),
    });
  }, [
    fieldValues,
    formPackQuery.data,
    onBehalfEnabled,
    onBehalfQuery,
    onBehalfReason,
    requestDraftStorageKey,
    requestIntent,
    selectedCategoryKey,
    selectedOnBehalfPerson,
    showAllCategoryOptions,
    step,
  ]);

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
    if (!selectedForm) {
      setError("Выберите категорию обращения.");
      return;
    }
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

  function canSelectStep(nextStep: WizardStep): boolean {
    if (nextStep === "details") {
      return true;
    }
    return canPreview;
  }

  function selectStep(nextStep: WizardStep) {
    if (nextStep === "details") {
      setError(null);
      setStep("details");
      return;
    }
    goToReview();
  }

  function resetOnBehalfState() {
    setOnBehalfEnabled(false);
    setOnBehalfQuery("");
    setOnBehalfPeople([]);
    setSelectedOnBehalfPerson(null);
    setOnBehalfReason("");
  }

  function selectCategoryKey(key: string) {
    if (key !== selectedCategoryKey) {
      resetOnBehalfState();
    }
    setSelectedCategoryKey(key);
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
      removeNewRequestDraft(requestDraftStorageKey);
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
    return {
      ...(primaryDevice?.device_id ? { device_id: primaryDevice.device_id } : {}),
      title: requestTitle,
      description: requestDescription,
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
      <RequestWizardShell
        canSelectStep={canSelectStep}
        draftStatusLabel="Черновик"
        error={error}
        onStepSelect={selectStep}
        step={step}
      >
        {step === "details" ? (
          <DetailsStepPanel
            categoryOptions={categoryOptions}
            categorySelectorOptions={categorySelectorOptions}
            contextualFields={contextualFields}
            fieldRefs={fieldRefs}
            fieldValues={fieldValues}
            goToReview={goToReview}
            missingFieldDetails={missingFieldDetails}
            missingFields={missingFields}
            onBehalfActive={onBehalfActive}
            onBehalfMissingRequired={onBehalfMissingRequired}
            onBehalfPeople={onBehalfPeople}
            onBehalfPolicy={onBehalfPolicy}
            onBehalfQuery={onBehalfQuery}
            onBehalfReason={onBehalfReason}
            recommendedCategoryKey={recommendedCategoryKey}
            requiresOnBehalfForAvailability={requiresOnBehalfForAvailability}
            runOnBehalfSearch={runOnBehalfSearch}
            selectedCategoryKey={selectedCategoryKey}
            selectedForm={selectedForm}
            selectedOnBehalfPerson={selectedOnBehalfPerson}
            setError={setError}
            setFieldValues={setFieldValues}
            setOnBehalfEnabled={setOnBehalfEnabled}
            setOnBehalfQuery={setOnBehalfQuery}
            setOnBehalfReason={setOnBehalfReason}
            setSelectedCategoryKey={selectCategoryKey}
            setSelectedOnBehalfPerson={setSelectedOnBehalfPerson}
            setShowAllCategoryOptions={setShowAllCategoryOptions}
            validationAttempted={validationAttempted}
            valueValidation={valueValidation}
          />
        ) : null}
        {step === "review" ? (
          <ReviewStepPanel
            canCreate={canCreate}
            createTicket={createTicket}
            primaryDevice={primaryDevice}
            previewResult={previewResult}
            previewSubmitting={previewSubmitting}
            requestDescription={requestDescription}
            requestTitle={requestTitle}
            runPreview={runPreview}
            selectedForm={selectedForm}
            selectedOffering={selectedOffering}
            submitting={submitting}
          />
        ) : null}
      </RequestWizardShell>
      <RequestSummaryAside
        bootstrap={bootstrap}
        primaryDevice={primaryDevice}
        selectedCategory={selectedCategory}
        selectedService={selectedService}
      />
    </div>
  );
}
