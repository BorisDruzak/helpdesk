import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ArticleVisibilityPanel } from "./article-visibility-panel";
import type { KnowledgeItem } from "./api";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const baseItem = {
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
  current_version_id: "ver-1",
  updated_at: "2026-06-14T08:00:00Z",
} as KnowledgeItem;

const registryPayload = {
  status: "ok",
  summary: {
    assets: 0,
    people: 3,
    locations: 1,
    departments: 2,
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
      id: "person-it-1",
      person_id: "person-it-1",
      display_name: "Иван ИТ",
      full_name: "Иван ИТ",
      phone: null,
      email: "it.user@example.test",
      login: "it.user@example.test",
      department_id: "dep-it",
      location_id: "loc-ekb",
      department_name: "ИТ",
      location_name: "Екатеринбург",
      source: "test",
      status: "active",
      updated_at: "2026-06-14T08:00:00Z",
    },
    {
      id: "person-it-2",
      person_id: "person-it-2",
      display_name: "Сервис-деск",
      full_name: "Сервис-деск",
      phone: null,
      email: "support@example.test",
      login: "support@example.test",
      department_id: "dep-helpdesk",
      location_id: "loc-ekb",
      department_name: "Сервис-деск",
      location_name: "Екатеринбург",
      source: "test",
      status: "active",
      updated_at: "2026-06-14T08:00:00Z",
    },
    {
      id: "person-finance",
      person_id: "person-finance",
      display_name: "Финансы",
      full_name: "Финансы",
      phone: null,
      email: "finance@example.test",
      login: "finance@example.test",
      department_id: "dep-finance",
      location_id: "loc-ekb",
      department_name: "Бухгалтерия",
      location_name: "Екатеринбург",
      source: "test",
      status: "active",
      updated_at: "2026-06-14T08:00:00Z",
    },
  ],
  locations: [
    {
      id: "loc-ekb",
      location_id: "loc-ekb",
      building: "HQ",
      floor: null,
      room: null,
      display_name: "Екатеринбург",
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
      name: "ИТ",
      parent_id: null,
      source: "test",
      status: "active",
      updated_at: "2026-06-14T08:00:00Z",
    },
    {
      id: "dep-helpdesk",
      department_id: "dep-helpdesk",
      code: "helpdesk",
      name: "Сервис-деск",
      parent_id: "dep-it",
      source: "test",
      status: "active",
      updated_at: "2026-06-14T08:00:00Z",
    },
    {
      id: "dep-finance",
      department_id: "dep-finance",
      code: "finance",
      name: "Бухгалтерия",
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
      name: "Сеть",
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
};

const existingRules = [
  {
    rule_id: "rule-dep-it",
    subject_type: "item",
    subject_id: "item-1",
    target_type: "department",
    target_id: "dep-it",
    effect: "allow",
    include_children: false,
    priority: 10,
    status: "active",
    reason: "IT article",
    metadata_json: {},
  },
];

function setupFetch(initialRules = existingRules) {
  let currentRules = initialRules;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.startsWith("/api/web/admin/knowledge/audience-rules?") && !init?.method) {
      return jsonResponse({ status: "success", data: { rules: currentRules } });
    }
    if (url === "/api/web/admin/knowledge/audience-rules" && init?.method === "PUT") {
      const body = JSON.parse(String(init.body));
      currentRules = body.rules.map((rule: Record<string, unknown>, index: number) => ({
        rule_id: `saved-${index + 1}`,
        subject_type: body.subject_type,
        subject_id: body.subject_id,
        effect: "allow",
        status: "active",
        metadata_json: {},
        priority: (index + 1) * 10,
        ...rule,
      }));
      return jsonResponse({ status: "success", data: { rules: currentRules } });
    }
    if (url === "/api/web/admin/knowledge/audience-rules/preview" && init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      const allowed = String(body.actor_id ?? "").includes("it.user");
      return jsonResponse({
        status: "success",
        data: {
          preview: {
            subject: { subject_type: "item", subject_id: "item-1" },
            audience: {
              person_id: allowed ? "person-it-1" : "person-finance",
              department_id: allowed ? "dep-it" : "dep-finance",
              department_ids: allowed ? ["dep-it"] : ["dep-finance"],
              audience_group_ids: allowed ? ["aud-ops"] : [],
              access_group_ids: [],
              actor_id: body.actor_id,
              actor_role: body.actor_role,
            },
            decision: {
              allowed,
              reason_code: allowed ? "audience_rule_matched" : "audience_rule_not_matched",
              matched_rule_ids: allowed ? ["rule-dep-it"] : [],
            },
            safe_payload: {},
          },
        },
      });
    }
    if (url.startsWith("/api/web/admin/knowledge/access/explain?") && !init?.method) {
      return jsonResponse({
        status: "success",
        data: {
          explain: {
            item: { item_id: "item-1", visibility: "requester" },
            audience: { person_id: "person-it-1", department_id: "dep-it" },
            rules: currentRules,
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
    if (url === "/api/web/admin/registry" && !init?.method) {
      return jsonResponse(registryPayload);
    }
    if (url === "/api/web/admin/registry/audience-groups" && !init?.method) {
      return jsonResponse({
        status: "ok",
        groups: [
          {
            audience_group_id: "aud-ops",
            code: "ops",
            name: "Операторы",
            description: "Операционная аудитория",
            source: "test",
            status: "active",
            metadata_json: {},
            created_at: "2026-06-14T08:00:00Z",
            updated_at: "2026-06-14T08:00:00Z",
            created_by: "admin",
            updated_by: "admin",
          },
        ],
      });
    }
    if (url === "/api/web/admin/access/summary" && !init?.method) {
      return jsonResponse({
        status: "success",
        data: {
          version: "test",
          users: [],
          queues: [],
          access_groups: [
            {
              group_id: 7,
              code: "support-line",
              name: "Линия поддержки",
              description: null,
              is_active: true,
              permissions: ["knowledge.view"],
              members: ["support@example.test"],
              queue_grants: [],
            },
          ],
          notes: [],
        },
      });
    }
    throw new Error(`Unexpected fetch ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock as typeof fetch);
  return fetchMock;
}

function renderPanel(item: KnowledgeItem = baseItem) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <ArticleVisibilityPanel canManage item={item} coarseVisibility={item.visibility} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ArticleVisibilityPanel", () => {
  it("loads registry-backed rules, previews access and saves the selected audience round-trip", async () => {
    const fetchMock = setupFetch();
    renderPanel();

    const panel = await screen.findByTestId("article-visibility-panel");
    expect(within(panel).getByRole("heading", { name: "Аудитория" })).toBeInTheDocument();
    expect(within(panel).getByText("Портал заявителя")).toBeInTheDocument();
    await waitFor(() => expect(within(panel).getAllByText("Подразделение: ИТ").length).toBeGreaterThanOrEqual(1));
    expect(within(panel).getByText("Оценка аудитории: 1 человек")).toBeInTheDocument();

    fireEvent.change(within(panel).getByLabelText("Тип правила"), { target: { value: "department_tree" } });
    fireEvent.change(within(panel).getByLabelText("Значение правила"), { target: { value: "dep-it" } });
    fireEvent.click(within(panel).getByRole("button", { name: "Добавить правило" }));
    expect(within(panel).getAllByText("Подразделение и дочерние: ИТ").length).toBeGreaterThanOrEqual(1);
    expect(within(panel).getByText("Оценка аудитории: 2 человека")).toBeInTheDocument();

    fireEvent.change(within(panel).getByLabelText("Тип правила"), { target: { value: "audience_group" } });
    fireEvent.change(within(panel).getByLabelText("Значение правила"), { target: { value: "aud-ops" } });
    fireEvent.click(within(panel).getByRole("button", { name: "Добавить правило" }));
    expect(within(panel).getAllByText("Аудитория: Операторы").length).toBeGreaterThanOrEqual(1);

    fireEvent.change(within(panel).getByLabelText("Пользователь для проверки"), {
      target: { value: "it.user@example.test" },
    });
    fireEvent.click(within(panel).getByRole("button", { name: "Предпросмотр правил" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/admin/knowledge/audience-rules/preview",
        expect.objectContaining({ method: "POST", credentials: "same-origin" }),
      ),
    );
    expect(await within(panel).findByText(/Можно видеть/)).toBeInTheDocument();

    fireEvent.click(within(panel).getByRole("button", { name: "Проверить доступ" }));
    await waitFor(() => expect(fetchMock.mock.calls.some((call) => String(call[0]).startsWith("/api/web/admin/knowledge/access/explain?"))).toBe(true));
    await waitFor(() => expect(within(panel).getAllByText(/Причина решения: audience_rule_matched/).length).toBeGreaterThanOrEqual(1));

    fireEvent.change(within(panel).getByLabelText("Причина изменения"), { target: { value: "Сужаем статью до ИТ" } });
    fireEvent.click(within(panel).getByRole("button", { name: "Сохранить правила видимости" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/admin/knowledge/audience-rules",
        expect.objectContaining({ method: "PUT", credentials: "same-origin" }),
      ),
    );
    const saveCall = fetchMock.mock.calls.find((call) => call[0] === "/api/web/admin/knowledge/audience-rules" && call[1]?.method === "PUT");
    expect(JSON.parse(String(saveCall?.[1]?.body))).toMatchObject({
      subject_type: "item",
      subject_id: "item-1",
      reason: "Сужаем статью до ИТ",
      rules: expect.arrayContaining([
        expect.objectContaining({ target_type: "department_tree", target_id: "dep-it", include_children: true }),
        expect.objectContaining({ target_type: "audience_group", target_id: "aud-ops" }),
      ]),
    });
    expect(await within(panel).findByText("Правила видимости сохранены")).toBeInTheDocument();
  });

  it("warns that internal articles cannot become requester-visible and renders Russian text without mojibake", async () => {
    setupFetch([]);
    renderPanel({ ...baseItem, visibility: "support_internal" });

    const panel = await screen.findByTestId("article-visibility-panel");
    expect(await within(panel).findByText("Внутренний материал не станет видимым заявителям из-за правил аудитории.")).toBeInTheDocument();
    const visibleText = panel.textContent ?? "";
    expect(visibleText).toContain("Аудитория уточняет доступ внутри выбранной видимости");
    expect(visibleText).not.toMatch(/\uFFFD|\u0420\u045A|\u0420\u045E|\u0420\u040F|\u0421\u045A|\u0421\u201A|\u0421\u2039|\u0421\u0453|\u0421\u2020|\u0421\u2021|\u0421\u02DC/);
  });
});
