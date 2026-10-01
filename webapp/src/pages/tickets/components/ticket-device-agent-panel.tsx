import { Link } from "react-router-dom";
import type { SupportTicketInventoryContext } from "../../../features/queues/api";
import type { SupportWorkspaceContext } from "../../../features/queues/support-workspace-model";
import { RegistryContext, contextDate } from "../../../features/admin/endpoint-context-view";
import { ContextSnapshotContent } from "../../../features/admin/endpoint-profile-content";

type TicketDeviceAgentPanelProps = {
  deviceContext?: SupportWorkspaceContext["device"] | null;
  inventoryContext?: SupportTicketInventoryContext | null;
};

export function TicketDeviceAgentPanel({ inventoryContext }: TicketDeviceAgentPanelProps) {
  const context = inventoryContext?.context;
  const inventory = context?.snapshots.find((snapshot) => snapshot.profile === "inventory_v1");
  return <section className="rounded-xl border border-white/10 p-4">
    <h3 className="text-base font-semibold">Устройство · Endpoint</h3>
    {context ? <>
      <p>{context.device.display_name} · {context.device.online && !context.device.retired_at ? "ONLINE" : "OFFLINE"}</p>
      <p>Последняя связь: {contextDate(context.device.last_seen_at)}</p>
      {inventory ? <ContextSnapshotContent snapshot={inventory} /> : <p>Inventory snapshot отсутствует.</p>}
      {inventoryContext?.registry ? <RegistryContext registry={inventoryContext.registry} /> : null}
      <Link to={`/app/admin/device?device=${encodeURIComponent(context.device.id)}`}>Открыть карточку устройства</Link>
    </> : <p>UNKNOWN · {inventoryContext?.status === "unmapped" ? "Нет подтверждённой привязки Endpoint" : "Endpoint context недоступен"}</p>}
    <Link className="mt-3 block" to="/app/admin/inventory">Открыть устройства</Link>
  </section>;
}
