import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KnowledgePortalSearchPage } from "./search-page";

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
      <KnowledgePortalSearchPage />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("KnowledgePortalSearchPage", () => {
  it("searches requester-safe knowledge through the public-compatible endpoint", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/knowledge/search" && init?.method === "POST") {
        return jsonResponse({
          status: "ok",
          display_message: "Поиск выполнен без AI",
          search_mode: "keyword_only",
          effective_mode: "keyword_only",
          ai_used: false,
          results: [
            {
              item_id: "ki-1",
              slug: "vpn-access",
              title: "Доступ к VPN",
              summary: "Как восстановить подключение к VPN",
              visibility: "requester",
            },
          ],
        });
      }
      throw new Error(`Unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderPage();

    expect(await screen.findByRole("heading", { name: "Поиск по базе знаний" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Запрос"), { target: { value: "VPN" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));

    await waitFor(() => expect(screen.getByText("Доступ к VPN")).toBeInTheDocument());
    expect(screen.getByText("AI не использовался")).toBeInTheDocument();
    expect(screen.getByText("Как восстановить подключение к VPN")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/knowledge/search",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(JSON.parse(fetchMock.mock.calls[0][1]?.body as string)).toMatchObject({
      query: "VPN",
      actor_role: "requester",
      surface: "requester_portal",
    });

    const visibleText = document.body.textContent ?? "";
    expect(visibleText).not.toContain("Рџ");
  });
});
