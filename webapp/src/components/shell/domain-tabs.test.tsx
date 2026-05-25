import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { DomainTabs } from "./domain-tabs";

const permissions = [
  "admin.inventory.view",
  "admin.observer.view",
];

function renderTabs(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <DomainTabs permissions={permissions} />
    </MemoryRouter>,
  );
}

describe("DomainTabs", () => {
  it("shows device operations last and disabled without device context", () => {
    renderTabs("/app/admin/device-operations");

    const links = screen.getAllByRole("link").map((link) => link.textContent?.trim());
    expect(links).toEqual(["Инвентарь", "Карточка устройства", "Обновления агента", "Observer", "Техпанель"]);

    const operationsTab = screen.getByText("Операции устройства");
    expect(operationsTab).toHaveAttribute("aria-disabled", "true");
    expect(operationsTab.parentElement?.lastElementChild).toBe(operationsTab);
  });

  it("activates device operations tab when a device operations workspace is open", () => {
    renderTabs("/app/admin/device-operations/device-1");

    const operationsTab = screen.getByRole("link", { name: "Операции устройства" });
    expect(operationsTab).toHaveAttribute("aria-current", "page");
    expect(operationsTab).toHaveAttribute("href", "/app/admin/device-operations/device-1");
  });
});
