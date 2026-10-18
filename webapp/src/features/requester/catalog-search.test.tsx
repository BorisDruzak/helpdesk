import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { CatalogSearch } from "./catalog-search";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const result = { title: "Принтер не печатает", description: "Проверим подключение и печать",
  category: "Оборудование", offering_full_code: "workplace.print", entry_point_key: "no_print",
  service_code: "workplace", help_mode: "guided", match_reason: "Возможно, в запросе опечатка" };

function mount(onSelect = vi.fn(), fallbackOffering = "general.unknown") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><CatalogSearch onSelect={onSelect}
    options={[{ key: "print", label: "Печать", serviceTitle: "Оборудование", offering: { full_code: "workplace.print", offering_code: "print", title: "Печать", guided_scenario_enabled: true,
      catalog_items: [{ key: "paper", title: "Бумага застряла", entry_point_key: "paper", synonyms: [], scenario_key: "print", version_id: "v1", target_block_id: "paper" }] } },
      { key: "general", label: "Общее обращение", offering: { full_code: "general.unknown", offering_code: "unknown", title: "Общее обращение" } },
      { key: "legacy", label: "Запрос доступа", offering: null }]}
    fallbackOffering={fallbackOffering} /></QueryClientProvider>);
  return onSelect;
}

it("suggests a published problem across the catalog and opens only the selected entrance", async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok", search: {
    results: [result, { ...result, title: "Unavailable", offering_full_code: "restricted.secret" }],
    suggestions: [result.title], corrected_query: null,
  } }), { headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", fetchMock);
  const onSelect = mount();
  expect(fetchMock).not.toHaveBeenCalled();
  fireEvent.change(screen.getByRole("combobox", { name: "Найти проблему во всём каталоге" }), { target: { value: "принтр не печатает" } });
  await screen.findByRole("option", { name: /Принтер не печатает/ });
  expect(screen.getByText(/Оборудование · Пошаговая помощь/)).toBeInTheDocument();
  expect(screen.queryByText("Unavailable")).not.toBeInTheDocument();
  expect(onSelect).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("option", { name: /Принтер не печатает/ }));
  expect(onSelect).toHaveBeenCalledWith("print", "no_print");
});

it("shows an empty state and offers the explicit other-problem fallback", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok", search: {
    results: [], suggestions: [], corrected_query: null,
  } }), { headers: { "Content-Type": "application/json" } })));
  const onSelect = mount();
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "неизвестная проблема" } });
  await screen.findByText("Подходящих проблем не найдено. Попробуйте другое описание.");
  fireEvent.click(screen.getByRole("button", { name: "Не нашёл свою проблему" }));
  expect(onSelect).toHaveBeenCalledWith("general", undefined);
});

it("does not turn a network failure into no matches and can retry", async () => {
  const fetchMock = vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(new Response(JSON.stringify({
    status: "ok", search: { results: [result], suggestions: [], corrected_query: null },
  }), { headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", fetchMock);
  mount();
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "принтер" } });
  await screen.findByRole("alert");
  expect(screen.queryByText(/Подходящих проблем не найдено/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Повторить поиск" }));
  await waitFor(() => expect(screen.getByText(result.title)).toBeInTheDocument());
});

it("opens the loaded guided and legacy choices on empty focus without starting or searching", () => {
  const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher); const onSelect = mount();
  const input = screen.getByRole("combobox");
  expect(screen.getByRole("button", { name: "Не нашёл свою проблему" })).toBeVisible();
  fireEvent.focus(input);
  expect(input).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("listbox", { name: "Доступные проблемы" })).toBeVisible();
  expect(screen.getByRole("option", { name: /Бумага застряла/ })).toBeVisible();
  expect(screen.getByRole("option", { name: /Запрос доступа/ })).toBeVisible();
  expect(fetcher).not.toHaveBeenCalled(); expect(onSelect).not.toHaveBeenCalled();
  fireEvent.keyDown(input, { key: "ArrowDown" }); fireEvent.keyDown(input, { key: "Enter" });
  expect(onSelect).toHaveBeenCalledWith("print", "paper");
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
});

it.each(["pending", "error", "match"])("keeps the configured fallback available during %s search", async state => {
  vi.stubGlobal("fetch", state === "pending" ? vi.fn(() => new Promise(() => {})) : state === "error" ? vi.fn().mockRejectedValue(new Error("offline")) : vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok", search: { results: [result], suggestions: [], corrected_query: null } }), { headers: { "Content-Type": "application/json" } })));
  const onSelect = mount(); fireEvent.change(screen.getByRole("combobox"), { target: { value: "принтер" } });
  expect(screen.getByRole("button", { name: "Не нашёл свою проблему" })).toBeEnabled();
  if (state === "error") await screen.findByRole("alert");
  if (state === "match") await screen.findByRole("option", { name: /Принтер не печатает/ });
  fireEvent.click(screen.getByRole("button", { name: "Не нашёл свою проблему" }));
  expect(onSelect).toHaveBeenCalledWith("general", undefined);
});

it("uses Escape without selecting and supports a form without an offering", () => {
  const onSelect = mount(); const input = screen.getByRole("combobox"); fireEvent.focus(input);
  fireEvent.keyDown(input, { key: "ArrowDown" }); fireEvent.keyDown(input, { key: "Escape" });
  expect(input).toHaveAttribute("aria-expanded", "false"); expect(onSelect).not.toHaveBeenCalled();
  fireEvent.focus(input); fireEvent.click(screen.getByRole("option", { name: /Запрос доступа/ }));
  expect(onSelect).toHaveBeenCalledWith("legacy", undefined);
});

it("aborts obsolete server searches and never replaces current matches with an older response", async () => {
  let resolveOld!: (response: Response) => void;
  const fetcher = vi.fn().mockImplementationOnce(() => new Promise<Response>(resolve => { resolveOld = resolve; })).mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok", search: { results: [{ ...result, title: "Новый результат" }], suggestions: [], corrected_query: null } }), { headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", fetcher); mount(); const input = screen.getByRole("combobox");
  fireEvent.change(input, { target: { value: "старый" } }); await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
  const signal = fetcher.mock.calls[0][1].signal as AbortSignal;
  fireEvent.change(input, { target: { value: "новый" } }); await screen.findByRole("option", { name: /Новый результат/ });
  expect(signal.aborted).toBe(true);
  await act(async () => { resolveOld(new Response(JSON.stringify({ status: "ok", search: { results: [result], suggestions: [], corrected_query: null } }), { headers: { "Content-Type": "application/json" } })); });
  expect(screen.queryByRole("option", { name: /Принтер не печатает/ })).not.toBeInTheDocument();
});

it("finds standalone legacy forms by typed title after the server-ranked catalog results", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok", search: { results: [result], suggestions: [], corrected_query: null } }), { headers: { "Content-Type": "application/json" } })));
  const onSelect = mount(); fireEvent.change(screen.getByRole("combobox"), { target: { value: "доступ" } });
  const local = await screen.findByRole("option", { name: /Запрос доступа/ });
  expect(screen.getAllByRole("option")[0]).toHaveTextContent("Принтер не печатает");
  fireEvent.click(local); expect(onSelect).toHaveBeenCalledWith("legacy", undefined);
});

it("shows a gated fallback without selecting another available form when configuration is unavailable", () => {
  const onSelect = mount(vi.fn(), "private.unavailable");
  const fallback = screen.getByRole("button", { name: "Не нашёл свою проблему" });
  expect(fallback).toBeDisabled(); fireEvent.click(fallback); expect(onSelect).not.toHaveBeenCalled();
  expect(screen.getByText(/Общее обращение пока недоступно/)).toBeVisible();
});
it("reopens the choice list when clicking the still-focused input after selection", () => {
  const onSelect = mount(); const input = screen.getByRole("combobox");
  fireEvent.focus(input); fireEvent.click(screen.getByRole("option", { name: /Бумага застряла/ }));
  expect(input).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(input);
  expect(input).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("option", { name: /Запрос доступа/ })).toBeVisible();
  expect(onSelect).toHaveBeenCalledTimes(1);
});
