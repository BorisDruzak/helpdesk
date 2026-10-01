import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { TicketDeviceAgentPanel } from "./ticket-device-agent-panel";
import type { SupportTicketInventoryContext } from "../../../features/queues/api";
const id = "00000000-0000-0000-0000-000000000001";
const context: SupportTicketInventoryContext = { status: "available", error_code: null, registry: { status: "unmapped", bindings: [] }, context: { device: { id, device_identifier: "pc", display_name: "PC", online: true, retired_at: null, last_seen_at: null }, profiles: [], snapshots: [] } };
describe("Ticket Endpoint device context", () => {
  it("links only to the exact provider UUID", () => {
    render(<MemoryRouter><TicketDeviceAgentPanel inventoryContext={context} /></MemoryRouter>);
    expect(screen.getByText(/ONLINE/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Открыть карточку устройства" })).toHaveAttribute("href", `/app/admin/device?device=${id}`);
    expect(screen.queryByText(/Версия агента/)).not.toBeInTheDocument();
  });
  it.each(["unmapped", "unavailable"] as const)("shows UNKNOWN for %s and never a local card link", (status) => {
    render(<MemoryRouter><TicketDeviceAgentPanel inventoryContext={{ status, error_code: "unavailable", context: null, registry: null }} /></MemoryRouter>);
    expect(screen.getByText(/UNKNOWN/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Открыть карточку устройства" })).not.toBeInTheDocument();
  });
});
