import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { OperatorInventoryDevices } from "./operator-inventory-devices";

afterEach(() => vi.unstubAllGlobals());

it("shows the assigned PC and checks existing diagnostics only for the ticket target", async () => {
  const fetchMock = vi.fn(async (url: string) => {
    const payload = url.endsWith("/diagnostics/capabilities")
      ? { status: "ok", capabilities: [{ execution_target: "endpoint_operation", readiness: "consent_required" }] }
      : { status: "success", data: { sync_state: "current", assignments: [{
          assignment_id: "one", name: "Fixture PC", role: "primary", endpoint_status: "online",
          endpoint_binding_state: "confirmed", diagnostic_target: true,
          inventory_url: "https://fixture.invalid/inventory/assets/one",
          workstation_url: "https://fixture.invalid/workstations?inventory_asset_id=one",
        }, {
          assignment_id: "two", name: "PC without agent", role: "shared", endpoint_status: "not_detected",
          endpoint_binding_state: "unbound", diagnostic_target: false,
          workstation_url: "https://fixture.invalid/workstations?inventory_asset_id=two",
        }] } };
    return new Response(JSON.stringify(payload), { headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><OperatorInventoryDevices ticketId="fixture-ticket" /></QueryClientProvider>);
  expect(fetchMock).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Назначенные компьютеры"));
  expect(await screen.findByText("Fixture PC")).toBeVisible();
  expect(screen.getByText(/Агент в сети/)).toBeVisible();
  expect(await screen.findByText("Для диагностики требуется согласие")).toBeVisible();
  expect(screen.getByRole("link", { name: "Открыть в инвентаризации" })).toHaveAttribute("href", "https://fixture.invalid/inventory/assets/one");
  expect(screen.getByRole("link", { name: "Установка и привязка" })).toHaveAttribute("href", "https://fixture.invalid/workstations?inventory_asset_id=two");
});
