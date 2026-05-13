import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Layers3, Plus, RefreshCw, ShieldAlert, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Button } from "../../components/ui/button";
import { PageHeading } from "../../components/ui/page-heading";
import { SearchField } from "../../components/ui/search-field";
import { Select } from "../../components/ui/select";
import { StatTile } from "../../components/ui/stat-tile";
import { Tabs } from "../../components/ui/tabs";
import { listAdminCapabilities, listAdminCapabilityProviderConfigs } from "./api";
import { CapabilityCatalogTable } from "./capability-catalog-table";
import { CapabilityCreateModal } from "./capability-create-modal";
import { CapabilityDetailDrawer } from "./capability-detail-drawer";
import { CapabilityProviderCards } from "./capability-provider-cards";
import { EvidenceMappingPanel } from "./evidence-mapping-panel";
import { ReadinessLabPanel } from "./readiness-lab-panel";
import { SdkModulesTab } from "./sdk-modules-tab";
import type { CapabilityDescriptor, DiagnosticProviderConfig, ProviderSummary } from "./types";

type CapabilityStudioTab = "catalog" | "providers" | "evidence" | "readiness" | "sdk";

const TABS = [
  { value: "catalog", label: "Каталог" },
  { value: "providers", label: "Providers" },
  { value: "evidence", label: "Evidence Mapping" },
  { value: "readiness", label: "Readiness Lab" },
  { value: "sdk", label: "SDK Modules" },
];

const TAB_VALUES = new Set(TABS.map((tab) => tab.value));

function normalizeTab(value: string | null): CapabilityStudioTab {
  return TAB_VALUES.has(value ?? "") ? (value as CapabilityStudioTab) : "catalog";
}

function distinct(values: Array<string | null | undefined>): string[] {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value)))).sort((a, b) =>
    a.localeCompare(b),
  );
}

function providerSummaries(
  capabilities: CapabilityDescriptor[],
  configs: DiagnosticProviderConfig[],
): ProviderSummary[] {
  const configsByProvider = new Map(configs.map((config) => [config.provider_id, config]));
  const summaries = new Map<string, ProviderSummary>();

  for (const capability of capabilities) {
    const providerId = capability.provider_id ?? "unknown";
    const current = summaries.get(providerId) ?? {
      provider_id: providerId,
      provider_type: capability.provider_type ?? capability.execution_target ?? "unknown",
      execution_targets: [],
      capability_count: 0,
      evidence_count: 0,
      high_risk_count: 0,
      integration_key: capability.integration_key,
      config: configsByProvider.get(providerId) ?? null,
    };
    current.capability_count += 1;
    if (!current.execution_targets.includes(capability.execution_target)) {
      current.execution_targets.push(capability.execution_target);
    }
    if (capability.evidence?.produces_evidence) {
      current.evidence_count += 1;
    }
    if (["high", "critical", "dangerous"].includes(capability.risk_level ?? "")) {
      current.high_risk_count += 1;
    }
    if (!current.integration_key && capability.integration_key) {
      current.integration_key = capability.integration_key;
    }
    summaries.set(providerId, current);
  }

  for (const config of configs) {
    if (!summaries.has(config.provider_id)) {
      summaries.set(config.provider_id, {
        provider_id: config.provider_id,
        provider_type: config.provider_type,
        execution_targets: [config.provider_type],
        capability_count: 0,
        evidence_count: 0,
        high_risk_count: 0,
        integration_key: config.integration_key,
        config,
      });
    }
  }

  return Array.from(summaries.values()).sort((a, b) => a.provider_id.localeCompare(b.provider_id));
}

function filterCapabilities(
  capabilities: CapabilityDescriptor[],
  filters: {
    domain: string;
    evidence: string;
    perspective: string;
    provider: string;
    query: string;
    readiness: string;
    risk: string;
    target: string;
  },
): CapabilityDescriptor[] {
  const query = filters.query.trim().toLowerCase();
  return capabilities.filter((capability) => {
    if (filters.target && capability.execution_target !== filters.target) {
      return false;
    }
    if (filters.provider && capability.provider_id !== filters.provider) {
      return false;
    }
    if (filters.domain && capability.evidence?.domain !== filters.domain) {
      return false;
    }
    if (filters.perspective && capability.evidence?.perspective !== filters.perspective) {
      return false;
    }
    if (filters.risk && capability.risk_level !== filters.risk) {
      return false;
    }
    if (filters.readiness && capability.readiness !== filters.readiness) {
      return false;
    }
    if (filters.evidence === "yes" && !capability.evidence?.produces_evidence) {
      return false;
    }
    if (filters.evidence === "no" && capability.evidence?.produces_evidence) {
      return false;
    }
    if (!query) {
      return true;
    }
    return [
      capability.id,
      capability.title,
      capability.description ?? "",
      capability.provider_id ?? "",
      capability.provider_type ?? "",
      capability.execution_target,
      capability.evidence?.kind ?? "",
      capability.evidence?.domain ?? "",
      capability.evidence?.perspective ?? "",
    ]
      .join(" ")
      .toLowerCase()
      .includes(query);
  });
}

export function CapabilityStudioPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState<CapabilityStudioTab>(() => normalizeTab(searchParams.get("tab")));
  const [selectedCapability, setSelectedCapability] = useState<CapabilityDescriptor | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [targetFilter, setTargetFilter] = useState("");
  const [providerFilter, setProviderFilter] = useState("");
  const [domainFilter, setDomainFilter] = useState("");
  const [perspectiveFilter, setPerspectiveFilter] = useState("");
  const [riskFilter, setRiskFilter] = useState("");
  const [readinessFilter, setReadinessFilter] = useState("");
  const [evidenceFilter, setEvidenceFilter] = useState("");

  const capabilitiesQuery = useQuery({
    queryKey: ["admin-capabilities"],
    queryFn: listAdminCapabilities,
    retry: false,
  });
  const providerConfigsQuery = useQuery({
    queryKey: ["admin-capability-provider-configs"],
    queryFn: listAdminCapabilityProviderConfigs,
    retry: false,
  });

  useEffect(() => {
    const nextTab = normalizeTab(searchParams.get("tab"));
    setActiveTab((current) => (current === nextTab ? current : nextTab));
  }, [searchParams]);

  const capabilities = capabilitiesQuery.data ?? [];
  const providerConfigs = providerConfigsQuery.data ?? [];
  const filteredCapabilities = useMemo(
    () =>
      filterCapabilities(capabilities, {
        domain: domainFilter,
        evidence: evidenceFilter,
        perspective: perspectiveFilter,
        provider: providerFilter,
        query,
        readiness: readinessFilter,
        risk: riskFilter,
        target: targetFilter,
      }),
    [capabilities, domainFilter, evidenceFilter, perspectiveFilter, providerFilter, query, readinessFilter, riskFilter, targetFilter],
  );
  const providers = useMemo(() => providerSummaries(capabilities, providerConfigs), [capabilities, providerConfigs]);
  const stats = useMemo(
    () => ({
      total: capabilities.length,
      agent: capabilities.filter((capability) => capability.execution_target.startsWith("agent_")).length,
      server: capabilities.filter((capability) => capability.execution_target.startsWith("server_")).length,
      connectors: capabilities.filter((capability) => capability.execution_target === "server_connector").length,
      evidence: capabilities.filter((capability) => capability.evidence?.produces_evidence).length,
      highRisk: capabilities.filter((capability) => ["high", "critical", "dangerous"].includes(capability.risk_level ?? "")).length,
    }),
    [capabilities],
  );

  const targetOptions = distinct(capabilities.map((capability) => capability.execution_target));
  const providerOptions = distinct(capabilities.map((capability) => capability.provider_id));
  const domainOptions = distinct(capabilities.map((capability) => capability.evidence?.domain));
  const perspectiveOptions = distinct(capabilities.map((capability) => capability.evidence?.perspective));
  const riskOptions = distinct(capabilities.map((capability) => capability.risk_level));
  const readinessOptions = distinct(capabilities.map((capability) => capability.readiness));

  function setTab(value: string) {
    const nextTab = normalizeTab(value);
    setActiveTab(nextTab);
    setSearchParams(nextTab === "catalog" ? {} : { tab: nextTab });
  }

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ["admin-capabilities"] });
    void queryClient.invalidateQueries({ queryKey: ["admin-capability-provider-configs"] });
  }

  return (
    <section className="space-y-6">
      <PageHeading
        actions={
          <>
            <Button leadingIcon={<Plus className="h-4 w-4" />} onClick={() => setCreateOpen(true)}>
              Создать capability
            </Button>
            <Button
              leadingIcon={<RefreshCw className="h-4 w-4" />}
              onClick={refresh}
              variant="outline"
            >
              Обновить
            </Button>
            <a href="/app/admin/modules">
              <Button variant="ghost">Документация</Button>
            </a>
          </>
        }
        description="Единый каталог диагностических возможностей, модулей агента, серверных проверок и внешних API."
        eyebrow="Возможности"
        title="Capabilities"
      />

      {capabilitiesQuery.isError ? (
        <p className="rounded-[0.9rem] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {capabilitiesQuery.error instanceof Error ? capabilitiesQuery.error.message : "Не удалось загрузить capabilities."}
        </p>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
        <StatTile accent={<Layers3 className="h-5 w-5 text-brand-700" />} label="Всего capabilities" value={String(stats.total)} />
        <StatTile label="Agent capabilities" value={String(stats.agent)} />
        <StatTile label="Server capabilities" value={String(stats.server)} />
        <StatTile label="Connectors" value={String(stats.connectors)} />
        <StatTile label="Produces evidence" value={String(stats.evidence)} />
        <StatTile accent={<ShieldAlert className="h-5 w-5 text-rose-600" />} label="High risk" value={String(stats.highRisk)} />
      </div>

      <Tabs items={TABS} onValueChange={setTab} value={activeTab} />

      {activeTab === "catalog" ? (
        <div className="space-y-4">
          <div className="grid gap-3 rounded-[1rem] border border-border bg-white p-4 md:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-8">
            <SearchField onChange={(event) => setQuery(event.target.value)} placeholder="Search capability/provider/domain" value={query} />
            <Select onChange={(event) => setTargetFilter(event.target.value)} value={targetFilter}>
              <option value="">Все targets</option>
              {targetOptions.map((option) => <option key={option} value={option}>{option}</option>)}
            </Select>
            <Select onChange={(event) => setProviderFilter(event.target.value)} value={providerFilter}>
              <option value="">Все providers</option>
              {providerOptions.map((option) => <option key={option} value={option}>{option}</option>)}
            </Select>
            <Select onChange={(event) => setDomainFilter(event.target.value)} value={domainFilter}>
              <option value="">Все domains</option>
              {domainOptions.map((option) => <option key={option} value={option}>{option}</option>)}
            </Select>
            <Select onChange={(event) => setPerspectiveFilter(event.target.value)} value={perspectiveFilter}>
              <option value="">Все perspectives</option>
              {perspectiveOptions.map((option) => <option key={option} value={option}>{option}</option>)}
            </Select>
            <Select onChange={(event) => setRiskFilter(event.target.value)} value={riskFilter}>
              <option value="">Все risk</option>
              {riskOptions.map((option) => <option key={option} value={option}>{option}</option>)}
            </Select>
            <Select onChange={(event) => setReadinessFilter(event.target.value)} value={readinessFilter}>
              <option value="">Все readiness</option>
              {readinessOptions.map((option) => <option key={option} value={option}>{option}</option>)}
            </Select>
            <Select onChange={(event) => setEvidenceFilter(event.target.value)} value={evidenceFilter}>
              <option value="">Evidence: any</option>
              <option value="yes">Produces evidence</option>
              <option value="no">No evidence</option>
            </Select>
          </div>
          <CapabilityCatalogTable
            capabilities={filteredCapabilities}
            isLoading={capabilitiesQuery.isLoading}
            onOpen={setSelectedCapability}
            onReadiness={(capability) => {
              setSelectedCapability(capability);
              setTab("readiness");
            }}
          />
        </div>
      ) : null}

      {activeTab === "providers" ? (
        <CapabilityProviderCards
          providers={providers}
          onSelectProvider={(providerId) => {
            setProviderFilter(providerId);
            setTab("catalog");
          }}
        />
      ) : null}

      {activeTab === "evidence" ? (
        <EvidenceMappingPanel capabilities={capabilities} onOpenCapability={setSelectedCapability} />
      ) : null}

      {activeTab === "readiness" ? (
        <ReadinessLabPanel globalCapabilities={capabilities} onOpenCapability={setSelectedCapability} />
      ) : null}

      {activeTab === "sdk" ? <SdkModulesTab /> : null}

      <div className="rounded-[1rem] border border-dashed border-border bg-white px-4 py-3 text-sm text-slate-500">
        <Sparkles className="mr-2 inline h-4 w-4 text-brand-700" />
        Low-code creation, persisted evidence mapping и declarative recipes помечены как Phase 2, чтобы MVP не подменял runtime contracts.
      </div>

      <CapabilityDetailDrawer capability={selectedCapability} onClose={() => setSelectedCapability(null)} />
      <CapabilityCreateModal open={createOpen} onClose={() => setCreateOpen(false)} />
    </section>
  );
}
