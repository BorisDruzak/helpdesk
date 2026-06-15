import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KnowledgeImportWizardPage } from "./import-wizard-page";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname + location.search}</span>;
}

function renderWizard(initialEntry = "/app/admin/knowledge/import") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <KnowledgeImportWizardPage />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("KnowledgeImportWizardPage", () => {
  it("previews markdown as a section-bound safe internal draft", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          status: "ok",
          spaces: [
            {
              space_id: "space-it",
              code: "it-support",
              title: "IT Support",
              visibility: "support_internal",
              lifecycle_status: "active",
              allow_rag: true,
            },
          ],
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
          item: {
            item_id: "item-1",
            slug: "vpn-import",
            title: "VPN Import",
            visibility: "support_internal",
            metadata: { ai_rag_policy: "inherit" },
          },
          version: { version_id: "ver-1", body_format: "markdown" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    renderWizard();

    expect(await screen.findByRole("heading", { name: "Импорт знаний" })).toBeInTheDocument();
    expect(await screen.findByRole("option", { name: "IT Support (it-support)" })).toBeInTheDocument();
    expect(screen.getByLabelText("Раздел базы знаний")).toHaveValue("it-support");

    fireEvent.change(screen.getByLabelText("Название"), { target: { value: "VPN Import" } });
    fireEvent.change(screen.getByLabelText("Slug"), { target: { value: "vpn-import" } });
    fireEvent.change(screen.getByLabelText("Источник"), { target: { value: "vpn.md" } });
    fireEvent.change(screen.getByLabelText("Текст импорта"), { target: { value: "# VPN Import\n\n## Steps\nReconnect VPN." } });
    fireEvent.click(screen.getByRole("button", { name: "Предпросмотр" }));

    expect(await screen.findByText("Обнаруженное название")).toBeInTheDocument();
    expect(screen.getByText("VPN Import")).toBeInTheDocument();
    expect(screen.getByText("Раздел: IT Support (it-support)")).toBeInTheDocument();
    expect(screen.getByText("Видимость: внутренний черновик для поддержки")).toBeInTheDocument();
    expect(screen.getByText("Аудитория: наследуется от раздела")).toBeInTheDocument();
    expect(screen.getByText("AI/RAG: по политике раздела")).toBeInTheDocument();
    expect(screen.getByText("Авторазметка: не будет запущена")).toBeInTheDocument();
    expect(screen.getByText("AI выключен")).toBeInTheDocument();
    expect(screen.getByText("Steps")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Создать черновик и открыть Studio" }));

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
      space_code: "it-support",
      visibility: "support_internal",
      metadata: { ai_rag_policy: "inherit" },
    });
    expect(JSON.parse(String(fetchMock.mock.calls[3][1]?.body))).toMatchObject({
      space_code: "it-support",
      slug: "vpn-import",
      visibility: "support_internal",
      metadata: {
        ai_rag_policy: "inherit",
        import_mode: "safe_draft",
      },
    });
    expect(await screen.findByText("Черновик создан")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/app/admin/knowledge/studio?item=item-1"));
  });

  it("uses auto-segmentation for long imports without a manual segmentation step", async () => {
    const longBody = `# Long Import\n\n${Array.from({ length: 900 }, () => "слово").join(" ")}`;
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          status: "ok",
          spaces: [
            {
              space_id: "space-sec",
              code: "secure-runbooks",
              title: "Security Runbooks",
              visibility: "support_internal",
              lifecycle_status: "active",
              allow_rag: false,
            },
          ],
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
            source_name: "long.md",
            body_format: "markdown",
            detected_title: "Long Import",
            section_count: 3,
            word_count: 900,
            sections: [{ heading: "Long Import", preview: "слово слово слово" }],
            ai_enrichment: { enabled: false, status: "disabled" },
          },
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          status: "ok",
          preview: { detected_title: "Long Import", section_count: 3, ai_enrichment: { enabled: false, status: "disabled" } },
          ai_enrichment: { enabled: false, status: "disabled" },
          segmentation: { enabled: true, status: "completed", profile_code: "default-auto", segments: [] },
          job: { job_id: "job-long", status: "review_required" },
          item: {
            item_id: "item-long",
            slug: "long-import",
            title: "Long Import",
            visibility: "support_internal",
            metadata: { ai_rag_policy: "inherit" },
          },
          version: { version_id: "ver-long", body_format: "markdown" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    renderWizard();

    await screen.findByRole("option", { name: "Security Runbooks (secure-runbooks)" });
    fireEvent.change(screen.getByLabelText("Название"), { target: { value: "Long Import" } });
    fireEvent.change(screen.getByLabelText("Slug"), { target: { value: "long-import" } });
    fireEvent.change(screen.getByLabelText("Источник"), { target: { value: "long.md" } });
    fireEvent.change(screen.getByLabelText("Текст импорта"), { target: { value: longBody } });
    fireEvent.click(screen.getByRole("button", { name: "Предпросмотр" }));

    expect(await screen.findByText("Авторазметка: будет запущена (длинный документ)")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Создать черновик и открыть Studio" }));

    await waitFor(() =>
      expect(JSON.parse(String(fetchMock.mock.calls[3][1]?.body))).toMatchObject({
        auto_segment_after_import: true,
        segmentation_profile_code: "default-auto",
        visibility: "support_internal",
        metadata: { ai_rag_policy: "inherit", import_mode: "safe_draft" },
      }),
    );
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/app/admin/knowledge/studio?item=item-long"));
  });

  it("shows remote policy controls and sends the selected segmentation profile", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          status: "ok",
          spaces: [
            {
              space_id: "space-it",
              code: "it-support",
              title: "IT Support",
              visibility: "support_internal",
              lifecycle_status: "active",
              allow_rag: true,
            },
          ],
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

    fireEvent.click(screen.getByLabelText("Запустить авторазметку после создания черновика"));
    fireEvent.change(screen.getByLabelText("Профиль авторазметки"), { target: { value: "paragraph-auto" } });
    fireEvent.click(screen.getByRole("button", { name: "Создать черновик и открыть Studio" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/import/create-drafts",
        expect.objectContaining({ method: "POST", credentials: "same-origin" }),
      ),
    );
    expect(JSON.parse(String(fetchMock.mock.calls[2][1]?.body))).toMatchObject({
      source_kind: "url",
      url: "https://docs.example.test/safe/runbook.md",
      visibility: "support_internal",
    });
    expect(JSON.parse(String(fetchMock.mock.calls[3][1]?.body))).toMatchObject({
      auto_segment_after_import: true,
      segmentation_profile_code: "paragraph-auto",
      visibility: "support_internal",
    });
    expect((await screen.findAllByText(/paragraph-auto/)).length).toBeGreaterThan(1);
  });
});
