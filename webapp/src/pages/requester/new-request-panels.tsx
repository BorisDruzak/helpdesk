import { CheckCircle2, Send } from "lucide-react";
import type { Dispatch, MutableRefObject, ReactNode, SetStateAction } from "react";

import {
  RequestFormFieldControl,
  type DynamicFormValidationResult,
  type DynamicFormValues,
} from "../../features/requester/dynamic-form";
import { requesterDeviceLabel } from "../../features/requester/labels";
import { Button, FormActions, InlineAlert } from "../../features/requester/ui/form-controls";
import type {
  RequestFormDefinition,
  RequesterDevice,
  RequesterOnBehalfPerson,
  ServiceCatalogSafePreview,
} from "../../features/requester/types";
import {
  CategorySelector,
  OnBehalfPanel,
  StepRail,
  primaryDeviceResolutionText,
  stepTitle,
  type CategoryOption,
  type WizardStep,
} from "./new-request-workflow";

export function DetailsStepPanel({
  categoryOptions,
  categorySelectorOptions,
  contextualFields,
  fieldRefs,
  fieldValues,
  goToReview,
  missingFieldDetails,
  missingFields,
  onBehalfActive,
  onBehalfMissingRequired,
  onBehalfPeople,
  onBehalfPolicy,
  onBehalfQuery,
  onBehalfReason,
  recommendedCategoryKey,
  requiresOnBehalfForAvailability,
  runOnBehalfSearch,
  selectedCategoryKey,
  selectedForm,
  selectedOnBehalfPerson,
  setError,
  setFieldValues,
  setOnBehalfEnabled,
  setOnBehalfQuery,
  setOnBehalfReason,
  setSelectedCategoryKey,
  setSelectedOnBehalfPerson,
  setShowAllCategoryOptions,
  validationAttempted,
  valueValidation,
}: {
  categoryOptions: CategoryOption[];
  categorySelectorOptions: CategoryOption[];
  contextualFields: RequestFormDefinition["fields"];
  fieldRefs: MutableRefObject<Record<string, HTMLElement | null>>;
  fieldValues: DynamicFormValues;
  goToReview: () => void;
  missingFieldDetails: Array<{ key: string; label: string }>;
  missingFields: string[];
  onBehalfActive: boolean;
  onBehalfMissingRequired: boolean;
  onBehalfPeople: RequesterOnBehalfPerson[];
  onBehalfPolicy: RequestFormDefinition["on_behalf_policy"] | null;
  onBehalfQuery: string;
  onBehalfReason: string;
  recommendedCategoryKey: string | null;
  requiresOnBehalfForAvailability: boolean;
  runOnBehalfSearch: () => void;
  selectedCategoryKey: string;
  selectedForm: RequestFormDefinition | null;
  selectedOnBehalfPerson: RequesterOnBehalfPerson | null;
  setError: (value: string | null) => void;
  setFieldValues: Dispatch<SetStateAction<DynamicFormValues>>;
  setOnBehalfEnabled: (value: boolean) => void;
  setOnBehalfQuery: (value: string) => void;
  setOnBehalfReason: (value: string) => void;
  setSelectedCategoryKey: (value: string) => void;
  setSelectedOnBehalfPerson: (value: RequesterOnBehalfPerson) => void;
  setShowAllCategoryOptions: (value: boolean) => void;
  validationAttempted: boolean;
  valueValidation: DynamicFormValidationResult;
}) {
  return (
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
      {validationAttempted && selectedForm && (missingFields.length || valueValidation.issues.length || onBehalfMissingRequired) ? (
        <p aria-live="polite" className="mt-3 text-sm text-rose-700" role="status">
          {valueValidation.issues[0]?.message ||
            `Заполните: ${[...missingFields, onBehalfMissingRequired ? "данные сотрудника" : ""].filter(Boolean).join(", ")}.`}
        </p>
      ) : null}
      <Button
        className="mt-4"
        disabled={!selectedForm}
        leadingIcon={<CheckCircle2 className="h-4 w-4" />}
        onClick={goToReview}
        type="button"
      >
        К проверке
      </Button>
    </section>
  );
}

export function ReviewStepPanel({
  canCreate,
  createTicket,
  primaryDevice,
  previewResult,
  previewSubmitting,
  runPreview,
  requestDescription,
  requestTitle,
  selectedForm,
  selectedOffering,
  submitting,
}: {
  canCreate: boolean;
  createTicket: () => void;
  primaryDevice: RequesterDevice | null;
  previewResult: ServiceCatalogSafePreview | null;
  previewSubmitting: boolean;
  requestDescription: string;
  requestTitle: string;
  runPreview: () => void;
  selectedForm: RequestFormDefinition | null;
  selectedOffering: CategoryOption["offering"];
  submitting: boolean;
}) {
  return (
    <section className="rounded-panel border border-slate-200 bg-white p-4">
      <h2 className="text-lg font-semibold text-slate-950">Проверка перед отправкой</h2>
      <dl className="mt-3 grid gap-2 text-sm">
        <div>
          <dt className="font-semibold text-slate-500">Тема</dt>
          <dd>{requestTitle}</dd>
        </div>
        {requestDescription && requestDescription !== requestTitle ? (
          <div>
            <dt className="font-semibold text-slate-500">Описание</dt>
            <dd>{requestDescription}</dd>
          </div>
        ) : null}
        <div>
          <dt className="font-semibold text-slate-500">Тип</dt>
          <dd>{selectedOffering?.title || selectedForm?.title}</dd>
        </div>
        {primaryDevice ? (
          <div>
            <dt className="font-semibold text-slate-500">Устройство</dt>
            <dd>{requesterDeviceLabel(primaryDevice, "Основное устройство")}</dd>
          </div>
        ) : null}
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
  );
}

export function RequestWizardShell({
  canSelectStep,
  children,
  draftStatusLabel,
  error,
  onStepSelect,
  step,
}: {
  canSelectStep?: (step: WizardStep) => boolean;
  children: ReactNode;
  draftStatusLabel?: string;
  error: string | null;
  onStepSelect?: (step: WizardStep) => void;
  step: WizardStep;
}) {
  return (
    <section className="space-y-4">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-semibold text-brand-700">Новое обращение</p>
          {draftStatusLabel ? (
            <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-800">
              {draftStatusLabel}
            </span>
          ) : null}
        </div>
        <h1 className="mt-1 text-2xl font-semibold text-slate-950">{stepTitle(step)}</h1>
      </div>
      <StepRail canSelectStep={canSelectStep} onStepSelect={onStepSelect} step={step} />
      {error ? <InlineAlert aria-live="assertive" role="alert" tone="danger">{error}</InlineAlert> : null}
      {children}
    </section>
  );
}

export function RequestSummaryAside({
  bootstrap,
  primaryDevice,
  selectedCategory,
  selectedService,
}: {
  bootstrap: { profile?: { display_name?: string | null; full_name?: string | null } | null; primary_device_resolution?: unknown } | null;
  primaryDevice: RequesterDevice | null;
  selectedCategory: CategoryOption | null;
  selectedService: CategoryOption["service"];
}) {
  return (
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
  );
}
