import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AdminKnowledgeStudioPage } from "./knowledge-studio-page";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const spacesPayload = {
  status: "ok",
  spaces: [
    {
      space_id: "space-1",
      code: "it-self-service",
      title: "IT Self-Service",
      visibility: "requester",
      lifecycle_status: "active",
      owner_actor_id: "owner",
      default_reviewer_actor_id: "reviewer",
    },
  ],
};

const itemsPayload = {
  status: "ok",
  items: [
    {
      item_id: "item-archived",
      space_id: "space-1",
      slug: "archived-live-draft",
      item_type: "article",
      type: "article",
      title: "Archived live draft",
      summary: "Archived item without versions should not be selected by default",
      status: "archived",
      visibility: "requester",
      owner_actor_id: "owner",
      reviewer_actor_id: "reviewer",
      tags: ["archived"],
      current_version_id: null,
      updated_at: "2026-06-12T08:00:00Z",
    },
    {
      item_id: "item-1",
      space_id: "space-1",
      slug: "vpn-access",
      item_type: "article",
      type: "article",
      title: "VPN access",
      summary: "How to reconnect VPN safely",
      status: "draft",
      visibility: "requester",
      owner_actor_id: "owner",
      reviewer_actor_id: "reviewer",
      tags: ["vpn", "remote"],
      current_version_id: "ver-1",
      updated_at: "2026-06-12T07:00:00Z",
    },
  ],
};

const versionsPayload = {
  status: "ok",
  versions: [
    {
      version_id: "ver-1",
      item_id: "item-1",
      version_number: 1,
      title: "VPN access",
      summary: "How to reconnect VPN safely",
      body_format: "markdown",
      body: "# VPN access\n\nCheck the tunnel adapter.\n\n## Escalation\nCreate a ticket if MFA fails.",
      created_at: "2026-06-12T07:00:00Z",
      published_at: null,
    },
    {
      version_id: "ver-old",
      item_id: "item-1",
      version_number: 0,
      title: "VPN access old",
      summary: "Previous stable VPN instruction",
      body_format: "markdown",
      body: "# VPN access\n\nUse the legacy VPN profile.",
      created_at: "2026-06-11T07:00:00Z",
      published_at: "2026-06-11T08:00:00Z",
    },
  ],
};

const templatesPayload = {
  status: "ok",
  templates: [
    {
      type: "troubleshooting",
      title: "Шаблон решения",
      sections: ["Симптом", "Проверка", "Решение"],
    },
  ],
};

function setupFetch() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === "/api/web/knowledge/spaces") {
      return jsonResponse(spacesPayload);
    }
    if (url === "/api/web/knowledge/items" && !init?.method) {
      return jsonResponse(itemsPayload);
    }
    if (url === "/api/web/knowledge/items" && init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      return jsonResponse({
        status: "ok",
        item: {
          ...itemsPayload.items[0],
          item_id: "item-2",
          title: body.title,
          slug: body.slug,
          summary: body.summary,
          status: "draft",
          current_version_id: null,
        },
      });
    }
    if (url === "/api/web/knowledge/templates") {
      return jsonResponse(templatesPayload);
    }
    if (url === "/api/web/knowledge/items/item-1/versions" && !init?.method) {
      return jsonResponse(versionsPayload);
    }
    if (url === "/api/web/knowledge/items/item-1/editor-history" && !init?.method) {
      return jsonResponse({
        status: "ok",
        events: [
          {
            event_id: "event-1",
            event_type: "version_created",
            summary: "Initial authoring version",
            actor_id: "admin-test",
            created_at: "2026-06-12T09:00:00Z",
          },
          {
            event_id: "event-2",
            event_type: "published",
            summary: "Publish from Studio",
            actor_id: "admin-test",
            created_at: "2026-06-12T09:05:00Z",
          },
        ],
        diff_cache: [
          {
            diff_id: "diff-1",
            from_version_id: "ver-old",
            to_version_id: "ver-1",
            added_lines: 2,
            removed_lines: 1,
            summary: { change_summary: "Initial authoring version" },
          },
        ],
      });
    }
    if (url === "/api/web/knowledge/items/item-1/versions" && init?.method === "POST") {
      return jsonResponse({
        status: "ok",
        version: {
          version_id: "ver-2",
          item_id: "item-1",
          version_number: 2,
          title: "VPN access",
          body_format: "markdown",
          body: JSON.parse(String(init.body)).body,
        },
      });
    }
    if (url === "/api/web/knowledge/items/item-1/publish" && init?.method === "POST") {
      return jsonResponse({
        status: "ok",
        item: { ...itemsPayload.items[0], status: "published", current_version_id: "ver-2" },
      });
    }
    if (url === "/api/web/knowledge/items/item-1/review-action" && init?.method === "POST") {
      return jsonResponse({
        status: "ok",
        result: {
          item: { ...itemsPayload.items[0], status: JSON.parse(String(init.body)).action === "archive" ? "archived" : "in_review" },
          event: { action: JSON.parse(String(init.body)).action },
        },
      });
    }
    if (url === "/api/web/knowledge/items/item-1/segments" && !init?.method) {
      return jsonResponse({
        status: "ok",
        segments: [
          {
            segment_id: "seg-1",
            item_id: "item-1",
            version_id: "ver-1",
            segment_index: 1,
            segment_type: "manual",
            title: "VPN диагностика",
            text: "Check the tunnel adapter.",
            keywords: ["vpn"],
            boost: 1,
            visibility: "requester",
            status: "active",
            source: "editor_selection",
          },
        ],
      });
    }
    if (url === "/api/web/knowledge/items/item-1/segments" && init?.method === "POST") {
      return jsonResponse({
        status: "ok",
        display_message: "Сегмент знаний сохранён",
        segment: {
          segment_id: "seg-2",
          item_id: "item-1",
          version_id: "ver-1",
          segment_index: 2,
          segment_type: "manual",
          title: "Новый сегмент",
          text: JSON.parse(String(init.body)).text,
          keywords: [],
          boost: 1,
          visibility: "requester",
          status: "active",
          source: "editor_selection",
        },
      });
    }
    if (url === "/api/web/knowledge/segmentation-profiles") {
      return jsonResponse({ status: "ok", profiles: [] });
    }
    if (url === "/api/web/knowledge/metadata" && !init?.method) {
      return jsonResponse({
        status: "ok",
        metadata: {
          spaces: [{ space_id: "space-1", code: "it-self-service", title: "IT Self-Service", visibility: "requester", lifecycle_status: "active" }],
          taxonomy_terms: [{ term_id: "term-vpn", space_id: "space-1", term_type: "product", code: "vpn", title: "VPN", visibility: "requester", status: "active" }],
          property_definitions: [
            {
              property_id: "prop-audience",
              space_id: "space-1",
              code: "audience",
              title: "Аудитория",
              value_type: "select",
              required: true,
              allowed_values: ["requester", "support"],
              applies_to_item_types: ["article"],
              quality_weight: 12,
              status: "active",
            },
          ],
          applicability_rules: [],
          quality_models: [{ model_id: "model-1", space_id: "space-1", code: "metadata-required", title: "Метаданные", weights: { properties: 12 }, thresholds: {}, status: "active", is_default: true }],
          item_metadata: [],
          summary: {
            taxonomy_terms_total: 1,
            taxonomy_terms_active: 1,
            property_definitions_total: 1,
            property_definitions_active: 1,
            applicability_rules_total: 0,
            applicability_rules_active: 0,
            quality_models_total: 1,
            quality_models_active: 1,
            item_metadata_total: 0,
          },
        },
      });
    }
    if (url === "/api/web/knowledge/items/item-1/metadata" && !init?.method) {
      return jsonResponse({
        status: "ok",
        item_metadata: {
          item_id: "item-1",
          space_id: "space-1",
          slug: "vpn-access",
          title: "VPN access",
          properties: {},
          taxonomy_terms: [],
          applicability_rules: [],
        },
      });
    }
    if (url === "/api/web/knowledge/items/item-1/applicability" && !init?.method) {
      return jsonResponse({ status: "ok", rules: [] });
    }
    throw new Error(`Unexpected fetch ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock as typeof fetch);
  return fetchMock;
}

function renderStudio() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <AdminKnowledgeStudioPage />
    </QueryClientProvider>,
  );
}

async function loadedEditorContent() {
  const editor = await screen.findByTestId("knowledge-editor-content");
  await waitFor(() => expect(editor.textContent ?? "").toContain("Check the tunnel adapter."));
  return editor;
}

function replaceEditorText(value: string) {
  const editor = screen.getByTestId("knowledge-editor-content");
  editor.textContent = value;
  fireEvent.input(editor);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AdminKnowledgeStudioPage", () => {
  it("renders one TipTap authoring editor with visible markup states instead of a raw markdown textarea", async () => {
    setupFetch();
    renderStudio();

    expect(await screen.findByRole("heading", { name: "Студия знаний" })).toBeInTheDocument();
    expect(await screen.findByTestId("knowledge-tiptap-editor")).toBeInTheDocument();
    expect(screen.getByText("Ручная разметка")).toBeInTheDocument();
    expect(screen.getByText("AI-предложение")).toBeInTheDocument();
    expect(screen.getByText("Автосегмент")).toBeInTheDocument();
    expect(screen.getByText("Изменённый текст")).toBeInTheDocument();
    expect(screen.queryByLabelText("Markdown")).not.toBeInTheDocument();
  });

  it("loads a dedicated product authoring workspace with metadata, editor, preview and publish checklist", async () => {
    setupFetch();
    renderStudio();

    expect(await screen.findByRole("heading", { name: "Студия знаний" })).toBeInTheDocument();
    expect(screen.getByText("Черновики и статьи")).toBeInTheDocument();
    expect(screen.getByText("Единый редактор статьи")).toBeInTheDocument();
    expect(screen.getByText("Инспектор и публикация")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /VPN access/ })).toBeInTheDocument();
    const editor = await loadedEditorContent();
    expect(screen.getByLabelText("Заголовок")).toHaveValue("VPN access");
    expect(editor.textContent ?? "").toContain("Check the tunnel adapter.");
    expect(screen.getByText("Живой предпросмотр")).toBeInTheDocument();
    expect(screen.getByText("Проверка публикации")).toBeInTheDocument();
    expect(within(screen.getByRole("group", { name: "Проверка публикации" })).getByLabelText("Текст статьи заполнен")).toBeChecked();
    expect(within(screen.getByRole("group", { name: "Проверка публикации" })).getByLabelText(/Есть сегменты поиска/)).toBeChecked();

    fireEvent.click(screen.getByRole("button", { name: "2. Метаданные" }));
    expect(screen.getByLabelText("Slug")).toHaveValue("vpn-access");
    expect(screen.getByLabelText("Пространство")).toHaveValue("it-self-service");
    expect(screen.getAllByLabelText("Видимость")[0]).toHaveValue("requester");
    expect(screen.getByLabelText("Владелец")).toHaveValue("owner");
    expect(screen.getByLabelText("Ревьюер")).toHaveValue("reviewer");
    expect(screen.getByLabelText("Теги")).toHaveValue("vpn, remote");
    expect(screen.getByText("Метаданные статьи")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Таксономия" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Свойства" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Применимость" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Качество" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "3. Разметка" }));
    expect(await screen.findByText("Создать сегмент из выделения редактора")).toBeInTheDocument();
    expect(screen.getByText("Сегменты версии")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "4. Проверка" }));
    expect(screen.getByText("Computed checklist")).toBeInTheDocument();
    expect(screen.getByText("Diff текущего draft")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "История" }));
    expect(await screen.findByText("История редактора")).toBeInTheDocument();
    expect(screen.getByText("version_created")).toBeInTheDocument();
    expect(screen.getByText("Publish from Studio")).toBeInTheDocument();
    expect(screen.getByText("Кэш различий: +2 / -1")).toBeInTheDocument();

    const visibleText = document.body.textContent ?? "";
    expect(visibleText).toContain("Редактор базы знаний");
    expect(visibleText).toContain("единый authoring workbench");
    expect(visibleText).not.toContain("Основные поля статьи");
    expect(visibleText).not.toContain("Ревью и жизненный цикл");
    expect(visibleText).not.toContain("AI-инструменты отключены");
    expect(visibleText).not.toContain("Knowledge Authoring");
    expect(visibleText).not.toContain("Owner нового черновика");
    expect(visibleText).not.toContain("Reviewer нового черновика");
    expect(visibleText).not.toContain("Requester-safe теги");
    expect(visibleText).not.toContain("requester-safe");
    expect(visibleText).not.toContain("Diff cache");
    expect(visibleText).not.toContain("Rewrite, summarize");
    expect(visibleText).not.toContain(String.fromCharCode(0x0420, 0x045f));
  });

  it("inserts a template, creates a version and publishes with checklist payload", async () => {
    const fetchMock = setupFetch();
    renderStudio();

    await screen.findByRole("heading", { name: "Студия знаний" });
    const editor = await loadedEditorContent();
    fireEvent.click(await screen.findByRole("button", { name: "Вставить шаблон: Шаблон решения" }));
    await waitFor(() => expect(editor.textContent ?? "").toContain("Симптом"));
    expect(editor.textContent ?? "").toContain("Решение");

    replaceEditorText("# VPN access\n\nUpdated requester-safe body.\n\n## Решение\nReconnect profile.");
    fireEvent.change(screen.getByLabelText("Краткое описание версии"), {
      target: { value: "Updated requester-safe body" },
    });
    fireEvent.change(screen.getByLabelText("Описание изменения"), {
      target: { value: "Добавлен requester-safe раздел решения" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Создать версию" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/items/item-1/versions",
        expect.objectContaining({ method: "POST", credentials: "same-origin" }),
      ),
    );
    const createCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/knowledge/items/item-1/versions" && call[1]?.method === "POST");
    expect(JSON.parse(String(createCall?.[1]?.body))).toMatchObject({
      title: "VPN access",
      summary: "Updated requester-safe body",
      body_format: "markdown",
      body: expect.stringContaining("Updated requester-safe body."),
      change_summary: "Добавлен requester-safe раздел решения",
    });

    const checklist = screen.getByRole("group", { name: "Проверка публикации" });
    expect(within(checklist).getByLabelText("Текст статьи заполнен")).toBeChecked();
    expect(within(checklist).getByLabelText("Есть краткое описание")).toBeChecked();
    expect(within(checklist).getByLabelText(/Безопасная видимость выбрана/)).toBeChecked();
    expect(within(checklist).getByLabelText("Назначен ревьюер")).toBeChecked();
    expect(within(checklist).getByLabelText(/Есть сегменты поиска/)).toBeChecked();
    fireEvent.change(screen.getByLabelText("Комментарий к публикации"), {
      target: { value: "Готово к порталу" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Опубликовать версию" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/items/item-1/publish",
        expect.objectContaining({ method: "POST", credentials: "same-origin" }),
      ),
    );
    const publishCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/knowledge/items/item-1/publish" && call[1]?.method === "POST");
    expect(JSON.parse(String(publishCall?.[1]?.body))).toMatchObject({
      version_id: "ver-2",
      review_note: "Готово к порталу",
    });
  });

  it("creates a new draft, runs review lifecycle actions and rolls back to a selected version", async () => {
    const fetchMock = setupFetch();
    renderStudio();

    await screen.findByRole("heading", { name: "Студия знаний" });
    await loadedEditorContent();

    fireEvent.click(screen.getByRole("button", { name: "Новый черновик" }));
    expect(screen.getByRole("dialog", { name: "Новый черновик" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Новый заголовок"), { target: { value: "Wi-Fi reconnect" } });
    fireEvent.change(screen.getByLabelText("Новый slug"), { target: { value: "wifi-reconnect" } });
    fireEvent.change(screen.getByLabelText("Краткое описание нового черновика"), { target: { value: "How to reconnect corporate Wi-Fi" } });
    fireEvent.click(screen.getByRole("button", { name: "Создать новый черновик" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/items",
        expect.objectContaining({ method: "POST", credentials: "same-origin" }),
      ),
    );
    const draftCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/knowledge/items" && call[1]?.method === "POST");
    expect(JSON.parse(String(draftCall?.[1]?.body))).toMatchObject({
      title: "Wi-Fi reconnect",
      slug: "wifi-reconnect",
      summary: "How to reconnect corporate Wi-Fi",
      space_code: "it-self-service",
      visibility: "requester",
      item_type: "article",
    });

    fireEvent.change(screen.getByLabelText("Комментарий ревью"), {
      target: { value: "Материал готов к проверке" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Отправить на ревью" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/items/item-1/review-action",
        expect.objectContaining({ method: "POST", credentials: "same-origin" }),
      ),
    );
    const submitReviewCall = fetchMock.mock.calls.find(
      (call) => call[0] === "/api/web/knowledge/items/item-1/review-action" && JSON.parse(String(call[1]?.body)).action === "submit_review",
    );
    expect(JSON.parse(String(submitReviewCall?.[1]?.body))).toMatchObject({
      action: "submit_review",
      note: "Материал готов к проверке",
    });

    fireEvent.change(screen.getByLabelText("Версия для сравнения"), { target: { value: "ver-old" } });
    fireEvent.change(screen.getByLabelText("Комментарий к публикации"), {
      target: { value: "Откат к стабильной версии" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Откатить к выбранной версии" }));

    await waitFor(() => {
      const rollbackCall = fetchMock.mock.calls.find(
        (call) => call[0] === "/api/web/knowledge/items/item-1/publish" && JSON.parse(String(call[1]?.body)).version_id === "ver-old",
      );
      expect(rollbackCall).toBeDefined();
    });

    fireEvent.click(screen.getByRole("button", { name: "Архивировать / заменить" }));
    await waitFor(() => {
      const archiveCall = fetchMock.mock.calls.find(
        (call) => call[0] === "/api/web/knowledge/items/item-1/review-action" && JSON.parse(String(call[1]?.body)).action === "archive",
      );
      expect(archiveCall).toBeDefined();
    });
  });

  it("runs review comment and approve actions", async () => {
    const fetchMock = setupFetch();
    renderStudio();

    await screen.findByRole("heading", { name: "Студия знаний" });
    await loadedEditorContent();

    fireEvent.change(screen.getByLabelText("Комментарий ревью"), {
      target: { value: "Reviewer comment" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Добавить комментарий" }));
    await waitFor(() => {
      const commentCall = fetchMock.mock.calls.find(
        (call) => call[0] === "/api/web/knowledge/items/item-1/review-action" && JSON.parse(String(call[1]?.body)).action === "comment",
      );
      expect(commentCall).toBeDefined();
      expect(JSON.parse(String(commentCall?.[1]?.body))).toMatchObject({ action: "comment", note: "Reviewer comment" });
    });

    fireEvent.change(screen.getByLabelText("Комментарий ревью"), {
      target: { value: "Approved by reviewer" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Одобрить" }));
    await waitFor(() => {
      const approveCall = fetchMock.mock.calls.find(
        (call) => call[0] === "/api/web/knowledge/items/item-1/review-action" && JSON.parse(String(call[1]?.body)).action === "approve",
      );
      expect(approveCall).toBeDefined();
      expect(JSON.parse(String(approveCall?.[1]?.body))).toMatchObject({ action: "approve", note: "Approved by reviewer" });
    });
  });

  it("inserts structured markdown blocks", async () => {
    setupFetch();
    renderStudio();

    await screen.findByRole("heading", { name: "Студия знаний" });
    const editor = await loadedEditorContent();

    fireEvent.click(screen.getByRole("button", { name: "Callout" }));
    fireEvent.click(screen.getByRole("button", { name: "Таблица" }));
    fireEvent.click(screen.getByRole("button", { name: "Код" }));
    fireEvent.click(screen.getByRole("button", { name: "Checklist" }));

    await waitFor(() => expect(editor.textContent ?? "").toContain("[!NOTE]"));
    expect(editor.textContent ?? "").toContain("| Шаг | Действие |");
    expect(editor.textContent ?? "").toContain("Команда или лог");
    expect(editor.textContent ?? "").toContain("[ ] Проверить результат");
  });
});
