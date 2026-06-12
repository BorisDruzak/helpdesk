import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ArticleSegmentationPanel } from "./article-segmentation-panel";
import type { KnowledgeItem, KnowledgeItemVersion } from "./api";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const item: KnowledgeItem = {
    item_id: "ki-1",
    space_id: "ks-1",
    slug: "vpn-access",
    item_type: "article",
    type: "article",
    title: "VPN access",
    status: "draft",
    visibility: "requester",
  };
  const version: KnowledgeItemVersion = {
    version_id: "ver-1",
    item_id: "ki-1",
    version_number: 1,
    title: "VPN access",
    body_format: "markdown",
    body: "# VPN access\n\nCheck the tunnel adapter and DNS suffix before escalation.\n\n## MFA token\n\nAsk the requester to refresh the authenticator prompt.",
  };

  render(
    <QueryClientProvider client={queryClient}>
      <ArticleSegmentationPanel item={item} version={version} canManage />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ArticleSegmentationPanel", () => {
  it("creates a manual segment from selected article text and runs auto segmentation", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/knowledge/items/ki-1/segments" && !init?.method) {
        return jsonResponse({
          status: "ok",
          segments: [
            {
              segment_id: "seg-1",
              item_id: "ki-1",
              version_id: "ver-1",
              segment_index: 1,
              segment_type: "manual",
              title: "VPN checks",
              text: "Check the tunnel adapter",
              keywords: ["vpn"],
              boost: 2,
              visibility: "requester",
              status: "active",
              source: "editor_selection",
              embedding_enabled: true,
              full_text_enabled: true,
            },
          ],
        });
      }
      if (url === "/api/web/knowledge/segmentation-profiles") {
        return jsonResponse({
          status: "ok",
          profiles: [{ profile_id: "default-auto", code: "default-auto", title: "Авторазметка по заголовкам", mode: "auto", enabled: true }],
        });
      }
      if (url === "/api/web/knowledge/items/ki-1/segments" && init?.method === "POST") {
        return jsonResponse({
          status: "ok",
          display_message: "Сегмент знаний сохранён",
          segment: { segment_id: "seg-2", title: "Tunnel adapter", text: "Check the tunnel adapter and DNS suffix before escalation." },
        });
      }
      if (url === "/api/web/knowledge/items/ki-1/segments/auto" && init?.method === "POST") {
        return jsonResponse({
          status: "ok",
          display_message: "Авторазметка выполнена без AI",
          job: { job_id: "job-1", mode: "auto", status: "completed" },
          segments: [{ segment_id: "seg-auto", title: "VPN access" }],
        });
      }
      throw new Error(`Unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderPanel();

    expect(await screen.findByRole("heading", { name: "Разметка статьи" })).toBeInTheDocument();
    expect(await screen.findByText("VPN checks")).toBeInTheDocument();
    expect(await screen.findByText("Авторазметка по заголовкам")).toBeInTheDocument();
    expect(screen.getByText("Портал заявителя")).toBeInTheDocument();
    expect(screen.getByText("Активный")).toBeInTheDocument();
    expect(screen.getByText("Ручной")).toBeInTheDocument();
    expect(screen.getByText("Выделение редактора")).toBeInTheDocument();
    expect(screen.getByText("вес 2")).toBeInTheDocument();

    const source = screen.getByLabelText("Текст версии для выделения") as HTMLTextAreaElement;
    const selectedText = "Check the tunnel adapter and DNS suffix before escalation.";
    source.focus();
    source.setSelectionRange(source.value.indexOf(selectedText), source.value.indexOf(selectedText) + selectedText.length);
    fireEvent.select(source);
    fireEvent.click(screen.getByRole("button", { name: "Взять выделенный текст" }));

    expect(screen.getByLabelText("Текст сегмента")).toHaveValue(selectedText);
    fireEvent.change(screen.getByLabelText("Заголовок сегмента"), { target: { value: "Tunnel adapter" } });
    fireEvent.change(screen.getByLabelText("Ключевые слова"), { target: { value: "vpn, dns, adapter" } });
    fireEvent.click(screen.getByRole("button", { name: "Создать сегмент" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/web/knowledge/items/ki-1/segments", expect.objectContaining({ method: "POST" })));
    const createCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/knowledge/items/ki-1/segments" && call[1]?.method === "POST");
    expect(JSON.parse(createCall?.[1]?.body as string)).toMatchObject({
      version_id: "ver-1",
      title: "Tunnel adapter",
      text: selectedText,
      keywords: ["vpn", "dns", "adapter"],
      visibility: "requester",
      segment_type: "manual",
    });

    fireEvent.click(screen.getByRole("button", { name: "Запустить авторазметку" }));
    await waitFor(() => expect(screen.getByText("Авторазметка выполнена без AI")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/knowledge/items/ki-1/segments/auto",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );

    const visibleText = document.body.textContent ?? "";
    expect(visibleText).toContain("Вес поиска");
    expect(visibleText).toContain("Полнотекстовый поиск");
    expect(visibleText).toContain("Эмбеддинги");
    expect(visibleText).not.toContain("requesteragent_requester_safe");
    expect(visibleText).not.toContain("Boost");
    expect(visibleText).not.toContain("Full-text");
    expect(visibleText).not.toContain("Embeddings");
    expect(visibleText).not.toContain("boost 2");
    expect(visibleText).not.toContain("editor_selection");
    expect(visibleText).not.toContain("Рџ");
  });
});
