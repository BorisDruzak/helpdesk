import { Button } from "../../components/ui/button";
import { useState } from "react";
import { Link } from "react-router-dom";
import type { AdminServiceCatalogOffering } from "../service-catalog/api";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import { EmptyState } from "../../components/ui-page/page-components";
import type { ScenarioCatalog, ScenarioItem } from "./scenario-api";

const labels = { draft: "Черновик", published: "Опубликован", errors: "Есть ошибки", archived: "Архив" };
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
export function ScenarioCatalogExplorer({ data, query, status, category, canEdit, onQuery, onStatus, onCategory, onOpen, onCreateForOffering, onEditCategory, onPage }: Props) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const scenarios = data.scenarios;
  const legacy = data.legacy_offerings ?? [];
  function location(item: ScenarioItem): string {
    const titles: string[] = [];
    const seen = new Set<string>();
    let id = item.category_id;
    while (id && !seen.has(id)) {
      seen.add(id);
      const node = data.categories.find(candidate => candidate.id === id && candidate.service_code === item.service_code);
      if (!node) { titles.unshift("Категория недоступна"); break; }
      titles.unshift(node.title); id = node.parent_id;
    }
    titles.unshift(data.services.find(service => service.code === item.service_code)?.public_title ?? "Раздел недоступен");
    return titles.join(" → ");
  }
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
    <nav aria-label="Категории сценариев" className="min-w-0 rounded-xl border p-3">
      <Button variant={category === null ? "secondary" : "ghost"} onClick={() => onCategory(null)}>Все категории</Button>
      {data.services.map(service => <details key={service.code} open className="mt-3"><summary className="cursor-pointer text-sm font-semibold">{service.public_title}</summary><ul>{tree(null, service.code)}</ul></details>)}
      {!data.categories.length && <p className="mt-3 text-sm text-slate-500">Категорий пока нет</p>}
    </nav>
    <section aria-label="Каталог сценариев" className="min-w-0 space-y-4">
      <div className="flex flex-wrap gap-3">
        <label className="min-w-0 flex-1">Поиск сценариев<Input value={query} onChange={event => onQuery(event.target.value)} placeholder="Название, категория или услуга" /></label>
        <label>Статус<Select value={status} onChange={event => onStatus(event.target.value)}><option value="all">Все статусы</option><option value="form_only">Обычная форма / нет сценария</option>{Object.entries(labels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</Select></label>
      </div>
      {!scenarios.length && !legacy.length ? <EmptyState title="Сценарии не найдены" description={query || category || status !== "all" ? "Измените поиск, категорию или статус." : "Создайте первый сценарий для существующей услуги."} /> : <ul className="space-y-2">
        {scenarios.map(item => <li key={item.id} className="rounded-xl border p-4">
          <Button variant="ghost" className="h-auto max-w-full justify-start whitespace-normal text-left text-base" onClick={() => onOpen(item)}>{item.title}</Button>
          <p className="mt-1 text-sm text-slate-500">{labels[item.status ?? "draft"]} · {data.offerings.find(offering => offering.full_code === item.offering_full_code)?.public_title ?? "Услуга недоступна"}</p>
          <p className="mt-1 break-words text-sm text-slate-500">{location(item)}</p>
          {item.description && <p className="mt-2 break-words text-sm">{item.description}</p>}
          <div className="mt-2 flex flex-wrap gap-3 text-sm text-slate-500">
            <span>{item.published_version ? `Версия ${item.published_version}` : item.published_version_id ? "Опубликованная версия" : "Ещё не опубликован"}</span>
            {item.updated_at && Number.isFinite(Date.parse(item.updated_at)) && <span>Изменён: <time dateTime={item.updated_at}>{new Date(item.updated_at).toLocaleString("ru-RU")}</time></span>}
          </div>
          {!!item.issues?.length && <p className="mt-2 text-sm text-amber-800">{item.issues[0].message}</p>}
        </li>)}
        {legacy.map(item => <li key={`legacy-${item.full_code}`} className="space-y-2 rounded-xl border p-4"><h2 className="font-semibold">{item.public_title}</h2><p className="text-sm text-slate-500">Обычная форма / нет сценария</p><div className="flex flex-wrap gap-3">{item.request_template_key && <Link className="text-sm text-brand-700 underline" to={`/app/admin/forms?template=${encodeURIComponent(item.request_template_key)}`}>Открыть обычную форму</Link>}{canEdit && item.request_template_key && <Button variant="secondary" size="sm" onClick={() => onCreateForOffering(item)}>Создать сценарий для услуги</Button>}</div></li>)}
      </ul>}
      <div className="flex flex-wrap items-center gap-3"><span className="text-sm">Всего: {data.total}</span><Button variant="ghost" disabled={data.offset === 0} onClick={() => onPage(Math.max(0, data.offset - data.limit))}>Предыдущая страница</Button><Button variant="ghost" disabled={data.offset + data.limit >= data.total} onClick={() => onPage(data.offset + data.limit)}>Следующая страница</Button></div>
    </section>
  </div>;
}
