import { describe, expect, it } from "vitest";

import type { CommandCenterItem, CommandCenterSection } from "./api";
import {
  buildSupportActionTasks,
  filterSupportActionTasks,
  groupSupportActionTasksForKanban,
} from "./task-projection";

function item(partial: Partial<CommandCenterItem>): CommandCenterItem {
  return {
    id: `${partial.ticket_id ?? "ticket-1"}:item`,
    ticket_id: partial.ticket_id ?? "ticket-1",
    ticket_number: partial.ticket_number ?? "T-000001",
    title: partial.title ?? "VPN не работает",
    status: partial.status ?? "queued",
    priority: partial.priority ?? "P2",
    queue: partial.queue ?? "Service Desk",
    assignee: partial.assignee ?? null,
    requester_name: partial.requester_name ?? "Иван Петров",
    reason: partial.reason ?? "Требуется действие",
    href: partial.href ?? `/app/tickets/${partial.ticket_id ?? "ticket-1"}`,
    ...partial,
  };
}

function section(partial: Partial<CommandCenterSection>): CommandCenterSection {
  return {
    key: partial.key ?? "operator_action",
    title: partial.title ?? "Требует действия оператора",
    description: partial.description ?? "Описание секции",
    severity: partial.severity ?? "warning",
    count: partial.count ?? partial.items?.length ?? 1,
    items: partial.items ?? [item({})],
    action: partial.action ?? null,
    ...partial,
  } as CommandCenterSection;
}

describe("buildSupportActionTasks", () => {
  it("builds a task from new_unassigned", () => {
    const tasks = buildSupportActionTasks([
      section({
        key: "new_unassigned",
        title: "Новые без владельца",
        items: [item({ ticket_id: "ticket-1", assignee: null })],
      }),
    ]);

    expect(tasks).toHaveLength(1);
    expect(tasks[0]).toMatchObject({
      ticketId: "ticket-1",
      taskType: "triage_unassigned",
      actionLabel: "Взять в работу",
      reasonBadges: ["Новые без владельца"],
    });
  });

  it("consolidates same ticket across SLA, unread messages and failed operation", () => {
    const tasks = buildSupportActionTasks([
      section({
        key: "unread_user_messages",
        title: "Сообщения пользователей",
        severity: "warning",
        items: [item({ ticket_id: "ticket-1", unread_user_messages: 2, updated_at: "2026-05-20T10:00:00Z" })],
      }),
      section({
        key: "failed_operation",
        title: "Ошибки операций",
        severity: "critical",
        items: [
          item({
            ticket_id: "ticket-1",
            operation: { id: "op-1", status: "failed", tool_name: "diag.logs.collect", error_summary: "timeout" },
          }),
        ],
      }),
      section({
        key: "sla_risk",
        title: "SLA риск",
        severity: "critical",
        items: [item({ ticket_id: "ticket-1", sla: { state: "breached", due_at: "2026-05-20T09:00:00Z" } })],
      }),
    ]);

    expect(tasks).toHaveLength(1);
    expect(tasks[0].taskType).toBe("sla_rescue");
    expect(tasks[0].actionLabel).toBe("Спасти SLA");
    expect(tasks[0].severity).toBe("critical");
    expect(tasks[0].reasonBadges).toEqual(["SLA риск", "Ошибки операций", "Сообщения пользователей"]);
    expect(tasks[0].sectionKeys).toEqual(["sla_risk", "failed_operation", "unread_user_messages"]);
  });

  it("keeps similar_spike grouped by similar_group.group_key", () => {
    const tasks = buildSupportActionTasks([
      section({
        key: "similar_tickets_spike",
        title: "Похожие обращения",
        items: [
          item({
            ticket_id: "ticket-1",
            similar_group: { group_key: "vpn-spike", count: 4, window_hours: 24, sample_ticket_ids: ["ticket-1"], reason: "VPN" },
          }),
          item({
            ticket_id: "ticket-2",
            similar_group: { group_key: "vpn-spike", count: 4, window_hours: 24, sample_ticket_ids: ["ticket-2"], reason: "VPN" },
          }),
        ],
      }),
    ]);

    expect(tasks).toHaveLength(1);
    expect(tasks[0]).toMatchObject({
      id: "similar_spike:vpn-spike",
      taskType: "similar_spike",
      actionLabel: "Проверить всплеск",
    });
    expect(tasks[0].sourceItems).toHaveLength(2);
  });

  it("sorts breached SLA before normal unread message", () => {
    const tasks = buildSupportActionTasks([
      section({
        key: "unread_user_messages",
        title: "Сообщения пользователей",
        items: [item({ ticket_id: "ticket-2", unread_user_messages: 1, updated_at: "2026-05-20T12:00:00Z" })],
      }),
      section({
        key: "sla_risk",
        title: "SLA риск",
        severity: "critical",
        items: [item({ ticket_id: "ticket-1", sla: { state: "breached", due_at: "2026-05-20T08:00:00Z" } })],
      }),
    ]);

    expect(tasks.map((task) => task.ticketId)).toEqual(["ticket-1", "ticket-2"]);
  });
});

describe("filterSupportActionTasks", () => {
  it("filters by task type", () => {
    const tasks = buildSupportActionTasks([
      section({ key: "new_unassigned", title: "Новые без владельца", items: [item({ ticket_id: "ticket-1" })] }),
      section({ key: "failed_operation", title: "Ошибки операций", items: [item({ ticket_id: "ticket-2" })] }),
    ]);

    expect(filterSupportActionTasks(tasks, { taskTypes: ["operation_failed"] }).map((task) => task.ticketId)).toEqual([
      "ticket-2",
    ]);
  });
});

describe("groupSupportActionTasksForKanban", () => {
  it("renders read-only Kanban groups from the task projection", () => {
    const tasks = buildSupportActionTasks([
      section({ key: "new_unassigned", title: "Новые без владельца", items: [item({ ticket_id: "ticket-1" })] }),
      section({ key: "closure_blocked", title: "Блокеры закрытия", items: [item({ ticket_id: "ticket-2" })] }),
    ]);

    const groups = groupSupportActionTasksForKanban(tasks);

    expect(groups.map((group) => group.title)).toContain("Intake");
    expect(groups.map((group) => group.title)).toContain("Closure");
    expect(groups.find((group) => group.key === "intake")?.tasks.map((task) => task.ticketId)).toEqual(["ticket-1"]);
  });
});
