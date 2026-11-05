import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchRequesterCatalog } from "./catalog-search-api";
import { CatalogCategories, type CatalogCategory } from "./catalog-categories";

/** Requester job: describe a problem, then explicitly choose a published entrance. */
export function CatalogSearch({ availableOfferings, fallbackOffering, fallbackEntryPointKey, onSelect, categories=[], selectedKey, selectedTitle, onCategorySelect, inputRef, error }: {
  availableOfferings: string[];
  fallbackOffering?: string;
  fallbackEntryPointKey?: string;
  onSelect: (offering: string, entry: string | undefined) => void;
  categories?:CatalogCategory[];
  selectedKey?:string;
  selectedTitle?:string;
  onCategorySelect?:(key:string)=>void;
  inputRef?:(element:HTMLInputElement | null)=>void;
  error?:string | null;
}) {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [browsing,setBrowsing]=useState(false);
  const [browseKey, setBrowseKey] = useState<string | undefined>();
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(query.trim()), 200);
    return () => window.clearTimeout(timer);
  }, [query]);
  const search = useQuery({
    queryKey: ["requester", "service-catalog", "search", debounced],
    queryFn: ({ signal }) => searchRequesterCatalog(debounced, signal),
    enabled: Boolean(debounced), retry: false,
  });
  const results = (search.data?.results ?? []).filter(item => availableOfferings.includes(item.offering_full_code));
  const updating = query.trim() !== debounced || search.isFetching;
  function choose(offering: string, entry?: string) {
    setQuery("");
    setDebounced("");
    setBrowsing(false);
    setBrowseKey(undefined);
    onSelect(offering, entry);
  }
  return <section className="rounded-panel border border-slate-200 bg-white p-4" aria-label="Поиск по каталогу">
    <label className="block font-semibold text-slate-950" htmlFor="requester-catalog-search">Найти проблему во всём каталоге</label>
    <input id="requester-catalog-search" ref={inputRef} type="search" maxLength={200} autoComplete="off" value={query}
      className="field-base mt-2 h-11 w-full px-4 text-sm" placeholder="Например: принтер не печатает"
      aria-describedby="requester-search-status" aria-expanded={browsing || Boolean(query.trim())} aria-controls="requester-catalog-choices" aria-invalid={error ? true : undefined}
      onFocus={()=>setBrowsing(true)} onClick={()=>setBrowsing(true)}
      onKeyDown={event=>{if(event.key==='Escape'){setBrowsing(false);event.currentTarget.blur();}}}
      onChange={event => {setQuery(event.target.value);setBrowsing(true);}} />
    {selectedTitle ? <p className="mt-2 text-sm text-slate-700">Выбрано: <strong>{selectedTitle}</strong></p> : null}
    {error ? <p className="mt-2 text-sm text-rose-700">{error}</p> : null}
    <div id="requester-search-status" role="status" aria-live="polite" className="mt-2 text-sm text-slate-600">
      {!query.trim() ? "Нажмите на поле, чтобы открыть все категории, или опишите проблему своими словами." : updating ? "Ищем услуги и проблемы…" : null}
      {query.trim() && !updating && !search.isError && search.data && !results.length
        ? "Услуга или проблема не найдена. Выберите «Не знаю» — поддержка поможет определить нужную услугу." : null}
    </div>
    <div id="requester-catalog-choices">
    {browsing && !query.trim() && categories.length ? <CatalogCategories key={browseKey ?? selectedKey} categories={categories} selectedKey={browseKey ?? selectedKey}
      onSelect={choose} onCategorySelect={key=>{setBrowsing(false);onCategorySelect?.(key);}}/> : null}
    {query.trim() && !updating && search.isError ? <div role="alert" className="mt-2 text-sm text-rose-700">
      Не удалось выполнить поиск. <button type="button" className="underline" onClick={() => { void search.refetch(); }}>Повторить поиск</button>
    </div> : null}
    {query.trim() && !updating && search.data ? <>
      {search.data.corrected_query ? <p className="mt-2 text-sm text-slate-600">Возможно, вы имели в виду: {search.data.corrected_query}</p> : null}
      {search.data.suggestions.length && results.length ? <p className="mt-2 text-sm text-slate-600">Близкие формулировки: {results.slice(0, 3).map(item => item.title).join("; ")}</p> : null}
      <ul className="mt-3 grid gap-2">
        {results.map(item => <li key={`${item.offering_full_code}:${item.entry_point_key ?? "default"}`}>
          <button type="button" className="w-full rounded-xl border border-slate-200 p-3 text-left hover:border-brand-500 focus-visible:outline-2 focus-visible:outline-brand-700"
            onClick={() => {
              const category = item.result_kind === "service" ? categories.find(value => value.offeringFullCode === item.offering_full_code) : undefined;
              if (category && onCategorySelect) {
                setQuery(""); setDebounced(""); setBrowseKey(category.key); setBrowsing(true); onCategorySelect(category.key);
              } else choose(item.offering_full_code, item.entry_point_key ?? undefined);
            }}>
            <span className="block font-semibold text-slate-950">{item.title}</span>
            <span className="block text-xs text-slate-500">{item.category} · {item.result_kind === "service" ? "Услуга · Выбрать проблему" : item.help_mode === "guided" ? "Пошаговая помощь" : "Обращение в поддержку"}</span>
            {item.description ? <span className="mt-1 block text-sm text-slate-700">{item.description}</span> : null}
            <span className="mt-1 block text-xs text-slate-500">{item.match_reason}</span>
          </button>
        </li>)}
      </ul>
    </> : null}
    {query.trim() && !updating && (search.data || search.isError) && fallbackOffering ? <button type="button" className="mt-3 rounded-lg border border-brand-200 bg-brand-50 px-4 py-3 text-left text-sm font-semibold text-brand-800 hover:bg-brand-100" onClick={() => choose(fallbackOffering, fallbackEntryPointKey)}>Не знаю / моей услуги нет в списке</button> : null}
    </div>
  </section>;
}
