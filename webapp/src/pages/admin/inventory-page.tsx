import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { PageHeading } from "../../components/ui/page-heading";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import { fetchEndpointFleet, endpointErrorText } from "../../features/admin/endpoint-context-api";
import type { AdminEndpointFleetItem } from "../../features/admin/endpoint-context-types";
import { contextBytes, contextDate } from "../../features/admin/endpoint-context-view";

const defaultFilters = { platform: "all", location: "all", mapping: "all", binding: "all", freshness: "all", lifecycle: "all" };
function inventoryObservation(item: AdminEndpointFleetItem, hours: number, now: number) {
  const timestamp = item.profiles.find(profile => profile.profile === "inventory_v1")?.last_collected_at;
  if (!item.inventory_summary || !timestamp) return {state: "missing", timestamp: null};
  return {state: now - Date.parse(timestamp) > hours * 3_600_000 ? "stale" : "fresh", timestamp};
}

export function AdminInventoryPage() {
  const [cursors, setCursors] = useState<Array<string | null>>([null]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [department, setDepartment] = useState("");
  const [filters, setFilters] = useState(defaultFilters);
  const [ageHours, setAgeHours] = useState(168);
  const now = Date.now();
  const choose = (key: keyof typeof filters, value: string) => setFilters(previous => ({...previous, [key]: value}));
  const cursor = cursors[cursors.length - 1];
  const fleet = useQuery({ queryKey: ["endpoint-fleet", cursor], queryFn: ({ signal }) => fetchEndpointFleet(cursor, signal), retry: false });
  const items = fleet.data?.items ?? [];
  const departments = [...new Set(items.map(item => item.registry.department).filter((name): name is string => Boolean(name)))].sort();
  const locations = [...new Set(items.map(item => item.registry.location).filter((name): name is string => Boolean(name)))].sort();
  const filtered = items.filter(item => {
    const summary = item.inventory_summary;
    const searchable = [item.device.id, item.device.display_name, item.device.device_identifier, summary?.hostname, summary?.os_name, summary?.model, summary?.serial_number, summary?.cpu_model, item.registry.inventory_number, item.registry.department, item.registry.location, ...item.registry.bindings.map(binding => binding.display_name)].join(" ").toLocaleLowerCase("ru");
    return searchable.includes(search.toLocaleLowerCase("ru")) && (status === "all" || (status === "online" ? item.device.online : status === "offline" && !item.device.online)) && (!department || item.registry.department === department)
      && (filters.platform === "all" || (filters.platform === "missing" ? !summary?.platform : summary?.platform === filters.platform))
      && (filters.location === "all" || item.registry.location === filters.location)
      && (filters.mapping === "all" || item.registry.status === filters.mapping)
      && (filters.binding === "all" || (filters.binding === "none" ? item.registry.status === "mapped" && !item.registry.bindings_truncated && !item.registry.bindings.length : item.registry.status === "mapped" && (item.registry.bindings.some(binding => filters.binding === "any" || binding.relationship_type === filters.binding) || item.registry.bindings_truncated)))
      && (filters.freshness === "all" || inventoryObservation(item, ageHours, now).state === filters.freshness)
      && (filters.lifecycle === "all" || (filters.lifecycle === "retired" ? Boolean(item.device.retired_at) : !item.device.retired_at));
  });
  const metrics = [["На странице", items.length], ["ONLINE", items.filter(item => item.device.online).length], ["OFFLINE", items.filter(item => !item.device.online).length], ["UNKNOWN", 0],
    ["Без inventory context", items.filter(item => inventoryObservation(item, ageHours, now).state === "missing").length],
    ["Устаревший inventory context", items.filter(item => inventoryObservation(item, ageHours, now).state === "stale").length],
    ["Без Registry-привязки", items.filter(item => item.registry.status === "unmapped").length]] as const;
  return <section className="space-y-6">
    <PageHeading eyebrow="Администрирование" title="Устройства" description="Технические данные Endpoint и подтверждённый бизнес-контекст Registry." actions={<Button variant="outline" onClick={() => void fleet.refetch()} disabled={fleet.isFetching}>Обновить список</Button>}/>
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{metrics.map(([label, count]) => <div className="rounded-panel border border-border bg-white p-4" key={label}><p className="text-sm text-slate-500">{label}</p><p className="mt-2 text-2xl font-semibold">{fleet.isError ? "UNKNOWN" : fleet.isPending ? "…" : count}</p></div>)}</div>
    <div className="grid gap-3 md:grid-cols-3">
      <Input aria-label="Поиск на странице" placeholder="Имя, UUID, модель, пользователь, инв. номер" value={search} onChange={event => setSearch(event.target.value)}/>
      <Select aria-label="Статус устройства" value={status} onChange={event => setStatus(event.target.value)}><option value="all">Все статусы</option><option value="online">ONLINE</option><option value="offline">OFFLINE</option><option value="unknown">UNKNOWN</option></Select>
      <Select aria-label="Платформа" value={filters.platform} onChange={event => choose("platform", event.target.value)}><option value="all">Все платформы</option><option value="windows">Windows</option><option value="linux">Linux</option><option value="missing">Платформа не предоставлена</option></Select>
      <Select aria-label="Подразделение" value={department} onChange={event => setDepartment(event.target.value)}><option value="">Все подразделения на странице</option>{departments.map(name => <option key={name}>{name}</option>)}</Select>
      <Select aria-label="Расположение" value={filters.location} onChange={event => choose("location", event.target.value)}><option value="all">Все расположения на странице</option>{locations.map(name => <option key={name}>{name}</option>)}</Select>
      <Select aria-label="Связь с Registry" value={filters.mapping} onChange={event => choose("mapping", event.target.value)}><option value="all">Любая связь с Registry</option><option value="mapped">Подтверждена</option><option value="unmapped">Не подтверждена</option><option value="unavailable">Registry недоступен</option></Select>
      <Select aria-label="Связь пользователя" value={filters.binding} onChange={event => choose("binding", event.target.value)}><option value="all">Любая связь пользователя</option><option value="any">Есть активная связь</option><option value="none">Нет активной связи</option><option value="primary_user">Основной пользователь</option><option value="owner">Владелец</option><option value="responsible">Ответственный</option><option value="shared_user">Общий пользователь</option><option value="temporary_user">Временный пользователь</option></Select>
      <Select aria-label="Актуальность inventory" value={filters.freshness} onChange={event => choose("freshness", event.target.value)}><option value="all">Любая актуальность inventory</option><option value="fresh">В пределах выбранного порога</option><option value="stale">Старше выбранного порога</option><option value="missing">Не собирался</option></Select>
      <Select aria-label="Lifecycle устройства" value={filters.lifecycle} onChange={event => choose("lifecycle", event.target.value)}><option value="all">Все lifecycle-состояния</option><option value="active">Активные устройства</option><option value="retired">Выведены из эксплуатации</option></Select>
    </div>
    <div className="flex flex-wrap items-center gap-3"><label className="text-sm">Порог актуальности inventory<Select aria-label="Порог актуальности inventory" value={ageHours} onChange={event => setAgeHours(Number(event.target.value))}><option value="24">24 часа</option><option value="168">7 дней</option><option value="720">30 дней</option></Select></label><Button variant="outline" onClick={() => {setSearch(""); setStatus("all"); setDepartment(""); setFilters(defaultFilters);}}>Сбросить фильтры</Button><p className="text-sm text-slate-500">Возраст inventory не определяет ONLINE/OFFLINE. Статус связи предоставляет Endpoint.</p></div>
    {fleet.isPending && <p role="status">Загрузка устройств…</p>}
    {fleet.isError ? <p role="alert" className="rounded-panel bg-amber-50 p-5">{endpointErrorText(fleet.error)}</p> : !fleet.isPending && <div className="overflow-x-auto rounded-panel border border-border bg-white"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-slate-500"><tr>{["Устройство", "Статус / последнее наблюдение", "ОС", "Оборудование", "Inventory context", "Registry / пользователь", "Подразделение / расположение"].map(label => <th key={label} className="p-4">{label}</th>)}</tr></thead><tbody>{filtered.map(item => <tr key={item.device.id} className="border-t border-border"><td className="p-4"><Link className="font-semibold text-brand-700 underline-offset-4 hover:underline" to={`/app/admin/device?device=${encodeURIComponent(item.device.id)}`}>{item.inventory_summary?.hostname ?? item.device.display_name}</Link><p className="mt-1 break-all text-xs text-slate-500">{item.device.id}</p>{item.device.retired_at && <p className="text-xs text-slate-500">Выведено из эксплуатации Endpoint</p>}</td><td className="p-4"><span>{item.device.online ? "ONLINE" : "OFFLINE"}</span><p className="text-xs text-slate-500">{contextDate(item.device.last_seen_at)}</p></td><td className="p-4">{[item.inventory_summary?.os_name, item.inventory_summary?.os_version].filter(Boolean).join(" ") || "Нет данных"}</td><td className="p-4">{item.inventory_summary?.model ?? "Нет данных"}<p className="text-xs text-slate-500">{item.inventory_summary?.cpu_model ?? "CPU: нет данных"}</p><p className="text-xs text-slate-500">RAM: {contextBytes(item.inventory_summary?.memory_bytes)}</p></td><td className="p-4"><p>{inventoryObservation(item, ageHours, now).state === "missing" ? "Не собирался" : inventoryObservation(item, ageHours, now).state === "stale" ? "Старше выбранного порога" : "В пределах выбранного порога"}</p>{inventoryObservation(item, ageHours, now).timestamp && <p className="text-xs text-slate-500">{contextDate(inventoryObservation(item, ageHours, now).timestamp)}</p>}<p className="text-xs text-slate-500">{item.profiles.find(profile => profile.profile === "inventory_v1")?.status ?? "Нет сбора"}</p></td><td className="p-4">{item.registry.status === "mapped" ? <><span>{item.registry.inventory_number ?? "Инвентарный номер не задан"}</span><p className="text-xs text-slate-500">{item.registry.bindings.find(binding => binding.relationship_type === "primary_user")?.display_name ?? "Пользователь не назначен"}</p></> : item.registry.status === "unavailable" ? "Registry недоступен" : "Связь не подтверждена"}{item.registry.bindings_truncated && <p className="text-xs text-slate-500">Список связей сокращён. Полный список — в Registry.</p>}{item.registry.bindings_truncated && !["all", "any", "none"].includes(filters.binding) && !item.registry.bindings.some(binding => binding.relationship_type === filters.binding) && <p className="text-xs text-amber-800">Тип связи требует проверки: в сокращённом списке нет подтверждения.</p>}<Link className="mt-2 block text-brand-700 underline" to="/app/admin/registry">Открыть реестр</Link></td><td className="p-4">{item.registry.status === "mapped" ? <><p>{item.registry.department ?? "Подразделение не задано"}</p><p className="text-xs text-slate-500">{item.registry.location ?? "Расположение не задано"}</p></> : item.registry.status === "unavailable" ? "Бизнес-контекст неизвестен" : "Связь с Registry не подтверждена"}</td></tr>)}</tbody></table>{!filtered.length && <p className="p-6 text-slate-500">{items.length ? "По выбранным фильтрам устройств нет." : "Endpoint не вернул устройств."}</p>}</div>}
    <div className="flex items-center justify-between gap-3"><Button variant="outline" disabled={cursors.length === 1 || fleet.isFetching} onClick={() => setCursors(previous => previous.slice(0, -1))}>Назад</Button><p className="text-sm text-slate-500">Страница {cursors.length} · Фильтры и счётчики относятся к текущей странице</p><Button variant="outline" disabled={!fleet.data?.next_cursor || fleet.isFetching || fleet.isError} onClick={() => setCursors(previous => [...previous, fleet.data!.next_cursor])}>Далее</Button></div>
  </section>;
}
