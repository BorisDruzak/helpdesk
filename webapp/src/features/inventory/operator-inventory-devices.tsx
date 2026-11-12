import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listTicketCapabilityReadiness } from "../capabilities/api";
import { contextDate } from "../admin/endpoint-context-view";

type Props = { ticketId: string; personId?: never } | { personId: string; ticketId?: never };

type Assignment = {
  assignment_id: string;
  name?: string | null;
  inventory_number?: string | null;
  os_name?: string | null;
  role: "primary" | "shared";
  endpoint_binding_state: "confirmed" | "review" | "unbound";
  endpoint_status: "online" | "offline" | "unknown" | "not_detected";
  agent_version?: string | null;
  last_seen_at?: string | null;
  diagnostic_target: boolean;
  inventory_url?: string | null;
  workstation_url?: string | null;
};

type Inventory = {
  sync_state: "disabled" | "unlinked" | "unavailable" | "stale" | "current";
  assignments: Assignment[];
};

const presenceLabel = {
  online: "Агент в сети",
  offline: "Агент не в сети",
  unknown: "Статус агента неизвестен",
  not_detected: "Агент не обнаружен",
};

function InventoryAssignments({ personId, ticketId }: Props) {
  const url = ticketId
    ? `/api/web/support/tickets/${encodeURIComponent(ticketId)}/inventory-devices`
    : `/api/web/admin/registry/people/${encodeURIComponent(personId!)}/inventory-devices`;
  const inventory = useQuery({
    queryKey: ["operator-inventory", url],
    queryFn: async ({ signal }) => {
      const response = await fetch(url, { signal, credentials: "same-origin", cache: "no-store" });
      if (!response.ok) throw new Error("Inventory unavailable");
      const body = await response.json() as { status: string; data: Inventory };
      if (body.status !== "success" || !Array.isArray(body.data?.assignments)) throw new Error("Inventory unavailable");
      return body.data;
    },
    gcTime: 0,
    retry: false,
    refetchInterval: 60_000,
  });
  const data = inventory.isError ? undefined : inventory.data;
  const fresh = !inventory.isError && !inventory.isPaused && data?.sync_state === "current";
  const target = fresh && data?.assignments.some(row => row.diagnostic_target);
  const readiness = useQuery({
    queryKey: ["inventory-diagnostic-readiness", ticketId],
    enabled: Boolean(ticketId && target),
    queryFn: ({ signal }) => listTicketCapabilityReadiness(ticketId!, signal),
    gcTime: 0,
    retry: false,
    refetchInterval: 60_000,
  });
  const endpointTools = readiness.data?.filter(tool => tool.execution_target === "endpoint_operation") ?? [];
  let readinessLabel = "Диагностика Endpoint сейчас недоступна";
  if (readiness.isError || readiness.isPaused) readinessLabel = "Доступность диагностики неизвестна";
  else if (readiness.isPending) readinessLabel = "Проверяем доступность диагностики…";
  else if (endpointTools.some(tool => tool.readiness === "available" && !tool.requires_consent)) readinessLabel = "Инструменты диагностики доступны в заявке";
  else if (endpointTools.some(tool => tool.readiness === "consent_required" || (tool.readiness === "available" && tool.requires_consent))) {
    readinessLabel = "Для диагностики требуется согласие";
  }

  if (inventory.isPending) return <p className="mt-2 text-sm" role="status">Загружаем назначения…</p>;
  return <>
    {inventory.isError || inventory.isPaused || data?.sync_state === "stale" || data?.sync_state === "unavailable"
      ? <p className="mt-2 text-sm" role="status">Инвентаризация сейчас недоступна. Статус агентов неизвестен.</p> : null}
    {data?.sync_state === "disabled" ? <p className="mt-2 text-sm">Интеграция с инвентаризацией отключена.</p> : null}
    {data?.sync_state === "unlinked" ? <p className="mt-2 text-sm">Профиль сотрудника ещё не связан с инвентаризацией.</p> : null}
    {fresh && !data?.assignments.length ? <p className="mt-2 text-sm">За сотрудником пока нет назначенных компьютеров.</p> : null}
    {data?.assignments.length ? <ul className="mt-2 space-y-2 text-sm">
      {data.assignments.map(row => <li className="space-y-1 break-words border-t border-current/10 pt-2" key={row.assignment_id}>
        <p className="font-medium">{row.name || row.inventory_number || "Рабочий компьютер"}</p>
        <p>{[row.name ? row.inventory_number : null, row.os_name, row.role === "primary" ? "Основной" : "Общий", presenceLabel[fresh ? row.endpoint_status : "unknown"]].filter(Boolean).join(" · ")}</p>
        {row.endpoint_binding_state === "review" ? <p>Привязка требует проверки</p> : null}
        {row.agent_version ? <p>Версия агента {row.agent_version}</p> : null}
        {row.last_seen_at ? <p>Последняя связь {contextDate(row.last_seen_at)}</p> : null}
        {fresh && row.diagnostic_target ? <p>{readinessLabel}</p> : null}
        {fresh && ticketId && !row.diagnostic_target ? <p>ПК не выбран для диагностики заявки</p> : null}
        {fresh && !ticketId && row.endpoint_binding_state === "confirmed" ? <p>Доступность диагностики проверяется в заявке</p> : null}
        <div className="flex flex-wrap gap-x-3 gap-y-1">
          {row.inventory_url ? <a className="underline" href={row.inventory_url} target="_blank" rel="noreferrer">Открыть в инвентаризации</a> : null}
          {fresh && row.endpoint_binding_state !== "confirmed" && row.workstation_url
            ? <a className="underline" href={row.workstation_url} target="_blank" rel="noreferrer">Установка и привязка</a> : null}
        </div>
      </li>)}
    </ul> : null}
  </>;
}

export function OperatorInventoryDevices(props: Props) {
  const [open, setOpen] = useState(false);
  return <details className="mt-3" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary className="cursor-pointer text-sm font-semibold">Назначенные компьютеры</summary>
    {open ? <InventoryAssignments {...props} /> : null}
  </details>;
}
