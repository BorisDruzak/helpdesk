import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchRequesterCatalog } from "./catalog-search-api";
import { CatalogCategories, type CatalogCategory } from "./catalog-categories";
import { CatalogSearchResults } from "./catalog-search-results";
import { useCatalogEvent } from "./catalog-funnel";

/** Requester job: describe a problem, then explicitly choose a published entrance. */
export function CatalogSearch({ availableOfferings, fallbackOffering, fallbackEntryPointKey, onSelect, categories=[], selectedKey, selectedTitle, onCategorySelect, inputRef, error, onBrowsingChange }: {
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
  onBrowsingChange?:(browsing:boolean)=>void;
}) {
  const [query, setQuery] = useState("");
  const recordCatalogEvent=useCatalogEvent();
  const [debounced, setDebounced] = useState("");
  const [browsing,setBrowsing]=useState(false);
  const [browseKey, setBrowseKey] = useState<string | undefined>();
  useEffect(() => { onBrowsingChange?.(browsing); }, [browsing, onBrowsingChange]);
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
  useEffect(()=>{
    if(debounced&&!updating&&search.data&&!search.isError)recordCatalogEvent('search_ready',{resultCount:results.length});
  },[debounced,search.dataUpdatedAt,updating,search.isError,recordCatalogEvent]);
  function choose(offering: string, entry?: string) {
    const rank=results.findIndex(item=>item.offering_full_code===offering&&item.entry_point_key===(entry??null))+1;
    recordCatalogEvent(offering===fallbackOffering&&entry===fallbackEntryPointKey?'fallback_selected':query.trim()?'result_selected':'catalog_selected',{rank});
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
      aria-describedby="requester-search-status" aria-expanded={browsing} aria-controls="requester-catalog-choices" aria-invalid={error ? true : undefined}
      onFocus={()=>setBrowsing(true)} onClick={()=>setBrowsing(true)}
      onKeyDown={event=>{if(event.key==='Escape'){event.preventDefault();setBrowsing(false);event.currentTarget.blur();}}}
      onChange={event => {setQuery(event.target.value);setBrowsing(true);}} />
    {browsing ? <button type="button" className="mt-2 rounded-lg px-2 py-2 text-sm font-semibold text-brand-800 underline" onClick={() => setBrowsing(false)}>Закрыть каталог</button> : null}
    <button type="button" className="mt-2 rounded-lg px-2 py-2 text-sm font-semibold text-brand-800 underline" onClick={() => { setQuery(""); setDebounced(""); setBrowseKey(undefined); setBrowsing(true); }}>Все услуги</button>
    {selectedTitle ? <p className="mt-2 text-sm text-slate-700">Выбрано: <strong>{selectedTitle}</strong></p> : null}
    {error ? <p className="mt-2 text-sm text-rose-700">{error}</p> : null}
    <div id="requester-search-status" role="status" aria-live="polite" className="mt-2 text-sm text-slate-600">
      {!query.trim() ? "Нажмите на поле, чтобы открыть все категории, или опишите проблему своими словами." : updating ? "Ищем услуги и проблемы…" : null}
      {query.trim() && !updating && !search.isError && search.data && !results.length
        ? fallbackOffering
          ? "Услуга или проблема не найдена. Выберите «Не знаю» — поддержка поможет определить нужную услугу."
          : "Услуга или проблема не найдена. Попробуйте другое название или выберите доступную форму помощи."
        : null}
    </div>
    <div id="requester-catalog-choices" hidden={!browsing}>
    {browsing && !query.trim() && categories.length ? <CatalogCategories key={browseKey ?? selectedKey} categories={categories} selectedKey={browseKey ?? selectedKey}
      onSelect={choose} onCategorySelect={key=>{recordCatalogEvent('catalog_selected');setBrowsing(false);onCategorySelect?.(key);}}/> : null}
    {query.trim() && !updating && search.isError ? <div role="alert" className="mt-2 text-sm text-rose-700">
      Не удалось выполнить поиск. <button type="button" className="underline" onClick={() => { void search.refetch(); }}>Повторить поиск</button>
    </div> : null}
    {query.trim() && !updating && search.data ? <>
      {search.data.corrected_query ? <p className="mt-2 text-sm text-slate-600">Возможно, вы имели в виду: {search.data.corrected_query}</p> : null}
      <CatalogSearchResults results={results} categories={categories} onSelect={choose} onService={category => {
        recordCatalogEvent('service_selected');
        setQuery(""); setDebounced(""); setBrowseKey(category.key); setBrowsing(true); onCategorySelect?.(category.key);
      }} />
    </> : null}
    {query.trim() && !updating && (search.data || search.isError) && fallbackOffering ? <button type="button" className="mt-3 rounded-lg border border-brand-200 bg-brand-50 px-4 py-3 text-left text-sm font-semibold text-brand-800 hover:bg-brand-100" onClick={() => choose(fallbackOffering, fallbackEntryPointKey)}>Не знаю / моей услуги нет в списке</button> : null}
    </div>
  </section>;
}
