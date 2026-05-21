import { Activity, AlertTriangle, Box, ExternalLink, Fingerprint, HardDrive, MapPin, Monitor, RefreshCw, Server, UserRound, type LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";

import type { SupportTicketInventoryContext } from "../../../features/queues/api";
import type { SupportWorkspaceContext } from "../../../features/queues/support-workspace-model";

type TicketDeviceAgentPanelProps = {
  deviceContext?: SupportWorkspaceContext["device"] | null;
  inventoryContext?: SupportTicketInventoryContext | null;
};

function valueOrDash(value: unknown): string {
  const text = String(value ?? "").trim();
  return text || "—";
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

function freshnessLabel(freshness: string | null | undefined): string {
  if (freshness === "fresh") {
    return "Актуальна";
  }
  if (freshness === "stale") {
    return "Устарела";
  }
  if (freshness === "missing") {
    return "Нет данных";
  }
  return "Неизвестно";
}

function agentStateLabel(state: string | null | undefined, fallbackOnline?: boolean): string {
  if (state === "online") {
    return "online";
  }
  if (state === "offline") {
    return "offline";
  }
  if (fallbackOnline === true) {
    return "online";
  }
  if (fallbackOnline === false) {
    return "offline";
  }
  return "unknown";
}

function signalBadges(context: SupportTicketInventoryContext | null | undefined): string[] {
  const signals = context?.signals;
  return [
    signals?.stale_inventory ? "Инвентаризация устарела" : null,
    signals?.missing_inventory ? "Инвентаризация отсутствует" : null,
    signals?.agent_offline ? "Агент offline" : null,
    signals?.failed_recent_refresh ? "Последнее обновление не удалось" : null,
    signals?.failed_recent_operation ? "Есть неуспешные операции" : null,
  ].filter((item): item is string => Boolean(item));
}

function InfoRow({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: unknown;
}) {
  return (
    <div className="grid grid-cols-[18px_minmax(0,0.9fr)_minmax(0,1.1fr)] items-start gap-2 text-sm">
      <Icon className="mt-0.5 h-4 w-4 text-slate-500" />
      <dt className="text-slate-500">{label}</dt>
      <dd className="min-w-0 break-words text-right font-medium text-slate-200">{valueOrDash(value)}</dd>
    </div>
  );
}

export function TicketDeviceAgentPanel({ deviceContext, inventoryContext }: TicketDeviceAgentPanelProps) {
  const deviceId = inventoryContext?.device_id ?? deviceContext?.id ?? null;
  const hostname = inventoryContext?.hostname ?? inventoryContext?.display_name ?? deviceContext?.hostname ?? "—";
  const agentState = agentStateLabel(inventoryContext?.agent?.connection_state, deviceContext?.online);
  const warnings = signalBadges(inventoryContext);
  const inventory = inventoryContext?.inventory ?? null;
  const binding = inventoryContext?.binding ?? null;
  const refresh = inventoryContext?.refresh ?? null;
  const tags = binding?.tags?.length ? binding.tags.join(", ") : null;
  const deviceUrl = deviceId ? `/app/admin/device?device=${encodeURIComponent(deviceId)}` : null;
  const inventoryUrl = deviceId ? `/app/admin/inventory?device=${encodeURIComponent(deviceId)}` : "/app/admin/inventory";

  return (
    <section className="rounded-xl border border-white/10 bg-[#111f33] p-4" data-testid="ticket-device-agent-panel">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Контекст устройства</p>
          <p className="mt-2 font-semibold text-white">{hostname}</p>
          <p className="mt-1 break-all text-xs text-slate-500">device_id: {valueOrDash(deviceId)}</p>
        </div>
        <span className={agentState === "online" ? "text-xs font-semibold text-emerald-300" : "text-xs font-semibold text-red-300"}>
          {agentState}
        </span>
      </div>

      {warnings.length ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {warnings.map((warning) => (
            <span className="inline-flex items-center gap-1 rounded-full border border-amber-300/30 bg-amber-500/10 px-2 py-1 text-xs font-semibold text-amber-200" key={warning}>
              <AlertTriangle className="h-3 w-3" />
              {warning}
            </span>
          ))}
        </div>
      ) : null}

      {inventoryContext ? (
        <div className="mt-4 space-y-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Агент</p>
            <dl className="mt-2 grid gap-2">
              <InfoRow icon={Activity} label="Состояние" value={agentState} />
              <InfoRow icon={Server} label="Версия" value={inventoryContext.agent?.version ?? deviceContext?.os} />
              <InfoRow icon={RefreshCw} label="Обновления" value={inventoryContext.agent?.update_status} />
              <InfoRow icon={Monitor} label="Последний вход" value={formatDateTime(inventoryContext.agent?.last_seen_at ?? deviceContext?.lastSeenLabel)} />
            </dl>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Инвентаризация</p>
            <dl className="mt-2 grid gap-2">
              <InfoRow icon={HardDrive} label="Свежесть" value={freshnessLabel(inventory?.freshness)} />
              <InfoRow icon={RefreshCw} label="Последний снимок" value={formatDateTime(inventory?.collected_at)} />
              <InfoRow icon={Box} label="Источник" value={inventory?.source} />
              <InfoRow icon={Fingerprint} label="snapshot_id" value={inventory?.latest_snapshot_id} />
            </dl>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Привязка</p>
            <dl className="mt-2 grid gap-2">
              <InfoRow icon={UserRound} label="Ответственный" value={binding?.responsible_person} />
              <InfoRow icon={Box} label="Отдел" value={binding?.department} />
              <InfoRow icon={MapPin} label="Здание" value={binding?.building} />
              <InfoRow icon={MapPin} label="Кабинет" value={binding?.room} />
              <InfoRow icon={Activity} label="Статус" value={binding?.status} />
              <InfoRow icon={Box} label="Теги" value={tags} />
            </dl>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Обновление</p>
            <dl className="mt-2 grid gap-2">
              <InfoRow icon={RefreshCw} label="Последний запуск" value={formatDateTime(refresh?.last_run_at)} />
              <InfoRow icon={Activity} label="Статус запуска" value={refresh?.last_run_status} />
              <InfoRow icon={RefreshCw} label="Следующий запуск" value={formatDateTime(refresh?.next_due_at)} />
              <InfoRow icon={Box} label="run_id" value={refresh?.last_run_id} />
            </dl>
          </div>
        </div>
      ) : (
        <p className="mt-4 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-slate-400">
          Нет данных инвентаризации для этого тикета.
        </p>
      )}

      <div className="mt-4 grid gap-2">
        {deviceUrl ? (
          <Link className="inline-flex items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-semibold text-slate-100 hover:border-brand-300/50 hover:text-brand-100" to={deviceUrl}>
            <ExternalLink className="h-4 w-4" />
            Открыть карточку устройства
          </Link>
        ) : null}
        <Link className="inline-flex items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-semibold text-slate-100 hover:border-brand-300/50 hover:text-brand-100" to={inventoryUrl}>
          <ExternalLink className="h-4 w-4" />
          Открыть Inventory
        </Link>
        <button
          className="inline-flex cursor-not-allowed items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2 text-sm font-semibold text-slate-500"
          disabled
          title="Запуск инвентаризации доступен из карточки Inventory с проверкой прав."
          type="button"
        >
          <RefreshCw className="h-4 w-4" />
          Обновить инвентаризацию
        </button>
      </div>
    </section>
  );
}
