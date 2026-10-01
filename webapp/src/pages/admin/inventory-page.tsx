import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { PageHeading } from "../../components/ui/page-heading";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import { fetchEndpointFleet, endpointErrorText } from "../../features/admin/endpoint-context-api";
import { contextBytes, contextDate } from "../../features/admin/endpoint-context-view";

export function AdminInventoryPage() {
  const [cursors, setCursors] = useState<Array<string | null>>([null]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [department, setDepartment] = useState("");
  const cursor = cursors[cursors.length - 1];
  const fleet = useQuery({ queryKey: ["endpoint-fleet", cursor], queryFn: ({ signal }) => fetchEndpointFleet(cursor, signal), retry: false });
  const items = fleet.data?.items ?? [];
  const departments = [...new Set(items.map(item => item.registry.department).filter((name): name is string => Boolean(name)))].sort();
  const filtered = items.filter(item => {
    const summary = item.inventory_summary;
    const searchable = [item.device.display_name, item.device.device_identifier, summary?.hostname, summary?.os_name, summary?.model, summary?.serial_number, summary?.cpu_model, item.registry.inventory_number, ...item.registry.bindings.map(binding => binding.display_name)].join(" ").toLocaleLowerCase("ru");
    return searchable.includes(search.toLocaleLowerCase("ru")) && (status === "all" || (status === "online" ? item.device.online : !item.device.online)) && (!department || item.registry.department === department);
  });
  return <section className="space-y-6">
    <PageHeading eyebrow="Администрирование" title="Устройства" description="Технические данные Endpoint и подтверждённый бизнес-контекст Registry." actions={<Button variant="outline" onClick={() => void fleet.refetch()} disabled={fleet.isFetching}>Обновить список</Button>}/>
    <div className="grid gap-3 sm:grid-cols-3">{[["На странице", items.length], ["ONLINE", items.filter(item => item.device.online).length], ["OFFLINE", items.filter(item => !item.device.online).length]].map(([label, count]) => <div className="rounded-panel border border-border bg-white p-5" key={label}><p className="text-sm text-slate-500">{label}</p><p className="mt-2 text-2xl font-semibold">{fleet.isError ? "UNKNOWN" : fleet.isPending ? "…" : count}</p></div>)}</div>
    <div className="grid gap-3 md:grid-cols-3"><Input aria-label="Поиск на странице" placeholder="Имя, модель, CPU, серийный номер, пользователь" value={search} onChange={event => setSearch(event.target.value)}/><Select aria-label="Статус устройства" value={status} onChange={event => setStatus(event.target.value)}><option value="all">Все статусы</option><option value="online">ONLINE</option><option value="offline">OFFLINE</option></Select><Select aria-label="Подразделение" value={department} onChange={event => setDepartment(event.target.value)}><option value="">Все подразделения на странице</option>{departments.map(name => <option key={name}>{name}</option>)}</Select></div>
    {fleet.isPending && <p role="status">Загрузка устройств…</p>}
    {fleet.isError ? <p role="alert" className="rounded-panel bg-amber-50 p-5">{endpointErrorText(fleet.error)}</p> : !fleet.isPending && <div className="overflow-x-auto rounded-panel border border-border bg-white"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-slate-500"><tr>{["Устройство", "Статус / последнее наблюдение", "ОС", "Оборудование", "Registry"].map(label => <th key={label} className="p-4">{label}</th>)}</tr></thead><tbody>{filtered.map(item => <tr key={item.device.id} className="border-t border-border"><td className="p-4"><Link className="font-semibold text-brand-700 underline-offset-4 hover:underline" to={`/app/admin/device?device=${encodeURIComponent(item.device.id)}`}>{item.inventory_summary?.hostname ?? item.device.display_name}</Link><p className="mt-1 break-all text-xs text-slate-500">{item.device.id}</p>{item.device.retired_at && <p className="text-xs text-slate-500">Выведено из эксплуатации Endpoint</p>}</td><td className="p-4"><span>{item.device.online ? "ONLINE" : "OFFLINE"}</span><p className="text-xs text-slate-500">{contextDate(item.device.last_seen_at)}</p></td><td className="p-4">{[item.inventory_summary?.os_name, item.inventory_summary?.os_version].filter(Boolean).join(" ") || "Нет данных"}</td><td className="p-4">{item.inventory_summary?.model ?? "Нет данных"}<p className="text-xs text-slate-500">{item.inventory_summary?.cpu_model ?? "CPU: нет данных"}</p><p className="text-xs text-slate-500">RAM: {contextBytes(item.inventory_summary?.memory_bytes)}</p></td><td className="p-4">{item.registry.status === "mapped" ? <><span>{item.registry.inventory_number ?? "Инвентарный номер не задан"}</span><p className="text-xs text-slate-500">{item.registry.department ?? "Подразделение не задано"}</p><p className="text-xs text-slate-500">{item.registry.bindings.find(binding => binding.relationship_type === "primary_user")?.display_name ?? "Пользователь не назначен"}</p></> : item.registry.status === "unavailable" ? "Registry недоступен" : "Связь не подтверждена"}</td></tr>)}</tbody></table>{!filtered.length && <p className="p-6 text-slate-500">{items.length ? "По выбранным фильтрам устройств нет." : "Endpoint не вернул устройств."}</p>}</div>}
    <div className="flex items-center justify-between gap-3"><Button variant="outline" disabled={cursors.length === 1 || fleet.isFetching} onClick={() => setCursors(previous => previous.slice(0, -1))}>Назад</Button><p className="text-sm text-slate-500">Страница {cursors.length} · Фильтры и счётчики относятся к текущей странице</p><Button variant="outline" disabled={!fleet.data?.next_cursor || fleet.isFetching || fleet.isError} onClick={() => setCursors(previous => [...previous, fleet.data!.next_cursor])}>Далее</Button></div>
  </section>;
}
