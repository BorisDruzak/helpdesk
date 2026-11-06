import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { ScenarioCatalogExplorer } from "./scenario-catalog";
import type { ScenarioCatalog } from "./scenario-api";
it("opens a service on double click and shows its settings in the catalog main area", () => {
  const offering = { full_code: "it.chat", service_code: "it", public_title: "Чат" };
  const scenario = { id: "s1", title: "Чат", offering_full_code: "it.chat", service_code: "it", archived: false };
  const data = { categories: [], services: [], offerings: [offering], scenarios: [scenario], entries: [{ offering, scenarios: [scenario], active_mode: "scenario", category_ids: [] }], total: 1, limit: 100, offset: 0 } as unknown as ScenarioCatalog;
  const open = vi.fn();
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><ScenarioCatalogExplorer data={data} query="" status="all" category={null} canEdit onOpen={open} onCreateForOffering={vi.fn()} onEditCategory={vi.fn()} onQuery={vi.fn()} onStatus={vi.fn()} onCategory={vi.fn()} onPage={vi.fn()} /></MemoryRouter></QueryClientProvider>);
  const row = screen.getByRole("button", { name: "Настроить услугу Чат" });
  fireEvent.click(row); expect(open).not.toHaveBeenCalled();
  expect(document.querySelector("aside.catalog-inspector")).toBeNull();
  expect(row.closest("li")).toContainElement(screen.getByRole("button", { name: "Открыть карту сценария" }));
  fireEvent.doubleClick(row); expect(open).toHaveBeenCalledWith(scenario);
});
