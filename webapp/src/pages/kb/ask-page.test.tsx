import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KnowledgePortalAskPage } from "./ask-page";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <KnowledgePortalAskPage />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("KnowledgePortalAskPage", () => {
  it("shows AI-disabled fallback and requester-safe search results", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/knowledge/ask" && init?.method === "POST") {
        return jsonResponse({
          status: "ok",
          answer: null,
          answer_status: "ai_disabled",
          display_message: "AI-ответы отключены. Ниже показаны результаты поиска по базе знаний.",
          ai_used: false,
          effective_mode: "keyword_only",
          citations: [],
          retrieval_results: [
            {
              item: {
                item_id: "ki-1",
                space_id: "ks-1",
                slug: "vpn-access",
                item_type: "article",
                type: "article",
                title: "Доступ к VPN",
                summary: "Как восстановить подключение к VPN",
                status: "published",
                visibility: "requester",
              },
              snippet: "Как восстановить подключение к VPN",
              citations: [],
            },
          ],
        });
      }
      throw new Error(`Unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderPage();

    expect(await screen.findByRole("heading", { name: "AI-вопрос по базе знаний" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Вопрос"), { target: { value: "Как подключить VPN?" } });
    fireEvent.click(screen.getByRole("button", { name: "Спросить" }));

    await waitFor(() => expect(screen.getByText("AI отключён")).toBeInTheDocument());
    expect(screen.getByText("AI не использовался")).toBeInTheDocument();
    expect(screen.getByText("Доступ к VPN")).toBeInTheDocument();
    expect(screen.getByText("Как восстановить подключение к VPN")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/knowledge/ask",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(JSON.parse(fetchMock.mock.calls[0][1]?.body as string)).toEqual({
      query: "Как подключить VPN?",
      surface: "requester_portal",
    });

    const visibleText = document.body.textContent ?? "";
    expect(visibleText).not.toContain("Рџ");
  });
});
