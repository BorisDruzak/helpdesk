import type { ReactNode } from "react";
import type { RegistryDeviceOverlay } from "./endpoint-context-types";

export function contextDate(value: string | null | undefined) {
  return value ? new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "Нет данных";
}
export function contextBytes(value: number | null | undefined) {
  return value == null ? "Нет данных" : `${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(value / 1024 ** 3)} ГБ`;
}
export function ContextFacts({ rows }: { rows: ReadonlyArray<readonly [string, ReactNode]> }) {
  return <dl className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{rows.map(([label, value]) => <div key={label} className="rounded-xl bg-slate-50 p-4"><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 break-words text-sm font-medium text-slate-900">{value ?? "Нет данных"}</dd></div>)}</dl>;
}
export function RegistryContext({ registry }: { registry: RegistryDeviceOverlay }) {
  if (registry.status === "unavailable") return <p role="status">Registry недоступен. Бизнес-контекст неизвестен.</p>;
  if (registry.status === "unmapped") return <p>Связь с Registry не подтверждена. Устройство доступно в Endpoint.</p>;
  return <div className="space-y-5"><ContextFacts rows={[["Объект Registry", registry.asset_name], ["Инвентарный номер", registry.inventory_number], ["Статус объекта", registry.asset_status], ["Подразделение объекта", registry.department], ["Расположение объекта", registry.location]]}/>
    <h3 className="font-semibold">Активные связи пользователей</h3>{registry.bindings.length ? <ul className="space-y-3">{registry.bindings.map(binding => <li key={binding.binding_id} className="rounded-xl border border-border p-4"><strong>{binding.display_name}</strong><p className="text-sm text-slate-500">{({ primary_user: "Основной пользователь", responsible: "Ответственный", owner: "Владелец", shared_user: "Общий пользователь", temporary_user: "Временный пользователь" } as Record<string, string>)[binding.relationship_type] ?? binding.relationship_type} · {binding.department ?? "Подразделение не задано"} · {binding.location ?? "Расположение не задано"}</p></li>)}</ul> : <p>Активные связи не назначены.</p>}
    {registry.bindings_truncated && <p role="status">Показаны первые шесть активных связей. Полный список доступен в Registry.</p>}
  </div>;
}
