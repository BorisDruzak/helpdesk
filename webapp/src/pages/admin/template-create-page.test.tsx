import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { AdminTemplateCreatePage } from "./template-create-page";
let role = "admin";
vi.mock("../../features/auth/session-provider", () => ({ useSession: () => ({ session: { actor_role: role, permissions: role === "admin" ? ["admin.forms.publish"] : [] } }) }));
function mount() { const router = createMemoryRouter([{ path: "*", element: <AdminTemplateCreatePage /> }]); render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><RouterProvider router={router} /></QueryClientProvider>); return router; }
afterEach(() => { role = "admin"; vi.unstubAllGlobals(); vi.restoreAllMocks(); });
it("publishes only a new template through explicit confirmation without rewriting the shared form pack", async () => {
  const bodies: Record<string, unknown>[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: unknown, init?: RequestInit) => {
    if (String(url).endsWith("/policies")) return new Response(JSON.stringify({ status: "success", data: { policies: { closure: [{ code: "close", title: "Закрытие", is_active: true, published_at: "2026-10-12" }, { code: "close", title: "Закрытие", is_active: true, published_at: "2026-10-11" }] } } }), { headers: { "content-type": "application/json" } });
    expect(url).toBe("/api/web/admin/helpdesk-model/request-templates/publish-from-form");
    bodies.push(JSON.parse(String(init?.body)));
    return new Response(JSON.stringify({ status: "success", data: { request_template: { template_code: "owned" } } }), { headers: { "content-type": "application/json" } });
  }));
  mount(); await screen.findByText("Форма и правила обработки");
  fireEvent.change(screen.getByLabelText("Название шаблона"), { target: { value: "Восстановление почты" } });
  fireEvent.click(screen.getByText("Как обрабатывать обращение"));
  expect(screen.getAllByRole("option", { name: "Закрытие" })).toHaveLength(1);
  fireEvent.change(screen.getByLabelText("Закрытие"), { target: { value: "close" } });
  fireEvent.click(screen.getByRole("button", { name: "Опубликовать шаблон" }));
  expect(bodies).toHaveLength(0);
  fireEvent.click(screen.getByRole("button", { name: "Подтвердить публикацию шаблона" }));
  await screen.findByText(/Шаблон опубликован/);
  expect(bodies).toHaveLength(1);
  expect(bodies[0]).toMatchObject({ publish_policies: false, form: { title: "Восстановление почты", ticket_type: "incident", closure_policy_ref: "close", fields: [{ label: "Опишите проблему", required: true }] } });
  expect((bodies[0].form as { key: string }).key).toMatch(/^template_[a-f0-9]{32}$/);
});
it("blocks non-admin template creation", () => { role = "auditor"; vi.stubGlobal("fetch", vi.fn()); mount(); expect(screen.queryByRole("button", { name: "Опубликовать шаблон" })).not.toBeInTheDocument(); });

it("preserves authoring on failed publication and protects dirty navigation", async () => {
  const fetcher = vi.fn(async (url: unknown) => new Response(JSON.stringify(String(url).endsWith("/policies") ? { status: "success", data: { policies: {} } } : { status: "error", error: "rejected" }), { status: String(url).endsWith("/policies") ? 200 : 400, headers: { "content-type": "application/json" } }));
  vi.stubGlobal("fetch", fetcher);const router=mount();await screen.findByText("Форма и правила обработки");
  fireEvent.change(screen.getByLabelText("Название шаблона"), { target: { value: "Мой шаблон" } });
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);await act(() => router.navigate("/other"));expect(confirm).toHaveBeenCalledTimes(1);expect(router.state.location.pathname).toBe("/");
  fireEvent.click(screen.getByRole("button", { name: "Опубликовать шаблон" }));fireEvent.click(screen.getByRole("button", { name: "Подтвердить публикацию шаблона" }));await screen.findByRole("alert");expect(screen.getByLabelText("Название шаблона")).toHaveValue("Мой шаблон");
});
