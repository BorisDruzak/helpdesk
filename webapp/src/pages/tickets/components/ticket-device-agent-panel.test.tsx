import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { TicketDeviceAgentPanel } from "./ticket-device-agent-panel";
import type { SupportTicketInventoryContext } from "../../../features/queues/api";
import type { SupportWorkspaceContext } from "../../../features/queues/support-workspace-model";

const deviceContext: SupportWorkspaceContext["device"] = {
  id: "device-1",
  assetId: "asset-1",
  assetTypeLabel: "Рабочая станция",
  hostname: "pc-01",
  os: "Windows 11",
  online: true,
  onlineLabel: "online",
  lastSeenLabel: "19.05.2026 10:00",
};

const inventoryContext: SupportTicketInventoryContext = {
  device_id: "device-1",
  hostname: "pc-01",
  display_name: "pc-01",
  agent: {
    connection_state: "online",
    last_seen_at: "2026-05-19T05:00:00Z",
    version: "2.5.0",
    update_status: "current",
    update_available: false,
  },
  inventory: {
    latest_snapshot_id: "snapshot-1",
    collected_at: "2026-05-19T05:01:00Z",
    age_seconds: 120,
    freshness: "fresh",
    source: "inventory.collect",
    summary: { os_name: "Windows", primary_ip: "192.168.100.54" },
  },
  binding: {
    responsible_person: "Иванова И.И.",
    department: "Бухгалтерия",
    building: "Администрация",
    room: "214",
    status: "active",
    tags: ["office"],
  },
  refresh: {
    policy_enabled: true,
    last_run_id: "run-1",
    last_run_status: "dispatched",
    last_run_at: "2026-05-19T05:01:00Z",
    next_due_at: "2026-05-20T05:01:00Z",
    can_request_refresh: false,
  },
  signals: {
    stale_inventory: false,
    missing_inventory: false,
    agent_offline: false,
    failed_recent_refresh: false,
    failed_recent_operation: false,
  },
};

function renderPanel(context: SupportTicketInventoryContext | null = inventoryContext) {
  render(
    <MemoryRouter>
      <TicketDeviceAgentPanel deviceContext={deviceContext} inventoryContext={context} />
    </MemoryRouter>,
  );
}

describe("TicketDeviceAgentPanel", () => {
  it("renders compact device, agent, inventory and binding context", () => {
    renderPanel();

    expect(screen.getByText("Контекст устройства")).toBeInTheDocument();
    expect(screen.getByText("pc-01")).toBeInTheDocument();
    expect(screen.getByText("Агент")).toBeInTheDocument();
    expect(screen.getByText("Инвентаризация")).toBeInTheDocument();
    expect(screen.getByText("Привязка")).toBeInTheDocument();
    expect(screen.getByText("Бухгалтерия")).toBeInTheDocument();
    expect(screen.getByText("Открыть карточку устройства")).toHaveAttribute("href", "/app/admin/device?device=device-1");
    expect(screen.getByText("Открыть Inventory")).toHaveAttribute("href", "/app/admin/inventory?device=device-1");
  });

  it("shows Russian warning badges for stale inventory and offline agent", () => {
    renderPanel({
      ...inventoryContext,
      agent: { ...inventoryContext.agent, connection_state: "offline" },
      inventory: { ...inventoryContext.inventory, freshness: "stale" },
      signals: {
        ...inventoryContext.signals,
        stale_inventory: true,
        agent_offline: true,
        failed_recent_refresh: true,
      },
    });

    expect(screen.getByText("Инвентаризация устарела")).toBeInTheDocument();
    expect(screen.getByText("Агент offline")).toBeInTheDocument();
    expect(screen.getByText("Последнее обновление не удалось")).toBeInTheDocument();
  });

  it("does not crash without inventory context", () => {
    renderPanel(null);

    expect(screen.getByText("Контекст устройства")).toBeInTheDocument();
    expect(screen.getByText("Нет данных инвентаризации для этого тикета.")).toBeInTheDocument();
  });
});
