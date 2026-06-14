import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AdminKnowledgeSectionsPage } from "./knowledge-sections-page";

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
      space_id: "space-it",
      code: "it-self-service",
      title: "IT Self-Service",
      description: "Инструкции для заявителей и поддержки",
      visibility: "requester",
      lifecycle_status: "active",
      owner_actor_id: "owner",
      default_reviewer_actor_id: "reviewer",
      allowed_item_types: ["article", "faq", "runbook"],
      allow_publication: true,
      allow_ingestion: true,
      allow_rag: true,
      metadata: {
        owner_note: "preserve",
        show_in_requester_portal: true,
        show_in_support_workspace: false,
        article_length_recommendation: "short",
      },
    },
    {
      space_id: "space-internal",
      code: "support-runbooks",
      title: "Support Runbooks",
      description: "Внутренние процедуры",
      visibility: "support_internal",
      lifecycle_status: "draft",
      owner_actor_id: null,
      default_reviewer_actor_id: null,
      allowed_item_types: ["runbook", "known_error"],
      allow_publication: false,
      allow_ingestion: true,
      allow_rag: false,
      metadata: {
        show_in_requester_portal: false,
        show_in_support_workspace: true,
        article_length_recommendation: "detailed",
      },
    },
  ],
};

const itemsPayload = {
  status: "ok",
  items: [
    {
      item_id: "item-1",
      space_id: "space-it",
      slug: "vpn-guide",
      item_type: "article",
      type: "article",
      title: "VPN guide",
      status: "published",
      visibility: "requester",
    },
    {
      item_id: "item-2",
      space_id: "space-it",
      slug: "vpn-faq",
      item_type: "faq",
      type: "faq",
      title: "VPN FAQ",
      status: "published",
      visibility: "requester",
    },
    {
      item_id: "item-3",
      space_id: "space-internal",
      slug: "incident-runbook",
      item_type: "runbook",
      type: "runbook",
      title: "Incident runbook",
      status: "draft",
      visibility: "support_internal",
    },
  ],
};

const registryPayload = {
  status: "ok",
  people: [
    {
      person_id: "person-it-1",
      display_name: "Ирина Инженер",
      email: "it.user@example.test",
      department_id: "dep-it",
      location_id: "loc-ekb",
      status: "active",
    },
    {
      person_id: "person-support-1",
      display_name: "Сергей Поддержка",
      email: "support@example.test",
      department_id: "dep-support",
      location_id: "loc-ekb",
      status: "active",
    },
  ],
  departments: [
    { department_id: "dep-it", code: "IT", name: "ИТ", parent_id: null, status: "active" },
    { department_id: "dep-it-field", code: "IT-FIELD", name: "ИТ выездная", parent_id: "dep-it", status: "active" },
    { department_id: "dep-support", code: "SUPPORT", name: "Поддержка", parent_id: null, status: "active" },
  ],
  locations: [{ location_id: "loc-ekb", display_name: "Екатеринбург", status: "active" }],
  services: [{ id: "svc-vpn", code: "vpn", name: "VPN", status: "active" }],
};

const existingRules = [
  {
    rule_id: "rule-dep-it",
    subject_type: "space",
    subject_id: "space-it",
    target_type: "department",
    target_id: "dep-it",
    effect: "allow",
    include_children: false,
    priority: 10,
    status: "active",
    reason: "IT section",
    metadata_json: {},
  },
];

function setupFetch() {
  let currentRules = existingRules;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url === "/api/web/knowledge/spaces" && !init?.method) {
      return jsonResponse(spacesPayload);
    }
    if (url === "/api/web/knowledge/items" && !init?.method) {
      return jsonResponse(itemsPayload);
    }
    if (url === "/api/web/knowledge/spaces" && init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      return jsonResponse({
        status: "ok",
        space: {
          ...spacesPayload.spaces[0],
          ...body,
          space_id: body.space_id ?? "space-it",
        },
      });
    }
    if (url.startsWith("/api/web/admin/knowledge/audience-rules?") && !init?.method) {
      return jsonResponse({ status: "success", data: { rules: currentRules } });
    }
    if (url === "/api/web/admin/knowledge/audience-rules/preview" && init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      return jsonResponse({
        status: "success",
        data: {
          preview: {
            subject: { subject_type: body.subject_type, subject_id: body.subject_id },
            item: null,
            space: { space_id: body.subject_id, code: "it-self-service", title: "IT Self-Service" },
            audience: {
              person_id: "person-it-1",
              department_id: "dep-it",
              department_ids: ["dep-it"],
              access_group_ids: [],
              audience_group_ids: [],
              actor_id: body.actor_id,
              actor_role: body.actor_role,
            },
            decision: {
              allowed: true,
              reason_code: "audience_rule_matched",
              matched_rule_ids: ["rule-dep-it"],
            },
            safe_payload: {},
          },
        },
      });
    }
    if (url === "/api/web/admin/knowledge/audience-rules" && init?.method === "PUT") {
      const body = JSON.parse(String(init.body));
      currentRules = body.rules.map((rule: Record<string, unknown>, index: number) => ({
        rule_id: `saved-space-${index + 1}`,
        subject_type: body.subject_type,
        subject_id: body.subject_id,
        effect: "allow",
        include_children: rule.target_type === "department_tree",
        priority: (index + 1) * 10,
        status: "active",
        metadata_json: {},
        ...rule,
      }));
      return jsonResponse({ status: "success", data: { rules: currentRules } });
    }
    if (url === "/api/web/admin/registry" && !init?.method) {
      return jsonResponse(registryPayload);
    }
    if (url === "/api/web/admin/registry/audience-groups" && !init?.method) {
      return jsonResponse({
        status: "ok",
        groups: [{ audience_group_id: "aud-ops", code: "ops", name: "Операторы", status: "active" }],
      });
    }
    if (url === "/api/web/admin/access/summary" && !init?.method) {
      return jsonResponse({
        status: "success",
        data: {
          access_groups: [
            {
              group_id: 7,
              code: "support-line",
              name: "Линия поддержки",
              is_active: true,
              members: ["support@example.test"],
            },
          ],
        },
      });
    }

    throw new Error(`Unexpected fetch ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock as typeof fetch);
  return fetchMock;
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
      <MemoryRouter initialEntries={["/app/admin/knowledge/sections"]}>
        <AdminKnowledgeSectionsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AdminKnowledgeSectionsPage", () => {
  it("renders a localized section constructor without raw JSON wording", async () => {
    setupFetch();
    renderPage();

    expect(await screen.findByRole("heading", { name: "Разделы базы знаний" })).toBeInTheDocument();
    expect(await screen.findByText("IT Self-Service")).toBeInTheDocument();
    expect((await screen.findAllByText("it-self-service")).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Портал заявителя").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Используется в AI/RAG")).toBeInTheDocument();
    expect(screen.getAllByText("Импорт разрешен").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("button", { name: "Сохранить раздел" })).toBeInTheDocument();

    const visibleText = document.body.textContent ?? "";
    expect(visibleText).toContain("Аудитория раздела");
    expect(visibleText).not.toContain("raw JSON");
    expect(visibleText).not.toMatch(/\uFFFD|\u0420\u045A|\u0420\u045E|\u0420\u040F|\u0421\u045A|\u0421\u201A|\u0421\u2039|\u0421\u0453|\u0421\u2020|\u0421\u2021|\u0421\u02DC/);
  });

  it("previews and saves audience rules against the selected knowledge section", async () => {
    const fetchMock = setupFetch();
    renderPage();

    const panel = await screen.findByTestId("section-audience-panel");
    await waitFor(() => expect(within(panel).getAllByText("Подразделение: ИТ").length).toBeGreaterThanOrEqual(1));

    fireEvent.change(within(panel).getByLabelText("Тип правила"), { target: { value: "department_tree" } });
    fireEvent.change(within(panel).getByLabelText("Значение правила"), { target: { value: "dep-it" } });
    fireEvent.click(within(panel).getByRole("button", { name: "Добавить правило" }));
    expect(within(panel).getAllByText("Подразделение и дочерние: ИТ").length).toBeGreaterThanOrEqual(1);
    expect(within(panel).getByText("Оценка аудитории: 1 человек")).toBeInTheDocument();

    fireEvent.change(within(panel).getByLabelText("Пользователь для проверки"), {
      target: { value: "it.user@example.test" },
    });
    fireEvent.click(within(panel).getByRole("button", { name: "Предпросмотр аудитории" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/admin/knowledge/audience-rules/preview",
        expect.objectContaining({ method: "POST", credentials: "same-origin" }),
      ),
    );
    const previewCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/admin/knowledge/audience-rules/preview");
    expect(JSON.parse(String(previewCall?.[1]?.body))).toMatchObject({
      subject_type: "space",
      subject_id: "space-it",
      actor_id: "it.user@example.test",
      rules: expect.arrayContaining([expect.objectContaining({ target_type: "department_tree", target_id: "dep-it" })]),
    });
    expect(await within(panel).findByText(/Можно видеть/)).toBeInTheDocument();

    fireEvent.change(within(panel).getByLabelText("Причина изменения"), { target: { value: "K1 section audience" } });
    fireEvent.click(within(panel).getByRole("button", { name: "Сохранить аудиторию" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/admin/knowledge/audience-rules",
        expect.objectContaining({ method: "PUT", credentials: "same-origin" }),
      ),
    );
    const saveRulesCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/admin/knowledge/audience-rules" && call[1]?.method === "PUT");
    expect(JSON.parse(String(saveRulesCall?.[1]?.body))).toMatchObject({
      subject_type: "space",
      subject_id: "space-it",
      reason: "K1 section audience",
    });
    expect(await within(panel).findByText("Аудитория раздела сохранена")).toBeInTheDocument();
  });

  it("saves section policy flags through the existing knowledge spaces API", async () => {
    const fetchMock = setupFetch();
    renderPage();

    const editor = await screen.findByTestId("section-policy-editor");
    expect(await within(editor).findByDisplayValue("IT Self-Service")).toBeInTheDocument();
    fireEvent.change(within(editor).getByLabelText("Название раздела"), { target: { value: "IT Knowledge" } });
    fireEvent.change(within(editor).getByLabelText("Статус раздела"), { target: { value: "active" } });
    fireEvent.click(within(editor).getByRole("checkbox", { name: /Использовать в AI\/RAG/ }));
    fireEvent.click(within(editor).getByRole("button", { name: "Сохранить раздел" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/spaces",
        expect.objectContaining({ method: "POST", credentials: "same-origin" }),
      ),
    );
    const saveCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/knowledge/spaces" && call[1]?.method === "POST");
    expect(JSON.parse(String(saveCall?.[1]?.body))).toMatchObject({
      code: "it-self-service",
      title: "IT Knowledge",
      visibility: "requester",
      lifecycle_status: "active",
      allow_rag: false,
      allow_ingestion: true,
      allow_publication: true,
    });
    expect(await within(editor).findByText("Раздел сохранен")).toBeInTheDocument();
  });

  it("shows article counts and saves allowed material types plus exposure metadata", async () => {
    const fetchMock = setupFetch();
    renderPage();

    expect(await screen.findByText("2 статьи")).toBeInTheDocument();
    expect(await screen.findByText("1 статья")).toBeInTheDocument();

    const editor = await screen.findByTestId("section-policy-editor");
    expect(within(editor).getByText("Разрешенные типы материалов")).toBeInTheDocument();
    expect(within(editor).getByRole("checkbox", { name: /Статья/ })).toBeChecked();
    expect(within(editor).getByRole("checkbox", { name: /FAQ/ })).toBeChecked();
    expect(within(editor).getByRole("checkbox", { name: /Показывать в портале заявителя/ })).toBeChecked();
    expect(within(editor).getByRole("checkbox", { name: /Показывать в рабочем месте поддержки/ })).not.toBeChecked();

    fireEvent.click(within(editor).getByRole("checkbox", { name: /FAQ/ }));
    fireEvent.click(within(editor).getByRole("checkbox", { name: /Показывать в рабочем месте поддержки/ }));
    fireEvent.change(within(editor).getByLabelText("Рекомендация по объему статьи"), { target: { value: "detailed" } });
    fireEvent.click(within(editor).getByRole("button", { name: "Сохранить раздел" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/knowledge/spaces",
        expect.objectContaining({ method: "POST", credentials: "same-origin" }),
      ),
    );
    const saveCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/knowledge/spaces" && call[1]?.method === "POST");
    expect(JSON.parse(String(saveCall?.[1]?.body))).toMatchObject({
      code: "it-self-service",
      allowed_item_types: ["article", "runbook"],
      metadata: expect.objectContaining({
        owner_note: "preserve",
        show_in_requester_portal: true,
        show_in_support_workspace: true,
        article_length_recommendation: "detailed",
      }),
    });
  });

  it("shows per-list audience summaries without exposing raw target ids", async () => {
    const fetchMock = setupFetch();
    renderPage();

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith("/api/web/admin/knowledge/audience-rules?subject_type=space", { credentials: "same-origin" }),
    );
    expect(await screen.findByText("Аудитория: 1 человек")).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByText("Подразделение: ИТ").length).toBeGreaterThanOrEqual(1));
    expect(screen.getByText("Аудитория: без уточнения")).toBeInTheDocument();

    const visibleText = document.body.textContent ?? "";
    expect(visibleText).not.toContain("dep-it");
  });
});
