import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ClipboardCheck,
  DatabaseZap,
  FileArchive,
  FlaskConical,
  ListChecks,
  Play,
  RefreshCcw,
  Search,
  ShieldCheck,
} from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Select } from "../../components/ui/select";
import { requirePermission, requireToolRunPermission } from "../auth/permissions";
import { useSession } from "../auth/session-provider";
import { cn } from "../../shared/ui/cn";
import {
  attachSelectedDiagnosticEvidenceToPassport,
  buildDiagnosticBundle,
  createManualEvidence,
  evaluateDiagnosticFindings,
  getTicketDiagnosticsOverview,
  listDiagnosticEvidence,
  listDiagnosticFindings,
  listDiagnosticSessions,
  listTicketDiagnosticCapabilities,
  runDiagnosticProfile,
  runTicketDiagnosticCapability,
  updateDiagnosticEvidence,
  type DiagnosticCapability,
  type DiagnosticEvidence,
} from "./api";

type DiagnosticCenterPanelProps = {
  ticketId: string;
};

type ManualEvidenceDraft = {
  title: string;
  summary: string;
  status: string;
};

const ALL_FILTER = "all";

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "нет данных";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function label(value: string | null | undefined, fallback = "не указано"): string {
  return value ? value.replaceAll("_", " ") : fallback;
}

function statusTone(value: string | null | undefined): "neutral" | "brand" | "success" | "warning" | "danger" | "info" {
  if (value === "ok" || value === "available" || value === "completed" || value === "ready") {
    return "success";
  }
  if (value === "warning" || value === "install_required" || value === "consent_required" || value === "credentials_missing") {
    return "warning";
  }
  if (value === "error" || value === "failed" || value === "agent_offline" || value === "permission_denied") {
    return "danger";
  }
  if (value === "running" || value === "installing") {
    return "info";
  }
  if (value === "integration_not_configured" || value === "mapping_missing") {
    return "brand";
  }
  return "neutral";
}

function distinctOptions(values: Array<string | null | undefined>): string[] {
  return Array.from(new Set(values.map((value) => String(value ?? "").trim()).filter(Boolean))).sort((a, b) =>
    a.localeCompare(b),
  );
}

function capabilityDomain(capability: DiagnosticCapability): string {
  return String(capability.evidence?.domain ?? "unknown");
}

function capabilityPerspective(capability: DiagnosticCapability): string {
  return String(capability.evidence?.perspective ?? "unknown");
}

function capabilityCanRun(capability: DiagnosticCapability): boolean {
  return capability.actions.includes("run") || capability.actions.includes("open_remote_assist");
}

function primaryActionLabel(capability: DiagnosticCapability): string {
  if (capability.actions.includes("open_remote_assist")) {
    return "Открыть удалённую помощь";
  }
  if (capability.actions.includes("request_consent")) {
    return "Запросить согласие";
  }
  if (capability.readiness === "install_required") {
    return capability.actions.includes("run") ? "Установить и запустить" : "Требуется установка";
  }
  return "Запустить";
}

function summarizeRunResult(result: Record<string, unknown> | null): string | null {
  if (!result) {
    return null;
  }
  const evidenceId = String(result.diagnostic_evidence_id ?? "").trim();
  const operationId = String(result.operation_id ?? "").trim();
  const message = String(result.message ?? "").trim();
  if (message) {
    return message;
  }
  if (evidenceId) {
    return `Evidence создано: ${evidenceId}`;
  }
  if (operationId) {
    return `Operation создана: ${operationId}`;
  }
  return `Статус: ${String(result.status ?? "ok")}`;
}

export function DiagnosticCenterPanel({ ticketId }: DiagnosticCenterPanelProps) {
  const queryClient = useQueryClient();
  const { session } = useSession();
  const [targetFilter, setTargetFilter] = useState(ALL_FILTER);
  const [domainFilter, setDomainFilter] = useState(ALL_FILTER);
  const [perspectiveFilter, setPerspectiveFilter] = useState(ALL_FILTER);
  const [providerFilter, setProviderFilter] = useState(ALL_FILTER);
  const [selectedCapabilityId, setSelectedCapabilityId] = useState<string | null>(null);
  const [manualDraft, setManualDraft] = useState<ManualEvidenceDraft>({
    title: "",
    summary: "",
    status: "info",
  });
  const [manualOpen, setManualOpen] = useState(false);
  const [lastActionMessage, setLastActionMessage] = useState<string | null>(null);

  const overviewQuery = useQuery({
    queryKey: ["ticket-diagnostics-overview", ticketId],
    queryFn: () => getTicketDiagnosticsOverview(ticketId),
    retry: false,
  });
  const capabilitiesQuery = useQuery({
    queryKey: ["ticket-diagnostics-capabilities", ticketId],
    queryFn: () => listTicketDiagnosticCapabilities(ticketId),
    retry: false,
  });
  const evidenceQuery = useQuery({
    queryKey: ["ticket-diagnostics-evidence", ticketId],
    queryFn: () => listDiagnosticEvidence(ticketId),
    retry: false,
  });
  const sessionsQuery = useQuery({
    queryKey: ["ticket-diagnostics-sessions", ticketId],
    queryFn: () => listDiagnosticSessions(ticketId),
    retry: false,
  });
  const findingsQuery = useQuery({
    queryKey: ["ticket-diagnostics-findings", ticketId],
    queryFn: () => listDiagnosticFindings(ticketId),
    retry: false,
  });

  const capabilities = capabilitiesQuery.data ?? [];
  const evidence = evidenceQuery.data ?? [];
  const findings = findingsQuery.data ?? [];
  const sessions = sessionsQuery.data ?? [];
  const overview = overviewQuery.data ?? null;

  const filteredCapabilities = useMemo(
    () =>
      capabilities.filter((capability) => {
        if (targetFilter !== ALL_FILTER && capability.execution_target !== targetFilter) {
          return false;
        }
        if (domainFilter !== ALL_FILTER && capabilityDomain(capability) !== domainFilter) {
          return false;
        }
        if (perspectiveFilter !== ALL_FILTER && capabilityPerspective(capability) !== perspectiveFilter) {
          return false;
        }
        if (providerFilter !== ALL_FILTER && capability.provider_id !== providerFilter) {
          return false;
        }
        return true;
      }),
    [capabilities, domainFilter, perspectiveFilter, providerFilter, targetFilter],
  );

  const selectedCapability =
    filteredCapabilities.find((capability) => capability.id === selectedCapabilityId) ?? filteredCapabilities[0] ?? null;
  const runAccess = selectedCapability ? requireToolRunPermission(session, selectedCapability.risk_level) : null;
  const manualAccess = requirePermission(session, "diagnostics.create_manual_evidence");
  const passportAccess = requirePermission(session, "ticket.passport.manage");
  const evidenceCounts = overview?.evidence_counts ?? {};

  const invalidateDiagnostics = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["ticket-diagnostics-overview", ticketId] }),
      queryClient.invalidateQueries({ queryKey: ["ticket-diagnostics-capabilities", ticketId] }),
      queryClient.invalidateQueries({ queryKey: ["ticket-diagnostics-evidence", ticketId] }),
      queryClient.invalidateQueries({ queryKey: ["ticket-diagnostics-sessions", ticketId] }),
      queryClient.invalidateQueries({ queryKey: ["ticket-diagnostics-findings", ticketId] }),
      queryClient.invalidateQueries({ queryKey: ["ticket-detail", ticketId] }),
      queryClient.invalidateQueries({ queryKey: ["ticket-passport", ticketId] }),
      queryClient.invalidateQueries({ queryKey: ["ticket-passport-candidates", ticketId] }),
    ]);
  };

  const runCapabilityMutation = useMutation({
    mutationFn: (capability: DiagnosticCapability) => runTicketDiagnosticCapability(ticketId, capability.id, {}),
    onSuccess: async (result) => {
      setLastActionMessage(summarizeRunResult(result));
      await invalidateDiagnostics();
    },
  });

  const manualEvidenceMutation = useMutation({
    mutationFn: () =>
      createManualEvidence(ticketId, {
        title: manualDraft.title.trim(),
        summary: manualDraft.summary.trim(),
        status: manualDraft.status,
        kind: "manual.operator_note",
        domain: "manual",
        perspective: "manual",
        passport_eligible: true,
      }),
    onSuccess: async () => {
      setManualDraft({ title: "", summary: "", status: "info" });
      setManualOpen(false);
      setLastActionMessage("Ручной диагностический факт создан.");
      await invalidateDiagnostics();
    },
  });

  const evidenceSelectionMutation = useMutation({
    mutationFn: (item: DiagnosticEvidence) =>
      updateDiagnosticEvidence(ticketId, item.id, { selected_for_passport: !item.selected_for_passport }),
    onSuccess: async () => {
      await invalidateDiagnostics();
    },
  });

  const attachPassportMutation = useMutation({
    mutationFn: () => attachSelectedDiagnosticEvidenceToPassport(ticketId),
    onSuccess: async (items) => {
      setLastActionMessage(`В паспорт добавлено evidence: ${items.length}`);
      await invalidateDiagnostics();
    },
  });

  const evaluateFindingsMutation = useMutation({
    mutationFn: () => evaluateDiagnosticFindings(ticketId),
    onSuccess: async (items) => {
      setLastActionMessage(`Finding engine обновил выводы: ${items.length}`);
      await invalidateDiagnostics();
    },
  });

  const bundleMutation = useMutation({
    mutationFn: () =>
      buildDiagnosticBundle(ticketId, {
        include_agent_actions: false,
        include_observer: true,
        include_artifacts: true,
        include_remote_assist: true,
        include_monitoring: true,
      }),
    onSuccess: async (bundle) => {
      setLastActionMessage(`Diagnostic bundle готов: ${bundle.id}`);
      await invalidateDiagnostics();
    },
  });

  const runProfileMutation = useMutation({
    mutationFn: () =>
      runDiagnosticProfile(ticketId, {
        profile_id: overview?.profile?.id,
        auto_select_evidence: true,
      }),
    onSuccess: async (result) => {
      setLastActionMessage(`Профиль ${result.profile_id} запущен, evidence: ${result.evidence_count}`);
      await invalidateDiagnostics();
    },
  });

  const targetOptions = distinctOptions(capabilities.map((capability) => capability.execution_target));
  const domainOptions = distinctOptions(capabilities.map(capabilityDomain));
  const perspectiveOptions = distinctOptions(capabilities.map(capabilityPerspective));
  const providerOptions = distinctOptions(capabilities.map((capability) => capability.provider_id));
  const selectedForPassport = evidence.filter((item) => item.selected_for_passport).length;
  const hasLoadError =
    overviewQuery.isError ||
    capabilitiesQuery.isError ||
    evidenceQuery.isError ||
    sessionsQuery.isError ||
    findingsQuery.isError;

  return (
    <div className="space-y-5">
      <div className="grid gap-3 md:grid-cols-4">
        <div className="rounded-[1rem] border border-border bg-white px-4 py-4">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
            <Activity className="h-4 w-4" />
            Статус
          </div>
          <Badge className="mt-3" tone={statusTone(overview?.status)}>
            {label(overview?.status, "unknown")}
          </Badge>
          <p className="mt-3 text-sm text-slate-600">{overview?.summary ?? "Диагностический обзор пока пуст."}</p>
        </div>
        <div className="rounded-[1rem] border border-border bg-white px-4 py-4">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
            <DatabaseZap className="h-4 w-4" />
            Evidence
          </div>
          <p className="mt-3 text-2xl font-semibold text-slate-950">{evidence.length}</p>
          <p className="mt-1 text-sm text-slate-500">
            ok {evidenceCounts.ok ?? 0} · warning {evidenceCounts.warning ?? 0} · error {evidenceCounts.error ?? 0}
          </p>
        </div>
        <div className="rounded-[1rem] border border-border bg-white px-4 py-4">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
            <FlaskConical className="h-4 w-4" />
            Выводы
          </div>
          <p className="mt-3 text-2xl font-semibold text-slate-950">{findings.length}</p>
          <p className="mt-1 text-sm text-slate-500">{findings[0]?.title ?? "Finding engine ещё не запускался."}</p>
        </div>
        <div className="rounded-[1rem] border border-border bg-white px-4 py-4">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
            <FileArchive className="h-4 w-4" />
            Bundle
          </div>
          <p className="mt-3 text-2xl font-semibold text-slate-950">{selectedForPassport}</p>
          <p className="mt-1 text-sm text-slate-500">выбрано для паспорта</p>
        </div>
      </div>

      {hasLoadError ? (
        <div className="rounded-[1rem] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          Не удалось загрузить часть диагностических данных. Обновите вкладку или проверьте права доступа.
        </div>
      ) : null}

      {lastActionMessage ? (
        <div className="rounded-[1rem] border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {lastActionMessage}
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Button
          disabled={runProfileMutation.isPending || !overview?.profile?.id}
          leadingIcon={<ListChecks className="h-4 w-4" />}
          onClick={() => runProfileMutation.mutate()}
          variant="secondary"
        >
          {runProfileMutation.isPending ? "Запускаем профиль..." : `Профиль: ${overview?.profile?.title ?? "generic"}`}
        </Button>
        <Button
          disabled={evaluateFindingsMutation.isPending}
          leadingIcon={<ClipboardCheck className="h-4 w-4" />}
          onClick={() => evaluateFindingsMutation.mutate()}
          variant="outline"
        >
          {evaluateFindingsMutation.isPending ? "Считаем выводы..." : "Обновить вывод"}
        </Button>
        <Button
          disabled={bundleMutation.isPending}
          leadingIcon={<FileArchive className="h-4 w-4" />}
          onClick={() => bundleMutation.mutate()}
          variant="outline"
        >
          {bundleMutation.isPending ? "Собираем пакет..." : "Собрать diagnostic bundle"}
        </Button>
        <Button
          disabled={!passportAccess.allowed || attachPassportMutation.isPending || selectedForPassport === 0}
          leadingIcon={<ShieldCheck className="h-4 w-4" />}
          onClick={() => attachPassportMutation.mutate()}
          variant="outline"
        >
          {attachPassportMutation.isPending ? "Прикрепляем..." : "Добавить выбранное в паспорт"}
        </Button>
      </div>
      {!passportAccess.allowed ? <p className="text-sm text-amber-700">{passportAccess.reason}</p> : null}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(22rem,0.8fr)]">
        <section className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Capabilities</CardTitle>
              <CardDescription>
                Единый список agent, server, observer, remote assist и manual проверок с readiness.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 md:grid-cols-4">
                <label className="space-y-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                  Target
                  <Select value={targetFilter} onChange={(event) => setTargetFilter(event.target.value)}>
                    <option value={ALL_FILTER}>Все</option>
                    {targetOptions.map((value) => (
                      <option key={value} value={value}>
                        {label(value)}
                      </option>
                    ))}
                  </Select>
                </label>
                <label className="space-y-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                  Domain
                  <Select value={domainFilter} onChange={(event) => setDomainFilter(event.target.value)}>
                    <option value={ALL_FILTER}>Все</option>
                    {domainOptions.map((value) => (
                      <option key={value} value={value}>
                        {label(value)}
                      </option>
                    ))}
                  </Select>
                </label>
                <label className="space-y-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                  Perspective
                  <Select value={perspectiveFilter} onChange={(event) => setPerspectiveFilter(event.target.value)}>
                    <option value={ALL_FILTER}>Все</option>
                    {perspectiveOptions.map((value) => (
                      <option key={value} value={value}>
                        {label(value)}
                      </option>
                    ))}
                  </Select>
                </label>
                <label className="space-y-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                  Provider
                  <Select value={providerFilter} onChange={(event) => setProviderFilter(event.target.value)}>
                    <option value={ALL_FILTER}>Все</option>
                    {providerOptions.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </Select>
                </label>
              </div>

              {capabilitiesQuery.isLoading ? <p className="text-sm text-slate-500">Загружаем capabilities...</p> : null}
              <div className="space-y-2">
                {filteredCapabilities.map((capability) => {
                  const active = selectedCapability?.id === capability.id;
                  return (
                    <button
                      className={cn(
                        "w-full rounded-[1rem] border px-4 py-4 text-left transition-colors",
                        active ? "border-brand-200 bg-brand-50" : "border-border bg-white hover:border-brand-100",
                      )}
                      key={capability.id}
                      onClick={() => setSelectedCapabilityId(capability.id)}
                      type="button"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="font-semibold text-slate-950">{capability.title || capability.id}</p>
                          <p className="mt-1 text-xs text-slate-500">
                            {capability.id} · {label(capability.execution_target)} · {capability.provider_id ?? "provider?"}
                          </p>
                        </div>
                        <Badge tone={statusTone(capability.readiness)}>{label(capability.readiness)}</Badge>
                      </div>
                      <p className="mt-3 text-sm text-slate-600">
                        {capability.reason ?? capability.description ?? "Готовность рассчитана без дополнительного пояснения."}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Badge tone="neutral">{capabilityDomain(capability)}</Badge>
                        <Badge tone="neutral">{capabilityPerspective(capability)}</Badge>
                        {capability.requires_consent ? <Badge tone="warning">consent</Badge> : null}
                        {capability.requires_integration ? <Badge tone="brand">{capability.integration_key}</Badge> : null}
                      </div>
                    </button>
                  );
                })}
                {!filteredCapabilities.length && !capabilitiesQuery.isLoading ? (
                  <div className="rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-center text-sm text-slate-500">
                    Под выбранные фильтры capabilities не найдены.
                  </div>
                ) : null}
              </div>
            </CardContent>
          </Card>
        </section>

        <aside className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Выбранная проверка</CardTitle>
              <CardDescription>Действия маршрутизируются через diagnostic capability router.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {selectedCapability ? (
                <>
                  <div className="rounded-[1rem] bg-surface-subtle px-4 py-4">
                    <p className="font-semibold text-slate-950">{selectedCapability.title}</p>
                    <p className="mt-2 break-all text-xs text-slate-500">{selectedCapability.id}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Badge tone={statusTone(selectedCapability.readiness)}>{label(selectedCapability.readiness)}</Badge>
                      <Badge tone="info">{label(selectedCapability.execution_target)}</Badge>
                      <Badge tone="neutral">{selectedCapability.risk_level}</Badge>
                    </div>
                    <p className="mt-3 text-sm text-slate-600">
                      {selectedCapability.description || selectedCapability.reason || "Описание capability не передано."}
                    </p>
                  </div>

                  {selectedCapability.evidence?.kind ? (
                    <div className="rounded-[1rem] border border-border bg-white px-4 py-4 text-sm">
                      <p className="font-semibold text-slate-900">Evidence mapping</p>
                      <p className="mt-2 text-slate-600">
                        {selectedCapability.evidence.kind} · {selectedCapability.evidence.domain} ·{" "}
                        {selectedCapability.evidence.perspective}
                      </p>
                      {selectedCapability.evidence.passport_eligible ? (
                        <p className="mt-2 text-emerald-700">Может попасть в passport.</p>
                      ) : null}
                    </div>
                  ) : null}

                  {selectedCapability.artifacts?.artifact_kinds?.length ? (
                    <div className="rounded-[1rem] border border-border bg-white px-4 py-4 text-sm">
                      <p className="font-semibold text-slate-900">Artifacts</p>
                      <p className="mt-2 text-slate-600">{selectedCapability.artifacts.artifact_kinds.join(", ")}</p>
                    </div>
                  ) : null}

                  <div className="space-y-2">
                    {capabilityCanRun(selectedCapability) ? (
                      <>
                        <Button
                          className="w-full"
                          disabled={!runAccess?.allowed || runCapabilityMutation.isPending}
                          leadingIcon={<Play className="h-4 w-4" />}
                          onClick={() => runCapabilityMutation.mutate(selectedCapability)}
                        >
                          {runCapabilityMutation.isPending ? "Выполняем..." : primaryActionLabel(selectedCapability)}
                        </Button>
                        {!runAccess?.allowed ? <p className="text-sm text-amber-700">{runAccess?.reason}</p> : null}
                      </>
                    ) : null}

                    {selectedCapability.actions.includes("configure_integration") ||
                    selectedCapability.actions.includes("add_credentials") ? (
                      <a
                        className="inline-flex w-full items-center justify-center gap-2 rounded-pill border border-border bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:border-brand-200 hover:bg-brand-50"
                        href="/app/admin/modules#diagnostic-provider-configs"
                      >
                        <Search className="h-4 w-4" />
                        Настроить provider
                      </a>
                    ) : null}

                    {selectedCapability.actions.includes("create_manual_evidence") ? (
                      <Button
                        className="w-full"
                        disabled={!manualAccess.allowed}
                        onClick={() => setManualOpen(true)}
                        variant="outline"
                      >
                        Добавить ручной факт
                      </Button>
                    ) : null}

                    {selectedCapability.actions.includes("install") && !selectedCapability.actions.includes("run") ? (
                      <p className="rounded-[0.8rem] border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                        Установка доступна как readiness action; запуск через старый tool launcher сохранён отдельно.
                      </p>
                    ) : null}
                  </div>
                </>
              ) : (
                <p className="text-sm text-slate-500">Выберите capability в списке.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Ручной факт</CardTitle>
              <CardDescription>Manual evidence не меняет статус тикета и проходит через diagnostic_evidence.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {!manualOpen ? (
                <Button
                  disabled={!manualAccess.allowed}
                  onClick={() => setManualOpen(true)}
                  variant="outline"
                >
                  Добавить manual evidence
                </Button>
              ) : (
                <div className="space-y-3">
                  <input
                    className="field-base w-full px-3 py-2 text-sm"
                    onChange={(event) => setManualDraft((draft) => ({ ...draft, title: event.target.value }))}
                    placeholder="Что проверено"
                    value={manualDraft.title}
                  />
                  <textarea
                    className="field-base min-h-24 w-full resize-none px-3 py-2 text-sm"
                    onChange={(event) => setManualDraft((draft) => ({ ...draft, summary: event.target.value }))}
                    placeholder="Краткий результат"
                    value={manualDraft.summary}
                  />
                  <Select
                    onChange={(event) => setManualDraft((draft) => ({ ...draft, status: event.target.value }))}
                    value={manualDraft.status}
                  >
                    <option value="info">info</option>
                    <option value="ok">ok</option>
                    <option value="warning">warning</option>
                    <option value="error">error</option>
                    <option value="unknown">unknown</option>
                  </Select>
                  <Button
                    disabled={!manualDraft.title.trim() || !manualAccess.allowed || manualEvidenceMutation.isPending}
                    onClick={() => manualEvidenceMutation.mutate()}
                  >
                    {manualEvidenceMutation.isPending ? "Сохраняем..." : "Сохранить факт"}
                  </Button>
                </div>
              )}
              {!manualAccess.allowed ? <p className="text-sm text-amber-700">{manualAccess.reason}</p> : null}
            </CardContent>
          </Card>
        </aside>
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Latest evidence</CardTitle>
            <CardDescription>Выбранные строки можно приложить к паспорту.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {(evidence.length ? evidence : overview?.latest_evidence ?? []).slice(0, 8).map((item) => (
              <div className="rounded-[1rem] border border-border bg-white px-4 py-4" key={item.id}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-semibold text-slate-950">{item.title}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {item.kind} · {item.domain} · {item.perspective}
                    </p>
                  </div>
                  <Badge tone={statusTone(item.status)}>{label(item.status)}</Badge>
                </div>
                <p className="mt-2 text-sm text-slate-600">{item.summary ?? "Краткое описание отсутствует."}</p>
                <div className="mt-3 flex items-center justify-between gap-3">
                  <span className="text-xs text-slate-400">{formatDateTime(item.observed_at)}</span>
                  <Button
                    disabled={!passportAccess.allowed || evidenceSelectionMutation.isPending}
                    onClick={() => evidenceSelectionMutation.mutate(item)}
                    size="sm"
                    variant={item.selected_for_passport ? "secondary" : "outline"}
                  >
                    {item.selected_for_passport ? "Выбрано" : "В паспорт"}
                  </Button>
                </div>
              </div>
            ))}
            {!evidence.length && !overview?.latest_evidence?.length ? (
              <p className="rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-center text-sm text-slate-500">
                Evidence пока нет. Запустите capability, playbook или добавьте ручной факт.
              </p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Sessions</CardTitle>
            <CardDescription>Диагностика остаётся отдельным слоем, не статусом тикета.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {sessions.slice(0, 6).map((sessionItem) => (
              <div className="rounded-[1rem] border border-border bg-white px-4 py-4" key={sessionItem.id}>
                <div className="flex items-center justify-between gap-3">
                  <p className="font-semibold text-slate-950">{sessionItem.profile_id ?? "manual session"}</p>
                  <Badge tone={statusTone(sessionItem.status)}>{label(sessionItem.status)}</Badge>
                </div>
                <p className="mt-2 text-sm text-slate-500">{sessionItem.summary ?? sessionItem.trigger_source ?? "без summary"}</p>
                <p className="mt-2 text-xs text-slate-400">{formatDateTime(sessionItem.started_at)}</p>
              </div>
            ))}
            {!sessions.length ? (
              <p className="rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-center text-sm text-slate-500">
                Диагностических сессий пока нет.
              </p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Findings</CardTitle>
            <CardDescription>Rule-based выводы по evidence без LLM.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {findings.slice(0, 6).map((finding) => (
              <div className="rounded-[1rem] border border-border bg-white px-4 py-4" key={finding.id}>
                <div className="flex items-start justify-between gap-3">
                  <p className="font-semibold text-slate-950">{finding.title}</p>
                  <Badge tone={statusTone(finding.status)}>{label(finding.status)}</Badge>
                </div>
                <p className="mt-2 text-sm text-slate-600">{finding.description ?? finding.root_cause_code ?? "Описание не заполнено."}</p>
                <p className="mt-2 text-xs text-slate-400">
                  confidence {finding.confidence ?? "n/a"} · evidence {finding.evidence_ids.length}
                </p>
              </div>
            ))}
            {!findings.length ? (
              <p className="rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-center text-sm text-slate-500">
                Выводов пока нет. Нажмите «Обновить вывод».
              </p>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
