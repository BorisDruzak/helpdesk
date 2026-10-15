import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchRequesterCatalog } from "./catalog-search-api";

/** Requester job: describe a problem, then explicitly choose a published entrance. */
export function CatalogSearch({ availableOfferings, fallbackOffering, onSelect }: {
  availableOfferings: string[];
  fallbackOffering?: string;
  onSelect: (offering: string, entry: string | undefined) => void;
}) {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
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
    onSelect(offering, entry);
  }
  return <section className="rounded-panel border border-slate-200 bg-white p-4" aria-label="Поиск по каталогу">
    <label className="block font-semibold text-slate-950" htmlFor="requester-catalog-search">Найти проблему во всём каталоге</label>
    <input id="requester-catalog-search" type="search" maxLength={200} autoComplete="off" value={query}
      className="field-base mt-2 w-full" placeholder="Например: принтер не печатает"
      aria-describedby="requester-search-status" onChange={event => setQuery(event.target.value)} />
    <div id="requester-search-status" role="status" aria-live="polite" className="mt-2 text-sm text-slate-600">
      {!query.trim() ? "Опишите проблему своими словами или выберите категорию ниже." : updating ? "Ищем подходящие проблемы…" : null}
      {query.trim() && !updating && !search.isError && search.data && !results.length
        ? "Подходящих проблем не найдено. Попробуйте другое описание." : null}
    </div>
    {query.trim() && !updating && search.isError ? <div role="alert" className="mt-2 text-sm text-rose-700">
      Не удалось выполнить поиск. <button type="button" className="underline" onClick={() => { void search.refetch(); }}>Повторить поиск</button>
    </div> : null}
    {query.trim() && !updating && search.data ? <>
      {search.data.corrected_query ? <p className="mt-2 text-sm text-slate-600">Возможно, вы имели в виду: {search.data.corrected_query}</p> : null}
      {search.data.suggestions.length && results.length ? <p className="mt-2 text-sm text-slate-600">Близкие формулировки: {results.slice(0, 3).map(item => item.title).join("; ")}</p> : null}
      <ul className="mt-3 grid gap-2">
        {results.map(item => <li key={`${item.offering_full_code}:${item.entry_point_key ?? "default"}`}>
          <button type="button" className="w-full rounded-xl border border-slate-200 p-3 text-left hover:border-brand-500 focus-visible:outline-2 focus-visible:outline-brand-700"
            onClick={() => choose(item.offering_full_code, item.entry_point_key ?? undefined)}>
            <span className="block font-semibold text-slate-950">{item.title}</span>
            <span className="block text-xs text-slate-500">{item.category} · {item.help_mode === "guided" ? "Пошаговая помощь" : "Обращение в поддержку"}</span>
            {item.description ? <span className="mt-1 block text-sm text-slate-700">{item.description}</span> : null}
            <span className="mt-1 block text-xs text-slate-500">{item.match_reason}</span>
          </button>
        </li>)}
      </ul>
      {fallbackOffering ? <button type="button" className="mt-3 text-sm font-semibold text-brand-700 underline" onClick={() => choose(fallbackOffering)}>Другая проблема</button> : null}
    </> : null}
  </section>;
}
