import { describe, expect, it } from "vitest";

import type { CommandCenterSection } from "./api";
import { buildPrioritizedAttentionList } from "./prioritization";

function section(partial: Partial<CommandCenterSection>): CommandCenterSection {
  return {
    key: "operator_action",
    title: "Требует действия оператора",
    description: "Описание",
    severity: "warning",
    count: 1,
    items: [],
    action: null,
    ...partial,
  } as CommandCenterSection;
}

describe("buildPrioritizedAttentionList", () => {
  it("deduplicates tickets and keeps all reason badges", () => {
    const sections = [
      section({
        key: "sla_risk",
        title: "SLA риск",
        severity: "critical",
        items: [
          {
            id: "ticket-1:sla",
            ticket_id: "ticket-1",
            title: "VPN down",
            status: "in_progress",
            reason: "SLA нарушен",
            href: "/app/tickets/ticket-1",
          },
        ],
      }),
      section({
        key: "failed_operation",
        title: "Ошибки операций",
        items: [
          {
            id: "ticket-1:failed",
            ticket_id: "ticket-1",
            title: "VPN down",
            status: "in_progress",
            reason: "Операция завершилась ошибкой",
            href: "/app/tickets/ticket-1",
          },
        ],
      }),
    ];

    const items = buildPrioritizedAttentionList(sections);

    expect(items).toHaveLength(1);
    expect(items[0].reason_badges).toEqual(["SLA риск", "Ошибки операций"]);
    expect(items[0].section_keys).toEqual(["sla_risk", "failed_operation"]);
  });

  it("puts breached SLA before informational diagnostics", () => {
    const items = buildPrioritizedAttentionList([
      section({
        key: "diagnostics_recommended",
        title: "Рекомендована диагностика",
        severity: "info",
        items: [
          {
            id: "ticket-2:diag",
            ticket_id: "ticket-2",
            title: "Need diagnostics",
            status: "queued",
            reason: "Диагностика рекомендована",
            href: "/app/tickets/ticket-2",
          },
        ],
      }),
      section({
        key: "sla_risk",
        title: "SLA риск",
        severity: "critical",
        items: [
          {
            id: "ticket-3:sla",
            ticket_id: "ticket-3",
            title: "Breach",
            status: "queued",
            reason: "SLA нарушен",
            href: "/app/tickets/ticket-3",
          },
        ],
      }),
    ]);

    expect(items[0].ticket_id).toBe("ticket-3");
  });
});
