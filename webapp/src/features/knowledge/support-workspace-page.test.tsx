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
});
