import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import {
  fetchAdminFormsCatalog,
  fetchHelpdeskModelRegistry,
} from "../../features/forms-builder/api";
import {
  fetchPolicyHealthDashboard,
  simulatePolicyHealth,
} from "../../features/policy-health/api";
import { buildStudioSimulationPayload, defaultGuidedSimulationDraft, type GuidedSimulationDraft } from "../../features/request-template-studio/options";
import { BlockInspector } from "../../features/request-template-studio/block-inspector";
import { FormPreviewPanel } from "../../features/request-template-studio/form-preview-panel";
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
import { fetchServiceCatalogDashboard } from "../../features/service-catalog/api";

export function AdminRequestTemplateStudioPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const catalogQuery = useQuery({ queryKey: ["request-studio", "catalog"], queryFn: fetchServiceCatalogDashboard });
  const registryQuery = useQuery({ queryKey: ["request-studio", "registry"], queryFn: fetchHelpdeskModelRegistry });
  const healthQuery = useQuery({ queryKey: ["request-studio", "policy-health"], queryFn: fetchPolicyHealthDashboard });
  const formsQuery = useQuery({ queryKey: ["request-studio", "forms"], queryFn: fetchAdminFormsCatalog });

  const [mode, setMode] = useState<RequestStudioMode>("basic");
  const [showTechnicalItems, setShowTechnicalItems] = useState(false);
  const [selectedBlockKey, setSelectedBlockKey] = useState<ProcessBlockKey>("form");
  const [simulationDraft, setSimulationDraft] = useState<GuidedSimulationDraft>(defaultGuidedSimulationDraft);
  const [offeringResetNotice, setOfferingResetNotice] = useState(false);

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
    const fromUrl = findStudioItem(items, {
      service: searchParams.get("service"),
      offering: searchParams.get("offering"),
      template: searchParams.get("template"),
    });
    return fromUrl ?? findDefaultStudioItem(items, showTechnicalItems);
  }, [items, searchParams, showTechnicalItems]);

  const selectedTemplateCode = selectedItem?.template?.template_code ?? searchParams.get("template") ?? "";
  const links = {
    forms: buildDeepLink("/app/admin/forms", selectedItem),
    serviceCatalog: buildDeepLink("/app/admin/service-catalog", selectedItem),
    policyHealth: buildDeepLink("/app/admin/policy-health", selectedItem),
  };
  const selectedBlock = selectedItem?.processBlocks.find((block) => block.key === selectedBlockKey) ?? selectedItem?.processBlocks[0] ?? null;
  const studioSimulationPayload = buildStudioSimulationPayload({
    selectedTemplateCode,
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
  });
  const readiness = buildReadinessSummary(selectedItem, simulationMutation.data);

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

  return (
    <RequestStudioShell
      expertLinks={links}
      mode={mode}
      modeLabel={getRequestStudioModeLabel(mode)}
      onModeChange={setMode}
      onRunValidation={() => simulationMutation.mutate()}
      publishHref={links.serviceCatalog}
      runValidationDisabled={!selectedTemplateCode || simulationMutation.isPending}
      selectedItem={selectedItem}
    >
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

              <FormPreviewPanel item={selectedItem} mode={mode} />

              <SimulationPanel
                draft={simulationDraft}
                error={simulationMutation.error}
                item={selectedItem}
                onDraftChange={updateSimulationDraft}
                onRun={() => simulationMutation.mutate()}
                payload={studioSimulationPayload}
                pending={simulationMutation.isPending}
                result={simulationMutation.data}
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
