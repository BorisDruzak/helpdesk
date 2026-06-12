import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KnowledgePortalCollectionPage } from "./collection-page";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderPage(path: string, route: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={route} element={<KnowledgePortalCollectionPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("KnowledgePortalCollectionPage", () => {
  it("renders requester-safe articles for a space", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/knowledge/portal/spaces/it") {
        return jsonResponse({
          status: "ok",
          collection_type: "space",
          collection_code: "it",
          title: "IT",
          description: "Инструкции для сотрудников",
          articles: [
            {
              item_id: "ki-1",
              slug: "vpn-access",
              title: "Доступ к VPN",
              summary: "Как восстановить подключение",
              visibility: "requester",
            },
          ],
        });
      }
      throw new Error(`Unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderPage("/app/kb/spaces/it", "/app/kb/spaces/:spaceCode");

    expect(await screen.findByRole("heading", { name: "IT" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Доступ к VPN")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /Доступ к VPN/i })).toHaveAttribute("href", "/app/kb/articles/vpn-access");
    expect(fetchMock).toHaveBeenCalledWith("/api/knowledge/portal/spaces/it", { credentials: "same-origin" });
  });
});
