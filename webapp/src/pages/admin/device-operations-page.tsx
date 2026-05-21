import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Box,
  ClipboardList,
  MonitorCog,
  Radio,
  RefreshCcw,
  ShieldAlert,
  Wrench,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { startTransition, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { Tabs } from "../../components/ui/tabs";
import { collectAdminDeviceInventory } from "../../features/admin/api";
import { fetchDeviceOperations } from "../../features/device-operations/api";
import type { DeviceOperationsPayload } from "../../features/device-operations/types";

type Tone = "danger" | "info" | "neutral" | "success" | "warning";

const tabs = [
  { value: "overview", label: "Обзор" },
  { value: "inventory", label: "Инвентаризация" },
  { value: "agent", label: "Агент и обновления" },
  { value: "modules", label: "Модули" },
  { value: "operations", label: "Outbox и операции" },
  { value: "observer", label: "Observer" },
  { value: "remote", label: "Remote Assist" },
  { value: "auth", label: "Provisioning / авторизация" },
];

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "Нет данных";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) {
    return "Нет данных";
  }
  if (seconds < 3600) {
    return `${Math.round(seconds / 60)} мин.`;
  }
  if (seconds < 86_400) {
    return `${Math.round(seconds / 3600)} ч.`;
  }
  return `${Math.round(seconds / 86_400)} дн.`;
}

function connectionLabel(value: string): string {
  if (value === "online") {
    return "Онлайн";
  }
  if (value === "offline") {
    return "Офлайн";
  }
  return "Неизвестно";
}

function freshnessLabel(value: string): string {
  if (value === "fresh") {
    return "Актуальна";
  }
  if (value === "stale") {
    return "Устарела";
  }
  if (value === "missing") {
    return "Нет данных";
  }
  return "Неизвестно";
}

function remoteAssistLabel(value: string): string {
  if (value === "available") {
    return "Доступна";
  }
  if (value === "requires_consent") {
    return "Требуется согласие";
  }
  if (value === "offline") {
    return "Офлайн";
  }
  if (value === "unavailable") {
    return "Недоступна";
  }
  return "Неизвестно";
}

function toneForState(value: string | null | undefined): Tone {
  const normalized = String(value ?? "").toLowerCase();
  if (["ok", "active", "fresh", "online", "available", "up_to_date", "synced"].includes(normalized)) {
    return "success";
  }
  if (["running", "queued", "pending", "sent", "requested", "requires_consent", "warning", "outdated"].includes(normalized)) {
    return "warning";
  }
  if (["failed", "error", "offline", "stale", "missing", "timed_out", "unknown", "unavailable"].includes(normalized)) {
    return "danger";
  }
  return "neutral";
}

function summaryEntries(value: DeviceOperationsPayload["inventory"]["summary"]): Array<[string, string]> {
  if (!value) {
    return [];
  }
  if (typeof value === "string") {
    return [["Сводка", value]];
  }
  return Object.entries(value)
    .slice(0, 8)
    .map(([key, item]) => [key, typeof item === "string" || typeof item === "number" || typeof item === "boolean" ? String(item) : "структура"]);
}

function StatCard({
  description,
  icon,
  title,
  tone,
  value,
}: {
  description: string;
  icon: ReactNode;
  title: string;
  tone: Tone;
  value: string;
}) {
  return (
    <Card className="min-w-0">
      <CardContent className="flex min-w-0 items-start gap-3 p-4">
        <span className="rounded-xl bg-surface-subtle p-2 text-brand-700">{icon}</span>
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{title}</p>
          <div className="mt-2">
            <Badge tone={tone} withDot>
              {value}
            </Badge>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-500">{description}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function FieldRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="grid gap-1 border-b border-border/70 py-2 text-sm last:border-b-0 sm:grid-cols-[180px_minmax(0,1fr)]">
      <span className="text-slate-500">{label}</span>
      <span className="min-w-0 break-words font-medium text-slate-900">{value || "Нет данных"}</span>
    </div>
  );
}

function EmptyState({ children }: { children: ReactNode }) {
  return <div className="rounded-xl border border-dashed border-border bg-surface-subtle px-4 py-6 text-sm text-slate-500">{children}</div>;
}

function ExternalLinkButton({ href, label }: { href: string | null | undefined; label: string }) {
  if (!href) {
    return null;
  }
  return (
    <Link className="inline-flex items-center gap-2 text-sm font-semibold text-brand-700 hover:text-brand-900" to={href}>
      {label}
      <ArrowUpRight className="h-4 w-4" />
    </Link>
  );
}

function OverviewTab({ data }: { data: DeviceOperationsPayload }) {
  const risks = [
    data.signals.agent_offline ? "Агент offline" : null,
    data.signals.stale_inventory ? "Инвентаризация устарела" : null,
    data.signals.missing_inventory ? "Инвентаризация отсутствует" : null,
    data.signals.update_available ? "Доступно обновление агента" : null,
    data.signals.module_reconcile_failed ? "Есть ошибки модулей" : null,
    data.signals.failed_recent_operation ? "Есть ошибки операций" : null,
    data.signals.observer_errors ? "Observer нашёл ошибки" : null,
    data.signals.auth_error ? "Ошибка авторизации агента" : null,
  ].filter(Boolean);
  const latestFailedOperation = data.operations.items.find((item) => ["failed", "timed_out"].includes(item.status ?? ""));
  const latestTraceError = data.observer.items.find((item) => item.error_summary || ["failed", "error"].includes(item.status ?? ""));

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>{data.device.display_name ?? data.device.hostname ?? data.device.device_id}</CardTitle>
            <CardDescription>{data.device.os_name ?? data.device.platform ?? "ОС не определена"}</CardDescription>
          </CardHeader>
          <CardContent>
            <FieldRow label="device_id" value={data.device.device_id} />
            <FieldRow label="Hostname" value={data.device.hostname} />
            <FieldRow label="Платформа" value={data.device.platform} />
            <FieldRow label="Последний контакт" value={formatDateTime(data.device.last_seen_at)} />
            <FieldRow label="Ответственный" value={data.binding?.responsible_person} />
            <FieldRow label="Локация" value={[data.binding?.building, data.binding?.room].filter(Boolean).join(" / ")} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Текущие риски</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {risks.length ? (
              risks.map((risk) => (
                <Badge key={risk} tone="warning" withDot>
                  {risk}
                </Badge>
              ))
            ) : (
              <p className="text-sm text-slate-500">Критичные сигналы по устройству не обнаружены.</p>
            )}
          </CardContent>
        </Card>

        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Последняя ошибка операции</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {latestFailedOperation ? (
                <>
                  <p className="font-semibold text-slate-900">{latestFailedOperation.tool_name ?? latestFailedOperation.id}</p>
                  <p className="text-slate-500">{latestFailedOperation.error_summary ?? "Ошибка без описания"}</p>
                  {latestFailedOperation.ticket_id ? <ExternalLinkButton href={`/app/tickets/${latestFailedOperation.ticket_id}`} label="Открыть тикет" /> : null}
                </>
              ) : (
                <EmptyState>Ошибки операций по устройству не найдены.</EmptyState>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Последняя ошибка Observer</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {latestTraceError ? (
                <>
                  <p className="font-semibold text-slate-900">{latestTraceError.title ?? latestTraceError.trace_id}</p>
                  <p className="text-slate-500">{latestTraceError.error_summary ?? latestTraceError.status}</p>
                  <ExternalLinkButton href={`/app/admin/observer?trace_id=${encodeURIComponent(latestTraceError.trace_id)}`} label="Открыть трассу" />
                </>
              ) : (
                <EmptyState>Ошибки Observer по устройству не найдены.</EmptyState>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Быстрые переходы</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <ExternalLinkButton href={data.links.inventory} label="Открыть Inventory" />
          <ExternalLinkButton href={data.links.device_card} label="Открыть карточку устройства" />
          <ExternalLinkButton href={data.links.agent_updates} label="Открыть обновления агента" />
          <ExternalLinkButton href={data.links.modules} label="Открыть модули" />
          <ExternalLinkButton href={data.links.observer} label="Открыть Observer" />
          <ExternalLinkButton href={data.links.tickets} label="Тикеты по устройству" />
        </CardContent>
      </Card>
    </div>
  );
}

function InventoryTab({ data }: { data: DeviceOperationsPayload }) {
  const entries = summaryEntries(data.inventory.summary);
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <Card>
        <CardHeader>
          <CardTitle>Инвентаризация</CardTitle>
          <CardDescription>Последний компактный snapshot без raw JSON.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {data.inventory.freshness === "missing" ? (
            <EmptyState>Инвентаризация ещё не получена.</EmptyState>
          ) : (
            <>
              <FieldRow label="Snapshot" value={data.inventory.latest_snapshot_id} />
              <FieldRow label="Собрано" value={formatDateTime(data.inventory.collected_at)} />
              <FieldRow label="Возраст" value={formatDuration(data.inventory.age_seconds)} />
              <FieldRow label="Свежесть" value={freshnessLabel(data.inventory.freshness)} />
              {entries.length ? entries.map(([key, value]) => <FieldRow key={key} label={key} value={value} />) : <EmptyState>Сводка snapshot отсутствует.</EmptyState>}
            </>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Привязка и refresh policy</CardTitle>
        </CardHeader>
        <CardContent>
          <FieldRow label="Отдел" value={data.binding?.department} />
          <FieldRow label="Ответственный" value={data.binding?.responsible_person} />
          <FieldRow label="Инв. номер" value={data.binding?.inventory_number} />
          <FieldRow label="Refresh включён" value={data.inventory.refresh_policy?.enabled ? "Да" : "Нет"} />
          <FieldRow label="Интервал" value={data.inventory.refresh_policy?.interval_minutes ? `${data.inventory.refresh_policy.interval_minutes} мин.` : null} />
          <FieldRow label="Последний refresh" value={data.inventory.latest_refresh_run?.status} />
          <ExternalLinkButton href={data.links.inventory} label="Открыть полный Inventory" />
        </CardContent>
      </Card>
    </div>
  );
}

function AgentTab({ data }: { data: DeviceOperationsPayload }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Агент и обновления</CardTitle>
        <CardDescription>Версия, протокол, toolset и update-состояние.</CardDescription>
      </CardHeader>
      <CardContent>
        <FieldRow label="Состояние" value={connectionLabel(data.agent.connection_state)} />
        <FieldRow label="Последний контакт" value={formatDateTime(data.agent.last_seen_at)} />
        <FieldRow label="Версия агента" value={data.agent.version} />
        <FieldRow label="Protocol" value={data.agent.protocol} />
        <FieldRow label="Capabilities" value={data.agent.capabilities_count ?? "Нет данных"} />
        <FieldRow label="Toolset hash" value={data.agent.toolset_hash} />
        <FieldRow label="Desired revision" value={data.agent.desired_revision} />
        <FieldRow label="Current revision" value={data.agent.current_revision} />
        <FieldRow label="Config status" value={data.agent.config_status} />
        <FieldRow label="Update status" value={data.agent.update_status} />
        <FieldRow label="Доступно обновление" value={data.agent.update_available ? "Да" : "Нет"} />
        <FieldRow label="Ожидает restart" value={data.agent.pending_restart ? "Да" : "Нет"} />
        <div className="pt-4">
          <ExternalLinkButton href={data.links.agent_updates} label="Открыть Agent Updates" />
        </div>
      </CardContent>
    </Card>
  );
}

function ModulesTab({ data }: { data: DeviceOperationsPayload }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Модули</CardTitle>
        <CardDescription>Actual/desired reconcile по устройству.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-4">
          <Badge tone={toneForState(data.modules.reconcile_state)} withDot>{data.modules.reconcile_state ?? "unknown"}</Badge>
          <span className="text-sm text-slate-500">Всего: {data.modules.module_count ?? 0}</span>
          <span className="text-sm text-slate-500">Missing: {data.modules.missing_count ?? 0}</span>
          <span className="text-sm text-slate-500">Outdated: {data.modules.outdated_count ?? 0}</span>
        </div>
        {data.modules.items.length ? (
          <div className="divide-y divide-border rounded-xl border border-border">
            {data.modules.items.map((item) => (
              <div className="grid gap-2 p-4 md:grid-cols-[minmax(0,1fr)_160px_160px_120px]" key={item.module_id}>
                <div className="min-w-0">
                  <p className="break-words font-semibold text-slate-900">{item.name ?? item.module_id}</p>
                  {item.last_error ? <p className="mt-1 text-sm text-rose-600">{item.last_error}</p> : null}
                </div>
                <span className="text-sm text-slate-500">Установлено: {item.installed_version ?? "нет"}</span>
                <span className="text-sm text-slate-500">Desired: {item.desired_version ?? "нет"}</span>
                <Badge tone={toneForState(item.state)}>{item.state ?? "unknown"}</Badge>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState>Данные о модулях отсутствуют.</EmptyState>
        )}
        <ExternalLinkButton href={data.links.modules} label="Открыть Modules" />
      </CardContent>
    </Card>
  );
}

function OperationsTab({ data }: { data: DeviceOperationsPayload }) {
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Outbox</CardTitle>
          <CardDescription>Очередь команд устройства.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Badge tone={data.outbox.pending_count ? "warning" : "success"}>Pending: {data.outbox.pending_count}</Badge>
            <Badge tone={data.outbox.failed_count ? "danger" : "success"}>Failed: {data.outbox.failed_count}</Badge>
          </div>
          {data.outbox.items.length ? (
            data.outbox.items.map((item) => (
              <div className="rounded-xl border border-border p-3 text-sm" key={item.id}>
                <p className="font-semibold text-slate-900">{item.command_type ?? item.id}</p>
                <p className="text-slate-500">{item.status ?? "unknown"} · {formatDateTime(item.created_at)}</p>
                {item.error_summary ? <p className="mt-1 text-rose-600">{item.error_summary}</p> : null}
              </div>
            ))
          ) : (
            <EmptyState>Очередь команд пуста.</EmptyState>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Операции</CardTitle>
          <CardDescription>Последние tool/playbook/remote операции.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Badge tone={data.operations.recent_running_count ? "info" : "neutral"}>Running: {data.operations.recent_running_count}</Badge>
            <Badge tone={data.operations.recent_failed_count ? "danger" : "success"}>Failed: {data.operations.recent_failed_count}</Badge>
          </div>
          {data.operations.items.length ? (
            data.operations.items.map((item) => (
              <div className="rounded-xl border border-border p-3 text-sm" key={item.id}>
                <p className="font-semibold text-slate-900">{item.tool_name ?? item.id}</p>
                <p className="text-slate-500">{item.status ?? "unknown"} · {formatDateTime(item.started_at)}</p>
                {item.error_summary ? <p className="mt-1 text-rose-600">{item.error_summary}</p> : null}
                <div className="mt-2 flex flex-wrap gap-3">
                  {item.ticket_id ? <ExternalLinkButton href={`/app/tickets/${item.ticket_id}`} label="Открыть тикет" /> : null}
                  {item.trace_id ? <ExternalLinkButton href={`/app/admin/observer?trace_id=${encodeURIComponent(item.trace_id)}`} label="Открыть трассу" /> : null}
                </div>
              </div>
            ))
          ) : (
            <EmptyState>Операции по устройству не найдены.</EmptyState>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ObserverTab({ data }: { data: DeviceOperationsPayload }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Трассы Observer</CardTitle>
        <CardDescription>Последние трассы, связанные с device_id.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Badge tone={data.observer.items.some((item) => item.error_summary) ? "danger" : "neutral"}>Трасс: {data.observer.trace_count ?? 0}</Badge>
        {data.observer.items.length ? (
          data.observer.items.map((item) => (
            <div className="rounded-xl border border-border p-3 text-sm" key={item.trace_id}>
              <p className="font-semibold text-slate-900">{item.title ?? item.trace_id}</p>
              <p className="text-slate-500">{item.status ?? "unknown"} · {formatDateTime(item.started_at)}</p>
              {item.error_summary ? <p className="mt-1 text-rose-600">{item.error_summary}</p> : null}
              <ExternalLinkButton href={`/app/admin/observer?trace_id=${encodeURIComponent(item.trace_id)}`} label="Открыть трассу" />
            </div>
          ))
        ) : (
          <EmptyState>Трассы по устройству не найдены.</EmptyState>
        )}
      </CardContent>
    </Card>
  );
}

function RemoteTab({ data }: { data: DeviceOperationsPayload }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Удалённая помощь</CardTitle>
        <CardDescription>Доступность Remote Assist без обхода consent workflow.</CardDescription>
      </CardHeader>
      <CardContent>
        <FieldRow label="Доступность" value={remoteAssistLabel(data.remote_assist.availability)} />
        <FieldRow label="Причина" value={data.remote_assist.reason} />
        <FieldRow label="Активная сессия" value={data.remote_assist.active_session_id} />
        <FieldRow label="Ожидает согласия" value={data.remote_assist.pending_consent_id} />
        <FieldRow label="Последняя сессия" value={formatDateTime(data.remote_assist.last_session_at)} />
        <p className="pt-4 text-sm text-slate-500">Запуск Remote Assist доступен только из тикета с реальным consent workflow.</p>
      </CardContent>
    </Card>
  );
}

function AuthTab({ data }: { data: DeviceOperationsPayload }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Provisioning / авторизация</CardTitle>
        <CardDescription>Connection request, token state и последние auth ошибки.</CardDescription>
      </CardHeader>
      <CardContent>
        <FieldRow label="Provisioning state" value={data.provisioning?.state} />
        <FieldRow label="Auth state" value={data.provisioning?.auth_state} />
        <FieldRow label="Token status" value={data.provisioning?.token_status} />
        <FieldRow label="Connection request" value={data.provisioning?.connection_request_id} />
        <FieldRow label="Последняя ошибка" value={data.provisioning?.last_error} />
        <FieldRow label="Время ошибки" value={formatDateTime(data.provisioning?.last_error_at)} />
        <p className="pt-4 text-sm text-slate-500">Approve/reject не выведены здесь как прямые действия: используйте существующий provisioning flow.</p>
      </CardContent>
    </Card>
  );
}

function renderTab(tab: string, data: DeviceOperationsPayload) {
  if (tab === "inventory") return <InventoryTab data={data} />;
  if (tab === "agent") return <AgentTab data={data} />;
  if (tab === "modules") return <ModulesTab data={data} />;
  if (tab === "operations") return <OperationsTab data={data} />;
  if (tab === "observer") return <ObserverTab data={data} />;
  if (tab === "remote") return <RemoteTab data={data} />;
  if (tab === "auth") return <AuthTab data={data} />;
  return <OverviewTab data={data} />;
}

export function AdminDeviceOperationsPage() {
  const params = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("overview");
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const deviceId = params.deviceId ?? searchParams.get("device_id") ?? searchParams.get("device") ?? "";

  const query = useQuery({
    queryKey: ["device-operations", deviceId],
    queryFn: () => fetchDeviceOperations(deviceId, { trace_limit: 10, outbox_limit: 20, operation_limit: 20 }),
    enabled: Boolean(deviceId),
    retry: false,
  });

  const collectMutation = useMutation({
    mutationFn: () => collectAdminDeviceInventory(deviceId),
    onSuccess: async () => {
      setActionMessage("Запрос инвентаризации отправлен.");
      await queryClient.invalidateQueries({ queryKey: ["device-operations", deviceId] });
    },
    onError: (error) => {
      setActionMessage(error instanceof Error ? error.message : "Не удалось запросить инвентаризацию.");
    },
  });

  const data = query.data;
  const healthCards = useMemo(() => {
    if (!data) return [];
    return [
      {
        title: "Агент",
        value: connectionLabel(data.agent.connection_state),
        tone: toneForState(data.agent.connection_state),
        description: `Последний контакт: ${formatDateTime(data.agent.last_seen_at)}`,
        icon: <Radio className="h-5 w-5" />,
      },
      {
        title: "Инвентаризация",
        value: freshnessLabel(data.inventory.freshness),
        tone: toneForState(data.inventory.freshness),
        description: `Возраст: ${formatDuration(data.inventory.age_seconds)}`,
        icon: <ClipboardList className="h-5 w-5" />,
      },
      {
        title: "Обновление",
        value: data.agent.update_available ? "Доступно" : data.agent.update_status ?? "Нет сигнала",
        tone: data.agent.update_available ? "warning" : toneForState(data.agent.update_status ?? "ok"),
        description: data.agent.pending_restart ? "Ожидается restart агента" : "Без прямого действия из workspace",
        icon: <RefreshCcw className="h-5 w-5" />,
      },
      {
        title: "Модули",
        value: data.modules.reconcile_state ?? "unknown",
        tone: toneForState(data.modules.reconcile_state),
        description: `Missing ${data.modules.missing_count ?? 0}, outdated ${data.modules.outdated_count ?? 0}, failed ${data.modules.failed_count ?? 0}`,
        icon: <Box className="h-5 w-5" />,
      },
      {
        title: "Outbox",
        value: data.outbox.pending_count ? `${data.outbox.pending_count} pending` : "Пусто",
        tone: data.outbox.failed_count ? "danger" : data.outbox.pending_count ? "warning" : "success",
        description: `Ошибок доставки: ${data.outbox.failed_count}`,
        icon: <Wrench className="h-5 w-5" />,
      },
      {
        title: "Операции",
        value: data.operations.recent_failed_count ? `${data.operations.recent_failed_count} failed` : "Без ошибок",
        tone: data.operations.recent_failed_count ? "danger" : "success",
        description: `Running: ${data.operations.recent_running_count}`,
        icon: <Activity className="h-5 w-5" />,
      },
      {
        title: "Remote Assist",
        value: remoteAssistLabel(data.remote_assist.availability),
        tone: toneForState(data.remote_assist.availability),
        description: data.remote_assist.reason ?? "Нет данных",
        icon: <MonitorCog className="h-5 w-5" />,
      },
    ] satisfies Array<{ description: string; icon: ReactNode; title: string; tone: Tone; value: string }>;
  }, [data]);

  if (!deviceId) {
    return (
      <section className="space-y-6">
        <PageHeading
          description="Передайте device_id в path или query, чтобы открыть рабочее пространство устройства."
          eyebrow="Admin"
          title="Операции устройства"
        />
        <EmptyState>device_id не указан.</EmptyState>
      </section>
    );
  }

  return (
    <section className="space-y-6">
      <PageHeading
        actions={
          <>
            <Button leadingIcon={<RefreshCcw className="h-4 w-4" />} onClick={() => void query.refetch()} size="sm" variant="outline">
              Обновить данные
            </Button>
            {data?.inventory.can_request_refresh ? (
              <Button
                disabled={collectMutation.isPending}
                leadingIcon={<ClipboardList className="h-4 w-4" />}
                onClick={() => collectMutation.mutate()}
                size="sm"
              >
                Запросить инвентаризацию
              </Button>
            ) : null}
            <Button
              leadingIcon={<ArrowUpRight className="h-4 w-4" />}
              onClick={() => {
                startTransition(() => navigate(`/app/admin/device?device=${encodeURIComponent(deviceId)}`));
              }}
              size="sm"
              variant="outline"
            >
              Открыть карточку устройства
            </Button>
          </>
        }
        description="Инвентаризация, агент, обновления, модули, outbox, трассы и удалённая помощь в одном месте."
        eyebrow="Admin"
        title="Операции устройства"
      />

      {query.isLoading ? <p className="text-sm text-slate-500">Загружаем состояние устройства...</p> : null}
      {query.isError ? (
        <Card>
          <CardContent className="flex items-start gap-3 p-5 text-sm text-rose-700">
            <ShieldAlert className="mt-0.5 h-5 w-5" />
            <span>{query.error instanceof Error ? query.error.message : "Не удалось загрузить операции устройства."}</span>
          </CardContent>
        </Card>
      ) : null}

      {actionMessage ? (
        <div className="rounded-xl border border-border bg-surface-subtle px-4 py-3 text-sm text-slate-700">{actionMessage}</div>
      ) : null}

      {data ? (
        <>
          <Card>
            <CardContent className="flex flex-wrap items-center justify-between gap-4 p-5">
              <div className="min-w-0">
                <p className="break-words text-2xl font-semibold text-slate-950">{data.device.display_name ?? data.device.hostname ?? data.device.device_id}</p>
                <p className="mt-1 break-all text-sm text-slate-500">device_id: {data.device.device_id}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge tone={toneForState(data.agent.connection_state)} withDot>{connectionLabel(data.agent.connection_state)}</Badge>
                <Badge tone={toneForState(data.inventory.freshness)}>{freshnessLabel(data.inventory.freshness)}</Badge>
                {data.signals.update_available ? <Badge tone="warning">Доступно обновление</Badge> : null}
                {data.signals.failed_recent_operation ? <Badge tone="danger">Ошибки операций</Badge> : null}
                {data.signals.auth_error || data.signals.provisioning_error ? <Badge tone="danger">Provisioning / auth</Badge> : null}
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {healthCards.map((item) => (
              <StatCard key={item.title} {...item} />
            ))}
          </div>

          {(data.signals.auth_error || data.signals.provisioning_error || data.signals.observer_errors) ? (
            <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
              <span>Есть сигналы, требующие проверки: auth/provisioning, Observer или ошибки операций.</span>
            </div>
          ) : null}

          <Tabs items={tabs} onValueChange={setActiveTab} value={activeTab} />
          {renderTab(activeTab, data)}
        </>
      ) : null}
    </section>
  );
}
