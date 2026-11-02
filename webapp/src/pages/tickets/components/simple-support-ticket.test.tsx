import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { SupportTicketDetailPayload } from "../../../features/queues/api";
import { SimpleSupportTicket } from "./simple-support-ticket";

const detail = { ticket: { ticket_id: "one", ticket_code: "T-001", title: "Принтер", description: "Не печатает", status: "queued", status_label: "В очереди", assignee_id: null, priority: "P2", queue: { name: "Поддержка" } },
  request_form: { rows: [{ key: "room", label: "Кабинет", value: "205" }] }, actions: { status_options: [{ value: "in_progress", label: "В работе" }], take_in_work: { allowed: true, reason_code: null, reason: null }, can_send_internal_note: true }, snapshot: { device: {} }, timeline: [],
} as unknown as SupportTicketDetailPayload;

describe("simple support ticket", () => {
  it("expands the entire long public result accessibly without exposing internal notes", () => {
    const result = "Восстановлено подключение.\n".repeat(30) + "Конечная проверка пройдена.";
    render(<SimpleSupportTicket detail={{ ...detail, ticket: { ...detail.ticket, requester_resolution_summary: result, resolution_summary: "Секретная внутренняя заметка", status: "closed" } }} actorId="operator" canWork onStatus={vi.fn()} onResolve={vi.fn()} onAdvanced={vi.fn()} onQueue={vi.fn()} conversation={null} />);
    const expand = screen.getByRole("button", { name: "Показать результат полностью" });
    expect(expand).toHaveAttribute("aria-expanded", "false");
    const targetId = expand.getAttribute("aria-controls")!;
    fireEvent.click(expand);
    expect(screen.getByRole("button", { name: "Свернуть результат" })).toHaveAttribute("aria-expanded", "true");
    expect(document.getElementById(targetId)).toHaveTextContent("Конечная проверка пройдена.");
    expect(document.getElementById(targetId)).toHaveAttribute("data-expanded", "true");
    expect(screen.queryByText("Секретная внутренняя заметка")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Свернуть результат" }));
    expect(document.getElementById(targetId)).toHaveAttribute("data-expanded", "false");
  });
  it("shows the problem and actual public result without opening a dialog", () => {
    render(<SimpleSupportTicket detail={{ ...detail, ticket: { ...detail.ticket, requester_resolution_summary: "Заменён картридж", resolution_summary: "Внутренняя диагностика", status: "closed" } }} actorId="operator" canWork onStatus={vi.fn()} onResolve={vi.fn()} onAdvanced={vi.fn()} onQueue={vi.fn()} conversation={null} />);
    expect(within(screen.getByRole("region", { name: "Проблема и результат" })).getByText("Не печатает")).toBeVisible();
    expect(screen.getByText("Заменён картридж")).toBeVisible();
    expect(screen.queryByText("Внутренняя диагностика")).not.toBeInTheDocument();
    expect(screen.getByText("205")).toBeInTheDocument();
  });

  it("offers resolve and close only when the server grants the combined action", () => {
    const resolve = vi.fn();
    render(<SimpleSupportTicket detail={{ ...detail, ticket: { ...detail.ticket, status: "in_progress", assignee_id: "operator" }, actions: { ...detail.actions, can_resolve_and_close: true, status_options: [{ value: "resolved", label: "Решено" }] } }} actorId="operator" canWork onStatus={vi.fn()} onResolve={resolve} onAdvanced={vi.fn()} onQueue={vi.fn()} conversation={null} />);
    fireEvent.click(screen.getByRole("button", { name: "Решить и закрыть" }));
    expect(resolve).toHaveBeenCalledOnce();
  });

  it("retains separate resolution for special policies", () => {
    render(<SimpleSupportTicket detail={{ ...detail, ticket: { ...detail.ticket, status: "in_progress", assignee_id: "operator" }, actions: { ...detail.actions, can_resolve_and_close: false, status_options: [{ value: "resolved", label: "Решено" }] } }} actorId="operator" canWork onStatus={vi.fn()} onResolve={vi.fn()} onAdvanced={vi.fn()} onQueue={vi.fn()} conversation={null} />);
    expect(screen.queryByRole("button", { name: "Решить и закрыть" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Решить обращение" })).toBeInTheDocument();
  });
  it("uses the server denial instead of offering an impossible take action", () => {
    const blocked = { ...detail, actions: { ...detail.actions, take_in_work: { allowed: false, reason_code: "ASSIGNEE_NOT_IN_QUEUE", reason: "Вы не состоите в очереди обращения." } } };
    render(<SimpleSupportTicket detail={blocked} actorId="operator" canWork canAssign onStatus={vi.fn()} onResolve={vi.fn()} onAdvanced={vi.fn()} onQueue={vi.fn()} conversation={null} />);
    expect(screen.queryByRole("button", { name: "Взять в работу" })).not.toBeInTheDocument();
    expect(screen.getByText("Вы не состоите в очереди обращения.")).toBeVisible();
    expect(screen.queryByText(/нажмите «Взять/)).not.toBeInTheDocument();
  });
  it("does not offer self-assignment without assignment permission", () => {
    render(<SimpleSupportTicket detail={detail} actorId="operator" canWork canAssign={false} onStatus={vi.fn()} onResolve={vi.fn()} onAdvanced={vi.fn()} onQueue={vi.fn()} conversation={null} />);
    expect(screen.queryByRole("button", { name: "Взять в работу" })).not.toBeInTheDocument();
  });

  it("shows compact content, scenario answers and a single take action without an agent", () => {
    const status = vi.fn();
    render(<SimpleSupportTicket detail={detail} actorId="operator" canWork onStatus={status} onResolve={vi.fn()} onAdvanced={vi.fn()} onQueue={vi.fn()} conversation={<div>Переписка</div>} />);
    expect(within(screen.getByRole("region", { name: "Проблема и результат" })).getByText("Не печатает")).toBeVisible();
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
