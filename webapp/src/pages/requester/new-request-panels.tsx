import { Send } from "lucide-react";
import type { Dispatch, MutableRefObject, ReactNode, SetStateAction } from "react";

import {
  RequestFormFieldControl,
  type DynamicFormValidationResult,
  type DynamicFormValues,
} from "../../features/requester/dynamic-form";
import { requesterDeviceLabel } from "../../features/requester/labels";
import { Button, InlineAlert } from "../../features/requester/ui/form-controls";
import type {
  RequestFormDefinition,
  RequesterDevice,
  RequesterOnBehalfPerson,
  ServiceCatalogSafePreview,
} from "../../features/requester/types";
import {
  CategorySelector,
  OnBehalfPanel,
  primaryDeviceResolutionText,
  type CategoryOption,
} from "./new-request-workflow";

export function DetailsStepPanel({
  categoryOptions,
  categoryError,
  categoryInputRef,
  categorySelectorOptions,
  createTicket,
  contextualFields,
  fieldRefs,
  fieldServerErrors,
  fieldValues,
  missingFieldDetails,
  missingFields,
  onBehalfAffectedPersonError,
  onBehalfActive,
  onBehalfMissingRequired,
  onBehalfPeople,
  onBehalfPolicy,
  onBehalfQuery,
  onBehalfReason,
  onBehalfReasonError,
  previewResult,
  previewSubmitting,
  recommendedCategoryKey,
  requiresOnBehalfForAvailability,
  runOnBehalfSearch,
  selectedCategoryKey,
  selectedForm,
  selectedOnBehalfPerson,
  clearFieldServerError,
  setError,
  setFieldValues,
  setOnBehalfEnabled,
  setOnBehalfQuery,
  setOnBehalfReason,
  setSelectedCategoryKey,
  setSelectedOnBehalfPerson,
  setShowAllCategoryOptions,
  submitting,
  validationAttempted,
  valueValidation,
}: {
  categoryOptions: CategoryOption[];
  categoryError?: string | null;
  categoryInputRef?: (element: HTMLSelectElement | null) => void;
  categorySelectorOptions: CategoryOption[];
  createTicket: () => void;
  contextualFields: RequestFormDefinition["fields"];
  fieldRefs: MutableRefObject<Record<string, HTMLElement | null>>;
  fieldServerErrors: Record<string, string>;
  fieldValues: DynamicFormValues;
  missingFieldDetails: Array<{ key: string; label: string }>;
  missingFields: string[];
  onBehalfAffectedPersonError?: string | null;
  onBehalfActive: boolean;
  onBehalfMissingRequired: boolean;
  onBehalfPeople: RequesterOnBehalfPerson[];
  onBehalfPolicy: RequestFormDefinition["on_behalf_policy"] | null;
  onBehalfQuery: string;
  onBehalfReason: string;
  onBehalfReasonError?: string | null;
  previewResult: ServiceCatalogSafePreview | null;
  previewSubmitting: boolean;
  recommendedCategoryKey: string | null;
  requiresOnBehalfForAvailability: boolean;
  runOnBehalfSearch: () => void;
  selectedCategoryKey: string;
  selectedForm: RequestFormDefinition | null;
  selectedOnBehalfPerson: RequesterOnBehalfPerson | null;
  clearFieldServerError: (fieldKey: string) => void;
  setError: (value: string | null) => void;
  setFieldValues: Dispatch<SetStateAction<DynamicFormValues>>;
  setOnBehalfEnabled: (value: boolean) => void;
  setOnBehalfQuery: (value: string) => void;
  setOnBehalfReason: (value: string) => void;
  setSelectedCategoryKey: (value: string) => void;
  setSelectedOnBehalfPerson: (value: RequesterOnBehalfPerson) => void;
  setShowAllCategoryOptions: (value: boolean) => void;
  submitting: boolean;
  validationAttempted: boolean;
  valueValidation: DynamicFormValidationResult;
}) {
  const previewBlockers = previewResult?.blockers ?? [];
  return (
    <section className="rounded-panel border border-slate-200 bg-white p-4">
      <CategorySelector
        canShowAll={categorySelectorOptions.length < categoryOptions.length}
        error={categoryError}
        inputRef={categoryInputRef}
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
          affectedPersonError={onBehalfAffectedPersonError}
          enabled={onBehalfActive}
          onQueryChange={setOnBehalfQuery}
          onReasonChange={setOnBehalfReason}
          onSearch={runOnBehalfSearch}
          onSelect={setSelectedOnBehalfPerson}
          people={onBehalfPeople}
          policy={onBehalfPolicy}
          query={onBehalfQuery}
          reason={onBehalfReason}
          reasonError={onBehalfReasonError}
          required={requiresOnBehalfForAvailability}
          selectedPerson={selectedOnBehalfPerson}
          setEnabled={setOnBehalfEnabled}
        />
      ) : null}
      <div className="mt-4 grid gap-3">
        {contextualFields.map((field) => (
          <RequestFormFieldControl
            error={
              fieldServerErrors[field.key] ??
              (validationAttempted
                ? missingFieldDetails.some((item) => item.key === field.key)
                  ? `Заполните поле: ${field.label}.`
                  : valueValidation.issues.find((item) => item.path === `fields.${field.key}`)?.message ?? null
                : null)
            }
            field={field}
            inputRef={(element) => {
              fieldRefs.current[field.key] = element;
            }}
            key={field.key}
            onChange={(value) => {
              setFieldValues((current) => ({ ...current, [field.key]: value }));
              clearFieldServerError(field.key);
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
      {previewBlockers.length ? (
        <InlineAlert className="mt-3" title="Нельзя создать обращение" tone="danger">
          <ul className="list-disc space-y-1 pl-5">
            {previewBlockers.map((blocker) => (
              <li key={blocker}>{blocker}</li>
            ))}
          </ul>
        </InlineAlert>
      ) : null}
      <Button
        className="mt-4"
        disabled={previewSubmitting || submitting}
        leadingIcon={<Send className="h-4 w-4" />}
        onClick={createTicket}
        type="button"
      >
        {previewSubmitting ? "Проверяем..." : submitting ? "Создаем..." : "Создать обращение"}
      </Button>
    </section>
  );
}

export function RequestWizardShell({
  children,
  draftStatusLabel,
  error,
}: {
  children: ReactNode;
  draftStatusLabel?: string;
  error: string | null;
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
        <h1 className="mt-1 text-2xl font-semibold text-slate-950">Категория и форма</h1>
      </div>
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
