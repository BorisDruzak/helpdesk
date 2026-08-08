import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchSupportTicketTimeline,
  fetchSupportTicketWorkspace,
  fetchSupportWorkspaceSummary,
  postSupportTicketRead,
} from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("support queue API", () => {
  it("loads workspace summary from the lightweight support endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "success",
          data: {
            views: {
              needs_action: 12,
              sla_risk: 8,
              unassigned: 7,
              requester_replied: 15,
            },
            queues: [{ id: "servicedesk_l1", code: "servicedesk_l1", name: "ServiceDesk L1", count: 18 }],
            smart_view_counts: [{ value: "my_action", label: "Нужен ответ", count: 12 }],
            smart_view_options: [{ value: "my_action", label: "Нужен ответ" }],
          },
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const summary = await fetchSupportWorkspaceSummary(300);

    expect(fetchMock).toHaveBeenCalledWith("/api/web/support/workspace/summary?limit=300", {
      credentials: "same-origin",
    });
    expect(summary.views.needs_action).toBe(12);
    expect(summary.queues[0]).toEqual({
      id: "servicedesk_l1",
      code: "servicedesk_l1",
      name: "ServiceDesk L1",
      count: 18,
    });
  });

  it("loads the unavailable Knowledge projection from the aggregate ticket workspace", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "success",
          data: {
            knowledge: {
              ticket_id: "ticket-1",
              status: "unavailable",
              code: "knowledge_unavailable",
              suggestions: [],
              similar_tickets: [],
              articles: [],
              requester_attempts: [],
              ai_summary: { text: null, sources: [] },
              diagnostics: {
                provider: "external_knowledge_port",
                provider_version: "v1",
                provider_status: "unavailable",
                external_provider_status: "not_configured",
                fallback_reason: "knowledge_unavailable",
              },
            },
          },
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const workspace = await fetchSupportTicketWorkspace("ticket-1");

    expect(fetchMock).toHaveBeenCalledWith("/api/web/support/tickets/ticket-1/workspace", {
      credentials: "same-origin",
    });
    expect(workspace.knowledge).toMatchObject({
      status: "unavailable",
      code: "knowledge_unavailable",
      suggestions: [],
    });
  });

  it("loads filtered ticket timeline from the typed support endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "success",
          data: {
            ticket_id: "ticket-1",
            filter: "diagnostics",
            total: 1,
            limit: 80,
            items: [
              {
                message_id: null,
                event_id: 7,
                event_type: "tool_call_result",
                event_category: "diagnostics",
                event_label: "Tool Call Result",
                event_details: {},
                from_role: "system",
                sender_display_name: "Система",
                text: "Результат инструмента: dns.resolve",
                ts: "2026-05-05T09:18:00+05:00",
                visibility: "system",
                direction: "system",
                attachments: [],
                reply_to: null,
                tool_name: "dns.resolve",
                tool_status: "succeeded",
                result_summary: "DNS resolved",
                result_preview: null,
                operation_steps: [{ name: "DNS", status: "ok", value: "example.test -> 192.0.2.10" }],
              },
            ],
          },
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const timeline = await fetchSupportTicketTimeline("ticket-1", "diagnostics");

    expect(fetchMock).toHaveBeenCalledWith("/api/web/support/tickets/ticket-1/timeline?filter=diagnostics", {
      credentials: "same-origin",
    });
    expect(timeline.items).toHaveLength(1);
    const item = timeline.items.at(0);
    expect(item?.event_category).toBe("diagnostics");
    expect(item?.operation_steps?.at(0)?.name).toBe("DNS");
  });

  it("marks requester messages as read through the ticket read endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "success",
          ticket_id: "ticket-1",
          read_scope: "staff",
          last_read_event_id: 42,
          no_op: false,
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await postSupportTicketRead("ticket-1", 42);

    expect(fetchMock).toHaveBeenCalledWith("/api/web/support/tickets/ticket-1/read", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ last_read_event_id: 42 }),
    });
    expect(result.last_read_event_id).toBe(42);
  });
});
