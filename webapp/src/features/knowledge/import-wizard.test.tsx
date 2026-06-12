import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KnowledgeImportWizardPage } from "./import-wizard-page";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderWizard() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <KnowledgeImportWizardPage />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("KnowledgeImportWizardPage", () => {
  it("previews markdown without AI and creates a draft", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          status: "ok",
          spaces: [{ code: "it-support", title: "IT Support", visibility: "support_internal", lifecycle_status: "active" }],
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          status: "ok",
          preview: {
            source_kind: "markdown",
            source_name: "vpn.md",
            body_format: "markdown",
            detected_title: "VPN Import",
            section_count: 1,
            word_count: 5,
            sections: [{ heading: "Steps", preview: "Reconnect VPN." }],
            ai_enrichment: { enabled: false, status: "disabled" },
          },
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          status: "ok",
          preview: { detected_title: "VPN Import", section_count: 1, ai_enrichment: { enabled: false, status: "disabled" } },
          ai_enrichment: { enabled: false, status: "disabled" },
          job: { job_id: "job-1", status: "review_required" },
          item: { item_id: "item-1", slug: "vpn-import", title: "VPN Import", visibility: "support_internal" },
          version: { version_id: "ver-1", body_format: "markdown" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    renderWizard();

    expect(await screen.findByRole("heading", { name: "Импорт знаний" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Название"), { target: { value: "VPN Import" } });
    fireEvent.change(screen.getByLabelText("Slug"), { target: { value: "vpn-import" } });
    fireEvent.change(screen.getByLabelText("Источник"), { target: { value: "vpn.md" } });
    fireEvent.change(screen.getByLabelText("Текст импорта"), { target: { value: "# VPN Import\n\n## Steps\nReconnect VPN." } });
    fireEvent.click(screen.getByRole("button", { name: "Предпросмотр" }));

    expect(await screen.findByText("VPN Import")).toBeInTheDocument();
    expect(screen.getByText("AI выключен")).toBeInTheDocument();
    expect(screen.getByText("Steps")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Создать черновик" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/import/create-drafts",
        expect.objectContaining({ method: "POST", credentials: "same-origin" }),
      ),
    );
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toMatchObject({
      source_kind: "markdown",
      source_name: "vpn.md",
      title: "VPN Import",
      ai_enrichment_enabled: false,
    });
    expect(JSON.parse(String(fetchMock.mock.calls[2][1]?.body))).toMatchObject({
      space_code: "it-support",
      slug: "vpn-import",
      visibility: "support_internal",
    });
    expect(await screen.findByText("Черновик создан")).toBeInTheDocument();
  });
});
