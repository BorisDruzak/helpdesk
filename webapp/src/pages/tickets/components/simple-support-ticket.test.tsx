import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { SupportTicketDetailPayload } from "../../../features/queues/api";
import { SimpleSupportTicket } from "./simple-support-ticket";

const detail = { ticket: { ticket_id: "one", ticket_code: "T-001", title: "Принтер", description: "Не печатает", status: "queued", status_label: "В очереди", assignee_id: null, priority: "P2", queue: { name: "Поддержка" } },
  request_form: { rows: [{ key: "room", label: "Кабинет", value: "205" }] }, actions: { status_options: [{ value: "in_progress", label: "В работе" }], can_send_internal_note: true }, snapshot: { device: {} }, timeline: [],
} as unknown as SupportTicketDetailPayload;

describe("simple support ticket", () => {
  it("does not offer self-assignment without assignment permission", () => {
    render(<SimpleSupportTicket detail={detail} actorId="operator" canWork canAssign={false} onStatus={vi.fn()} onResolve={vi.fn()} onAdvanced={vi.fn()} onQueue={vi.fn()} conversation={null} />);
    expect(screen.queryByRole("button", { name: "Взять в работу" })).not.toBeInTheDocument();
  });

  it("shows compact content, scenario answers and a single take action without an agent", () => {
    const status = vi.fn();
    render(<SimpleSupportTicket detail={detail} actorId="operator" canWork onStatus={status} onResolve={vi.fn()} onAdvanced={vi.fn()} onQueue={vi.fn()} conversation={<div>Переписка</div>} />);
    expect(screen.getByText("Не печатает")).toBeInTheDocument();
    expect(screen.getByText("205")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Взять в работу" }));
    expect(status).toHaveBeenCalledWith("in_progress");
    expect(screen.getByText(/Без агента/)).toBeInTheDocument();
    expect(screen.queryByText("Перед закрытием")).not.toBeInTheDocument();
  });

  it("does not let a second operator take an assigned ticket", () => {
    render(<SimpleSupportTicket detail={{ ...detail, ticket: { ...detail.ticket, assignee_id: "colleague", status: "assigned" } }} actorId="operator" canWork onStatus={vi.fn()} onResolve={vi.fn()} onAdvanced={vi.fn()} onQueue={vi.fn()} conversation={null} />);
    expect(screen.queryByRole("button", { name: "Начать работу" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Взять в работу" })).not.toBeInTheDocument();
    expect(screen.getByText(/Назначено другому/)).toBeInTheDocument();
  });
});
