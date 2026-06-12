import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KnowledgePortalArticlePage } from "./article-page";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderPage(slug = "vpn-access") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/app/kb/articles/${slug}`]}>
        <Routes>
          <Route path="/app/kb/articles/:slug" element={<KnowledgePortalArticlePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("KnowledgePortalArticlePage", () => {
  it("loads and renders requester-safe article body", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/knowledge/articles/vpn-access") {
        return jsonResponse({
          status: "ok",
          article: {
            item_id: "ki-1",
            space_id: "ks-1",
            slug: "vpn-access",
            item_type: "article",
            type: "article",
            title: "Доступ к VPN",
            summary: "Как восстановить подключение",
            status: "published",
            visibility: "requester",
            tags: ["vpn", "network"],
            owner_actor_id: "owner",
            review_due_at: "2026-07-01T00:00:00+00:00",
          },
          version: {
            version_id: "ver-1",
            item_id: "ki-1",
            version_number: 1,
            title: "Доступ к VPN",
            summary: "Как восстановить подключение",
            body_format: "markdown",
            body: "# VPN\nПереподключите профиль компании.",
          },
          segments: [{ segment_id: "seg-1", title: "Подключение", text: "Переподключите профиль компании." }],
          related_articles: [],
        });
      }
      if (url === "/api/knowledge/articles/vpn-access/feedback" && init?.method === "POST") {
        return jsonResponse({ status: "ok", event: { event_type: JSON.parse(String(init.body)).helpful ? "helpful" : "not_helpful" } });
      }
      if (url === "/api/knowledge/articles/vpn-access/correction-request" && init?.method === "POST") {
        return jsonResponse({ status: "ok", event: { event_type: "not_helpful", result: "correction_requested" } });
      }
      if (url === "/api/knowledge/articles/vpn-access/bookmark" && init?.method === "POST") {
        return jsonResponse({ status: "ok", bookmark: { bookmarked: true } });
      }
      throw new Error(`Unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderPage();

    expect(await screen.findByRole("heading", { name: "Доступ к VPN" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByText(/Переподключите профиль компании/).length).toBeGreaterThan(0));
    expect(screen.getByText("Как восстановить подключение")).toBeInTheDocument();
    expect(screen.getByText("Подключение")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Полезно" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "В закладки" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Создать обращение" })).toHaveAttribute("href", "/app/requester/new");
    expect(screen.getByLabelText("Комментарий к исправлению")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Полезно" }));
    await waitFor(() => expect(screen.getByText("Спасибо за оценку.")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Комментарий к исправлению"), {
      target: { value: "В шаге 2 нужно указать split tunnel." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Предложить исправление" }));
    await waitFor(() => expect(screen.getByText("Запрос на исправление отправлен.")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "В закладки" }));
    await waitFor(() => expect(screen.getByText("Статья добавлена в закладки.")).toBeInTheDocument());

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/knowledge/articles/vpn-access",
      expect.objectContaining({ credentials: "same-origin" }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/knowledge/articles/vpn-access/feedback",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/knowledge/articles/vpn-access/correction-request",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({ comment: "В шаге 2 нужно указать split tunnel." }),
      }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/knowledge/articles/vpn-access/bookmark",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(document.body.textContent ?? "").not.toContain("Р Сџ");
  });
});
