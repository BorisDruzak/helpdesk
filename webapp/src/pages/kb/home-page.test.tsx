import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KnowledgePortalHomePage } from "./home-page";

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
      <MemoryRouter>
        <KnowledgePortalHomePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("KnowledgePortalHomePage", () => {
  it("shows portal home sections with requester-safe articles", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/knowledge/portal/home") {
        return jsonResponse({
          status: "ok",
          display_message: "Портал базы знаний загружен",
          spaces: [
            {
              space_id: "ks-1",
              code: "it",
              title: "IT",
              description: "Инструкции для сотрудников",
              visibility: "requester",
              lifecycle_status: "active",
            },
          ],
          featured_articles: [
            {
              item_id: "ki-1",
              space_id: "ks-1",
              slug: "vpn-access",
              item_type: "article",
              type: "article",
              title: "Доступ к VPN",
              summary: "Как восстановить подключение",
              status: "published",
              visibility: "requester",
              tags: ["vpn"],
            },
          ],
          recent_articles: [],
          popular_articles: [],
        });
      }
      throw new Error(`Unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderPage();

    expect(await screen.findByRole("heading", { name: "База знаний" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Доступ к VPN")).toBeInTheDocument());
    expect(screen.getByText("IT")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Доступ к VPN/i })).toHaveAttribute("href", "/app/kb/articles/vpn-access");
    expect(screen.getByRole("link", { name: "Поиск" })).toHaveAttribute("href", "/app/kb/search");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/knowledge/portal/home",
      expect.objectContaining({ credentials: "same-origin" }),
    );
    expect(document.body.textContent ?? "").not.toContain("Рџ");
  });
});
