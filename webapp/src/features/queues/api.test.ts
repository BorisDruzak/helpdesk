import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchSupportTicketKnowledgeSuggestions,
  fetchSupportTicketTimeline,
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

  it("loads ticket knowledge suggestions from the typed support endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "success",
          data: {
            ticket_id: "ticket-1",
            similar_tickets: [
              {
                id: "ticket-1011",
                number: "T-001011",
                subject: "Ошибка 502",
                resolution_summary: "Перезапуск upstream.",
              },
            ],
            articles: [{ id: "KB-502", title: "Ошибка 502 Bad Gateway", url: "/app/knowledge/KB-502" }],
            ai_summary: { text: "AI-рекомендация / Бета: проверьте источники.", sources: ["KB-502", "T-001011"] },
          },
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const knowledge = await fetchSupportTicketKnowledgeSuggestions("ticket-1");

    expect(fetchMock).toHaveBeenCalledWith("/api/web/support/tickets/ticket-1/knowledge-suggestions", {
      credentials: "same-origin",
    });
    expect(knowledge.articles[0].id).toBe("KB-502");
    expect(knowledge.ai_summary.sources).toContain("T-001011");
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

    expect(fetchMock).toHaveBeenCalledWith("/api/tickets/ticket-1/read", {
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
