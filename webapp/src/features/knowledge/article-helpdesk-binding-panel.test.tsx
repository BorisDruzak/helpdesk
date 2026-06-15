import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ArticleHelpDeskBindingPanel } from "./article-helpdesk-binding-panel";
import type { KnowledgeItem, KnowledgeItemBinding } from "./api";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const item = {
  item_id: "item-1",
  space_id: "space-1",
  slug: "vpn-access",
  item_type: "article",
  type: "article",
  title: "VPN access",
  summary: "VPN help",
  status: "draft",
  visibility: "requester",
  tags: [],
} as KnowledgeItem;

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <ArticleHelpDeskBindingPanel item={item} visibility="requester" />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("ArticleHelpDeskBindingPanel", () => {
  it("edits and deletes existing binding surfaces with localized controls", async () => {
    let bindings: KnowledgeItemBinding[] = [
      {
        binding_id: "binding-1",
        item_id: "item-1",
        service_code: "network",
        offering_code: "network.vpn_issue",
        request_template_key: "network",
        metadata: { surfaces: ["requester_pre_submit"] },
      },
    ];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/service-catalog/current") {
        return jsonResponse({
          services: [
            {
              service_code: "network",
              title: "Сеть и VPN",
              offerings: [
                {
                  full_code: "network.vpn_issue",
                  offering_code: "network.vpn_issue",
                  request_template_key: "network",
                  title: "VPN не подключается",
                },
              ],
            },
          ],
        });
      }
      if (url === "/api/web/knowledge/items/item-1/bindings" && !init?.method) {
        return jsonResponse({ status: "ok", bindings });
      }
      if (url === "/api/web/knowledge/items/item-1/bindings/binding-1" && init?.method === "PATCH") {
        const body = JSON.parse(String(init.body));
        bindings = [{ ...bindings[0], ...body }];
        return jsonResponse({ status: "ok", binding: bindings[0] });
      }
      if (url === "/api/web/knowledge/items/item-1/bindings/binding-1" && init?.method === "DELETE") {
        const [deleted] = bindings;
        bindings = [];
        return jsonResponse({ status: "ok", binding: deleted });
      }
      throw new Error(`Unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);
    vi.spyOn(window, "confirm").mockReturnValue(true);

    renderPanel();

    expect(await screen.findByRole("heading", { name: "Связь с обращениями" })).toBeInTheDocument();
    const savedSection = (await screen.findByText("Сохранённые связи")).closest("div");
    expect(savedSection).not.toBeNull();
    const saved = within(savedSection as HTMLElement).getByText(/VPN не подключается/);
    expect(saved).toBeInTheDocument();
    expect(screen.getAllByText("Форма обращения до отправки").length).toBeGreaterThanOrEqual(1);

    fireEvent.click(screen.getByRole("button", { name: "Изменить" }));
    fireEvent.click(screen.getByLabelText(/AI\/RAG/));
    fireEvent.click(screen.getByRole("button", { name: "Обновить связь" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/items/item-1/bindings/binding-1",
        expect.objectContaining({ method: "PATCH", credentials: "same-origin" }),
      ),
    );
    const patchCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/knowledge/items/item-1/bindings/binding-1" && call[1]?.method === "PATCH");
    expect(JSON.parse(String(patchCall?.[1]?.body))).toMatchObject({
      metadata: { surfaces: expect.arrayContaining(["requester_pre_submit", "ai_rag"]) },
    });
    expect(await screen.findByText("Связь с обращениями обновлена.")).toBeInTheDocument();

    fireEvent.click(within(savedSection as HTMLElement).getByRole("button", { name: "Удалить" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/items/item-1/bindings/binding-1",
        expect.objectContaining({ method: "DELETE", credentials: "same-origin" }),
      ),
    );
    expect(await screen.findByText("Связь с обращениями удалена.")).toBeInTheDocument();
  });
});
