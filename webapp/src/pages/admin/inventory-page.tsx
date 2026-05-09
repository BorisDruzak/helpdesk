import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  BellRing,
  CheckCircle2,
  ClipboardList,
  DownloadCloud,
  KeyRound,
  Layers3,
  Monitor,
  MoreHorizontal,
  RefreshCcw,
  Rocket,
  ShieldCheck,
  ShieldQuestion,
  Trash2,
  XCircle,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { startTransition, useDeferredValue, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { SearchField } from "../../components/ui/search-field";
import { Select } from "../../components/ui/select";
import { StatTile } from "../../components/ui/stat-tile";
import {
  approveAdminConnectionRequest,
  cleanupAdminEnvUuidDuplicates,
  fetchAdminConnectionPolicy,
  fetchAdminConnectionRequests,
  fetchAdminDeviceTokens,
  fetchAdminDevices,
  rejectAdminConnectionRequest,
  revokeAdminDeviceToken,
  updateAdminConnectionPolicy,
  type AdminConnectionPolicy,
  type AdminConnectionRequestItem,
  type AdminDevicesPayload,
  type AdminStatusFilter,
} from "../../features/admin/api";
import { cn } from "../../shared/ui/cn";

type DeviceItem = AdminDevicesPayload["devices"][number];
type InventoryPanel = "agents" | "requests" | "tokens" | "rollout";

const PANEL_OPTIONS: Array<{ id: InventoryPanel; label: string; icon: typeof Monitor }> = [
  { id: "agents", label: "Агенты", icon: Monitor },
  { id: "requests", label: "Подключения", icon: BellRing },
  { id: "tokens", label: "Токены", icon: KeyRound },
  { id: "rollout", label: "Rollout", icon: Rocket },
];

const POLICY_LABELS: Record<AdminConnectionPolicy, string> = {
  accept_all: "Автоматически принимать",
  manual: "Ручное одобрение",
  reject_all: "Отклонять все",
};

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "Нет данных";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function compactId(value: string | null | undefined): string {
  if (!value) {
    return "n/a";
  }
  return value.length > 14 ? `${value.slice(0, 8)}...${value.slice(-4)}` : value;
}

function getUpdateTone(value: string | null | undefined): "danger" | "info" | "neutral" | "success" | "warning" {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (!normalized) {
    return "neutral";
  }
  if (["succeeded", "ok", "completed", "up_to_date"].includes(normalized)) {
    return "success";
  }
  if (["queued", "running", "in_progress"].includes(normalized)) {
    return "info";
  }
  if (["failed", "timed_out", "error"].includes(normalized)) {
    return "danger";
  }
  return "warning";
}

function getOsLabel(value: string | null | undefined): string {
  const normalized = String(value ?? "").trim();
  return normalized || "Не определена";
}

function getRequestSubtitle(request: AdminConnectionRequestItem): string {
  const metadata = request.metadata ?? {};
  const source = String(metadata["agent_version"] ?? metadata["os"] ?? metadata["machine_id"] ?? "").trim();
  return [request.ip_address, source].filter(Boolean).join(" / ") || "Ожидает решения администратора";
}

function metadataRows(metadata: Record<string, unknown>): Array<[string, string]> {
  return Object.entries(metadata)
    .slice(0, 6)
    .map(([key, value]) => [key, typeof value === "object" ? JSON.stringify(value) : String(value ?? "")]);
}

export function AdminInventoryPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<AdminStatusFilter>("all");
  const [activePanel, setActivePanel] = useState<InventoryPanel>(
    PANEL_OPTIONS.some((option) => option.id === searchParams.get("panel"))
      ? (searchParams.get("panel") as InventoryPanel)
      : "agents"
  );
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null);
  const [cleanupFeedback, setCleanupFeedback] = useState<string | null>(null);
  const deferredQuery = useDeferredValue(query);

  const devicesQuery = useQuery({
    queryKey: ["admin-devices-page", deferredQuery, statusFilter],
    queryFn: () => fetchAdminDevices({ query: deferredQuery, statusFilter }),
    retry: false,
    refetchInterval: 15_000,
  });

  const connectionRequestsQuery = useQuery({
    queryKey: ["admin-connection-requests"],
    queryFn: fetchAdminConnectionRequests,
    retry: false,
    refetchInterval: 5_000,
  });

  const policyQuery = useQuery({
    queryKey: ["admin-connection-policy"],
    queryFn: fetchAdminConnectionPolicy,
    retry: false,
  });

  const devices = devicesQuery.data?.devices ?? [];
  const requests = connectionRequestsQuery.data?.connection_requests ?? [];
  const selectedDeviceId = searchParams.get("device");
  const selectedDevice = devices.find((item) => item.device_id === selectedDeviceId) ?? devices[0] ?? null;
  const selectedRequest =
    requests.find((item) => item.device_id === selectedRequestId) ?? requests[0] ?? null;

  const deviceTokensQuery = useQuery({
    queryKey: ["admin-device-tokens", selectedDevice?.device_id],
    queryFn: () => fetchAdminDeviceTokens(selectedDevice?.device_id ?? ""),
    enabled: Boolean(selectedDevice?.device_id),
    retry: false,
  });

  const rolloutAssignments = selectedDevice
    ? (devicesQuery.data?.rollout ?? []).filter((item) => item.target === selectedDevice.target)
    : devicesQuery.data?.rollout ?? [];

  const alertCount = useMemo(
    () =>
      devices.filter((device) => {
        const status = String(device.latest_update.status ?? "").trim().toLowerCase();
        return ["failed", "timed_out", "error"].includes(status) || device.duplicate_warning;
      }).length,
    [devices]
  );
  const offlineCount = Math.max(0, devices.length - (devicesQuery.data?.summary.online_count ?? 0));

  const cleanupMutation = useMutation({
    mutationFn: async (apply: boolean) => {
      if (!selectedDevice?.hostname) {
        throw new Error("Для чистки нужен hostname выбранного устройства.");
      }
      return cleanupAdminEnvUuidDuplicates({
        hostname: selectedDevice.hostname,
        keepDeviceId: selectedDevice.identity_summary.is_stable ? selectedDevice.device_id : undefined,
        apply,
      });
    },
    onSuccess: async (result) => {
      setCleanupFeedback(
        result.applied
          ? `Архивировано env_uuid-дублей: ${result.archived_count}.`
          : `Кандидатов для безопасной архивации: ${result.candidates.length}.`
      );
      await queryClient.invalidateQueries({ queryKey: ["admin-devices-page"] });
    },
    onError: (error) => {
      setCleanupFeedback(error instanceof Error ? error.message : "Не удалось выполнить чистку дублей.");
    },
  });

  const revokeTokenMutation = useMutation({
    mutationFn: async (tokenHash: string) => {
      if (!selectedDevice?.device_id) {
        throw new Error("Не выбрано устройство.");
      }
      await revokeAdminDeviceToken(selectedDevice.device_id, tokenHash);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-device-tokens", selectedDevice?.device_id] });
      await queryClient.invalidateQueries({ queryKey: ["admin-devices-page"] });
    },
  });

  const policyMutation = useMutation({
    mutationFn: updateAdminConnectionPolicy,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-connection-policy"] });
    },
  });

  const approveRequestMutation = useMutation({
    mutationFn: approveAdminConnectionRequest,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-connection-requests"] });
      await queryClient.invalidateQueries({ queryKey: ["shell-pending-connection-requests"] });
      await queryClient.invalidateQueries({ queryKey: ["admin-devices-page"] });
    },
  });

  const rejectRequestMutation = useMutation({
    mutationFn: rejectAdminConnectionRequest,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-connection-requests"] });
      await queryClient.invalidateQueries({ queryKey: ["shell-pending-connection-requests"] });
    },
  });

  useEffect(() => {
    if (!selectedDevice?.device_id) {
      return;
    }
    if (searchParams.get("device") === selectedDevice.device_id) {
      return;
    }
    const nextSearchParams = new URLSearchParams(searchParams);
    nextSearchParams.set("device", selectedDevice.device_id);
    startTransition(() => {
      setSearchParams(nextSearchParams, { replace: true });
    });
  }, [searchParams, selectedDevice?.device_id, setSearchParams]);

  useEffect(() => {
    setCleanupFeedback(null);
  }, [selectedDevice?.device_id]);

  useEffect(() => {
    const panel = searchParams.get("panel");
    if (PANEL_OPTIONS.some((option) => option.id === panel)) {
      setActivePanel(panel as InventoryPanel);
    }
  }, [searchParams]);

  function selectDevice(device: DeviceItem) {
    const nextSearchParams = new URLSearchParams(searchParams);
    nextSearchParams.set("device", device.device_id);
    startTransition(() => {
      setSearchParams(nextSearchParams, { replace: true });
      setActivePanel("agents");
    });
  }

  function selectRequest(request: AdminConnectionRequestItem) {
    setSelectedRequestId(request.device_id);
    setActivePanel("requests");
  }

  function openDeviceCard() {
    if (!selectedDevice) {
      return;
    }
    startTransition(() => {
      navigate(`/app/admin/device?device=${encodeURIComponent(selectedDevice.device_id)}`);
    });
  }

  return (
    <section className="space-y-5">
      <PageHeading
        actions={
          <>
            <Button
              leadingIcon={<RefreshCcw className="h-4 w-4" />}
              onClick={() => {
                void devicesQuery.refetch();
                void connectionRequestsQuery.refetch();
              }}
              size="sm"
              variant="outline"
            >
              Обновить
            </Button>
            <Button
              disabled={!selectedDevice}
              leadingIcon={<ArrowUpRight className="h-4 w-4" />}
              onClick={openDeviceCard}
              size="sm"
            >
              Карточка
            </Button>
          </>
        }
        description="Управление подключенными агентами, pending-запросами, токенами и rollout-состоянием."
        eyebrow="Admin workspace"
        title="Агенты"
      />

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <StatTile helper="Все найденные устройства" label="Всего агентов" value={String(devices.length)} />
        <StatTile helper="По активному heartbeat" label="Онлайн" value={String(devicesQuery.data?.summary.online_count ?? 0)} />
        <StatTile helper="Ошибки, дубли и риски" label="С предупреждениями" value={String(alertCount)} />
        <StatTile helper="Нет активной сессии" label="Офлайн" value={String(offlineCount)} />
        <StatTile helper="Ждут решения администратора" label="Новые подключения" value={String(requests.length)} />
      </div>

      <div className="grid gap-5 2xl:grid-cols-[minmax(0,1fr)_360px]">
        <Card className="overflow-hidden">
          <div className="border-b border-border px-5 pt-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div className="flex flex-wrap gap-2">
                {PANEL_OPTIONS.map((option) => {
                  const Icon = option.icon;
                  const isActive = activePanel === option.id;
                  return (
                    <button
                      className={cn(
                        "inline-flex h-10 items-center gap-2 rounded-pill px-4 text-sm font-semibold transition-colors",
                        isActive
                          ? "bg-brand-50 text-brand-800"
                          : "text-slate-500 hover:bg-slate-100 hover:text-slate-900"
                      )}
                      key={option.id}
                      onClick={() => setActivePanel(option.id)}
                      type="button"
                    >
                      <Icon className="h-4 w-4" />
                      {option.label}
                      {option.id === "requests" && requests.length > 0 ? (
                        <span className="rounded-full bg-rose-500 px-1.5 py-0.5 text-[10px] font-bold text-white">
                          {requests.length}
                        </span>
                      ) : null}
                    </button>
                  );
                })}
              </div>

              <div className="flex flex-col gap-3 md:flex-row md:items-center">
                <SearchField
                  className="min-w-[280px]"
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Поиск по имени, IP, ОС, версии"
                  value={query}
                />
                <Select
                  className="md:w-[180px]"
                  onChange={(event) => setStatusFilter(event.target.value as AdminStatusFilter)}
                  value={statusFilter}
                >
                  {(devicesQuery.data?.filters.status_options ?? [
                    { value: "all", label: "Все устройства" },
                    { value: "online", label: "Только онлайн" },
                    { value: "offline", label: "Только офлайн" },
                  ]).map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
          </div>

          {requests.length > 0 ? (
            <div className="border-b border-amber-100 bg-amber-50/70 px-5 py-3">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-amber-600">
                    <BellRing className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-amber-950">Есть новые запросы подключения</p>
                    <p className="text-sm text-amber-800">
                      Агент ожидает ручного одобрения, после принятия токен будет доставлен при следующем polling.
                    </p>
                  </div>
                </div>
                <Button
                  leadingIcon={<BellRing className="h-4 w-4" />}
                  onClick={() => setActivePanel("requests")}
                  size="sm"
                  variant="outline"
                >
                  Открыть запросы
                </Button>
              </div>
            </div>
          ) : null}

          <CardContent className="p-0">
            {activePanel === "agents" ? (
              <AgentsTable
                devices={devices}
                isLoading={devicesQuery.isLoading}
                onSelect={selectDevice}
                selectedDeviceId={selectedDevice?.device_id ?? null}
              />
            ) : null}

            {activePanel === "requests" ? (
              <ConnectionRequestsPanel
                isLoading={connectionRequestsQuery.isLoading}
                onApprove={(deviceId) => approveRequestMutation.mutate(deviceId)}
                onReject={(deviceId) => rejectRequestMutation.mutate(deviceId)}
                onSelect={selectRequest}
                policy={policyQuery.data?.policy ?? "accept_all"}
                policyBusy={policyMutation.isPending || policyQuery.isLoading}
                requests={requests}
                selectedRequestId={selectedRequest?.device_id ?? null}
                setPolicy={(policy) => policyMutation.mutate(policy)}
              />
            ) : null}

            {activePanel === "tokens" ? (
              <TokensPanel
                isLoading={deviceTokensQuery.isLoading}
                onRevoke={(tokenHash) => revokeTokenMutation.mutate(tokenHash)}
                revokeBusy={revokeTokenMutation.isPending}
                selectedDevice={selectedDevice}
                tokens={deviceTokensQuery.data?.tokens ?? []}
              />
            ) : null}

            {activePanel === "rollout" ? (
              <RolloutPanel
                assignments={devicesQuery.data?.rollout ?? []}
                onOpenAgentUpdates={() => {
                  const query = new URLSearchParams();
                  if (selectedDevice?.device_id) {
                    query.set("device", selectedDevice.device_id);
                  }
                  if (selectedDevice?.target) {
                    query.set("target", selectedDevice.target);
                  }
                  navigate(`/app/admin/agent-updates${query.toString() ? `?${query.toString()}` : ""}`);
                }}
                onOpenModules={() => navigate("/app/admin/modules")}
                selectedDevice={selectedDevice}
              />
            ) : null}
          </CardContent>
        </Card>

        <AgentDetailsPanel
          cleanupBusy={cleanupMutation.isPending}
          cleanupFeedback={cleanupFeedback}
          device={selectedDevice}
          onCleanupPreview={() => cleanupMutation.mutate(false)}
          onCleanupApply={() => cleanupMutation.mutate(true)}
          onOpenAgentUpdates={() => {
            const query = new URLSearchParams();
            if (selectedDevice?.device_id) {
              query.set("device", selectedDevice.device_id);
            }
            if (selectedDevice?.target) {
              query.set("target", selectedDevice.target);
            }
            navigate(`/app/admin/agent-updates${query.toString() ? `?${query.toString()}` : ""}`);
          }}
          onOpenDeviceCard={openDeviceCard}
          onOpenPlaybooks={() => navigate("/app/admin/playbooks")}
          request={activePanel === "requests" ? selectedRequest : null}
          rolloutAssignments={rolloutAssignments}
          tokenSummary={deviceTokensQuery.data?.summary ?? null}
        />
      </div>
    </section>
  );
}

function AgentsTable({
  devices,
  isLoading,
  onSelect,
  selectedDeviceId,
}: {
  devices: DeviceItem[];
  isLoading: boolean;
  onSelect: (device: DeviceItem) => void;
  selectedDeviceId: string | null;
}) {
  if (isLoading) {
    return <EmptyState icon={Activity} title="Загружаем агентов" description="Собираем актуальный список устройств." />;
  }
  if (devices.length === 0) {
    return <EmptyState icon={Monitor} title="Агенты не найдены" description="Измените фильтр или дождитесь heartbeat." />;
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-border text-sm">
        <thead className="bg-slate-50/80 text-left text-xs font-semibold uppercase text-slate-500">
          <tr>
            <th className="px-5 py-3">Агент</th>
            <th className="px-5 py-3">Статус</th>
            <th className="px-5 py-3">ОС</th>
            <th className="px-5 py-3">Версия</th>
            <th className="px-5 py-3">Активность</th>
            <th className="px-5 py-3">Состояние</th>
            <th className="px-5 py-3 text-right">Действия</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border bg-white">
          {devices.map((device) => {
            const selected = selectedDeviceId === device.device_id;
            return (
              <tr
                className={cn("cursor-pointer transition-colors hover:bg-brand-50/40", selected ? "bg-brand-50/70" : "")}
                key={device.device_id}
                onClick={() => onSelect(device)}
              >
                <td className="px-5 py-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 text-slate-700">
                      <Monitor className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="font-semibold text-slate-950">{device.hostname || compactId(device.device_id)}</p>
                      <p className="text-xs text-slate-500">{compactId(device.device_id)}</p>
                    </div>
                  </div>
                </td>
                <td className="px-5 py-4">
                  <Badge tone={device.online ? "success" : "neutral"} withDot>
                    {device.connection_status_label}
                  </Badge>
                </td>
                <td className="px-5 py-4 text-slate-600">{getOsLabel(device.os)}</td>
                <td className="px-5 py-4 text-slate-600">{device.agent_version || "n/a"}</td>
                <td className="px-5 py-4 text-slate-600">{formatDateTime(device.last_seen_at)}</td>
                <td className="px-5 py-4">
                  <Badge tone={getUpdateTone(device.latest_update.status)}>
                    {device.latest_update.label}
                  </Badge>
                </td>
                <td className="px-5 py-4 text-right">
                  <button
                    aria-label="Действия агента"
                    className="inline-flex h-9 w-9 items-center justify-center rounded-full text-slate-500 hover:bg-slate-100 hover:text-slate-900"
                    type="button"
                  >
                    <MoreHorizontal className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ConnectionRequestsPanel({
  isLoading,
  onApprove,
  onReject,
  onSelect,
  policy,
  policyBusy,
  requests,
  selectedRequestId,
  setPolicy,
}: {
  isLoading: boolean;
  onApprove: (deviceId: string) => void;
  onReject: (deviceId: string) => void;
  onSelect: (request: AdminConnectionRequestItem) => void;
  policy: AdminConnectionPolicy;
  policyBusy: boolean;
  requests: AdminConnectionRequestItem[];
  selectedRequestId: string | null;
  setPolicy: (policy: AdminConnectionPolicy) => void;
}) {
  return (
    <div className="space-y-0">
      <div className="grid gap-4 border-b border-border p-5 xl:grid-cols-[minmax(0,1fr)_260px]">
        <div>
          <p className="text-sm font-semibold text-slate-950">Политика подключения</p>
          <p className="mt-1 text-sm text-slate-500">
            Ручное одобрение показывает новые устройства здесь и в колокольчике верхней панели.
          </p>
        </div>
        <Select
          disabled={policyBusy}
          onChange={(event) => setPolicy(event.target.value as AdminConnectionPolicy)}
          value={policy}
        >
          <option value="manual">{POLICY_LABELS.manual}</option>
          <option value="accept_all">{POLICY_LABELS.accept_all}</option>
          <option value="reject_all">{POLICY_LABELS.reject_all}</option>
        </Select>
      </div>

      {isLoading ? (
        <EmptyState icon={Activity} title="Проверяем очередь" description="Ищем активные запросы подключения." />
      ) : requests.length === 0 ? (
        <EmptyState icon={ShieldCheck} title="Новых подключений нет" description="Очередь ручного одобрения пуста." />
      ) : (
        <div className="divide-y divide-border">
          {requests.map((request) => (
            <div
              aria-label={`Выбрать запрос ${request.hostname || compactId(request.device_id)}`}
              className={cn(
                "flex w-full cursor-pointer flex-col gap-3 px-5 py-4 text-left transition-colors hover:bg-brand-50/40 lg:flex-row lg:items-center lg:justify-between",
                selectedRequestId === request.device_id ? "bg-brand-50/70" : "bg-white"
              )}
              key={request.device_id}
              onClick={() => onSelect(request)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelect(request);
                }
              }}
              role="button"
              tabIndex={0}
            >
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 text-amber-700">
                  <ShieldQuestion className="h-4 w-4" />
                </div>
                <div>
                  <p className="font-semibold text-slate-950">{request.hostname || compactId(request.device_id)}</p>
                  <p className="mt-1 text-sm text-slate-500">{getRequestSubtitle(request)}</p>
                  <p className="mt-1 text-xs text-slate-400">Создан: {formatDateTime(request.created_at)}</p>
                </div>
              </div>
              <div className="flex shrink-0 gap-2">
                <Button
                  leadingIcon={<CheckCircle2 className="h-4 w-4" />}
                  onClick={(event) => {
                    event.stopPropagation();
                    onApprove(request.device_id);
                  }}
                  size="sm"
                >
                  Одобрить
                </Button>
                <Button
                  className="border-rose-200 text-rose-700 hover:bg-rose-50 hover:text-rose-800"
                  leadingIcon={<XCircle className="h-4 w-4" />}
                  onClick={(event) => {
                    event.stopPropagation();
                    onReject(request.device_id);
                  }}
                  size="sm"
                  variant="outline"
                >
                  Отклонить
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TokensPanel({
  isLoading,
  onRevoke,
  revokeBusy,
  selectedDevice,
  tokens,
}: {
  isLoading: boolean;
  onRevoke: (tokenHash: string) => void;
  revokeBusy: boolean;
  selectedDevice: DeviceItem | null;
  tokens: Array<{
    token_hash: string;
    token_prefix: string | null;
    created_at: string | null;
    expires_at: string | null;
    revoked_at: string | null;
    last_used_at: string | null;
    is_active: boolean;
  }>;
}) {
  if (!selectedDevice) {
    return <EmptyState icon={KeyRound} title="Выберите агента" description="После выбора здесь появятся токены." />;
  }
  if (isLoading) {
    return <EmptyState icon={Activity} title="Загружаем токены" description="Проверяем активные и отозванные токены." />;
  }
  if (tokens.length === 0) {
    return <EmptyState icon={KeyRound} title="Токенов нет" description="Для устройства не найдено записей токенов." />;
  }

  return (
    <div className="divide-y divide-border">
      {tokens.map((token) => (
        <div className="grid gap-3 px-5 py-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center" key={token.token_hash}>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-mono text-sm font-semibold text-slate-950">{token.token_prefix || compactId(token.token_hash)}</p>
              <Badge tone={token.is_active ? "success" : "neutral"}>{token.is_active ? "Активен" : "Неактивен"}</Badge>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              Создан: {formatDateTime(token.created_at)} / Последнее использование: {formatDateTime(token.last_used_at)}
            </p>
          </div>
          <Button
            className="border-rose-200 text-rose-700 hover:bg-rose-50 hover:text-rose-800"
            disabled={!token.is_active || revokeBusy}
            leadingIcon={<Trash2 className="h-4 w-4" />}
            onClick={() => onRevoke(token.token_hash)}
            size="sm"
            variant="outline"
          >
            Отозвать
          </Button>
        </div>
      ))}
    </div>
  );
}

function RolloutPanel({
  assignments,
  onOpenAgentUpdates,
  onOpenModules,
  selectedDevice,
}: {
  assignments: AdminDevicesPayload["rollout"];
  onOpenAgentUpdates: () => void;
  onOpenModules: () => void;
  selectedDevice: DeviceItem | null;
}) {
  return (
    <div className="space-y-0">
      <div className="flex flex-col gap-3 border-b border-border p-5 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-sm font-semibold text-slate-950">Rollout-назначения</p>
          <p className="mt-1 text-sm text-slate-500">Контекст обновления агента и target выбранного устройства.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button leadingIcon={<DownloadCloud className="h-4 w-4" />} onClick={onOpenAgentUpdates} size="sm">
            Agent Updates
          </Button>
          <Button leadingIcon={<Layers3 className="h-4 w-4" />} onClick={onOpenModules} size="sm" variant="outline">
            Модули
          </Button>
        </div>
      </div>
      <div className="divide-y divide-border">
        {selectedDevice ? (
          <div className="px-5 py-4">
            <p className="text-xs font-semibold uppercase text-slate-400">Выбранный агент</p>
            <p className="mt-1 font-semibold text-slate-950">{selectedDevice.hostname || compactId(selectedDevice.device_id)}</p>
            <p className="mt-1 text-sm text-slate-500">Target: {selectedDevice.target || "не определен"}</p>
          </div>
        ) : null}
        {assignments.length === 0 ? (
          <EmptyState icon={Rocket} title="Rollout не настроен" description="Нет активных назначений для targets." />
        ) : (
          assignments.map((assignment) => (
            <div className="grid gap-2 px-5 py-4 md:grid-cols-4" key={`${assignment.target}-${assignment.channel}`}>
              <div>
                <p className="text-xs text-slate-400">Target</p>
                <p className="font-semibold text-slate-950">{assignment.target}</p>
              </div>
              <div>
                <p className="text-xs text-slate-400">Канал</p>
                <p className="text-slate-700">{assignment.channel}</p>
              </div>
              <div>
                <p className="text-xs text-slate-400">Версия</p>
                <p className="text-slate-700">{assignment.version}</p>
              </div>
              <div>
                <p className="text-xs text-slate-400">Обновлено</p>
                <p className="text-slate-700">{formatDateTime(assignment.updated_at)}</p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function AgentDetailsPanel({
  cleanupBusy,
  cleanupFeedback,
  device,
  onCleanupApply,
  onCleanupPreview,
  onOpenAgentUpdates,
  onOpenDeviceCard,
  onOpenPlaybooks,
  request,
  rolloutAssignments,
  tokenSummary,
}: {
  cleanupBusy: boolean;
  cleanupFeedback: string | null;
  device: DeviceItem | null;
  onCleanupApply: () => void;
  onCleanupPreview: () => void;
  onOpenAgentUpdates: () => void;
  onOpenDeviceCard: () => void;
  onOpenPlaybooks: () => void;
  request: AdminConnectionRequestItem | null;
  rolloutAssignments: AdminDevicesPayload["rollout"];
  tokenSummary: { total_count: number; active_count: number; revoked_count: number } | null;
}) {
  if (request) {
    return (
      <Card className="h-fit overflow-hidden">
        <CardHeader className="border-b border-border">
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle>Запрос подключения</CardTitle>
              <p className="mt-1 text-sm text-slate-500">{request.hostname || compactId(request.device_id)}</p>
            </div>
            <Badge tone="warning">Pending</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-5 p-5">
          <DetailRows
            rows={[
              ["Device ID", compactId(request.device_id)],
              ["IP адрес", request.ip_address || "n/a"],
              ["Создан", formatDateTime(request.created_at)],
              ["Статус", request.status],
            ]}
          />
          <div>
            <p className="text-xs font-semibold uppercase text-slate-400">Metadata</p>
            <div className="mt-3 space-y-2">
              {metadataRows(request.metadata).length > 0 ? (
                metadataRows(request.metadata).map(([key, value]) => (
                  <div className="rounded-lg bg-slate-50 px-3 py-2" key={key}>
                    <p className="text-xs font-semibold text-slate-500">{key}</p>
                    <p className="mt-1 break-all text-sm text-slate-800">{value}</p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-500">Метаданные не переданы.</p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="h-fit overflow-hidden">
      <CardHeader className="border-b border-border">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>Свойства агента</CardTitle>
            <p className="mt-1 text-sm text-slate-500">{device?.hostname || "Устройство не выбрано"}</p>
          </div>
          {device ? (
            <Badge tone={device.online ? "success" : "neutral"} withDot>
              {device.online ? "Онлайн" : "Офлайн"}
            </Badge>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-5 p-5">
        {device ? (
          <>
            <DetailRows
              rows={[
                ["Device ID", compactId(device.device_id)],
                ["ОС", getOsLabel(device.os)],
                ["Версия агента", device.agent_version || "n/a"],
                ["Target", device.target || "n/a"],
                ["Последняя активность", formatDateTime(device.last_seen_at)],
                ["Идентификатор", device.identity_summary.source_label],
              ]}
            />

            <div className="grid grid-cols-3 gap-2">
              <MiniMetric label="Токенов" value={String(tokenSummary?.total_count ?? 0)} />
              <MiniMetric label="Активных" value={String(tokenSummary?.active_count ?? 0)} />
              <MiniMetric label="Rollout" value={String(rolloutAssignments.length)} />
            </div>

            {device.duplicate_warning ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                <div className="flex gap-2">
                  <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-600" />
                  <div>
                    <p className="text-sm font-semibold text-amber-950">{device.duplicate_warning.title}</p>
                    <p className="mt-1 text-sm text-amber-800">{device.duplicate_warning.description}</p>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button disabled={cleanupBusy} onClick={onCleanupPreview} size="sm" variant="outline">
                    Проверить
                  </Button>
                  <Button disabled={cleanupBusy} onClick={onCleanupApply} size="sm">
                    Очистить
                  </Button>
                </div>
              </div>
            ) : (
              <div className="rounded-lg border border-emerald-100 bg-emerald-50 p-3 text-sm text-emerald-800">
                Дубли и нестабильные identity не обнаружены.
              </div>
            )}

            {cleanupFeedback ? <p className="text-sm text-slate-600">{cleanupFeedback}</p> : null}

            <div className="space-y-2">
              <Button
                className="w-full justify-start"
                leadingIcon={<DownloadCloud className="h-4 w-4" />}
                onClick={onOpenAgentUpdates}
                size="sm"
              >
                Обновления агента
              </Button>
              <Button
                className="w-full justify-start"
                leadingIcon={<ArrowUpRight className="h-4 w-4" />}
                onClick={onOpenDeviceCard}
                size="sm"
                variant="outline"
              >
                Открыть карточку
              </Button>
              <Button
                className="w-full justify-start"
                leadingIcon={<ClipboardList className="h-4 w-4" />}
                onClick={onOpenPlaybooks}
                size="sm"
                variant="outline"
              >
                Запустить плейбук
              </Button>
            </div>
          </>
        ) : (
          <EmptyState icon={Monitor} title="Нет выбранного агента" description="Выберите строку в таблице." compact />
        )}
      </CardContent>
    </Card>
  );
}

function DetailRows({ rows }: { rows: Array<[string, string]> }) {
  return (
    <div className="space-y-3">
      {rows.map(([label, value]) => (
        <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-3 text-sm" key={label}>
          <p className="text-slate-500">{label}</p>
          <p className="break-words font-medium text-slate-900">{value}</p>
        </div>
      ))}
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function EmptyState({
  compact = false,
  description,
  icon: Icon,
  title,
}: {
  compact?: boolean;
  description: string;
  icon: typeof Activity;
  title: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center px-6 text-center", compact ? "py-6" : "min-h-[280px] py-12")}>
      <div className="flex h-11 w-11 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        <Icon className="h-5 w-5" />
      </div>
      <p className="mt-3 font-semibold text-slate-950">{title}</p>
      <p className="mt-1 max-w-md text-sm text-slate-500">{description}</p>
    </div>
  );
}
