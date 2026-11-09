import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { SupportQueuePayload } from "../../../features/queues/api";
import { SimpleSupportQueue } from "./simple-support-queue";

const rows = [
  { ticket_id: "new", ticket_code: "T-001", title: "Принтер", status: "queued", status_label: "В очереди", assignee_id: null },
  { ticket_id: "mine", ticket_code: "T-002", title: "Почта", status: "in_progress", status_label: "В работе", assignee_id: "operator" },
  { ticket_id: "other", ticket_code: "T-003", title: "VPN", status: "in_progress", status_label: "В работе", assignee_id: "colleague" },
].map((row) => ({ ...row, take_in_work: { allowed: true, reason_code: null, reason: null }, priority: "P2", requester_display_name: "Сотрудник", queue_code: "Поддержка", unread_user_messages: 2,
  device_id: null, updated_at: null, created_at: null, requires_operator_action: true }));
const queue = { tickets: rows, summary: { visible_count: 3, queue_counts: [] } } as unknown as SupportQueuePayload;

describe("simple support queue", () => {
  it("distinguishes an approaching SLA deadline from an overdue one in miniatures",()=>{
    vi.useFakeTimers();
    try{
      vi.setSystemTime(new Date("2026-11-09T10:00:00Z"));
      const props={queue:{...queue,tickets:[{...rows[0],first_response_due_at:"2026-11-09T10:01:00Z"}]},compact:true,collapsed:true,canWork:true,filter:"open" as const,search:"",onFilterChange:vi.fn(),onSearchChange:vi.fn(),onOpenTicket:vi.fn(),onTakeTicket:vi.fn(),onAdvanced:vi.fn()};
      const view=render(<SimpleSupportQueue {...props}/>);
      expect(screen.getByText("SLA скоро срок")).toBeVisible();
      expect(screen.queryByText("SLA нарушен")).not.toBeInTheDocument();
      vi.setSystemTime(new Date("2026-11-09T10:02:00Z"));
      view.rerender(<SimpleSupportQueue {...props}/>);
      expect(screen.getByText("SLA нарушен")).toBeVisible();
    }finally{vi.useRealTimers();}
  });
  it("shows actions within the primary queue with one shared search", () => {
    const mode = vi.fn(); const search = vi.fn();
    render(<SimpleSupportQueue queue={queue} canWork filter="open" search="VPN" view="actions" onViewChange={mode}
      actionCenter={<div>Приоритетные действия</div>} onFilterChange={vi.fn()} onSearchChange={search}
      onOpenTicket={vi.fn()} onTakeTicket={vi.fn()} onAdvanced={vi.fn()} />);
    expect(screen.getByRole("tab", { name: "Действия" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Приоритетные действия")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getAllByRole("searchbox")).toHaveLength(1);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Принтер" } });
    expect(search).toHaveBeenCalledWith("Принтер");
    fireEvent.click(screen.getByRole("tab", { name: "Обращения" }));
    expect(mode).toHaveBeenCalledWith("tickets");
  });

  it("uses five colored filters and compact header controls beside the ticket", () => {
    const filter = vi.fn(); const toggle = vi.fn();
    const props = { queue, compact: true, actorId: "operator", canWork: true, filter: "open" as const, search: "", onFilterChange: filter,
      onSearchChange: vi.fn(), onOpenTicket: vi.fn(), onTakeTicket: vi.fn(), onAdvanced: vi.fn(), onToggleCollapsed: toggle };
    const view = render(<SimpleSupportQueue {...props} />);
    expect(screen.queryByRole("tab", { name: "SLA риск" })).not.toBeInTheDocument();
    const tabs=screen.getAllByRole("tab");
    expect(tabs).toHaveLength(5);
    for(const tab of tabs)expect(tab).toHaveAttribute("data-filter");
    fireEvent.click(screen.getByRole("tab", { name: "Новые" }));
    expect(filter).toHaveBeenCalledWith("new");
    fireEvent.click(screen.getByRole("button", { name: "Скрыть список заявок" }));
    expect(toggle).toHaveBeenCalledOnce();
    view.rerender(<SimpleSupportQueue {...props} collapsed />);
    expect(screen.queryByText("Принтер")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Показать список заявок" })).toHaveAttribute("aria-expanded", "false");
    const miniature=screen.getByRole("button",{name:/T-001.*В очереди.*SLA/});
    expect(within(miniature).getByText("T-001")).toBeVisible();
    fireEvent.click(miniature);
    expect(props.onOpenTicket).toHaveBeenCalledWith("new");
  });
  it("opens the full queue from the compact list and hides partitions in unified mode", () => {
    const full = vi.fn();
    render(<SimpleSupportQueue queue={{ ...queue, queue_mode: "unified", summary: { ...queue.summary, queue_counts: [{ id: 1, code: "legacy", name: "Старая очередь", count: 3 }] } }} compact actorId="operator" canWork filter="open" search=""
      onFilterChange={vi.fn()} onSearchChange={vi.fn()} onOpenTicket={vi.fn()} onTakeTicket={vi.fn()} onAdvanced={vi.fn()} onQueueChange={vi.fn()} onOpenQueue={full} />);
    fireEvent.click(screen.getByRole("button", { name: /Открыть всю очередь/ }));
    expect(full).toHaveBeenCalledOnce();
    expect(screen.queryByRole("combobox", { name: "Очередь" })).not.toBeInTheDocument();
    expect(screen.getByText(/Единая очередь/)).toBeVisible();
  });
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
