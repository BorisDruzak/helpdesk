import { fireEvent,render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach,describe, expect, it, vi } from "vitest";
import {loadPanelPreferences,savePanelPreferences} from "../../shared/ui/workspace-panel-preferences";
import { AppShell } from "./app-shell";

vi.mock("../../features/auth/session-provider", () => ({
  useSession: () => ({ logout: vi.fn(), session: { user_login: "operator", actor_role: "support",
    available_workspaces: ["support"], default_workspace: "support",
    permissions: ["workspace.support.view", "ticket.queue.view", "ticket.detail.view"] } }),
}));
vi.mock("../../components/shell/app-topbar", () => ({ AppTopbar: () => <header>Общая панель</header> }));
afterEach(()=>localStorage.clear());

describe("ticket workspace shell", () => {
  it("reserves the viewport for Studio and defaults to compact navigation", () => {
    render(<MemoryRouter initialEntries={["/app/admin/request-template-studio"]}><AppShell><p>Карта</p></AppShell></MemoryRouter>);
    expect(screen.getByRole("button", { name: "Развернуть меню" })).toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveClass("min-h-0");
  });
  it("retains the common navigation and header on ticket routes", () => {
    render(<MemoryRouter initialEntries={["/app/tickets/ticket-1"]}><AppShell><p>Переписка</p></AppShell></MemoryRouter>);
    expect(screen.getByText("Общая панель")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Центр действий" })).toHaveAttribute("href", "/app/support");
    expect(screen.getByText("Переписка")).toBeInTheDocument();
  });
  it("collapses support navigation independently of the ticket list",()=>{
    savePanelPreferences("operator","support",{navigationCollapsed:false,ticketListCollapsed:true});
    render(<MemoryRouter initialEntries={["/app/tickets/ticket-1"]}><AppShell><p>Переписка</p></AppShell></MemoryRouter>);
    fireEvent.click(screen.getByRole("button",{name:"Свернуть меню"}));
    expect(screen.getByRole("button",{name:"Развернуть меню"})).toHaveAttribute("aria-expanded","false");
    expect(screen.getByText("Переписка")).toBeInTheDocument();
    expect(loadPanelPreferences("operator","support")).toEqual({navigationCollapsed:true,ticketListCollapsed:true});
  });
});
