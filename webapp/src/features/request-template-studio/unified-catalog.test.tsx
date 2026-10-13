import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { ScenarioCatalogExplorer } from "./scenario-catalog";
import type { ScenarioCatalog } from "./scenario-api";
import { ScenarioPurpose } from "./scenario-purpose";

it("shows one offering link with actual requester mode and draft status, and selectable service categories", () => {
  const offering = { full_code: "it.print", service_code: "it", public_title: "Не печатает" };
  const draft = { id: "draft", offering_full_code: offering.full_code, status: "errors", issues: [{ message: "Добавьте вопросы" }] };
  const data = { categories: [], services: [{ code: "it", public_title: "Рабочее место" }], offerings: [offering], scenarios: [draft],
    entries: [{ offering, scenarios: [draft], active_mode: "form", category_ids: [] }], total: 1, offset: 0, limit: 100 } as unknown as ScenarioCatalog;
  const onCategory = vi.fn();
  render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><ScenarioCatalogExplorer data={data} query="" status="all" category={null} canEdit onCategory={onCategory}
    onQuery={vi.fn()} onStatus={vi.fn()} onOpen={vi.fn()} onCreateForOffering={vi.fn()} onEditCategory={vi.fn()} onPage={vi.fn()} /></MemoryRouter></QueryClientProvider>);
  expect(screen.getByRole("button", { name: "Настроить услугу Не печатает" })).toBeVisible();
  expect(screen.getByText("Сценарий", { selector: "span" })).toBeVisible();
  expect(screen.getByText("Ошибки черновика карты", {selector:"span"})).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Рабочее место · 1" }));
  expect(onCategory).toHaveBeenCalledWith("service:it");
});

it("explains category selection before offering selection instead of an empty selector", () => {
  const catalog = { categories: [], offerings: [], services: [] } as unknown as ScenarioCatalog;
  render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><ScenarioPurpose catalog={catalog} definition={{ title: "Новый", service_code: "", offering_full_code: "", blocks: [], scenario_key: "new", process_binding: { request_template_key: "" } }} disabled={false} existing={false} onChange={vi.fn()} /></MemoryRouter></QueryClientProvider>);
  expect(screen.getByLabelText("Категория (необязательно)")).toBeDisabled();
  expect(screen.getByText("Соедините «Начало» с первым шагом. Название на этой линии — пункт, который сотрудник увидит в каталоге.")).toBeVisible();
});
