import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import {
  fetchAdminFormsCatalog,
  fetchHelpdeskModelRegistry,
  saveAdminFormsDraft,
} from "../../features/forms-builder/api";
import {
  fetchPolicyHealthDashboard,
  simulatePolicyHealth,
} from "../../features/policy-health/api";
import { buildStudioSimulationPayload, defaultGuidedSimulationDraft, type GuidedSimulationDraft } from "../../features/request-template-studio/options";
import { BlockInspector } from "../../features/request-template-studio/block-inspector";
import { CreateRequestWizard } from "../../features/request-template-studio/create-request-wizard";
import {
  buildFormsDraftPayload,
  buildInitialStudioDraft,
  buildOfferingDraftPayload,
  type StudioDraft,
} from "../../features/request-template-studio/draft-model";
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
  findDefaultStudioItem,
  findStudioItem,
  getRequestStudioModeLabel,
  type ProcessBlockKey,
  type RequestStudioMode,
} from "../../features/request-template-studio/studio-model";
import { fetchServiceCatalogDashboard, saveOfferingDraft } from "../../features/service-catalog/api";

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
  const [saveStatus, setSaveStatus] = useState<"saved" | "dirty" | "draft_saved" | "validation_required">("saved");
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
  const links = {
    forms: buildDeepLink("/app/admin/forms", selectedItem),
    serviceCatalog: buildDeepLink("/app/admin/service-catalog", selectedItem),
    policyHealth: buildDeepLink("/app/admin/policy-health", selectedItem),
  };
  const selectedBlock = selectedItem?.processBlocks.find((block) => block.key === selectedBlockKey) ?? selectedItem?.processBlocks[0] ?? null;
  const draftSnapshot = studioDraft ? JSON.stringify(studioDraft) : "";
  const hasUnsavedChanges = Boolean(studioDraft && draftSnapshot !== savedDraftSnapshot);
  const studioSimulationPayload = buildStudioSimulationPayload({
    selectedTemplateCode: studioDraft?.templateCode || selectedTemplateCode,
    selectedService: selectedItem?.service ?? null,
    selectedOffering: selectedItem?.offering ?? null,
    simulationDraft,
  });

  const simulationMutation = useMutation({
    mutationFn: () => {
      if (!selectedTemplateCode) {
        throw new Error("Тип обращения не выбран");
      }
      return simulatePolicyHealth(studioSimulationPayload);
    },
    onSuccess: () => setSaveStatus("saved"),
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
      });
      const offeringPayload = buildOfferingDraftPayload(studioDraft, selectedItem?.offering);
      const [formsResult, offeringResult] = await Promise.all([
        saveAdminFormsDraft(formsPayload),
        saveOfferingDraft(offeringPayload),
      ]);
      return { formsResult, offeringResult };
    },
    onSuccess: async () => {
      setSavedDraftSnapshot(draftSnapshot);
      setSaveStatus("draft_saved");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["request-studio", "catalog"] }),
        queryClient.invalidateQueries({ queryKey: ["request-studio", "forms"] }),
        queryClient.invalidateQueries({ queryKey: ["request-studio", "registry"] }),
        queryClient.invalidateQueries({ queryKey: ["request-studio", "policy-health"] }),
      ]);
    },
  });
  const readiness = buildReadinessSummary(selectedItem, simulationMutation.data);

  useEffect(() => {
    const requestedTemplate = searchParams.get("template");
    const selectedTemplate = selectedItem?.template?.template_code ?? selectedItem?.offering?.request_template_key ?? "";
    const pendingCreatedTemplate = createdDraftTemplateRef.current ?? createdDraftTemplate;
    if (pendingCreatedTemplate && selectedTemplate !== pendingCreatedTemplate) {
      return;
    }
    const nextDraft = buildInitialStudioDraft(selectedItem);
    setStudioDraft(nextDraft);
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
      setSaveStatus("dirty");
    }
  }, [draftSnapshot, savedDraftSnapshot, studioDraft]);

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
    setSaveStatus("dirty");
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
      onRunValidation={() => simulationMutation.mutate()}
      publishHref={links.serviceCatalog}
      saveDraftDisabled={!studioDraft || !hasUnsavedChanges}
      saveDraftPending={saveDraftMutation.isPending}
      runValidationDisabled={!(studioDraft?.templateCode || selectedTemplateCode) || simulationMutation.isPending}
      selectedItem={selectedItem}
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
          {selectedItem ? (
            <>
              {selectedItem.isTechnical ? (
                <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                  <p className="font-semibold">Выбран тестовый или выведенный объект.</p>
                  <p className="mt-1">Для настройки рабочего обращения выберите опубликованный раздел и тип обращения.</p>
                </div>
              ) : null}

              <ProcessMap blocks={selectedItem.processBlocks} onSelectBlock={setSelectedBlockKey} selectedBlockKey={selectedBlock?.key ?? selectedBlockKey} />

              <BlockInspector block={selectedBlock} item={selectedItem} mode={mode} expertLinks={links} />

              {studioDraft ? (
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
              ) : null}

              <FormPreviewPanel item={selectedItem} mode={mode} />

              <SimulationPanel
                draft={simulationDraft}
                error={simulationMutation.error}
                item={selectedItem}
                mode={mode}
                hasUnsavedChanges={hasUnsavedChanges}
                onDraftChange={updateSimulationDraft}
                onRun={() => simulationMutation.mutate()}
                payload={studioSimulationPayload}
                pending={simulationMutation.isPending}
                result={simulationMutation.data}
              />
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

        <ReadinessPanel expertLinks={links} item={selectedItem} readiness={readiness} />
      </section>
    </RequestStudioShell>
  );
}
