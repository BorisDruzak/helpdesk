import type { CatalogSearchResult } from "./catalog-search-api";
import type { CatalogCategory } from "./catalog-categories";
import { catalogDescription } from "./catalog-display";

function distinctDescription(item: CatalogSearchResult) {
  return catalogDescription(item.title, item.description);
}

export function CatalogSearchResults({ results, categories, onSelect, onService }: {
  results: CatalogSearchResult[];
  categories: CatalogCategory[];
  onSelect: (offering: string, entry?: string) => void;
  onService: (category: CatalogCategory) => void;
}) {
  const groups = new Map<string, CatalogSearchResult[]>();
  for (const item of results) {
    const rows = groups.get(item.offering_full_code) ?? [];
    rows.push(item);
    groups.set(item.offering_full_code, rows);
  }
  return <div className="mt-3 grid gap-3">
    {[...groups].map(([code, rows]) => {
      const category = categories.find(item => item.offeringFullCode === code);
      const service = rows.find(item => item.result_kind === "service");
      const title = service?.title || rows[0].offering_title || category?.title || rows[0].category;
      let problems = rows.filter(item => item.result_kind !== "service");
      if (!problems.length && service && category) {
        problems = category.items.map(item => ({ ...service, title:item.title, description:item.description || "",
          result_kind:"problem" as const, entry_point_key:item.entry_point_key }));
      }
      const openService = () => category ? onService(category) : onSelect(code);
      return <section key={code} aria-label={title} className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold text-slate-950">{title}</h2>
          {category || service ? <button type="button" onClick={openService} className="rounded-lg px-2 py-2 text-sm font-semibold text-brand-800 underline">Все проблемы услуги</button> : null}
        </div>
        {service && distinctDescription(service) ? <p className="mt-1 text-sm text-slate-600">{distinctDescription(service)}</p> : null}
        <ul className="mt-2 grid gap-2">
          {problems.slice(0, 3).map(item => <li key={item.entry_point_key ?? "default"}>
            <button type="button" className="w-full rounded-lg border border-slate-200 p-3 text-left hover:border-brand-500 focus-visible:outline-2 focus-visible:outline-brand-700" onClick={() => onSelect(code, item.entry_point_key ?? undefined)}>
              <span className="block font-semibold text-slate-950">{item.title}</span>
              <span className="block text-xs text-slate-600">{item.offering_title ? `${item.offering_title} · ` : ""}{item.category} · {item.help_mode === "guided" ? "Пошаговая помощь" : "Обращение в поддержку"}</span>
              {distinctDescription(item) ? <span className="mt-1 block text-sm text-slate-700">{distinctDescription(item)}</span> : null}
            </button>
          </li>)}
        </ul>
        {problems.length > 3 ? <p className="mt-2 text-sm text-slate-600">Ещё совпадений: {problems.length - 3}. Откройте все проблемы услуги.</p> : null}
      </section>;
    })}
  </div>;
}
