import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { AdminServiceCreatePage } from "./service-create-page";
let role = "admin";
vi.mock("../../features/auth/session-provider", () => ({ useSession: () => ({ session: { actor_role: role } }) }));
function response(payload: unknown) { return new Response(JSON.stringify(payload), { headers: { "content-type": "application/json" } }); }
function mount() {
  const router = createMemoryRouter([{ path: "/new", element: <AdminServiceCreatePage /> }, { path: "*", element: <h1>Страница услуги</h1> }], { initialEntries: ["/new"] });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><RouterProvider router={router} /></QueryClientProvider>); return router;
}
function mock() { const request = vi.fn(async (url: unknown, init?: RequestInit) => {
  if (String(url).includes("save-draft")) return response({ status: "ok", offering: { ...JSON.parse(String(init?.body)), full_code: "it.owned" } });
  if (String(url).endsWith("/helpdesk-model/policies")) return response({ status: "success", data: { request_templates: [{ template_code: "printer", public_title: "Принтер", ticket_type: "incident", is_active: true, published_at: "2026-01-01" }] } });
  return response({ status: "success", data: { services: [{ code: "it", public_title: "ИТ", lifecycle_status: "published", visibility: "public" }], offerings: [] } });
}); vi.stubGlobal("fetch", request); return request; }
afterEach(() => { role = "admin"; vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it("protects unsaved creation and navigates to the service after saving without creating a scenario", async () => {
  const request = mock(); const router = mount();
  await screen.findByRole("option", { name: "Принтер" });
  fireEvent.change(screen.getByLabelText("Название услуги"), { target: { value: "Моя услуга" } });
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  await act(() => router.navigate("/other"));
  expect(confirm).toHaveBeenCalledTimes(1); expect(router.state.location.pathname).toBe("/new");
  fireEvent.change(screen.getByLabelText("Шаблон обработки"), { target: { value: "printer" } });
  fireEvent.click(screen.getByRole("button", { name: "Создать черновик услуги" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/app/admin/request-template-studio/services/it.owned"));
  expect(confirm).toHaveBeenCalledTimes(1);
  expect(request.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
});

it("does not show a creation form to an auditor", async () => {
  role = "auditor"; mock(); mount();
  expect(screen.getByText("Создание услуг доступно администратору.")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Создать черновик услуги" })).not.toBeInTheDocument();
});
