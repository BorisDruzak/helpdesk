import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KnowledgeSearchSettingsPage } from "./search-settings-page";

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
      <KnowledgeSearchSettingsPage />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("KnowledgeSearchSettingsPage", () => {
  it("renders Russian AI-off search controls and saves settings", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/knowledge/search-settings" && !init?.method) {
        return jsonResponse({
          status: "ok",
          display_message: "Настройки поиска загружены",
          settings: {
            settings_id: "global",
            search_mode: "keyword_only",
            effective_mode: "keyword_only",
            fallback_mode: null,
            ai_enabled: false,
            keyword_enabled: true,
            full_text_enabled: false,
            vector_enabled: false,
            rerank_enabled: false,
            ai_query_rewrite_enabled: false,
            rag_answer_enabled: false,
            keyword_weight: 1,
            full_text_weight: 1,
            vector_weight: 1,
            max_results: 10,
            snippet_length: 180,
            metadata_json: {},
          },
        });
      }
      if (url === "/api/web/knowledge/search-settings" && init?.method === "POST") {
        return jsonResponse({
          status: "ok",
          display_message: "Настройки поиска сохранены",
          settings: {
            settings_id: "global",
            search_mode: "hybrid_no_ai",
            effective_mode: "hybrid_no_ai",
            ai_enabled: false,
            keyword_enabled: true,
            full_text_enabled: true,
            vector_enabled: false,
            rerank_enabled: false,
            ai_query_rewrite_enabled: false,
            rag_answer_enabled: false,
            keyword_weight: 1,
            full_text_weight: 1,
            vector_weight: 1,
            max_results: 8,
            snippet_length: 220,
            metadata_json: {},
          },
        });
      }
      if (url === "/api/web/knowledge/search" && init?.method === "POST") {
        return jsonResponse({
          status: "ok",
          display_message: "Поиск выполнен без AI",
          search_mode: "keyword_only",
          effective_mode: "keyword_only",
          ai_used: false,
          results: [
            {
              item_id: "ki-1",
              slug: "vpn-keyword-baseline",
              title: "VPN keyword baseline",
              summary: "Keyword search result without AI",
              visibility: "requester",
              score: 1,
            },
          ],
        });
      }
      throw new Error(`Unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderPage();

    expect(await screen.findByRole("heading", { name: "Настройки поиска базы знаний" })).toBeInTheDocument();
    expect(screen.getByText("AI выключен")).toBeInTheDocument();
    expect(screen.getAllByText("keyword_only").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByLabelText("Keyword поиск")).toBeChecked();
    expect(screen.getByLabelText("Vector поиск")).not.toBeChecked();
    expect(screen.getByLabelText("RAG ответы")).not.toBeChecked();
    expect(screen.getByDisplayValue("10")).toBeInTheDocument();
    expect(screen.getByDisplayValue("180")).toBeInTheDocument();

    const modeSelect = screen.getByLabelText("Режим поиска") as HTMLSelectElement;
    fireEvent.change(modeSelect, { target: { value: "hybrid_no_ai" } });
    fireEvent.click(screen.getByLabelText("Full-text поиск"));
    fireEvent.change(screen.getByLabelText("Максимум результатов"), { target: { value: "8" } });
    fireEvent.change(screen.getByLabelText("Длина сниппета"), { target: { value: "220" } });
    await waitFor(() => expect(modeSelect.value).toBe("hybrid_no_ai"));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить настройки" }));

    await waitFor(() => expect(screen.getByText("Настройки поиска сохранены")).toBeInTheDocument());
    const postCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/knowledge/search-settings" && call[1]?.method === "POST");
    expect(postCall).toBeDefined();
    expect(postCall?.[1]).toEqual(expect.objectContaining({ method: "POST", credentials: "same-origin" }));
    expect(JSON.parse(postCall?.[1]?.body as string)).toMatchObject({
      search_mode: "hybrid_no_ai",
      full_text_enabled: true,
      vector_enabled: false,
      max_results: 8,
      snippet_length: 220,
    });

    fireEvent.change(screen.getByLabelText("Проверочный запрос"), { target: { value: "VPN" } });
    fireEvent.click(screen.getByRole("button", { name: "Проверить поиск" }));

    await waitFor(() => expect(screen.getByText("VPN keyword baseline")).toBeInTheDocument());
    expect(screen.getByText("Поиск выполнен без AI")).toBeInTheDocument();
    expect(screen.getByText("AI не использовался")).toBeInTheDocument();
    expect(screen.getAllByText("keyword_only").length).toBeGreaterThanOrEqual(1);
    const previewCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/knowledge/search" && call[1]?.method === "POST");
    expect(previewCall).toBeDefined();
    expect(previewCall?.[1]).toEqual(expect.objectContaining({ method: "POST", credentials: "same-origin" }));
    expect(JSON.parse(previewCall?.[1]?.body as string)).toMatchObject({
      query: "VPN",
      actor_role: "support",
      surface: "admin_knowledge_search",
    });

    const visibleText = document.body.textContent ?? "";
    expect(visibleText).not.toContain("Рџ");
  });
});
