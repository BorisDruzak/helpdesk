import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { ScenarioCatalogExplorer } from "./scenario-catalog";
import type { ScenarioCatalog } from "./scenario-api";

it("shows human location, description, published version and timestamp, with independently collapsible categories", () => {
  const data = { services: [{ code: "it", public_title: "ИТ" }], offerings: [{ full_code: "it.print", public_title: "Печать" }],
    categories: [{ id: "parent", service_code: "it", parent_id: null, title: "Оборудование" },
      { id: "child", service_code: "it", parent_id: "parent", title: "Принтеры" }],
    scenarios: [{ id: "s1", service_code: "it", offering_full_code: "it.print", category_id: "child", title: "Не печатает",
      description: "Помощь при остановке печати", status: "published", published_version: 7, updated_at: "2026-10-11T10:00:00Z" }],
    total: 1, offset: 0, limit: 100 } as ScenarioCatalog;
  render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><ScenarioCatalogExplorer data={data} query="" status="all" category="child" canEdit
    onQuery={vi.fn()} onStatus={vi.fn()} onCategory={vi.fn()} onOpen={vi.fn()} onCreateForOffering={vi.fn()} onEditCategory={vi.fn()} onPage={vi.fn()} /></MemoryRouter></QueryClientProvider>);
  expect(screen.getByText("ИТ → Оборудование → Принтеры")).toBeVisible();
  fireEvent.click(screen.getByRole("button",{name:"Настроить услугу Не печатает"}));
  expect(screen.getByRole("button",{name:"Открыть карту сценария"})).toBeVisible();
  expect(document.querySelector("time")).toHaveAttribute("datetime", "2026-10-11T10:00:00Z");
  const toggle = screen.getByRole("button", { name: "Свернуть категорию Оборудование" });
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  fireEvent.click(toggle);
  expect(screen.queryByRole("button", { name: "Принтеры" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Развернуть категорию Оборудование" }));
  expect(screen.getByRole("button", { name: "Принтеры" })).toHaveAttribute("aria-pressed", "true");
});
