import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KnowledgeIndexingPage } from "./indexing-page";

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
      <KnowledgeIndexingPage />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("KnowledgeIndexingPage", () => {
  it("renders Russian indexing status and runs item reindex", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/knowledge/indexing/status") {
        return jsonResponse({
          status: "ok",
          indexing: {
            embeddings: { indexed: 2, failed: 1, disabled: 3, pending: 0 },
            jobs: { completed: 1 },
            vector_enabled: false,
            embedding_model: null,
          },
        });
      }
      if (url === "/api/web/knowledge/indexing/jobs") {
        return jsonResponse({
          status: "ok",
          jobs: [{ job_id: "job-123456", scope_type: "item", status: "completed", stats_json: { indexed_embeddings: 2, failed_embeddings: 0 } }],
        });
      }
      if (url === "/api/web/knowledge/items") {
        return jsonResponse({
          status: "ok",
          items: [
            {
              item_id: "ki-1",
              space_id: "space-1",
              slug: "vpn-access",
              item_type: "article",
              type: "article",
              title: "VPN access",
              summary: "VPN reconnect guide",
              status: "published",
              visibility: "requester",
            },
          ],
        });
      }
      if (url === "/api/web/knowledge/indexing/reindex-item" && init?.method === "POST") {
        return jsonResponse({
          status: "ok",
          display_message: "Индексация embeddings выполнена",
          job: { job_id: "job-2", scope_type: "item", status: "completed" },
          embeddings: [{ embedding_id: "emb-1", chunk_id: "chunk-1", item_id: "ki-1", version_id: "ver-1", status: "disabled", content_hash: "hash", visibility: "requester" }],
          stats: { disabled_embeddings: 1 },
        });
      }
      return jsonResponse({ status: "error" }, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    expect(await screen.findByRole("heading", { name: "Индексация знаний" })).toBeInTheDocument();
    expect(await screen.findByText("Vector поиск выключен")).toBeInTheDocument();
    expect(screen.getByText(/Raw vectors не показываются/)).toBeInTheDocument();
    expect(await screen.findByText("job-1234")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Поиск статьи"), { target: { value: "vpn" } });
    fireEvent.click(await screen.findByRole("button", { name: /VPN access/ }));
    fireEvent.click(screen.getByText("Advanced: raw ids"));
    fireEvent.change(screen.getByLabelText("Raw version id"), { target: { value: "ver-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Запустить reindex" }));

    await waitFor(() => expect(screen.getByText("Индексация embeddings выполнена")).toBeInTheDocument());
    const reindexCall = fetchMock.mock.calls.find((call) => String(call[0]) === "/api/web/knowledge/indexing/reindex-item");
    expect(JSON.parse(reindexCall?.[1]?.body as string)).toMatchObject({ item_id: "ki-1", version_id: "ver-1" });
  });
});
