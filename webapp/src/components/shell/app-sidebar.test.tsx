import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AppSidebar } from "./app-sidebar";

describe("AppSidebar", () => {
  it("shows admin navigation items only when the session has matching permissions", () => {
    const { rerender } = render(
      <MemoryRouter>
        <AppSidebar hasAdminAccess hasSupportAccess={false} permissions={[]} />
      </MemoryRouter>,
    );

    expect(screen.queryByText("Access Control")).not.toBeInTheDocument();
    expect(screen.queryByText("Модули")).not.toBeInTheDocument();
    expect(screen.queryByText("Конструктор форм")).not.toBeInTheDocument();

    rerender(
      <MemoryRouter>
        <AppSidebar
          hasAdminAccess
          hasSupportAccess={false}
          permissions={["admin.access.view", "admin.modules.view"]}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("Access Control")).toBeInTheDocument();
    expect(screen.getByText("Модули")).toBeInTheDocument();
    expect(screen.queryByText("Конструктор форм")).not.toBeInTheDocument();
  });
});
