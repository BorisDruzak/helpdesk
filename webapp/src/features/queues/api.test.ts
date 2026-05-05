import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchSupportTicketKnowledgeSuggestions, fetchSupportWorkspaceSummary } from "./api";

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
});
