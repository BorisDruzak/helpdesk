import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KnowledgeSupportWorkspacePage } from "./support-workspace-page";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderWorkspace(route = "/app/knowledge") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/app/knowledge" element={<KnowledgeSupportWorkspacePage />} />
          <Route path="/app/knowledge/articles/:itemId" element={<KnowledgeSupportWorkspacePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const itemsPayload = {
  status: "ok",
  items: [
    {
      item_id: "item-runbook",
      slug: "vpn-runbook",
      title: "VPN support runbook",
      summary: "Support steps for reconnecting VPN.",
      item_type: "runbook",
      type: "runbook",
      status: "published",
      visibility: "support_internal",
      space_id: "space-it",
      current_version_id: "version-runbook",
      current_version: { version_id: "version-runbook", item_id: "item-runbook", version_number: 2, title: "VPN support runbook", body_format: "markdown" },
    },
    {
      item_id: "item-requester",
      slug: "vpn-requester",
      title: "VPN requester guide",
      summary: "Requester-safe VPN answer.",
      item_type: "article",
      type: "article",
      status: "published",
      visibility: "requester",
      space_id: "space-it",
      current_version_id: "version-requester",
      current_version: { version_id: "version-requester", item_id: "item-requester", version_number: 1, title: "VPN requester guide", body_format: "markdown" },
    },
    {
      item_id: "item-known-error",
      slug: "vpn-error",
      title: "VPN known error 809",
      summary: "Known error and workaround.",
      item_type: "known_error",
      type: "known_error",
      status: "published",
      visibility: "support_internal",
      space_id: "space-it",
      current_version_id: "version-error",
      current_version: { version_id: "version-error", item_id: "item-known-error", version_number: 1, title: "VPN known error 809", body_format: "markdown" },
    },
  ],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("KnowledgeSupportWorkspacePage", () => {
  it("renders support search, filters runbooks and opens selected article details", async () => {
    const fetchMock = vi.fn((url: string) => {
      if (url === "/api/web/knowledge/items") {
        return Promise.resolve(jsonResponse(itemsPayload));
      }
      if (url === "/api/web/knowledge/items/item-runbook/versions") {
        return Promise.resolve(
          jsonResponse({
            status: "ok",
            versions: [
              {
                version_id: "version-runbook",
                item_id: "item-runbook",
                version_number: 2,
                title: "VPN support runbook",
                summary: "Support steps for reconnecting VPN.",
                body_format: "markdown",
                body: "Restart VPN service and verify tunnel health.",
              },
            ],
          }),
        );
      }
      return Promise.resolve(jsonResponse({ status: "ok", versions: [] }));
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("navigator", { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });

    renderWorkspace("/app/knowledge/articles/item-runbook");

    expect(await screen.findByRole("heading", { name: "База знаний поддержки" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Поиск по статье, runbook, known error")).toBeInTheDocument();
    expect(await screen.findAllByText("VPN support runbook")).toHaveLength(2);

    fireEvent.click(screen.getByRole("button", { name: "Runbooks" }));
    const list = screen.getByTestId("support-knowledge-results");
    expect(within(list).getByText("VPN support runbook")).toBeInTheDocument();
    expect(within(list).queryByText("VPN requester guide")).not.toBeInTheDocument();

    expect(screen.getByRole("heading", { name: "VPN support runbook" })).toBeInTheDocument();
    expect(await screen.findByText("Restart VPN service and verify tunnel health.")).toBeInTheDocument();
    expect(screen.getAllByText("support_internal").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Copy-safe answer" }));
    await waitFor(() => expect(navigator.clipboard.writeText).not.toHaveBeenCalled());
    expect(screen.getByText("Только requester-safe материалы можно копировать как ответ пользователю.")).toBeInTheDocument();
  });

  it("runs support Ask preview and renders debug score, chunk and policy details", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/knowledge/items") {
        return Promise.resolve(jsonResponse(itemsPayload));
      }
      if (url === "/api/web/knowledge/items/item-runbook/versions") {
        return Promise.resolve(jsonResponse({ status: "ok", versions: [] }));
      }
      if (url === "/api/web/knowledge/ask/preview" && init?.method === "POST") {
        return Promise.resolve(
          jsonResponse({
            status: "ok",
            answer: null,
            answer_status: "provider_unavailable",
            display_message: "AI-провайдер недоступен. Ниже показаны результаты поиска.",
            ai_used: false,
            effective_mode: "rag_answer",
            search_mode: "rag_answer",
            fallback_mode: "provider_unavailable",
            audit_id: "audit-1",
            citations: [{ ref_id: "chunk-1", title: "VPN support runbook", chunk_id: "chunk-1", segment_id: "segment-1" }],
            retrieval_results: [
              {
                item: itemsPayload.items[0],
                snippet: "Restart VPN service and verify tunnel health.",
                chunk_id: "chunk-1",
                segment_id: "segment-1",
                score: 57,
                score_parts: { keyword_title: 42, keyword_chunk: 15 },
                source_mode: ["keyword", "segment"],
                citations: [{ chunk_id: "chunk-1", segment_id: "segment-1" }],
              },
            ],
          }),
        );
      }
      return Promise.resolve(jsonResponse({ status: "ok", versions: [] }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWorkspace("/app/knowledge/articles/item-runbook");

    await screen.findByRole("heading", { name: "База знаний поддержки" });
    fireEvent.change(screen.getByLabelText("Ask debug query"), { target: { value: "VPN error" } });
    fireEvent.click(screen.getByRole("button", { name: "Проверить Ask" }));

    await waitFor(() => expect(screen.getByText("provider_unavailable")).toBeInTheDocument());
    expect(screen.getByText("rag_answer")).toBeInTheDocument();
    expect(screen.getByText("audit-1")).toBeInTheDocument();
    expect(screen.getByText("chunk-1")).toBeInTheDocument();
    expect(screen.getByText("segment-1")).toBeInTheDocument();
    expect(screen.getByText("keyword_title: 42")).toBeInTheDocument();
    expect(screen.getByText("keyword_chunk: 15")).toBeInTheDocument();
    expect(JSON.parse(fetchMock.mock.calls.find((call) => String(call[0]) === "/api/web/knowledge/ask/preview")?.[1]?.body as string)).toMatchObject({
      query: "VPN error",
      surface: "support_ask_debug",
      limit: 5,
    });
  });

  it("links the selected article to ticket context and records support feedback", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/knowledge/items") {
        return Promise.resolve(jsonResponse(itemsPayload));
      }
      if (url === "/api/web/knowledge/items/item-requester/versions") {
        return Promise.resolve(
          jsonResponse({
            status: "ok",
            versions: [
              {
                version_id: "version-requester",
                item_id: "item-requester",
                version_number: 1,
                title: "VPN requester guide",
                summary: "Requester-safe VPN answer.",
                body_format: "markdown",
                body: "Reconnect VPN from the requester portal.",
              },
            ],
          }),
        );
      }
      if (url === "/api/web/support/tickets/ticket-1/kb_links" && init?.method === "POST") {
        return Promise.resolve(jsonResponse({ status: "ok", kb_link: { id: 42, article_ref: "item-requester" } }));
      }
      if (url === "/api/knowledge/feedback" && init?.method === "POST") {
        return Promise.resolve(jsonResponse({ status: "ok", event: { event_id: "event-1" } }));
      }
      return Promise.resolve(jsonResponse({ status: "ok", versions: [] }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWorkspace("/app/knowledge/articles/item-requester?ticket_id=ticket-1");

    expect(await screen.findByText("Ticket context")).toBeInTheDocument();
    expect(screen.getByText("ticket-1")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "VPN requester guide" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Связать с тикетом" }));
    await waitFor(() => expect(screen.getByText("Статья связана с тикетом.")).toBeInTheDocument());
    expect(JSON.parse(fetchMock.mock.calls.find((call) => String(call[0]) === "/api/web/support/tickets/ticket-1/kb_links")?.[1]?.body as string)).toMatchObject({
      article_ref: "item-requester",
      title: "VPN requester guide",
      source: "knowledge_support_workspace",
    });

    fireEvent.click(screen.getByRole("button", { name: "Отметить использование" }));
    await waitFor(() => expect(screen.getByText("Использование статьи записано.")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Сообщить о слабой статье" }));
    await waitFor(() => expect(screen.getByText("Слабая статья отмечена для улучшения.")).toBeInTheDocument());

    const feedbackBodies = fetchMock.mock.calls
      .filter((call) => String(call[0]) === "/api/knowledge/feedback")
      .map((call) => JSON.parse(call[1]?.body as string));
    expect(feedbackBodies).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          item_id: "item-requester",
          version_id: "version-requester",
          event_type: "support_used",
          ticket_id: "ticket-1",
          surface: "support_workspace",
        }),
        expect.objectContaining({
          item_id: "item-requester",
          version_id: "version-requester",
          event_type: "not_helpful",
          result: "weak_article_reported",
          ticket_id: "ticket-1",
          surface: "support_workspace",
        }),
      ]),
    );
  });
});
