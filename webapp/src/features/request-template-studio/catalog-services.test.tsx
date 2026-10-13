import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { ScenarioCatalogExplorer } from "./scenario-catalog";
import type { ScenarioCatalog } from "./scenario-api";

it("keeps services together and opens settings in place, maps only on their own tab", () => {
  const offering = { code: "vpn", full_code: "network.vpn", service_code: "network", public_title: "VPN не подключается", lifecycle_status: "published", visibility: "public", request_template_key: "network" };
  const map = { id: "s", title: "Диагностика VPN", offering_full_code: offering.full_code, status: "draft", archived: false, issues: [] };
  const data = { categories: [], services: [{ code: "network", public_title: "Сеть" }], offerings: [offering], scenarios: [map], entries: [{ offering, scenarios: [map], active_mode: "form", requester_available: true, category_ids: [] }], total: 1, offset: 0, limit: 100 } as unknown as ScenarioCatalog;
  render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><ScenarioCatalogExplorer data={data} query="" status="all" category={null} canEdit onCategory={vi.fn()} onQuery={vi.fn()} onStatus={vi.fn()} onOpen={vi.fn()} onCreateForOffering={vi.fn()} onEditCategory={vi.fn()} onPage={vi.fn()} /></MemoryRouter></QueryClientProvider>);
  expect(screen.queryByRole("region", { name: "Карты сценариев" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Настроить услугу VPN не подключается" }));
  expect(screen.getByRole("complementary", { name: "Настройки услуги" })).toBeVisible();
  expect(screen.getByLabelText("Название услуги")).toHaveValue("VPN не подключается");
  expect(screen.getByText("Обычная форма", { selector: "span" })).toBeVisible();
  fireEvent.click(screen.getByRole("tab", { name: "Карты сценариев" }));
  expect(screen.getByRole("region", { name: "Карты сценариев" })).toBeVisible();
});
