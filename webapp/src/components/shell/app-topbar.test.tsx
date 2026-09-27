import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { AppTopbar } from "./app-topbar";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("keeps ticket notifications without polling retired agent enrollment routes", async () => {
  const requested: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: string) => {
    requested.push(String(input));
    return new Response(JSON.stringify({ status: "ok", unread_count: 2 }), {
      status: 200, headers: { "Content-Type": "application/json" },
    });
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const props = {
    onLogout: vi.fn(), onWorkspaceChange: vi.fn(), searchPlaceholder: "Поиск",
    userLogin: "synthetic-admin", userRoleLabel: "Администратор",
    workspaceOptions: [{ label: "Администрирование", value: "admin" }], workspaceValue: "admin",
  };
  const view = render(<MemoryRouter initialEntries={["/app/admin/tech"]}>
    <QueryClientProvider client={client}><AppTopbar {...props} /></QueryClientProvider>
  </MemoryRouter>);
  await waitFor(() => expect(requested).toContain("/api/web/notifications/unread_count"));
  fireEvent.click(screen.getByRole("button", { name: "Уведомления" }));
  await screen.findByText("Тикетные уведомления: 2");
  expect(requested).not.toContain("/api/web/admin/connection_requests");
  view.unmount(); client.clear();
});
