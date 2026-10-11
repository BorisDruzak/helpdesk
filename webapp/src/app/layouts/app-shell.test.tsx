import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AppShell } from "./app-shell";

vi.mock("../../features/auth/session-provider", () => ({
  useSession: () => ({ logout: vi.fn(), session: { user_login: "operator", actor_role: "support",
    available_workspaces: ["support"], default_workspace: "support",
    permissions: ["workspace.support.view", "ticket.queue.view", "ticket.detail.view"] } }),
}));
vi.mock("../../components/shell/app-topbar", () => ({ AppTopbar: () => <header>Общая панель</header> }));

describe("ticket workspace shell", () => {
  it("retains the common navigation and header on ticket routes", () => {
    render(<MemoryRouter initialEntries={["/app/tickets/ticket-1"]}><AppShell><p>Переписка</p></AppShell></MemoryRouter>);
    expect(screen.getByText("Общая панель")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Центр действий" })).toHaveAttribute("href", "/app/support");
    expect(screen.getByText("Переписка")).toBeInTheDocument();
  });
});
