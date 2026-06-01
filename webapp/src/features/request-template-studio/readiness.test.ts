import { describe, expect, it } from "vitest";

import { buildReadinessSummary } from "./readiness";
import type { RequestStudioItem } from "./studio-model";

function item(overrides: Partial<RequestStudioItem> = {}): RequestStudioItem {
  return {
    id: "access",
    group: "Доступы",
    isTechnical: false,
    service: { code: "access", public_title: "Доступы", lifecycle_status: "published", visibility: "public" },
    offering: {
      code: "grant_access",
      full_code: "access.grant_access",
      service_code: "access",
      public_title: "Выдать доступ",
      lifecycle_status: "published",
      visibility: "public",
      request_template_key: "access",
    },
    template: {
      template_code: "access",
      version: "1.0.0",
      public_title: "Выдать доступ",
      description: null,
      ticket_type: "access_request",
      is_active: true,
      published_at: "2026-06-01T00:00:00Z",
      form_schema_id: "access",
      form_schema_version: "1.0.0",
      routing_policy_code: "route_l1",
      priority_policy_code: null,
      sla_policy_code: "sla_default",
      ola_policy_code: null,
      approval_policy_code: null,
      closure_policy_code: "closure_basic",
      diagnostic_policy_code: null,
      visibility_policy_code: "visibility_default",
      notification_policy_code: null,
      reporting_policy_code: null,
    },
    formPreview: {
      title: "Выдать доступ",
      description: "Форма доступа",
      source: "forms-builder",
      fields: [{ key: "system", label: "Система", type: "text", required: true }],
    },
    processProfile: {
      profileName: "Заявка на доступ",
      requiredMissing: [],
      recommendedMissing: [],
      readyLabels: ["маршрут", "SLA", "закрытие"],
      issueLabels: [],
    },
    processBlocks: [],
    readinessStatus: "ok",
    links: { serviceCatalog: "#", forms: "#", policyHealth: "#" },
    ...overrides,
  } as RequestStudioItem;
}

describe("request studio readiness", () => {
  it("marks a complete draft as publishable from Studio when safe publish is available", () => {
    const summary = buildReadinessSummary(
      item(),
      {
        template_code: "access",
        routing: {},
        priority: {},
        sla: {},
        ola: {},
        approval: {},
        closure: {},
        visibility: {},
        diagnostic: {},
        warnings: [],
        would_create_ticket: false,
      },
      { hasDraft: true },
    );

    expect(summary.status).toBe("ok");
    expect(summary.blockers).toEqual([]);
    expect(summary.ready).toContain("Черновик готов к публикации из Studio.");
    expect(summary.recommendations).not.toContain("Studio publish недоступен до safe publish contract.");
  });

  it("does not duplicate the missing form blocker when the process block already explains it", () => {
    const summary = buildReadinessSummary(
      item({
        formPreview: { title: "Пустая форма", description: "", source: "forms-builder", fields: [] },
        processBlocks: [
          {
            key: "form",
            title: "Форма пользователя",
            status: "error",
            explanation: "Форма не найдена. Без формы публикация невозможна.",
            actionLabel: "Настроить форму",
          },
        ],
      }),
      undefined,
      { hasDraft: true },
    );

    expect(summary.blockers).toEqual(["Форма не найдена. Без формы публикация невозможна."]);
  });
});
