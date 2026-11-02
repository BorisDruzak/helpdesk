import { fireEvent,render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach,describe, expect, it, vi } from "vitest";
import {loadPanelPreferences,savePanelPreferences} from "../../shared/ui/workspace-panel-preferences";
import { AppShell } from "./app-shell";

const fixture = vi.hoisted(() => ({ portal: undefined as string | undefined, requester: false }));
vi.mock("../../features/auth/session-provider", () => ({
  useSession: () => ({ logout: vi.fn(), session: { user_login: "operator", actor_role: "support",
    available_workspaces: fixture.requester ? ["requester"] : ["support"], default_workspace: fixture.requester ? "requester" : "support",
    worktime_portal_url: fixture.portal,
    permissions: ["workspace.support.view", "ticket.queue.view", "ticket.detail.view"] } }),
}));
vi.mock("../../components/shell/app-topbar", () => ({ AppTopbar: () => <header>Общая панель</header> }));
afterEach(()=>{ localStorage.clear(); fixture.portal = undefined; fixture.requester = false; });

describe("ticket workspace shell", () => {
  it.each(["https://endpoint.sosnadmin.local/employee", "https://endpoint-staging.sosnadmin.local/employee"])("offers WorkTime %s alongside requester navigation in desktop and mobile layouts", (url) => {
    fixture.requester = true;
    fixture.portal = url;
    render(<MemoryRouter initialEntries={["/app/requester"]}><AppShell><p>Кабинет</p></AppShell></MemoryRouter>);
    const links = screen.getAllByRole("link", { name: "Рабочее время" });
    expect(links).toHaveLength(2);
    for (const link of links) expect(link).toHaveAttribute("href", fixture.portal);
  });
  it("hides WorkTime when unconfigured or outside the employee workspace", () => {
    fixture.portal = "https://endpoint.sosnadmin.local/employee";
    render(<MemoryRouter initialEntries={["/app/support"]}><AppShell><p>Поддержка</p></AppShell></MemoryRouter>);
    expect(screen.queryByRole("link", { name: "Рабочее время" })).not.toBeInTheDocument();
  });
  it.each([undefined, "https://untrusted.test/employee", "https://endpoint.sosnadmin.local/employee?person_id=other", "https://endpoint-staging.sosnadmin.local/employee?person_id=other", "https://endpoint-staging.sosnadmin.local.evil.test/employee", "https://endpoint-staging.sosnadmin.local:444/employee"])("hides unconfigured or unsafe employee portal %s", (url) => {
    fixture.requester = true;
    fixture.portal = url;
    render(<MemoryRouter initialEntries={["/app/requester"]}><AppShell><p>Кабинет</p></AppShell></MemoryRouter>);
    expect(screen.queryByRole("link", { name: "Рабочее время" })).not.toBeInTheDocument();
  });
  it("reserves the viewport for Studio and defaults to compact navigation", () => {
    render(<MemoryRouter initialEntries={["/app/admin/request-template-studio"]}><AppShell><p>Карта</p></AppShell></MemoryRouter>);
    expect(screen.getByRole("button", { name: "Развернуть меню" })).toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveClass("min-h-0");
  });
  it("retains the common navigation and header on ticket routes", () => {
    render(<MemoryRouter initialEntries={["/app/tickets/ticket-1"]}><AppShell><p>Переписка</p></AppShell></MemoryRouter>);
    expect(screen.getByText("Общая панель")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Очередь обращений" })).toHaveAttribute("href", "/app/support");
    expect(screen.getByRole("link", { name: "Расширенный центр" })).toHaveAttribute("href", "/app/support/advanced");
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
