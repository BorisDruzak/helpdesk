import { Button } from "../../components/ui/button";
import { useState } from "react";
import { catalogEntries, OfferingCardLink } from "./offering-card";
import type { AdminServiceCatalogOffering } from "../service-catalog/api";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import { EmptyState } from "../../components/ui-page/page-components";
import type { ScenarioCatalog, ScenarioItem } from "./scenario-api";

const labels = { draft: "Есть неопубликованный черновик", published: "Есть опубликованная версия", errors: "Ошибки черновика", archived: "Есть архив" };
export function categoryDescendants(data: ScenarioCatalog, id: string): Set<string> {
  const ids = new Set([id]);
  for (let changed = true; changed;) {
    changed = false;
    for (const category of data.categories) if (category.parent_id && ids.has(category.parent_id) && !ids.has(category.id)) { ids.add(category.id); changed = true; }
  }
  return ids;
}
type Props = { data: ScenarioCatalog; query: string; status: string; category: string | null; canEdit: boolean;
  onQuery: (value: string) => void; onStatus: (value: string) => void; onCategory: (id: string | null) => void;
  onOpen: (item: ScenarioItem) => void; onCreateForOffering: (item: AdminServiceCatalogOffering) => void; onEditCategory: (id: string) => void; onPage: (offset: number) => void };
export function ScenarioCatalogExplorer({ data, query, status, category, canEdit, onQuery, onStatus, onCategory, onEditCategory, onPage, onOpen }: Props) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const cards = catalogEntries(data);
  function tree(parent: string | null, serviceCode: string, ancestors = new Set<string>()): React.ReactNode {
    return data.categories.filter(item => item.service_code === serviceCode && item.parent_id === parent && item.lifecycle_status !== "archived" && !ancestors.has(item.id)).map(item => (
      <li key={item.id} className="min-w-0">
        <div className="flex items-center gap-1">
          {data.categories.some(child => child.parent_id === item.id && child.service_code === serviceCode && child.lifecycle_status !== "archived") && <Button variant="ghost" size="sm"
            aria-label={`${collapsed.has(item.id) ? "Развернуть" : "Свернуть"} категорию ${item.title}`} aria-expanded={!collapsed.has(item.id)}
            onClick={() => setCollapsed(previous => { const next = new Set(previous); if (next.has(item.id)) next.delete(item.id); else next.add(item.id); return next; })}>{collapsed.has(item.id) ? "▸" : "▾"}</Button>}
          <Button variant={category === item.id ? "secondary" : "ghost"} className="min-w-0 flex-1 justify-start whitespace-normal text-left" aria-pressed={category === item.id} onClick={() => onCategory(item.id)}>{item.title}</Button>
          {canEdit && <Button variant="ghost" size="sm" aria-label={`Изменить категорию ${item.title}`} onClick={() => onEditCategory(item.id)}>…</Button>}
        </div>
        {!collapsed.has(item.id) && <ul className="ml-3 border-l pl-2">{tree(item.id, serviceCode, new Set([...ancestors, item.id]))}</ul>}
      </li>
    ));
  }
  return <div className="grid min-w-0 gap-5 md:grid-cols-[240px_minmax(0,1fr)]">
    <nav aria-label="Категории услуг" className="min-w-0 rounded-xl border p-3">
      <Button variant={category === null ? "secondary" : "ghost"} onClick={() => onCategory(null)}>Все категории</Button>
      {data.services.map(service => <div key={service.code} className="mt-3">
        <Button className="h-auto w-full justify-start whitespace-normal text-left" variant={category === `service:${service.code}` ? "secondary" : "ghost"} aria-pressed={category === `service:${service.code}`} onClick={() => onCategory(`service:${service.code}`)}>{service.public_title} · {data.offerings.filter(item => item.service_code === service.code).length}</Button>
        <ul>{tree(null, service.code)}</ul>
      </div>)}
      {!data.categories.length && <p className="mt-3 text-sm text-slate-500">Все услуги распределены по разделам. Подкатегории можно добавить при необходимости.</p>}
    </nav>
    <section aria-label="Каталог услуг" className="min-w-0 space-y-4">
      <div className="flex flex-wrap gap-3">
        <label className="min-w-0 flex-1">Поиск услуг<Input value={query} onChange={event => onQuery(event.target.value)} placeholder="Название, категория или услуга" /></label>
        <label>Статус<Select value={status} onChange={event => onStatus(event.target.value)}><option value="all">Все статусы</option><option value="form_only">Для сотрудника: обычная форма</option><option value="guided">Для сотрудника: пошаговый сценарий</option>{Object.entries(labels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</Select></label>
      </div>
      {!!data.scenarios.length && <section aria-label="Карты сценариев" className="space-y-3"><h2 className="text-lg font-semibold">Карты сценариев</h2><ul className="grid min-w-0 gap-3 lg:grid-cols-2">{data.scenarios.map(item => <li key={item.id} className="min-w-0 rounded-xl border bg-white p-4"><Button variant="secondary" className="h-auto max-w-full whitespace-normal text-left" onClick={() => onOpen(item)}>{item.title}</Button><p className="mt-2 break-words text-sm">{item.description}</p><p className="text-sm text-slate-500">{item.archived ? "Архив" : item.status === "published" ? "Опубликована" : "Черновик"} · {item.published_version ? `Активная версия ${item.published_version}` : "Без опубликованной версии"}{item.published_entry_count !== undefined ? ` · Опубликованных входов: ${item.published_entry_count}` : ""}</p>{item.updated_at && <span className="text-xs text-slate-500">Изменена: {new Date(item.updated_at).toLocaleDateString("ru-RU")}</span>}</li>)}</ul></section>}
      {!cards.length ? <EmptyState title="Услуги не найдены" description={query || category || status !== "all" ? "Измените поиск, категорию или статус." : "Создайте услугу в выбранном разделе."} /> : <ul className="grid min-w-0 gap-3 lg:grid-cols-2">
        {cards.map(card => <OfferingCardLink key={card.offering.full_code} card={card} data={data} />)}
      </ul>}
      <div className="flex flex-wrap items-center gap-3"><span className="text-sm">Всего: {data.total}</span><Button variant="ghost" disabled={data.offset === 0} onClick={() => onPage(Math.max(0, data.offset - data.limit))}>Предыдущая страница</Button><Button variant="ghost" disabled={data.offset + data.limit >= data.total} onClick={() => onPage(data.offset + data.limit)}>Следующая страница</Button></div>
    </section>
  </div>;
}
