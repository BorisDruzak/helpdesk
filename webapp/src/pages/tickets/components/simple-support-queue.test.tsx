import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { SupportQueuePayload } from "../../../features/queues/api";
import { SimpleSupportQueue } from "./simple-support-queue";

const rows = [
  { ticket_id: "new", ticket_code: "T-001", title: "Принтер", status: "queued", status_label: "В очереди", assignee_id: null },
  { ticket_id: "mine", ticket_code: "T-002", title: "Почта", status: "in_progress", status_label: "В работе", assignee_id: "operator" },
  { ticket_id: "other", ticket_code: "T-003", title: "VPN", status: "in_progress", status_label: "В работе", assignee_id: "colleague" },
].map((row) => ({ ...row, priority: "P2", requester_display_name: "Сотрудник", queue_code: "Поддержка", unread_user_messages: 2,
  device_id: null, updated_at: null, created_at: null, requires_operator_action: true }));
const queue = { tickets: rows, summary: { visible_count: 3, queue_counts: [] } } as unknown as SupportQueuePayload;

describe("simple support queue", () => {
  it("offers take only for unassigned tickets and keeps other operators' work read-only", () => {
    const take = vi.fn(); const open = vi.fn();
    render(<SimpleSupportQueue queue={queue} actorId="operator" canWork filter="open" search="" onFilterChange={vi.fn()}
      onSearchChange={vi.fn()} onOpenTicket={open} onTakeTicket={take} onAdvanced={vi.fn()} />);
    const unassigned = screen.getByRole("row", { name: /T-001/ });
    fireEvent.click(within(unassigned).getByRole("button", { name: "Взять в работу" }));
    expect(take).toHaveBeenCalledWith("new");
    expect(within(screen.getByRole("row", { name: /T-002/ })).getByRole("button", { name: "Открыть" })).toBeEnabled();
    fireEvent.click(within(screen.getByRole("row", { name: /T-003/ })).getByRole("button", { name: "Просмотр" }));
    expect(open).toHaveBeenCalledWith("other");
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("exposes five operational filters and preserves loaded rows on refresh failure", () => {
    const filter = vi.fn();
    render(<SimpleSupportQueue queue={queue} actorId="operator" canWork filter="open" search="" error
      onFilterChange={filter} onSearchChange={vi.fn()} onOpenTicket={vi.fn()} onTakeTicket={vi.fn()} onAdvanced={vi.fn()} />);
    for (const name of ["Открытые", "Новые", "Мои", "Ожидают ответа", "Завершённые"]) expect(screen.getByRole("tab", { name })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Мои" }));
    expect(filter).toHaveBeenCalledWith("mine");
    expect(screen.getByRole("alert")).toHaveTextContent("Не удалось обновить");
    expect(screen.getByText("Принтер")).toBeInTheDocument();
  });
});
