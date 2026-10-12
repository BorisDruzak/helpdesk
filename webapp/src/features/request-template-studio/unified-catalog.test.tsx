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
  render(<MemoryRouter><ScenarioCatalogExplorer data={data} query="" status="all" category={null} canEdit onCategory={onCategory}
    onQuery={vi.fn()} onStatus={vi.fn()} onOpen={vi.fn()} onCreateForOffering={vi.fn()} onEditCategory={vi.fn()} onPage={vi.fn()} /></MemoryRouter>);
  expect(screen.getByRole("link", { name: "Не печатает" })).toHaveAttribute("href", "/app/admin/request-template-studio/services/it.print");
  expect(screen.getByText("Для сотрудника: обычная форма", { selector: "p" })).toBeVisible();
  expect(screen.getByText("Черновик: есть ошибки")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Рабочее место · 1" }));
  expect(onCategory).toHaveBeenCalledWith("service:it");
});

it("explains category selection before offering selection instead of an empty selector", () => {
  const catalog = { categories: [], offerings: [], services: [] } as unknown as ScenarioCatalog;
  render(<ScenarioPurpose catalog={catalog} definition={{ title: "Новый", service_code: "", offering_full_code: "", blocks: [], scenario_key: "new", process_binding: { request_template_key: "" } }} disabled={false} existing={false} onChange={vi.fn()} />);
  expect(screen.getByLabelText("Подкатегория")).toBeDisabled();
  expect(screen.getByText("Сначала выберите услугу — её раздел и подкатегории появятся здесь.")).toBeVisible();
});
