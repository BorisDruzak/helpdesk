import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AppSidebar } from "./app-sidebar";

const fullPermissions = [
  "ticket.queue.view",
  "workspace.support.view",
  "settings.view",
  "admin.access.view",
  "admin.forms.view",
  "admin.inventory.view",
  "admin.modules.view",
  "admin.observer.view",
  "admin.playbooks.view",
  "admin.registry.view",
];

describe("AppSidebar", () => {
  it("shows admin navigation items only when the session has matching permissions", () => {
    const { rerender } = render(
      <MemoryRouter initialEntries={["/app/admin"]}>
        <AppSidebar hasAdminAccess hasSupportAccess={false} permissions={[]} />
      </MemoryRouter>,
    );

    expect(screen.queryByText("Доступ")).not.toBeInTheDocument();
    expect(screen.queryByText("Модули")).not.toBeInTheDocument();
    expect(screen.queryByText("Конструктор форм")).not.toBeInTheDocument();

    rerender(
      <MemoryRouter initialEntries={["/app/admin"]}>
        <AppSidebar
          hasAdminAccess
          hasSupportAccess={false}
          permissions={["admin.access.view", "admin.modules.view"]}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("button", { name: /Автоматизация/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Система/ })).toBeInTheDocument();
    expect(screen.queryByText("Конструктор форм")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Автоматизация/ }));
    fireEvent.click(screen.getByRole("button", { name: /Система/ }));

    expect(screen.getByRole("link", { name: /Доступ/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Модули/ })).toBeInTheDocument();
  });

  it("shows only support navigation while the active route belongs to support", () => {
    render(
      <MemoryRouter initialEntries={["/app/support"]}>
        <AppSidebar hasAdminAccess hasSupportAccess permissions={fullPermissions} />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: /Центр действий/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Тикеты/ })).toBeInTheDocument();
    expect(screen.queryByText("Устройства и агенты")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Инвентарь устройств/ })).not.toBeInTheDocument();
  });

  it("groups admin navigation by domains and expands the active domain", () => {
    render(
      <MemoryRouter initialEntries={["/app/admin/inventory?panel=requests"]}>
        <AppSidebar hasAdminAccess hasSupportAccess permissions={fullPermissions} />
      </MemoryRouter>,
    );

    expect(screen.queryByRole("link", { name: /Тикеты/ })).not.toBeInTheDocument();

    const devicesGroup = screen.getByRole("button", { name: /Устройства и агенты/ });
    expect(devicesGroup).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: /Инвентарь устройств/ })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: /Каталог и обращения/ })).toBeInTheDocument();
  });

  it("allows collapsing the active admin domain after it was auto-expanded", () => {
    render(
      <MemoryRouter initialEntries={["/app/admin/registry"]}>
        <AppSidebar hasAdminAccess hasSupportAccess permissions={fullPermissions} />
      </MemoryRouter>,
    );

    const systemGroup = screen.getByRole("button", { name: /Система/ });
    expect(systemGroup).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: /Реестры/ })).toHaveAttribute("aria-current", "page");

    fireEvent.click(systemGroup);

    expect(systemGroup).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("link", { name: /Реестры/ })).not.toBeInTheDocument();
  });

  it("hides admin groups that have no visible children", () => {
    render(
      <MemoryRouter initialEntries={["/app/admin/access"]}>
        <AppSidebar hasAdminAccess hasSupportAccess={false} permissions={["admin.access.view"]} />
      </MemoryRouter>,
    );

    expect(screen.queryByRole("button", { name: /Устройства и агенты/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Система/ })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: /Доступ/ })).toHaveAttribute("aria-current", "page");
  });

  it("keeps collapsed admin sidebar accessible through labels and titles", () => {
    render(
      <MemoryRouter initialEntries={["/app/admin/modules"]}>
        <AppSidebar collapsed hasAdminAccess hasSupportAccess={false} permissions={fullPermissions} />
      </MemoryRouter>,
    );

    expect(screen.getByRole("button", { name: /Автоматизация/ })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: /Модули/ })).toHaveAttribute("title", expect.stringContaining("Модули"));
  });

  it("collapses after expanded admin navigation and expands before using collapsed icons", () => {
    const handleCollapsedChange = vi.fn();
    const handleNavigate = vi.fn();
    const { rerender } = render(
      <MemoryRouter initialEntries={["/app/admin/modules"]}>
        <AppSidebar
          hasAdminAccess
          hasSupportAccess={false}
          onCollapsedChange={handleCollapsedChange}
          onNavigate={handleNavigate}
          permissions={fullPermissions}
          showCollapseToggle
        />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("link", { name: /Возможности/ }));
    expect(handleNavigate).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Свернуть меню" }));
    expect(handleCollapsedChange).toHaveBeenCalledWith(true);

    handleCollapsedChange.mockClear();
    handleNavigate.mockClear();
    rerender(
      <MemoryRouter initialEntries={["/app/admin/modules"]}>
        <AppSidebar
          collapsed
          hasAdminAccess
          hasSupportAccess={false}
          onCollapsedChange={handleCollapsedChange}
          onNavigate={handleNavigate}
          permissions={fullPermissions}
          showCollapseToggle
        />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("link", { name: /Возможности/ }));
    expect(handleCollapsedChange).toHaveBeenCalledWith(false);
    expect(handleNavigate).not.toHaveBeenCalled();
  });
});
