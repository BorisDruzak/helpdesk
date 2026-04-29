import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AppSidebar } from "./app-sidebar";

describe("AppSidebar", () => {
  it("shows Access Control only when the session has the RBAC permission", () => {
    const { rerender } = render(
      <MemoryRouter>
        <AppSidebar hasAdminAccess hasSupportAccess={false} permissions={[]} />
      </MemoryRouter>,
    );

    expect(screen.queryByText("Access Control")).not.toBeInTheDocument();

    rerender(
      <MemoryRouter>
        <AppSidebar hasAdminAccess hasSupportAccess={false} permissions={["admin.access.view"]} />
      </MemoryRouter>,
    );

    expect(screen.getByText("Access Control")).toBeInTheDocument();
  });
});
