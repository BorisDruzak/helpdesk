import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AdminRequestTemplateStudioPage } from "./request-template-studio-page";

vi.mock("../../features/auth/session-provider", () => ({ useSession: () => ({ session: { actor_role: role } }) }));
let role = "admin";
const definition = { scenario_key: "printer", service_code: "it", offering_full_code: "it.printer", title: "Не печатает", blocks: [], process_binding: { request_template_key: "printer" } };
const detail = { scenario: { id: "s1", ...definition, archived: false }, draft: { revision: 3, definition } };
const catalog = { categories: [{ id: "c1", parent_id: null, service_code: "it", title: "Оборудование", slug: "hardware", revision: 1, visibility: "internal", lifecycle_status: "draft" }], services: [{ code: "it", public_title: "ИТ" }], offerings: [{ full_code: "it.printer", service_code: "it", public_title: "Принтер", request_template_key: "printer" }], scenarios: [{ ...detail.scenario, status: "draft", revision: 3, category_id: "c1", issues: [] }], total: 1, offset: 0, limit: 100 };
function response(data: unknown, status = 200) { return new Response(JSON.stringify(status === 200 ? { status: "success", data } : { status: "error", error_code: "REVISION_CONFLICT" }), { status, headers: { "content-type": "application/json" } }); }
function mount() { render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><RouterProvider router={createMemoryRouter([{ path: "*", element: <AdminRequestTemplateStudioPage /> }])} /></QueryClientProvider>); }
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
  it("opens catalog first with search, categories and primary create", async () => {
    mockFetch(); mount();
    expect(await screen.findByRole("button", { name: "Создать сценарий" })).toBeVisible();
    expect(await screen.findByRole("button", { name: "Не печатает" })).toBeVisible();
    expect(screen.getByLabelText("Поиск сценариев")).toBeVisible();
    expect(screen.getByRole("button", { name: "Оборудование" })).toBeVisible();
    expect(screen.queryByText("Экспертный")).not.toBeInTheDocument();
  });
  it("opens one wizard step and saves with the server revision", async () => {
    const fetcher = mockFetch(); mount(); fireEvent.click(await screen.findByRole("button", { name: "Не печатает" }));
    fireEvent.change(await screen.findByLabelText("Название сценария"), { target: { value: "Проверка принтера" } });
    expect(screen.queryByText("Блоки сценария")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Сохранить черновик" }));
    expect(await screen.findByText("Черновик сохранён. Ревизия 4.")).toBeVisible();
    const saved = fetcher.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(JSON.parse(String(saved?.[1]?.body))).toMatchObject({ revision: 3, definition: { title: "Проверка принтера" } });
  });
  it("keeps local edits on conflict until explicit reload", async () => {
    const fetcher = mockFetch(); mount(); fireEvent.click(await screen.findByRole("button", { name: "Не печатает" }));
    fireEvent.change(await screen.findByLabelText("Название сценария"), { target: { value: "Локальная правка" } });
    fetcher.mockImplementation(async (_, init) => init?.method === "PUT" ? response(null, 409) : response(detail));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить черновик" }));
    expect(await screen.findByText(/Черновик изменён другим администратором/)).toBeVisible();
    expect(screen.getByLabelText("Название сценария")).toHaveValue("Локальная правка");
    fireEvent.click(screen.getByRole("button", { name: "Загрузить серверную версию" }));
    await waitFor(() => expect(screen.getByLabelText("Название сценария")).toHaveValue("Не печатает"));
  });
  it("auditor can inspect but cannot mutate", async () => {
    role = "auditor"; mockFetch(); mount();
    expect(await screen.findByRole("button", { name: "Не печатает" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Создать сценарий" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Не печатает" }));
    expect(await screen.findByLabelText("Название сценария")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Сохранить черновик" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "4. Тестирование" }));
    expect(screen.getByRole("button", { name: "Начать проверку" })).toBeEnabled();
  });
});
