import { Link } from "react-router-dom";
import type { SupportTicketDetailPayload, SupportTicketInventoryContext } from "../../../features/queues/api";
import type { SupportWorkspaceContext } from "../../../features/queues/support-workspace-model";
import { RegistryContext, contextDate } from "../../../features/admin/endpoint-context-view";
import { ContextSnapshotContent } from "../../../features/admin/endpoint-profile-content";

type TicketDeviceAgentPanelProps = {
  deviceContext?: SupportWorkspaceContext["device"] | null;
  inventoryContext?: SupportTicketInventoryContext | null;
  deviceSnapshot?: SupportTicketDetailPayload["snapshot"]["device"] | null;
};

export function TicketDeviceAgentPanel({ inventoryContext, deviceContext, deviceSnapshot }: TicketDeviceAgentPanelProps) {
  const context = inventoryContext?.context;
  const inventory = context?.snapshots.find((snapshot) => snapshot.profile === "inventory_v1");
  const device = context?.device;
  const hasDevice = Boolean(device || deviceSnapshot?.device_id || deviceContext?.id);
  const connection = device ? (device.retired_at ? "Устройство выведено из эксплуатации" : device.online ? "В сети" : "Не в сети")
    : deviceSnapshot?.connection_state === "unknown" || !hasDevice ? "Неизвестно" : (deviceSnapshot?.online ?? deviceContext?.online) ? "В сети" : "Не в сети";
  const missingContext = inventoryContext?.status === "unmapped" ? "Нет подтверждённой привязки Endpoint"
    : inventoryContext?.status === "unavailable" ? "Контекст устройства временно недоступен"
    : !hasDevice ? "Устройство не указано. Обращение можно обработать без агента." : "Подробный контекст устройства пока не получен";
  return <section className="rounded-xl border border-white/10 p-4">
    <h3 className="text-base font-semibold">Устройство и агент</h3>
    {hasDevice ? <p className="mt-2 font-semibold">{device?.display_name ?? deviceSnapshot?.hostname ?? deviceContext?.hostname}</p> : null}
    <dl className="mt-3 grid gap-2 text-sm">
      <div><dt className="text-xs text-slate-500">Соединение</dt><dd>{connection}</dd></div>
      <div><dt className="text-xs text-slate-500">Последняя связь</dt><dd>{contextDate(device?.last_seen_at ?? deviceSnapshot?.last_seen_at)}</dd></div>
      <div><dt className="text-xs text-slate-500">Версия агента</dt><dd>{deviceSnapshot?.agent_version || "Нет данных"}</dd></div>
      <div><dt className="text-xs text-slate-500">Версия загрузчика</dt><dd>Нет данных</dd></div>
    </dl>
    {deviceContext?.assetId ? <details className="mt-3 text-sm"><summary className="cursor-pointer">Привязка устройства</summary><p>{deviceContext.assetTypeLabel}</p><p>{deviceContext.assetId}</p></details> : null}
    {context ? <>
      {inventory ? <details className="mt-3"><summary className="cursor-pointer text-sm font-semibold">Характеристики устройства</summary><ContextSnapshotContent snapshot={inventory} /></details> : <p className="mt-3 text-sm text-slate-500">Характеристики устройства пока не получены.</p>}
      {inventoryContext?.registry ? <RegistryContext registry={inventoryContext.registry} /> : null}
      <Link to={`/app/admin/device?device=${encodeURIComponent(context.device.id)}`}>Открыть карточку устройства</Link>
    </> : <p className="mt-3 text-sm text-slate-500">{missingContext}</p>}
    <Link className="mt-3 block" to="/app/admin/inventory">Открыть устройства</Link>
  </section>;
}
