import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { InventoryComputers } from "./inventory-computers";

afterEach(() => vi.unstubAllGlobals());

function InstallationDraftProbe() {
  const { search, state } = useLocation();
  return <output>{search} {state?.installationComputer}</output>;
}

it("keeps inventory visibility separate from ticket device access", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
    status: "success",
    data: {
      sync_state: "current",
      assignments: [
        { assignment_id: "1", name: "Fixture ALT", os_name: "ALT Linux", endpoint_status: "offline",
          endpoint_binding_state: "confirmed", endpoint_device_id: "endpoint-uuid", request_device_id: "owned", last_seen_at: "2026-11-11T10:00:00Z" },
        { assignment_id: "2", name: "Fixture Windows", endpoint_status: "unknown",
          endpoint_binding_state: "confirmed", endpoint_device_id: "not-owned" },
        { assignment_id: "3", name: "Fixture unbound", inventory_number: "INV-3", endpoint_status: "not_detected",
          endpoint_binding_state: "unbound", endpoint_device_id: null },
      ],
    },
  }), { headers: { "Content-Type": "application/json" } })));
  const client = new QueryClient();
  render(<QueryClientProvider client={client}>
    <MemoryRouter><InventoryComputers personId="fixture" /><InstallationDraftProbe /></MemoryRouter>
  </QueryClientProvider>);
  expect(await screen.findByText("Fixture ALT")).toBeInTheDocument();
  expect(screen.getByText(/Агент не в сети/)).toBeInTheDocument();
  expect(screen.getByText("Состояние неизвестно")).toBeInTheDocument();
  expect(screen.getByText("Агент не обнаружен")).toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: "Создать обращение для компьютера" })).toHaveLength(1);
  fireEvent.click(screen.getByRole("link", { name: "Запросить установку" }));
  expect(screen.getByRole("status", { name: "" })).toHaveTextContent("?intent=endpoint_install Fixture unbound (INV-3)");
});
