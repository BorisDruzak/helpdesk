import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import {
  fetchAdminFormsCatalog,
  fetchHelpdeskModelRegistry,
  saveAdminFormsDraft,
  type AdminHelpdeskModelPayload,
} from "../../features/forms-builder/api";
import {
  fetchPolicyHealthDashboard,
  simulatePolicyHealth,
  type PolicyHealthSimulationResult,
  type PolicySimulationPayload,
} from "../../features/policy-health/api";
import { buildStudioSimulationPayload, defaultGuidedSimulationDraft, type GuidedSimulationDraft } from "../../features/request-template-studio/options";
import { BlockInspector } from "../../features/request-template-studio/block-inspector";
import { CreateRequestWizard } from "../../features/request-template-studio/create-request-wizard";
import {
  buildFormsDraftPayload,
  buildInitialStudioDraft,
  buildOfferingDraftPayload,
  buildRequestStudioPublishPayload,
  type StudioDraft,
} from "../../features/request-template-studio/draft-model";
import {
  previewRequestStudioPublish,
  publishRequestStudioDraft,
  type RequestStudioPublishPreview,
} from "../../features/request-template-studio/api";
import { FormFieldEditor } from "../../features/request-template-studio/form-field-editor";
import { FormPreviewPanel } from "../../features/request-template-studio/form-preview-panel";
import { ProcessEditors } from "../../features/request-template-studio/process-editors";
import { ProcessMap } from "../../features/request-template-studio/process-map";
import { ReadinessPanel } from "../../features/request-template-studio/readiness-panel";
import { RequestItemList } from "../../features/request-template-studio/request-item-list";
import { RequestStudioShell } from "../../features/request-template-studio/request-studio-shell";
import { buildReadinessSummary } from "../../features/request-template-studio/readiness";
import { SimulationPanel } from "../../features/request-template-studio/simulation-panel";
import {
  buildDeepLink,
  buildRequestStudioItems,
  buildWorkingRequestStudioItem,
  findDefaultStudioItem,
  findStudioItem,
  getRequestStudioModeLabel,
  type ProcessBlockKey,
  type RequestStudioItem,
  type RequestStudioMode,
} from "../../features/request-template-studio/studio-model";
import { fetchServiceCatalogDashboard, saveOfferingDraft } from "../../features/service-catalog/api";
import { Button } from "../../components/ui/button";

export function AdminRequestTemplateStudioPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const catalogQuery = useQuery({ queryKey: ["request-studio", "catalog"], queryFn: fetchServiceCatalogDashboard });
  const registryQuery = useQuery({ queryKey: ["request-studio", "registry"], queryFn: fetchHelpdeskModelRegistry });
  const healthQuery = useQuery({ queryKey: ["request-studio", "policy-health"], queryFn: fetchPolicyHealthDashboard });
  const formsQuery = useQuery({ queryKey: ["request-studio", "forms"], queryFn: fetchAdminFormsCatalog });

  const [mode, setMode] = useState<RequestStudioMode>("basic");
  const [showTechnicalItems, setShowTechnicalItems] = useState(false);
  const [selectedBlockKey, setSelectedBlockKey] = useState<ProcessBlockKey>("form");
  const [simulationDraft, setSimulationDraft] = useState<GuidedSimulationDraft>(defaultGuidedSimulationDraft);
  const [offeringResetNotice, setOfferingResetNotice] = useState(false);
  const [studioDraft, setStudioDraft] = useState<StudioDraft | null>(null);
  const [savedDraftSnapshot, setSavedDraftSnapshot] = useState<string>("");
  const [saveStatus, setSaveStatus] = useState<"saved" | "dirty" | "draft_saved" | "validation_required" | "check_complete" | "check_stale">("saved");
  const [publishPreview, setPublishPreview] = useState<RequestStudioPublishPreview | null>(null);
  const [publishSuccessMessage, setPublishSuccessMessage] = useState<string | null>(null);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardValue, setWizardValue] = useState<{
    processProfile: string;
    serviceCode: string;
    title: string;
    description: string;
    visibility: StudioDraft["visibility"];
  }>({
    processProfile: "Заявка на доступ",
    serviceCode: "",
    title: "",
    description: "",
    visibility: "public" as const,
  });
  const [selectedFieldIndex, setSelectedFieldIndex] = useState(0);
  const [showAutoFix, setShowAutoFix] = useState(false);
  const [createdDraftTemplate, setCreatedDraftTemplate] = useState<string | null>(null);
  const createdDraftTemplateRef = useRef<string | null>(null);

  const items = useMemo(
    () =>
      buildRequestStudioItems({
        services: catalogQuery.data?.services ?? [],
        offerings: catalogQuery.data?.offerings ?? [],
        registry: registryQuery.data,
        forms: formsQuery.data?.forms ?? [],
        health: healthQuery.data,
      }),
    [catalogQuery.data, formsQuery.data, healthQuery.data, registryQuery.data],
  );

  const selectedItem = useMemo(() => {
    const requestedTemplate = searchParams.get("template");
    const fromUrl = findStudioItem(items, {
      service: searchParams.get("service"),
      offering: searchParams.get("offering"),
      template: requestedTemplate,
    });
    if (createdDraftTemplate && requestedTemplate === createdDraftTemplate && fromUrl?.template?.template_code !== createdDraftTemplate) {
      return null;
    }
    return fromUrl ?? findDefaultStudioItem(items, showTechnicalItems);
  }, [createdDraftTemplate, items, searchParams, showTechnicalItems]);

  const selectedTemplateCode = selectedItem?.template?.template_code ?? searchParams.get("template") ?? "";
  const workingItem = useMemo(
    () =>
      buildWorkingRequestStudioItem({
        selectedItem,
        draft: studioDraft,
        services: catalogQuery.data?.services ?? [],
        registry: registryQuery.data,
        health: healthQuery.data,
      }),
    [catalogQuery.data?.services, healthQuery.data, registryQuery.data, selectedItem, studioDraft],
  );
  const links = {
    forms: buildDeepLink("/app/admin/forms", workingItem ?? selectedItem),
    serviceCatalog: buildDeepLink("/app/admin/service-catalog", workingItem ?? selectedItem),
    policyHealth: buildDeepLink("/app/admin/policy-health", workingItem ?? selectedItem),
  };
  const selectedBlock = workingItem?.processBlocks.find((block) => block.key === selectedBlockKey) ?? workingItem?.processBlocks[0] ?? null;
  const draftSnapshot = studioDraft ? JSON.stringify(studioDraft) : "";
  const hasUnsavedChanges = Boolean(studioDraft && draftSnapshot !== savedDraftSnapshot);
  const studioSimulationPayload = buildStudioSimulationPayload({
    selectedTemplateCode: studioDraft?.templateCode || workingItem?.template?.template_code || selectedTemplateCode,
    selectedService: workingItem?.service ?? null,
    selectedOffering: workingItem?.offering ?? null,
    simulationDraft,
  });

  const simulationMutation = useMutation({
    mutationFn: () => {
      if (hasUnsavedChanges) {
        throw new Error("Сначала сохраните черновик, затем запустите проверку.");
      }
      if (!(studioDraft?.templateCode || selectedTemplateCode)) {
        throw new Error("Тип обращения не выбран");
      }
      return simulatePolicyHealth(studioSimulationPayload);
    },
    onSuccess: () => setSaveStatus("check_complete"),
  });
  const saveDraftMutation = useMutation({
    mutationFn: async () => {
      if (!studioDraft) {
        throw new Error("Черновик не выбран.");
      }
      const formsPayload = buildFormsDraftPayload({
        draft: studioDraft,
        currentForms: formsQuery.data?.forms ?? [],
        baseVersion: formsQuery.data?.summary.version ?? null,
        registry: registryQuery.data,
      });
      const offeringPayload = buildOfferingDraftPayload(studioDraft, selectedItem?.offering, registryQuery.data);
      const results = await Promise.allSettled([
        saveAdminFormsDraft(formsPayload),
        saveOfferingDraft(offeringPayload),
      ]);
      const failed = results
        .map((result, index) => ({ result, label: index === 0 ? "форма" : "вариант услуги" }))
        .filter((entry): entry is { result: PromiseRejectedResult; label: string } => entry.result.status === "rejected");
      if (failed.length) {
        throw new Error(`Не удалось сохранить: ${failed.map((entry) => entry.label).join(", ")}.`);
      }
      const [formsResult, offeringResult] = results.map((result) => (result as PromiseFulfilledResult<unknown>).value);
      return { formsResult, offeringResult };
    },
    onSuccess: async () => {
      setSavedDraftSnapshot(draftSnapshot);
      setSaveStatus("draft_saved");
      setPublishPreview(null);
      setPublishSuccessMessage(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["request-studio", "catalog"] }),
        queryClient.invalidateQueries({ queryKey: ["request-studio", "forms"] }),
        queryClient.invalidateQueries({ queryKey: ["request-studio", "registry"] }),
        queryClient.invalidateQueries({ queryKey: ["request-studio", "policy-health"] }),
      ]);
    },
  });
  const publishPreviewMutation = useMutation({
    mutationFn: () => {
      if (!studioDraft) {
        throw new Error("Черновик не выбран.");
      }
      if (hasUnsavedChanges) {
        throw new Error("Сначала сохраните черновик, затем подготовьте публикацию.");
      }
      return previewRequestStudioPublish(
        buildRequestStudioPublishPayload({
          draft: studioDraft,
          registry: registryQuery.data,
        }),
      );
    },
    onSuccess: (preview) => {
      setPublishPreview(preview);
      setPublishSuccessMessage(null);
    },
  });
  const publishMutation = useMutation({
    mutationFn: () => {
      if (!studioDraft || !publishPreview?.confirmation_token) {
        throw new Error("Сначала подготовьте safe publish preview.");
      }
      return publishRequestStudioDraft(
        buildRequestStudioPublishPayload({
          draft: studioDraft,
          registry: registryQuery.data,
          confirmationToken: publishPreview.confirmation_token,
        }),
      );
    },
    onSuccess: async (result) => {
      setPublishPreview(null);
      setPublishSuccessMessage(result.message || "Тип обращения опубликован из Studio.");
      setSaveStatus("check_complete");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["request-studio", "catalog"] }),
        queryClient.invalidateQueries({ queryKey: ["request-studio", "forms"] }),
        queryClient.invalidateQueries({ queryKey: ["request-studio", "registry"] }),
        queryClient.invalidateQueries({ queryKey: ["request-studio", "policy-health"] }),
      ]);
    },
  });
  const readiness = buildReadinessSummary(workingItem, simulationMutation.data, {
    hasDraft: Boolean(studioDraft),
    hasUnsavedChanges,
  });

  useEffect(() => {
    const requestedTemplate = searchParams.get("template");
    const selectedTemplate = selectedItem?.template?.template_code ?? selectedItem?.offering?.request_template_key ?? "";
    const pendingCreatedTemplate = createdDraftTemplateRef.current ?? createdDraftTemplate;
    if (pendingCreatedTemplate && selectedTemplate !== pendingCreatedTemplate) {
      return;
    }
    const nextDraft = buildInitialStudioDraft(selectedItem);
    setStudioDraft(nextDraft);
    setPublishSuccessMessage(null);
    const snapshot = nextDraft ? JSON.stringify(nextDraft) : "";
    setSavedDraftSnapshot(snapshot);
    setSaveStatus("saved");
    setSelectedFieldIndex(0);
  }, [createdDraftTemplate, selectedItem?.id, searchParams]);

  useEffect(() => {
    if (!studioDraft) {
      return;
    }
    if (draftSnapshot !== savedDraftSnapshot) {
      setSaveStatus((current) => (current === "check_stale" || simulationMutation.data ? "check_stale" : "dirty"));
    }
  }, [draftSnapshot, savedDraftSnapshot, simulationMutation.data, studioDraft]);

  useEffect(() => {
    const requestedOffering = searchParams.get("offering");
    const requestedService = searchParams.get("service");
    if (!requestedOffering || !requestedService || !catalogQuery.data) {
      return;
    }
    const candidate = catalogQuery.data.offerings.find((offering) => offering.full_code === requestedOffering || offering.code === requestedOffering);
    if (!candidate || candidate.service_code === requestedService) {
      return;
    }
    const next = new URLSearchParams(searchParams);
    next.delete("offering");
    setSearchParams(next, { replace: true });
    setOfferingResetNotice(true);
  }, [catalogQuery.data, searchParams, setSearchParams]);

  function selectItem(itemId: string) {
    createdDraftTemplateRef.current = null;
    setCreatedDraftTemplate(null);
    setPublishSuccessMessage(null);
    const item = items.find((candidate) => candidate.id === itemId);
    const next = new URLSearchParams(searchParams);
    if (!item) {
      next.delete("service");
      next.delete("offering");
      next.delete("template");
      setSearchParams(next);
      return;
    }
    next.set("service", item.service.code);
    if (item.offering?.full_code) {
      next.set("offering", item.offering.full_code);
    } else {
      next.delete("offering");
    }
    if (item.template?.template_code) {
      next.set("template", item.template.template_code);
    } else {
      next.delete("template");
    }
    setSearchParams(next);
  }

  function updateSimulationDraft(key: keyof GuidedSimulationDraft, value: string) {
    setSimulationDraft((current) => ({ ...current, [key]: value }));
  }

  function updateStudioDraft(nextDraft: StudioDraft) {
    setStudioDraft(nextDraft);
    setPublishPreview(null);
    setPublishSuccessMessage(null);
    setSaveStatus(simulationMutation.data ? "check_stale" : "dirty");
  }

  function handleCreateDraft(draft: StudioDraft) {
    createdDraftTemplateRef.current = draft.templateCode;
    updateStudioDraft(draft);
    setCreatedDraftTemplate(draft.templateCode);
    const service = catalogQuery.data?.services.find((candidate) => candidate.code === draft.serviceCode);
    const next = new URLSearchParams(searchParams);
    next.set("service", draft.serviceCode);
    next.set("offering", `${draft.serviceCode}.${draft.offeringCode}`);
    next.set("template", draft.templateCode);
    setSearchParams(next);
    setWizardValue((current) => ({
      ...current,
      serviceCode: service?.code ?? draft.serviceCode,
      title: "",
      description: "",
    }));
  }

  return (
    <RequestStudioShell
      expertLinks={links}
      mode={mode}
      modeLabel={getRequestStudioModeLabel(mode)}
      draftStatus={saveStatus}
      onCreateRequest={() => setWizardOpen(true)}
      onSaveDraft={() => saveDraftMutation.mutate()}
      onModeChange={setMode}
      onPublish={() => publishPreviewMutation.mutate()}
      onRunValidation={() => simulationMutation.mutate()}
      publishDisabled={!studioDraft || hasUnsavedChanges || saveDraftMutation.isPending || publishMutation.isPending}
      publishPending={publishPreviewMutation.isPending || publishMutation.isPending}
      saveDraftDisabled={!studioDraft || !hasUnsavedChanges}
      saveDraftPending={saveDraftMutation.isPending}
      runValidationDisabled={!(studioDraft?.templateCode || selectedTemplateCode) || hasUnsavedChanges || simulationMutation.isPending || saveDraftMutation.isPending}
      selectedItem={workingItem}
    >
      <CreateRequestWizard
        open={wizardOpen}
        services={catalogQuery.data?.services ?? []}
        value={wizardValue}
        onChange={setWizardValue}
        onClose={() => setWizardOpen(false)}
        onCreateDraft={handleCreateDraft}
      />

      {saveDraftMutation.error ? (
        <div className="rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {saveDraftMutation.error instanceof Error ? saveDraftMutation.error.message : "Не удалось сохранить черновик."}
        </div>
      ) : null}

      {publishSuccessMessage ? (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
          {publishSuccessMessage}
        </div>
      ) : null}

      {publishPreviewMutation.error || publishMutation.error ? (
        <div className="rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {publishPreviewMutation.error instanceof Error
            ? publishPreviewMutation.error.message
            : publishMutation.error instanceof Error
              ? publishMutation.error.message
              : "Не удалось выполнить публикацию из Studio."}
        </div>
      ) : null}

      {publishPreview ? (
        <section className="surface-panel space-y-4 p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-950">Safe publish preview</h2>
              <p className="mt-1 text-sm text-slate-600">{publishPreview.message}</p>
            </div>
            <Button disabled={!publishPreview.validation.can_publish || publishMutation.isPending} onClick={() => publishMutation.mutate()} type="button" variant="primary">
              {publishMutation.isPending ? "Публикуем..." : "Подтвердить публикацию"}
            </Button>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            {publishPreview.steps.map((step) => (
              <div className="rounded-md border border-slate-200 bg-white p-3" key={step.key}>
                <p className="text-sm font-semibold text-slate-900">{step.label}</p>
                <p className="mt-1 text-xs font-semibold text-brand-800">{step.status === "blocked" ? "Заблокировано" : "Будет опубликовано"}</p>
                {step.details ? <p className="mt-2 text-sm text-slate-600">{step.details}</p> : null}
              </div>
            ))}
          </div>
          {publishPreview.validation.issues.length ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
              <p className="text-sm font-semibold text-amber-900">Что нужно проверить</p>
              <ul className="mt-2 space-y-1 text-sm text-amber-900">
                {publishPreview.validation.issues.map((issue) => (
                  <li key={`${issue.code}-${issue.path ?? ""}`}>{issue.message}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>
      ) : null}

      {offeringResetNotice ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Вариант услуги не относится к выбранному разделу и был сброшен.
        </div>
      ) : null}

      <section className="grid gap-5 2xl:grid-cols-[320px_minmax(0,1fr)_370px]">
        <RequestItemList
          items={items}
          onSelectItem={selectItem}
          onToggleTechnicalItems={setShowTechnicalItems}
          selectedItemId={selectedItem?.id ?? null}
          showTechnicalItems={showTechnicalItems}
        />

        <main className="space-y-5">
          {workingItem ? (
            <>
              {workingItem.isTechnical ? (
                <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                  <p className="font-semibold">Выбран тестовый или выведенный объект.</p>
                  <p className="mt-1">Для настройки рабочего обращения выберите опубликованный раздел и тип обращения.</p>
                </div>
              ) : null}

              <ProcessMap blocks={workingItem.processBlocks} onSelectBlock={setSelectedBlockKey} selectedBlockKey={selectedBlock?.key ?? selectedBlockKey} />

              <BlockInspector block={selectedBlock} item={workingItem} mode={mode} expertLinks={links} />

              {studioDraft ? (
                <SelectedBlockEditor
                  blockKey={selectedBlock?.key ?? selectedBlockKey}
                  draft={studioDraft}
                  hasUnsavedChanges={hasUnsavedChanges}
                item={workingItem}
                mode={mode}
                registry={registryQuery.data}
                readiness={readiness}
                selectedFieldIndex={selectedFieldIndex}
                showAutoFix={showAutoFix}
                simulationDraft={simulationDraft}
                  simulationError={simulationMutation.error}
                  simulationPayload={studioSimulationPayload}
                  simulationPending={simulationMutation.isPending}
                  simulationResult={simulationMutation.data}
                  onDraftChange={updateStudioDraft}
                  onRunSimulation={() => simulationMutation.mutate()}
                  onSelectFieldIndex={setSelectedFieldIndex}
                  onShowAutoFixChange={setShowAutoFix}
                  onSimulationDraftChange={updateSimulationDraft}
                />
              ) : null}

              <details className="surface-panel p-5">
                <summary className="cursor-pointer text-sm font-semibold text-slate-800">Preview пользователя и исполнителя</summary>
                <div className="mt-4">
                  <FormPreviewPanel item={workingItem} mode={mode} embedded />
                </div>
              </details>
            </>
          ) : studioDraft ? (
            <>
              <FormFieldEditor
                draft={studioDraft}
                selectedIndex={selectedFieldIndex}
                onSelectIndex={setSelectedFieldIndex}
                onChange={updateStudioDraft}
              />
              <ProcessEditors
                draft={studioDraft}
                registry={registryQuery.data}
                showAutoFix={showAutoFix}
                onDraftChange={updateStudioDraft}
                onShowAutoFixChange={setShowAutoFix}
              />
            </>
          ) : (
            <section className="surface-panel p-6">
              <h2 className="text-lg font-semibold text-slate-950">Выберите тип обращения</h2>
              <p className="mt-2 text-sm text-slate-600">
                Опубликованные рабочие типы обращений не найдены. Включите показ тестовых и выведенных объектов или откройте экспертный каталог услуг.
              </p>
            </section>
          )}
        </main>

        <ReadinessPanel
          expertLinks={links}
          item={workingItem}
          readiness={readiness}
          onAutoFix={() => {
            setShowAutoFix(true);
            setSelectedBlockKey("processing");
          }}
        />
      </section>
    </RequestStudioShell>
  );
}

function SelectedBlockEditor({
  blockKey,
  draft,
  hasUnsavedChanges,
  item,
  mode,
  readiness,
  registry,
  selectedFieldIndex,
  showAutoFix,
  simulationDraft,
  simulationError,
  simulationPayload,
  simulationPending,
  simulationResult,
  onDraftChange,
  onRunSimulation,
  onSelectFieldIndex,
  onShowAutoFixChange,
  onSimulationDraftChange,
}: {
  blockKey: ProcessBlockKey;
  draft: StudioDraft;
  hasUnsavedChanges: boolean;
  item: RequestStudioItem;
  mode: RequestStudioMode;
  readiness: ReturnType<typeof buildReadinessSummary>;
  registry: AdminHelpdeskModelPayload | undefined;
  selectedFieldIndex: number;
  showAutoFix: boolean;
  simulationDraft: GuidedSimulationDraft;
  simulationError: unknown;
  simulationPayload: PolicySimulationPayload;
  simulationPending: boolean;
  simulationResult: PolicyHealthSimulationResult | undefined;
  onDraftChange: (draft: StudioDraft) => void;
  onRunSimulation: () => void;
  onSelectFieldIndex: (index: number) => void;
  onShowAutoFixChange: (value: boolean) => void;
  onSimulationDraftChange: (key: keyof GuidedSimulationDraft, value: string) => void;
}) {
  if (blockKey === "form") {
    return <FormFieldEditor draft={draft} selectedIndex={selectedFieldIndex} onSelectIndex={onSelectFieldIndex} onChange={onDraftChange} />;
  }

  if (blockKey === "validation") {
    return (
      <SimulationPanel
        draft={simulationDraft}
        error={simulationError}
        item={item}
        mode={mode}
        hasUnsavedChanges={hasUnsavedChanges}
        onDraftChange={onSimulationDraftChange}
        onRun={onRunSimulation}
        payload={simulationPayload}
        pending={simulationPending}
        result={simulationResult}
      />
    );
  }

  if (blockKey === "publication") {
    return (
      <section className="surface-panel space-y-4 p-5">
        <h2 className="text-lg font-semibold text-slate-950">Публикация</h2>
        <p className="text-sm text-slate-600">
          Черновик публикуется из Studio через safe publish preview: сначала backend проверяет форму, route, SLA, закрытие, видимость и каталог, затем требует подтверждение того же draft.
        </p>
        <div className="grid gap-3 md:grid-cols-2">
          <PublicationList title="Уже готово" items={readiness.ready} empty="Готовые блоки появятся после сохранения и проверки черновика." />
          <PublicationList title="Блокирует публикацию" items={readiness.blockers} empty="Базовые блокеры не найдены." />
        </div>
        <div className="rounded-md border border-brand-200 bg-brand-50 px-3 py-2 text-sm text-brand-900">
          Используйте кнопку "Опубликовать из Studio" вверху экрана. Если draft изменён, сначала сохраните черновик.
        </div>
      </section>
    );
  }

  return (
    <ProcessEditors
      draft={draft}
      focusedBlockKey={blockKey === "execution" ? "processing" : blockKey}
      mode={mode}
      registry={registry}
      showAutoFix={showAutoFix}
      onDraftChange={onDraftChange}
      onShowAutoFixChange={onShowAutoFixChange}
    />
  );
}

function PublicationList({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-3">
      <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      {items.length ? (
        <ul className="mt-2 space-y-1 text-sm text-slate-600">
          {items.slice(0, 5).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-slate-500">{empty}</p>
      )}
    </div>
  );
}
