import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { fetchRequesterInventory } from "../../features/requester/api";
import { requesterQueryKeys } from "../../features/requester/queries";

const presenceLabels = {
  online: "Агент в сети",
  offline: "Агент не в сети",
  not_detected: "Агент не обнаружен",
  unknown: "Состояние неизвестно",
};

const lastActivityFormat = new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" });

export function InventoryComputers({ personId }: { personId: string }) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["requester", "inventory-computers", personId],
    queryFn: ({ signal }) => fetchRequesterInventory(signal),
    gcTime: 0,
    retry: false,
    refetchOnWindowFocus: "always",
    refetchInterval: 60_000,
  });
  const result = query.data;
  if (result?.sync_state === "disabled") return null;
  const assignments = result?.assignments ?? [];
  const observationExpired = query.dataUpdatedAt > 0 && Date.now() - query.dataUpdatedAt > 120_000;
  const uncertain = query.isError || query.isPaused || observationExpired
    || result?.sync_state === "stale" || result?.sync_state === "unavailable";

  return (
    <section className="surface-panel space-y-3 px-5 py-5" aria-labelledby="inventory-computers-title">
      <h2 className="text-lg font-semibold text-slate-950" id="inventory-computers-title">Мои компьютеры</h2>
      {query.isPending ? <p className="text-sm text-slate-600" role="status">Загружаем компьютеры…</p> : null}
      {uncertain ? (
        <p className="text-sm text-slate-700" role="status">Инвентаризация сейчас недоступна. Состояние агентов неизвестно.</p>
      ) : null}
      {result?.sync_state === "unlinked" ? (
        <p className="text-sm text-slate-700">Профиль ещё не связан с инвентаризацией. <Link className="underline" to="/app/requester/new">Обратиться в поддержку</Link></p>
      ) : null}
      {result?.sync_state === "current" && !assignments.length ? (
        <p className="text-sm text-slate-700">За вами пока не закреплены компьютеры. <Link className="underline" to="/app/requester/new">Обратиться в поддержку</Link></p>
      ) : null}
      {assignments.length ? (
        <ul className="divide-y divide-slate-200">
          {assignments.map((asset) => {
            const activity = asset.last_seen_at ? new Date(asset.last_seen_at) : null;
            const name = asset.name || asset.inventory_number || "Рабочий компьютер";
            const authorizedDevice = !uncertain && asset.helpdesk_binding_state !== "conflict"
              ? asset.request_device_id : null;
            return (
              <li className="flex flex-wrap justify-between gap-2 py-3" key={asset.assignment_id}>
                <div className="min-w-0">
                  <p className="break-words font-medium">{name}</p>
                  <p className="text-sm text-slate-700">
                    {[asset.os_name,
                      asset.endpoint_binding_state === "review" || asset.helpdesk_binding_state === "conflict"
                        ? "Привязка требует проверки" : null,
                      presenceLabels[uncertain ? "unknown" : asset.endpoint_status]].filter(Boolean).join(" · ")}
                  </p>
                  {activity && Number.isFinite(activity.getTime()) ? (
                    <p className="text-sm text-slate-600">Последняя связь: <time dateTime={asset.last_seen_at ?? undefined}>{lastActivityFormat.format(activity)}</time></p>
                  ) : null}
                </div>
                {authorizedDevice ? (
                  <Link className="text-sm underline" state={{ requestDeviceId: authorizedDevice }} to="/app/requester/new"
                    onClick={() => void client.invalidateQueries({queryKey: requesterQueryKeys.bootstrap()})}>Создать обращение для компьютера</Link>
                ) : null}
                {!uncertain && asset.endpoint_status === "not_detected" && asset.endpoint_binding_state === "unbound" ? (
                  <Link className="text-sm underline" to="/app/requester/new?intent=endpoint_install"
                    state={{ installationComputer: asset.name && asset.inventory_number ? `${name} (${asset.inventory_number})` : name }}>
                    Запросить установку
                  </Link>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
    </section>
  );
}
