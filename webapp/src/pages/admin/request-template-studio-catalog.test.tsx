import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AdminRequestTemplateStudioPage } from "./request-template-studio-page";

vi.mock("../../features/auth/session-provider", () => ({ useSession: () => ({ session: { actor_role: role } }) }));
let role = "admin";
const definition = { schema_version: 2, scenario_key: "printer", service_code: "it", offering_full_code: "it.printer", title: "Не печатает", blocks: [], process_binding: { request_template_key: "printer" } };
const detail = { scenario: { id: "s1", ...definition, archived: false }, draft: { revision: 3, definition } };
const catalog = { categories: [{ id: "c1", parent_id: null, service_code: "it", title: "Оборудование", slug: "hardware", revision: 1, visibility: "internal", lifecycle_status: "draft" }], services: [{ code: "it", public_title: "ИТ" }], offerings: [{ full_code: "it.printer", service_code: "it", public_title: "Принтер", request_template_key: "printer" }], scenarios: [{ ...detail.scenario, status: "draft", revision: 3, category_id: "c1", issues: [] }], total: 1, offset: 0, limit: 100 };
function response(data: unknown, status = 200) { return new Response(JSON.stringify(status === 200 ? { status: "success", data } : { status: "error", error_code: "REVISION_CONFLICT" }), { status, headers: { "content-type": "application/json" } }); }
function mount() { render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><RouterProvider router={createMemoryRouter([{ path: "/app/admin/request-template-studio/services/:offeringCode", element: <AdminRequestTemplateStudioPage /> }, { path: "*", element: <AdminRequestTemplateStudioPage /> }])} /></QueryClientProvider>); }
async function openMap() {
  fireEvent.click(await screen.findByRole("button", { name: "Настроить услугу Не печатает" }));
  fireEvent.click(screen.getByRole("button", { name: "Открыть карту сценария" }));
  expect(await screen.findByLabelText("Визуальная карта сценария")).toBeVisible();
}
async function openServiceSettings() {
  fireEvent.click(await screen.findByRole("button", { name: "Опубликовать" }));
  fireEvent.click(await screen.findByRole("button", { name: "Настройки услуги" }));
  const title = await screen.findByRole("textbox", { name: "Название услуги" });
  expect(title).toHaveValue("Не печатает");
  return title;
}
function mockFetch() {
  const fetcher = vi.fn(async (url: unknown, init?: RequestInit) => {
    if (String(url).includes("/catalog")) return response(catalog);
    if (init?.method === "PUT") return response({ ...detail, draft: { revision: 4, definition: JSON.parse(String(init.body)).definition } });
    return response(detail);
  });
  vi.stubGlobal("fetch", fetcher); return fetcher;
}
afterEach(() => { vi.unstubAllGlobals(); role = "admin"; });
describe("Guided Studio catalog", () => {
  it("opens the unified catalog with a primary create-service action", async () => {
    mockFetch(); mount();
    expect(await screen.findByRole("button", { name: "Создать услугу" })).toBeVisible();
    expect(await screen.findByRole("button", { name: "Настроить услугу Не печатает" })).toBeVisible();
    expect(screen.getByLabelText("Поиск услуг")).toBeVisible();
    expect(screen.queryByLabelText("Визуальная карта сценария")).not.toBeInTheDocument();
    expect(screen.queryByText("Экспертный")).not.toBeInTheDocument();
  });
  it("opens the service map and autosaves with the server revision", async () => {
    const fetcher = mockFetch();
    mount();
    await openMap();
    expect(screen.getByRole("heading", { name: "Библиотека блоков" })).toBeVisible();
    fireEvent.change(await openServiceSettings(), { target: { value: "Проверка принтера" } });
    expect(await screen.findByText("Черновик сохранён. Ревизия 4.", {}, { timeout: 3500 })).toBeVisible();
    const saved = fetcher.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(JSON.parse(String(saved?.[1]?.body))).toMatchObject({ revision: 3, definition: { title: "Проверка принтера" } });
  });
  it("keeps local edits on conflict until explicit reload", async () => {
    const fetcher = mockFetch();
    mount();
    await openMap();
    const title = await openServiceSettings();
    fetcher.mockImplementation(async (url, init) => {
      if (init?.method === "PUT") return response(null, 409);
      return response(String(url).includes("/catalog") ? catalog : detail);
    });
    fireEvent.change(title, { target: { value: "Локальная правка" } });
    expect(await screen.findByText(/Черновик изменён другим администратором/, {}, { timeout: 3500 })).toBeVisible();
    expect(title).toHaveValue("Локальная правка");
    fireEvent.click(screen.getByRole("button", { name: "Загрузить серверную версию" }));
    await waitFor(() => expect(screen.getByLabelText("Название услуги")).toHaveValue("Не печатает"));
  });
  it("auditor can inspect but cannot mutate", async () => {
    role = "auditor";
    const fetcher = mockFetch();
    mount();
    await openMap();
    expect(screen.getByRole("button", { name: "Опубликовать" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Тестировать" }));
    expect(screen.getByRole("button", { name: "Начать проверку" })).toBeEnabled();
    expect(fetcher.mock.calls.every(([, init]) => !["POST", "PUT", "DELETE"].includes(init?.method ?? "GET"))).toBe(true);
  });
});
