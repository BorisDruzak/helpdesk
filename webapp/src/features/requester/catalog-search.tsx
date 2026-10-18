import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchRequesterCatalog } from "./catalog-search-api";
import type { ServiceCatalogOffering } from "./types";

type CatalogOption = { key: string; label: string; serviceTitle?: string | null; offering: ServiceCatalogOffering | null; form?: { description?: string | null } };
type Choice = { key: string; entry?: string; title: string; description?: string | null; category?: string | null; guided?: boolean; reason?: string };

/** One explicit selection path for published entrances and available request forms. */
export function CatalogSearch({ options, fallbackOffering, selectedKey, selectedEntry, inputRef, error, onSelect }: {
  options: CatalogOption[];
  fallbackOffering?: string;
  selectedKey?: string;
  selectedEntry?: string;
  inputRef?: (element: HTMLInputElement | null) => void;
  error?: string | null;
  onSelect: (key: string, entry: string | undefined) => void;
}) {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLUListElement>(null);
  useEffect(() => { if (open && active >= 0) list.current?.querySelector<HTMLElement>(`#requester-choice-${active}`)?.scrollIntoView?.({ block: "nearest" }); }, [active, open]);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(query.trim()), 200);
    return () => window.clearTimeout(timer);
  }, [query]);
  const search = useQuery({
    queryKey: ["requester", "service-catalog", "search", debounced],
    queryFn: ({ signal }) => searchRequesterCatalog(debounced, signal),
    enabled: Boolean(debounced), retry: false,
  });
  const loaded: Choice[] = options.flatMap(option => option.offering?.guided_scenario_enabled && option.offering.catalog_items?.length
    ? option.offering.catalog_items.map(item => ({ key: option.key, entry: item.entry_point_key, title: item.title, description: item.description, category: option.serviceTitle, guided: true }))
    : [{ key: option.key, title: option.label, description: option.offering?.description, category: option.serviceTitle, guided: option.offering?.guided_scenario_enabled }]);
  const serverResults: Choice[] = (search.data?.results ?? []).flatMap(item => {
    const option = options.find(option => option.offering?.full_code === item.offering_full_code);
    return option ? [{ key: option.key, entry: item.entry_point_key ?? undefined, title: item.title, description: item.description, category: item.category, guided: item.help_mode === "guided", reason: item.match_reason }] : [];
  });
  const localResults: Choice[] = options.filter(option => !option.offering && [option.label, option.form?.description].join(" ").toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()))
    .map(option => ({ key: option.key, title: option.label, description: option.form?.description }));
  const results = [...serverResults, ...localResults];
  const updating = query.trim() !== debounced || search.isFetching;
  const rows = !query.trim() ? loaded : !updating ? search.isError ? localResults : results : [];
  const fallback = fallbackOffering ? options.find(option => option.offering?.full_code === fallbackOffering) : undefined;
  const selected = loaded.find(row => row.key === selectedKey && row.entry === selectedEntry);
  const selectedTitle = selected?.title ?? options.find(option => option.key === selectedKey)?.label;
  function choose(key: string, entry?: string) {
    setQuery(""); setDebounced(""); setOpen(false); setActive(-1);
    onSelect(key, entry);
  }
  function changeProblem() { setQuery(""); setDebounced(""); setActive(-1); setOpen(true); input.current?.focus(); }
  return <section className="relative rounded-panel border border-slate-200 bg-white p-4" aria-label="Поиск по каталогу"
    onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) { setOpen(false); setActive(-1); } }}>
    <label className="block font-semibold text-slate-950" htmlFor="requester-catalog-search">Найти проблему во всём каталоге</label>
    <input id="requester-catalog-search" role="combobox" type="search" maxLength={200} autoComplete="off" value={query}
      ref={element => { input.current = element; inputRef?.(element); }}
      className="field-base mt-2 w-full" placeholder="Например: принтер не печатает"
      aria-autocomplete="list" aria-expanded={open} aria-controls="requester-catalog-choices"
      aria-activedescendant={open && rows[active] ? `requester-choice-${active}` : undefined}
      aria-invalid={error ? true : undefined} aria-describedby="requester-search-status"
      onFocus={() => setOpen(true)} onClick={() => setOpen(true)} onChange={event => { setQuery(event.target.value); setActive(-1); setOpen(true); }}
      onKeyDown={event => {
        if (event.key === "Escape") { event.preventDefault(); setOpen(false); setActive(-1); }
        else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
          event.preventDefault(); setOpen(true);
          setActive(current => rows.length ? event.key === "ArrowDown" ? (current + 1) % rows.length : (current < 0 ? rows.length - 1 : (current + rows.length - 1) % rows.length) : -1);
        } else if (event.key === "Enter" && open && rows[active]) { event.preventDefault(); choose(rows[active].key, rows[active].entry); }
      }} />
    <div id="requester-search-status" role="status" aria-live="polite" className="mt-2 text-sm text-slate-600">
      {error || (!query.trim() ? "Опишите проблему или откройте список доступных вариантов." : updating ? "Ищем подходящие проблемы…" : !search.isError && search.data && !results.length ? "Подходящих проблем не найдено. Попробуйте другое описание." : null)}
    </div>
    <button type="button" className="mt-2 text-left text-sm font-semibold text-brand-700 underline disabled:text-slate-500" disabled={!fallback}
      onClick={() => { if (fallback) choose(fallback.key); }}>Не нашёл свою проблему</button>
    {!fallback && <p className="mt-1 text-xs text-slate-500">Общее обращение пока недоступно для вашего профиля. Выберите доступный вариант или обратитесь в поддержку.</p>}
    {selectedTitle && <div className="mt-3 text-sm"><p className="font-semibold text-slate-950">Выбрано: {selectedTitle}</p><button type="button" className="mt-1 text-brand-700 underline" onClick={changeProblem}>Изменить проблему</button></div>}
    {open && <div className="mt-3 rounded-xl border border-slate-200 bg-white shadow-sm">
      {query.trim() && !updating && search.isError ? <div role="alert" className="p-3 text-sm text-rose-700">
        Не удалось выполнить поиск. <button type="button" className="underline" onClick={() => { void search.refetch(); }}>Повторить поиск</button>
      </div> : null}
      {query.trim() && !updating && search.data?.corrected_query ? <p className="p-3 text-sm text-slate-600">Возможно, вы имели в виду: {search.data.corrected_query}</p> : null}
      <ul ref={list} id="requester-catalog-choices" role="listbox" aria-label="Доступные проблемы" className="max-h-64 overflow-y-auto p-1">
        {rows.map((item, index) => <li role="presentation" key={`${item.key}:${item.entry ?? "default"}`}>
          <button type="button" role="option" id={`requester-choice-${index}`} tabIndex={-1} aria-selected={active === index}
            className={`w-full rounded-lg p-3 text-left hover:bg-brand-50 ${active === index ? "bg-brand-50 outline-2 outline-brand-700" : ""}`}
            onMouseDown={event => event.preventDefault()} onClick={() => choose(item.key, item.entry)}>
            <span className="block font-semibold text-slate-950">{item.title}</span>
            <span className="block text-xs text-slate-500">{[item.category, item.guided ? "Пошаговая помощь" : "Обращение в поддержку"].filter(Boolean).join(" · ")}</span>
            {item.description ? <span className="mt-1 block text-sm text-slate-700">{item.description}</span> : null}
            {item.reason ? <span className="mt-1 block text-xs text-slate-500">{item.reason}</span> : null}
          </button>
        </li>)}
      </ul>
    </div>}
  </section>;
}
