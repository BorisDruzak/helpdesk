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
          profiles: [{ code: "default-auto", title: "Default auto", mode: "auto", enabled: true }],
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
    expect(JSON.parse(String(fetchMock.mock.calls[2][1]?.body))).toMatchObject({
      source_kind: "markdown",
      source_name: "vpn.md",
      title: "VPN Import",
      ai_enrichment_enabled: false,
    });
    expect(JSON.parse(String(fetchMock.mock.calls[3][1]?.body))).toMatchObject({
      space_code: "it-support",
      slug: "vpn-import",
      visibility: "support_internal",
    });
    expect(await screen.findByText("Черновик создан")).toBeInTheDocument();
  });

  it("shows remote policy controls and sends segmentation profile with draft creation", async () => {
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
          profiles: [
            { code: "default-auto", title: "Default auto", mode: "auto", enabled: true },
            { code: "paragraph-auto", title: "Paragraph auto", mode: "auto", enabled: true },
          ],
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          status: "ok",
          preview: {
            source_kind: "url",
            source_name: "docs.example.test",
            body_format: "markdown",
            detected_title: "Remote URL Import",
            section_count: 1,
            word_count: 5,
            sections: [{ heading: "Steps", preview: "Reconnect VPN." }],
            remote_source: { source_kind: "url", host: "docs.example.test", path: "/safe/runbook.md", bytes: 128 },
            ai_enrichment: { enabled: false, status: "disabled" },
          },
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          status: "ok",
          preview: { detected_title: "Remote URL Import", section_count: 1, ai_enrichment: { enabled: false, status: "disabled" } },
          ai_enrichment: { enabled: false, status: "disabled" },
          segmentation: { enabled: true, status: "completed", profile_code: "paragraph-auto", segments: [] },
          job: { job_id: "job-remote", status: "review_required" },
          item: { item_id: "item-remote", slug: "remote-url-import", title: "Remote URL Import", visibility: "support_internal" },
          version: { version_id: "ver-remote", body_format: "markdown" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    renderWizard();

    await screen.findByRole("heading", { name: "Импорт знаний" });
    fireEvent.change(screen.getByLabelText("Формат"), { target: { value: "url" } });
    expect(screen.getByText(/KNOWLEDGE_REMOTE_IMPORT_ENABLED/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("URL источника"), { target: { value: "https://docs.example.test/safe/runbook.md" } });
    fireEvent.click(screen.getByRole("button", { name: "Предпросмотр" }));

    expect(await screen.findByText("Remote URL Import")).toBeInTheDocument();
    expect(screen.getByText("host: docs.example.test")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Запустить авторазметку после создания draft"));
    fireEvent.change(screen.getByLabelText("Профиль разметки"), { target: { value: "paragraph-auto" } });
    fireEvent.click(screen.getByRole("button", { name: "Создать черновик" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/import/create-drafts",
        expect.objectContaining({ method: "POST", credentials: "same-origin" }),
      ),
    );
    expect(JSON.parse(String(fetchMock.mock.calls[2][1]?.body))).toMatchObject({
      source_kind: "url",
      url: "https://docs.example.test/safe/runbook.md",
    });
    expect(JSON.parse(String(fetchMock.mock.calls[3][1]?.body))).toMatchObject({
      auto_segment_after_import: true,
      segmentation_profile_code: "paragraph-auto",
    });
    expect((await screen.findAllByText(/paragraph-auto/)).length).toBeGreaterThan(1);
  });
});
