import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchOperationDetail } from "../../features/operations/operation-detail-api";
import { AdminOperationDetailPage } from "./operation-detail-page";

vi.mock("../../features/operations/operation-detail-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../features/operations/operation-detail-api")>();
  return {
    ...actual,
    fetchOperationDetail: vi.fn(),
  };
});

function renderPage(initialEntry = "/app/admin/operations/op-1") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <QueryClientProvider client={client}>
        <Routes>
          <Route path="/app/admin/operations/:operationId" element={<AdminOperationDetailPage />} />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("AdminOperationDetailPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders read-only operation diagnostics and safe context links", async () => {
    vi.mocked(fetchOperationDetail).mockResolvedValue({
      operation: {
        operation_id: "op-1",
        device_id: "device-1",
        ticket_id: "ticket-1",
        kind: "tool_call",
        tool_name: "inventory.collect",
        actor_role: "support",
        trace_id: "trace-1",
        status: "failed",
        error_code: "COLLECT_FAILED",
        error_message: "collector failed",
        result_summary: "no inventory",
      },
      links: {
        device_operations: "/app/admin/device-operations/device-1",
        ticket: "/app/tickets/ticket-1",
        observer: "/app/admin/observer?trace_id=trace-1",
      },
    });

    renderPage();

    expect(await screen.findByRole("heading", { name: "Операция op-1" })).toBeInTheDocument();
    expect(await screen.findByText("inventory.collect")).toBeInTheDocument();
    expect(screen.getByText("COLLECT_FAILED")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Открыть тикет" })).toHaveAttribute("href", "/app/tickets/ticket-1");
    expect(screen.getByRole("link", { name: "Device Operations" })).toHaveAttribute("href", "/app/admin/device-operations/device-1");
    expect(screen.getByRole("link", { name: "Observer" })).toHaveAttribute("href", "/app/admin/observer?trace_id=trace-1");
    expect(screen.queryByRole("button", { name: /retry|cancel|approve|restart/i })).not.toBeInTheDocument();
  });
});
