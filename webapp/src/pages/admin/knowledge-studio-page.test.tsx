import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

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

const extraArticleItems = Array.from({ length: 11 }, (_, index) => {
  const number = index + 1;
  return {
    item_id: `item-extra-${number}`,
    space_id: "space-1",
    slug: `scrollable-article-${number}`,
    item_type: "article",
    type: "article",
    title: `Scrollable article ${number}`,
    summary: `Extra article ${number} for explorer scrolling`,
    status: "draft",
    visibility: "requester",
    owner_actor_id: "owner",
    reviewer_actor_id: "reviewer",
    tags: ["scroll"],
    current_version_id: null,
    updated_at: `2026-06-12T05:${String(number).padStart(2, "0")}:00Z`,
  };
});

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
    {
      item_id: "item-2",
      space_id: "space-1",
      slug: "printer-reset",
      item_type: "article",
      type: "article",
      title: "Printer reset",
      summary: "Reset a workplace printer safely",
      status: "draft",
      visibility: "support_internal",
      owner_actor_id: "owner",
      reviewer_actor_id: "reviewer",
      tags: ["printer"],
      current_version_id: "ver-printer",
      updated_at: "2026-06-12T06:00:00Z",
    },
    ...extraArticleItems,
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

const item2VersionsPayload = {
  status: "ok",
  versions: [
    {
      version_id: "ver-printer",
      item_id: "item-2",
      version_number: 1,
      title: "Printer reset",
      summary: "Reset a workplace printer safely",
      body_format: "markdown",
      body: "# Printer reset\n\nPower-cycle the printer and verify the queue.",
      created_at: "2026-06-12T06:00:00Z",
      published_at: null,
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
          item_id: "item-created",
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
    if (url === "/api/web/knowledge/items/item-2/versions" && !init?.method) {
      return jsonResponse(item2VersionsPayload);
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
    if (url === "/api/web/knowledge/items/item-2/editor-history" && !init?.method) {
      return jsonResponse({
        status: "ok",
        events: [],
        diff_cache: [],
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
    if (url === "/api/web/knowledge/items/item-2/segments" && !init?.method) {
      return jsonResponse({
        status: "ok",
        segments: [],
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
    if (url === "/api/web/knowledge/items/item-2/metadata" && !init?.method) {
      return jsonResponse({
        status: "ok",
        item_metadata: {
          item_id: "item-2",
          space_id: "space-1",
          slug: "printer-reset",
          title: "Printer reset",
          properties: {},
          taxonomy_terms: [],
          applicability_rules: [],
        },
      });
    }
    if (url === "/api/web/knowledge/items/item-1/applicability" && !init?.method) {
      return jsonResponse({ status: "ok", rules: [] });
    }
    if (url === "/api/web/knowledge/items/item-2/applicability" && !init?.method) {
      return jsonResponse({ status: "ok", rules: [] });
    }
    if (url.startsWith("/api/web/admin/knowledge/audience-rules?") && !init?.method) {
      return jsonResponse({
        status: "success",
        data: {
          rules: [],
        },
      });
    }
    if (url === "/api/web/admin/registry" && !init?.method) {
      return jsonResponse({
        status: "ok",
        summary: {
          assets: 0,
          people: 1,
          locations: 1,
          departments: 1,
          services: 1,
          vendors: 0,
          registrations_pending: 0,
          registrations_conflicts: 0,
          unregistered_devices: 0,
          active_bindings: 0,
          stale_bindings: 0,
          data_quality_issues: 0,
          suggestions: 0,
        },
        assets: [],
        people: [
          {
            id: "person-1",
            person_id: "person-1",
            display_name: "Knowledge Tester",
            full_name: "Knowledge Tester",
            phone: null,
            email: "knowledge@example.test",
            login: "knowledge@example.test",
            department_id: "dep-it",
            location_id: "loc-1",
            department_name: "IT",
            location_name: "Office",
            source: "test",
            status: "active",
            updated_at: "2026-06-14T08:00:00Z",
          },
        ],
        locations: [
          {
            id: "loc-1",
            location_id: "loc-1",
            building: "HQ",
            floor: null,
            room: null,
            display_name: "Office",
            source: "test",
            status: "active",
            updated_at: "2026-06-14T08:00:00Z",
          },
        ],
        departments: [
          {
            id: "dep-it",
            department_id: "dep-it",
            code: "it",
            name: "IT",
            parent_id: null,
            source: "test",
            status: "active",
            updated_at: "2026-06-14T08:00:00Z",
          },
        ],
        services: [
          {
            id: "svc-network",
            code: "network",
            name: "Network",
            support_queue: null,
            owner_person_id: null,
            vendor_id: null,
            source: "test",
            status: "active",
            updated_at: "2026-06-14T08:00:00Z",
          },
        ],
        vendors: [],
        data_quality: [],
        suggestions: [],
        registration_claims: [],
        active_bindings: [],
      });
    }
    if (url === "/api/web/admin/registry/audience-groups" && !init?.method) {
      return jsonResponse({ status: "ok", groups: [] });
    }
    if (url === "/api/web/admin/access/summary" && !init?.method) {
      return jsonResponse({
        status: "success",
        data: {
          version: "test",
          users: [],
          queues: [],
          access_groups: [],
          notes: [],
        },
      });
    }
    throw new Error(`Unexpected fetch ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock as typeof fetch);
  return fetchMock;
}

function renderStudio(initialEntry = "/app/admin/knowledge/studio") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <AdminKnowledgeStudioPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function loadedEditorContent() {
  const editor = await screen.findByTestId("knowledge-editor-content");
  await waitFor(() => expect(editor.textContent ?? "").toContain("Check the tunnel adapter."));
  return editor;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AdminKnowledgeStudioPage", () => {
  it("selects the article requested by the item query parameter", async () => {
    setupFetch();
    renderStudio("/app/admin/knowledge/studio?item=item-2");

    expect(await screen.findByRole("heading", { name: "Студия знаний" })).toBeInTheDocument();
    const editor = await screen.findByTestId("knowledge-editor-content");
    await waitFor(() => expect(editor.textContent ?? "").toContain("Power-cycle the printer"));
    expect(screen.getByLabelText("Заголовок")).toHaveValue("Printer reset");
  });

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

  it("loads a simplified article editor with one save action and no review or manual segmentation in the default UI", async () => {
    setupFetch();
    renderStudio();

    expect(await screen.findByRole("heading", { name: "Студия знаний" })).toBeInTheDocument();
    expect(screen.getByText("Черновики и статьи")).toBeInTheDocument();
    expect(screen.getByText("Редактор статьи")).toBeInTheDocument();
    expect(screen.getByText("Сохранение статьи")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Сохранить статью" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "История версий" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /VPN access/ })).toBeInTheDocument();
    const editor = await loadedEditorContent();
    expect(screen.getByLabelText("Заголовок")).toHaveValue("VPN access");
    expect(editor.textContent ?? "").toContain("Check the tunnel adapter.");
    expect(screen.queryByText("Живой предпросмотр")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(screen.getByText("Живой предпросмотр")).toBeInTheDocument();
    expect(screen.getByText("Готовность к сохранению")).toBeInTheDocument();
    expect(within(screen.getByRole("group", { name: "Готовность к сохранению" })).getByLabelText("Текст статьи заполнен")).toBeChecked();

    fireEvent.click(screen.getByRole("button", { name: "2. Настройки" }));
    expect(screen.getByText("Основные настройки статьи")).toBeInTheDocument();
    expect(screen.getByLabelText("Раздел базы знаний")).toHaveValue("it-self-service");
    expect(screen.getByText(/Раздел определяет, где хранится статья/)).toBeInTheDocument();
    expect(screen.getByLabelText("Тип материала")).toHaveValue("article");
    expect(screen.getByText(/Тип определяет шаблон и смысл статьи/)).toBeInTheDocument();
    expect(screen.getByLabelText("Кому доступна статья")).toHaveValue("requester");
    expect(screen.getByText(/Это базовый уровень доступа/)).toBeInTheDocument();
    expect(screen.getByText("Где показывать статью")).toBeInTheDocument();
    expect(screen.getByText(/Определяет, в каких сценариях система будет предлагать статью/)).toBeInTheDocument();
    const visibilityPanel = await screen.findByTestId("article-visibility-panel");
    expect(within(visibilityPanel).getByRole("heading", { name: "Аудитория" })).toBeInTheDocument();
    expect(within(visibilityPanel).getByText(/Аудитория уточняет доступ внутри выбранной видимости/)).toBeInTheDocument();
    expect(screen.getByText("Advanced / служебные поля")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Advanced / служебные поля"));
    expect(screen.getByLabelText("Адрес статьи")).toHaveValue("vpn-access");
    expect(screen.getByLabelText("Владелец")).toHaveValue("owner");
    expect(screen.getByLabelText("Теги")).toHaveValue("vpn, remote");

    expect(screen.queryByRole("button", { name: "Создать версию" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Опубликовать версию" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Отправить на ревью" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Одобрить" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Добавить комментарий" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Комментарий ревью")).not.toBeInTheDocument();
    expect(screen.queryByText("Назначен ревьюер")).not.toBeInTheDocument();
    expect(screen.queryByText("Создать сегмент из выделения редактора")).not.toBeInTheDocument();
    expect(screen.queryByText("Сегменты версии")).not.toBeInTheDocument();
    expect(screen.queryByText("Полнотекстовый поиск")).not.toBeInTheDocument();
    expect(screen.queryByText("Эмбеддинги")).not.toBeInTheDocument();
    expect(screen.getByText("Поисковые фрагменты создаются автоматически по заголовкам и тексту статьи.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "3. Проверка" }));
    expect(screen.getByText("Computed checklist")).toBeInTheDocument();
    expect(screen.getByText("Diff текущего draft")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "История" }));
    expect(await screen.findByText("История редактора")).toBeInTheDocument();
    expect(screen.getByText("version_created")).toBeInTheDocument();
    expect(screen.getByText("Publish from Studio")).toBeInTheDocument();
    expect(screen.getAllByText("Кэш различий: +2 / -1").length).toBeGreaterThanOrEqual(1);

    const visibleText = document.body.textContent ?? "";
    expect(visibleText).toContain("Редактор базы знаний");
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

  it("keeps every filtered article reachable in the explorer scroll list", async () => {
    setupFetch();
    renderStudio();

    await screen.findByRole("heading", { name: "Студия знаний" });
    const explorer = await screen.findByTestId("knowledge-article-explorer");

    expect(explorer).toHaveClass("overflow-y-auto");
    expect(within(explorer).getByText("Scrollable article 11")).toBeInTheDocument();
    expect(within(explorer).queryByText(/Показаны первые 10/)).not.toBeInTheDocument();
    expect(within(explorer).getByText("Прокрутите список, чтобы увидеть все 14 материалов.")).toBeInTheDocument();
  });

  it("inserts a template and saves the article through one create-version plus publish flow", async () => {
    const fetchMock = setupFetch();
    renderStudio();

    await screen.findByRole("heading", { name: "Студия знаний" });
    const editor = await loadedEditorContent();
    expect(screen.queryByRole("button", { name: "Вставить шаблон: Шаблон решения" })).not.toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "Вставить шаблон" }));
    fireEvent.click(await screen.findByRole("menuitem", { name: "Шаблон решения" }));
    await waitFor(() => expect(editor.textContent ?? "").toContain("Симптом"));
    expect(editor.textContent ?? "").toContain("Решение");

    fireEvent.change(screen.getByLabelText("Краткое описание"), {
      target: { value: "Updated requester-safe body" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Сохранить статью" }));
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
      body: expect.stringContaining("## Симптом"),
      change_summary: "Сохранено из упрощённой Studio",
    });

    const checklist = screen.getByRole("group", { name: "Готовность к сохранению" });
    expect(within(checklist).getByLabelText("Текст статьи заполнен")).toBeChecked();
    expect(within(checklist).getByLabelText("Есть краткое описание")).toBeChecked();
    expect(within(checklist).getByLabelText(/Безопасная видимость выбрана/)).toBeChecked();

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/items/item-1/publish",
        expect.objectContaining({ method: "POST", credentials: "same-origin" }),
      ),
    );
    const publishCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/knowledge/items/item-1/publish" && call[1]?.method === "POST");
    expect(JSON.parse(String(publishCall?.[1]?.body))).toMatchObject({
      version_id: "ver-2",
    });
    expect(JSON.parse(String(publishCall?.[1]?.body))).not.toHaveProperty("review_note");
    expect(await screen.findByText("Статья сохранена и опубликована. Текущая версия: v2.")).toBeInTheDocument();
  });

  it("creates a new draft without reviewer fields and keeps rollback inside version history", async () => {
    const fetchMock = setupFetch();
    renderStudio();

    await screen.findByRole("heading", { name: "Студия знаний" });
    await loadedEditorContent();

    fireEvent.click(screen.getByRole("button", { name: "Новый черновик" }));
    expect(screen.getByRole("dialog", { name: "Новый черновик" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Ревьюер нового черновика")).not.toBeInTheDocument();
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
    expect(JSON.parse(String(draftCall?.[1]?.body))).toMatchObject({ reviewer_actor_id: null });

    fireEvent.click(screen.getByRole("button", { name: "История версий" }));
    const historyDrawer = await screen.findByRole("dialog", { name: "История версий" });
    fireEvent.click(within(historyDrawer).getByRole("button", { name: /v0: VPN access old/ }));
    fireEvent.click(within(historyDrawer).getByLabelText("Подтвердить восстановление выбранной версии"));
    fireEvent.click(within(historyDrawer).getByRole("button", { name: "Восстановить выбранную версию" }));

    await waitFor(() => {
      const rollbackCall = fetchMock.mock.calls.find(
        (call) => call[0] === "/api/web/knowledge/items/item-1/publish" && JSON.parse(String(call[1]?.body)).version_id === "ver-old",
      );
      expect(rollbackCall).toBeDefined();
    });
    expect(fetchMock.mock.calls.some((call) => call[0] === "/api/web/knowledge/items/item-1/review-action")).toBe(false);
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
