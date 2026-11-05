import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { CatalogSearch } from "./catalog-search";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const result = { title: "Принтер не печатает", description: "Проверим подключение и печать",
  category: "Оборудование", offering_full_code: "workplace.print", entry_point_key: "no_print",
  service_code: "workplace", help_mode: "guided", match_reason: "Возможно, в запросе опечатка" };

function mount(onSelect = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><CatalogSearch onSelect={onSelect}
    availableOfferings={["workplace.print"]} fallbackOffering="general.unknown" fallbackEntryPointKey="not_found"
    categories={[{key:"print",title:"Печать",offeringFullCode:"workplace.print",items:[{key:"no_print",title:"Принтер не печатает",entry_point_key:"no_print"}]}]}
    onCategorySelect={()=>{}} /></QueryClientProvider>);
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
  fireEvent.change(screen.getByRole("searchbox", { name: "Найти проблему во всём каталоге" }), { target: { value: "принтр не печатает" } });
  await screen.findByRole("button", { name: /Принтер не печатает/ });
  expect(screen.getByText(/Оборудование · Пошаговая помощь/)).toBeInTheDocument();
  expect(screen.queryByText("Unavailable")).not.toBeInTheDocument();
  expect(onSelect).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: /Принтер не печатает/ }));
  expect(onSelect).toHaveBeenCalledWith("workplace.print", "no_print");
});

it("opens categories from the only search field and starts only an explicit problem", () => {
  vi.stubGlobal("fetch",vi.fn());
  const select=mount();
  const input=screen.getByRole("searchbox");
  fireEvent.focus(input);
  fireEvent.click(screen.getByRole("button",{name:"Печать"}));
  expect(select).not.toHaveBeenCalled();
  expect(screen.getAllByRole("searchbox")).toHaveLength(1);
  fireEvent.click(screen.getByRole("button",{name:"Принтер не печатает"}));
  expect(select).toHaveBeenCalledWith("workplace.print","no_print");
});

it("shows an empty state and offers the explicit other-problem fallback", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok", search: {
    results: [], suggestions: [], corrected_query: null,
  } }), { headers: { "Content-Type": "application/json" } })));
  const onSelect = mount();
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "неизвестная проблема" } });
  await screen.findByText(/Услуга или проблема не найдена/);
  fireEvent.click(screen.getByRole("button", { name: "Не знаю / моей услуги нет в списке" }));
  expect(onSelect).toHaveBeenCalledWith("general.unknown", "not_found");
});

it("opens the problems of a matching service without starting a remembered scenario", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok", search: {
    results: [{ ...result, title: "Печать", result_kind: "service", entry_point_key: null }], suggestions: [], corrected_query: null,
  } }), { headers: { "Content-Type": "application/json" } })));
  const select = mount();
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "печать" } });
  fireEvent.click(await screen.findByRole("button", { name: /^Печать/ }));
  expect(select).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "Принтер не печатает" })).toBeVisible();
});

it("does not turn a network failure into no matches and can retry", async () => {
  const fetchMock = vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(new Response(JSON.stringify({
    status: "ok", search: { results: [result], suggestions: [], corrected_query: null },
  }), { headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", fetchMock);
  mount();
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "принтер" } });
  await screen.findByRole("alert");
  expect(screen.queryByText(/Подходящих проблем не найдено/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Повторить поиск" }));
  await waitFor(() => expect(screen.getByText(result.title)).toBeInTheDocument());
});
