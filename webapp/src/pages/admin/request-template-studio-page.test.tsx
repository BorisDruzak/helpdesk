import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AdminRequestTemplateStudioPage } from "./request-template-studio-page";
vi.mock("../../features/auth/session-provider", () => ({ useSession: () => ({ session: { actor_role: "admin" } }) }));
const category = { id: "c1", parent_id: null, service_code: "it", title: "Оборудование", slug: "hardware", description: "", sort_order: 0, revision: 1, visibility: "internal", lifecycle_status: "draft" };
const catalog = { categories: [category], services: [{ code: "it", public_title: "ИТ" }], offerings: [{ full_code: "it.printer", service_code: "it", public_title: "Принтер", request_template_key: "printer" }], scenarios: [], total: 0, offset: 0, limit: 100 };
function response(data: unknown, status = 200) { return new Response(JSON.stringify({ status: status === 200 ? "success" : "error", data }), { status, headers: { "content-type": "application/json" } }); }
function mount(path = "/") { const router = createMemoryRouter([{ path: "/app/admin/request-template-studio/services/:offeringCode", element: <AdminRequestTemplateStudioPage /> }, { path: "*", element: <AdminRequestTemplateStudioPage /> }], { initialEntries: [path] }); render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><RouterProvider router={router} /></QueryClientProvider>); return router; }
async function ready() { await waitFor(() => expect(screen.getByRole("button", { name: "Создать сценарий" })).toBeEnabled()); }
function mock() { const fetcher = vi.fn(async (_url: unknown, _init?: RequestInit) => _init?.method === "POST" && String(_url).endsWith("/scenarios") ? response({ scenario: { id: "s1", archived: false }, draft: { revision: 1, definition: JSON.parse(String(_init.body)).definition } }) : response(catalog)); vi.stubGlobal("fetch", fetcher); return fetcher; }
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });
describe("Guided Studio workflow", () => {
  it("offers independent service creation before scenario authoring", async () => {
    mock(); mount(); await ready();
    expect(screen.getByRole("link", { name: "Создать услугу" })).toHaveAttribute("href", "/app/admin/request-template-studio/services/new");
  });
  it("updates the service category when the URL changes in the same router", async () => {
    const fetcher = mock(); const router = mount("/?service=it"); await ready();
    expect(String(fetcher.mock.calls.at(-1)?.[0])).toContain("service_code=it");
    await act(() => router.navigate("/?service=mail"));
    await waitFor(() => expect(String(fetcher.mock.calls.at(-1)?.[0])).toContain("service_code=mail"));
  });
  it("does not create from incomplete paginated deep-link context", async () => { const fetcher = mock(); fetcher.mockResolvedValue(response({ ...catalog, total: 200 })); mount("/?offering=it.printer"); expect(await screen.findByText(/Каталог содержит несколько страниц/)).toBeVisible(); expect(screen.queryByLabelText("Название сценария")).not.toBeInTheDocument(); });
  it("shows legacy forms and starts a scenario from their offering", async () => { const fetcher = mock(); fetcher.mockImplementation(async () => response({ ...catalog, legacy_offerings: catalog.offerings, total: 1 })); mount(); fireEvent.click(await screen.findByRole("link", { name: "Принтер" })); await screen.findByRole("button", { name: "Создать сценарий для услуги" }); expect(screen.getByRole("link", { name: "Открыть обычную форму" })).toHaveAttribute("href", "/app/admin/forms?template=printer"); fireEvent.click(screen.getByRole("button", { name: "Создать сценарий для услуги" })); expect(screen.getByLabelText("Услуга")).toHaveValue("it.printer"); });
  it("blocks router navigation and unload while edits are dirty", async () => { mock(); const router = mount(); await ready(); fireEvent.click(screen.getByRole("button", { name: "Создать сценарий" })); const confirm = vi.spyOn(window, "confirm").mockReturnValue(false); await act(() => router.navigate("/other")); expect(confirm).toHaveBeenCalled(); expect(router.state.location.pathname).toBe("/"); const event = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(event); expect(event.defaultPrevented).toBe(true); confirm.mockReturnValue(true); await act(() => router.navigate("/other")); expect(router.state.location.pathname).toBe("/other"); });
  it("preserves offering/template deep links from the existing catalog", async () => { mock(); mount("/?offering=it.printer&template=printer"); expect(await screen.findByLabelText("Услуга")).toHaveValue("it.printer"); expect(screen.getByLabelText("Название сценария")).toHaveValue("Принтер"); });
  it("shows loading while catalog is pending", () => { vi.stubGlobal("fetch", () => new Promise(() => {})); mount(); expect(screen.getByText("Загрузка Студии")).toBeVisible(); });
  it("shows the empty catalog", async () => { mock(); mount(); expect(await screen.findByText("Услуги не найдены")).toBeVisible(); });
  it("retries a failed catalog", async () => { const fetcher = mock(); fetcher.mockResolvedValueOnce(response(null, 500)); mount(); expect(await screen.findByText("Каталог недоступен")).toBeVisible(); fireEvent.click(screen.getByRole("button", { name: /Повторить/ })); expect(await screen.findByText("Услуги не найдены")).toBeVisible(); });
  it("searches and filters through the server", async () => { const fetcher = mock(); mount(); fireEvent.change(await screen.findByLabelText("Поиск услуг"), { target: { value: "принтер" } }); await waitFor(() => expect(String(fetcher.mock.calls.at(-1)?.[0])).toContain("q=%D0%BF%D1%80%D0%B8%D0%BD%D1%82%D0%B5%D1%80")); fireEvent.change(await screen.findByLabelText("Статус"), { target: { value: "draft" } }); await waitFor(() => expect(String(fetcher.mock.calls.at(-1)?.[0])).toContain("status=draft")); });
  it("filters the category tree on the server", async () => { const fetcher = mock(); mount(); fireEvent.click(await screen.findByRole("button", { name: "Оборудование" })); await waitFor(() => expect(String(fetcher.mock.calls.at(-1)?.[0])).toContain("category_id=c1")); });
  it("creates a draft using an offering picker", async () => {
    const fetcher = mock(); mount(); await ready(); fireEvent.click(screen.getByRole("button", { name: "Создать сценарий" }));
    fireEvent.change(screen.getByLabelText("Название сценария"), { target: { value: "Не печатает" } });
    fireEvent.change(screen.getByLabelText("Услуга"), { target: { value: "it.printer" } });
    fetcher.mockImplementation(async (_url: unknown, init?: RequestInit) => init?.method === "POST" ? response({ scenario: { id: "s1", archived: false }, draft: { revision: 1, definition: JSON.parse(String(init.body)).definition } }) : response(catalog));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить черновик" }));
    expect(await screen.findByText("Черновик сохранён. Ревизия 1.")).toBeVisible();
  });
  it("shows only the current wizard step", async () => { mock(); mount(); await ready(); fireEvent.click(screen.getByRole("button", { name: "Создать сценарий" })); expect(screen.getByRole("button", { name: "Следующий этап" })).toBeDisabled(); fireEvent.change(screen.getByLabelText("Услуга"), { target: { value: "it.printer" } }); fireEvent.click(screen.getByRole("button", { name: "Сохранить черновик" })); await screen.findByText("Черновик сохранён. Ревизия 1."); fireEvent.click(screen.getByRole("button", { name: "Следующий этап" })); expect(screen.getByText("Блоки сценария")).toBeVisible(); expect(screen.queryByLabelText("Название сценария")).not.toBeInTheDocument(); expect(screen.queryByText("Проверка пользовательского сценария")).not.toBeInTheDocument(); });
  it("requires an explicit decision before discarding edits", async () => { mock(); mount(); await ready(); fireEvent.click(screen.getByRole("button", { name: "Создать сценарий" })); fireEvent.click(screen.getByRole("button", { name: "Вернуться в каталог" })); expect(screen.getByText("Уйти без сохранения локальных изменений?")).toBeVisible(); fireEvent.click(screen.getByRole("button", { name: "Отмена" })); expect(screen.getByLabelText("Название сценария")).toBeVisible(); });
  it("creates a category through local settings", async () => { const fetcher = mock(); mount(); await ready(); fireEvent.click(screen.getByRole("button", { name: "Создать категорию" })); fireEvent.change(screen.getByLabelText("Название категории"), { target: { value: "Принтеры" } }); expect(screen.getByText("Расширенные настройки")).toBeVisible(); fireEvent.click(screen.getByRole("button", { name: "Сохранить категорию" })); await waitFor(() => expect(fetcher.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true)); });
});
