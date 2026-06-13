import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { MemoryRouter } from "react-router-dom";

import { AdminRegistryPage } from "./registry-page";

const registryPayload = {
  summary: {
    assets: 1,
    people: 1,
    locations: 1,
    departments: 1,
    services: 0,
    vendors: 0,
    registrations_pending: 0,
    registrations_conflicts: 0,
    unregistered_devices: 0,
    active_bindings: 0,
    stale_bindings: 0,
    data_quality_issues: 0,
    suggestions: 0,
    ui_users: 1,
    ui_users_linked: 0,
    ui_users_unlinked: 1,
  },
  assets: [
    {
      id: "asset-1",
      asset_type: "computer",
      name: "Office PC",
      hostname: "PC-01",
      serial_number: null,
      inventory_number: null,
      status: "active",
      source: "agent",
      device_id: "device-1",
      assigned_person_id: null,
      location_id: "loc-1",
      department_id: null,
      service_id: null,
      vendor_id: null,
      owner_name: null,
      registration_status: "unregistered",
      active_binding_id: null,
      active_person_id: null,
      active_person_name: null,
      pending_claim_count: 0,
      last_claim_at: null,
      current_os_user: null,
      department_name: null,
      location_name: "Кабинет 101",
      service_name: null,
      vendor_name: null,
      ticket_count: 0,
      last_seen_at: null,
      updated_at: null,
    },
  ],
  people: [
    {
      id: "person-1",
      person_id: "person-1",
      display_name: "Иван Петров",
      full_name: "Петров Иван",
      phone: null,
      email: "ivan@example.test",
      login: "ivan",
      department_id: null,
      location_id: "loc-1",
      department_name: null,
      location_name: "Кабинет 101",
      source: "manual",
      status: "active",
      updated_at: null,
    },
  ],
  locations: [
    {
      id: "loc-1",
      location_id: "loc-1",
      building: "HQ",
      floor: "1",
      room: "101",
      display_name: "Кабинет 101",
      source: "manual",
      status: "active",
      users_count: 1,
      devices_count: 1,
      updated_at: null,
    },
  ],
  departments: [
    {
      id: "dept-1",
      department_id: "dept-1",
      code: "it",
      name: "ИТ",
      source: "manual",
      status: "active",
      users_count: 0,
      devices_count: 0,
      updated_at: null,
    },
  ],
  services: [],
  vendors: [],
  data_quality: [],
  suggestions: [],
  registration_claims: [],
  active_bindings: [],
  bindings: [],
  account_sessions: [],
  account_login_requests: [],
  ui_users: [
    {
      user_login: "ivan@example.test",
      actor_role: "user",
      is_active: true,
      failed_attempts: 0,
      locked_until: null,
      last_login_at: null,
      created_at: null,
      updated_at: null,
      linked_person_id: null,
      linked_person_name: null,
      linked_identity_id: null,
      linked_identity_verified: false,
    },
  ],
};

const registryPayloadWithApprovalDiff = {
  ...registryPayload,
  registration_claims: [
    {
      claim_id: "claim-1",
      device_id: "device-1",
      asset_id: "asset-1",
      person_id: "person-claim",
      person_name: "Анна Смирнова",
      status: "conflict",
      claim_type: "self_reported",
      relationship_type: "primary_user",
      confidence: 0.9,
      submitted_at: "2026-06-13T12:00:00Z",
      user_confirmed_at: "2026-06-13T12:05:00Z",
      conflict_reason: "active_primary_user_exists",
      profile_snapshot: {
        hostname: "PC-01",
        full_name: "Анна Смирнова",
        login: "anna",
        email: "anna@example.test",
        department_id: "dept-1",
        location_id: "loc-1",
      },
    },
  ],
  active_bindings: [
    {
      binding_id: "binding-1",
      device_id: "device-1",
      asset_id: "asset-1",
      hostname: "PC-01",
      person_id: "person-1",
      person_name: "Иван Петров",
      relationship_type: "primary_user",
      status: "active",
      source: "registration_claim",
      source_claim_id: "old-claim",
      confirmed_at: "2026-06-12T09:00:00Z",
      confirmed_by_admin: "admin",
    },
  ],
  bindings: [
    {
      binding_id: "binding-1",
      device_id: "device-1",
      asset_id: "asset-1",
      hostname: "PC-01",
      person_id: "person-1",
      person_name: "Иван Петров",
      relationship_type: "primary_user",
      status: "active",
      source: "registration_claim",
      source_claim_id: "old-claim",
      confirmed_at: "2026-06-12T09:00:00Z",
      confirmed_by_admin: "admin",
    },
  ],
};

const audienceGroupsPayload = {
  groups: [
    {
      audience_group_id: "aud-1",
      code: "it_staff",
      name: "ИТ сотрудники",
      description: "Сотрудники ИТ",
      source: "manual",
      status: "active",
      metadata_json: {},
      created_at: null,
      updated_at: null,
      created_by: "admin",
      updated_by: "admin",
    },
  ],
};

const accessSummaryPayload = {
  version: "test",
  users: [
    {
      user_login: "ivan@example.test",
      actor_role: "user",
      role_label: "Пользователь",
      is_active: true,
      groups: ["support_l1"],
      queue_count: 1,
    },
  ],
  queues: [
    {
      queue_id: 1,
      queue_code: "support",
      queue_name: "Support",
      is_active: true,
      members_count: 1,
    },
  ],
  access_groups: [
    {
      group_id: 10,
      code: "support_l1",
      name: "Support L1",
      description: "Первая линия поддержки",
      is_active: true,
      permissions: ["tickets.view"],
      members: ["ivan@example.test"],
      queue_grants: [
        {
          queue_id: 1,
          queue_code: "support",
          queue_name: "Support",
          role_in_queue: "member",
        },
      ],
    },
  ],
  notes: ["Тестовая сводка RBAC"],
};

function jsonResponse(data: unknown) {
  return Promise.resolve(new Response(JSON.stringify({ status: "success", data }), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  }));
}

function renderRegistry() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AdminRegistryPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("AdminRegistryPage", () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let currentRegistryPayload: unknown;

  beforeEach(() => {
    currentRegistryPayload = registryPayload;
    fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.startsWith("/api/web/admin/registry/account-login-requests")) {
        return jsonResponse({ items: [] });
      }
      if (url === "/api/web/admin/registry") {
        return jsonResponse(currentRegistryPayload);
      }
      if (url === "/api/web/admin/registry/audience-groups") {
        if (init?.method === "POST") {
          return jsonResponse({ group: audienceGroupsPayload.groups[0] });
        }
        return jsonResponse(audienceGroupsPayload);
      }
      if (url === "/api/web/admin/registry/audience-groups/aud-1/members") {
        if (init?.method === "PUT") {
          return jsonResponse({ members: [{ member_type: "department_tree", member_id: "dept-1", include_children: true }] });
        }
        return jsonResponse({ members: [] });
      }
      if (url === "/api/web/admin/registry/audience-groups/aud-1/preview-members") {
        return jsonResponse({
          preview: {
            audience_group_id: "aud-1",
            code: "it_staff",
            member_count: 1,
            person_count: 1,
            people: [{ person_id: "person-1", display_name: "Иван Петров", full_name: null, email: "ivan@example.test", department_id: "dept-1", location_id: "loc-1", status: "active" }],
            warnings: [],
          },
        });
      }
      if (url === "/api/web/admin/access/summary") {
        return jsonResponse(accessSummaryPayload);
      }
      if (url === "/api/web/admin/registry/bulk/preview") {
        return jsonResponse({
          operation: "devices.assign_department",
          dry_run: true,
          requires_confirmation: true,
          counts: { requested: 1, successful: 1, failed: 0, changes: 1 },
          results: [{ id: "device-1", success: true }],
          changes: [{ kind: "registry_asset", action: "update", object_id: "asset-1" }],
          warnings: [],
          blockers: [],
        });
      }
      if (url === "/api/web/admin/registry/bulk/devices/assign-department") {
        return jsonResponse({
          bulk_operation_id: "bulk-1",
          operation: "devices.assign_department",
          summary: { selected: 1, success: 1, failed: 0 },
          items: [{ id: "device-1", status: "success" }],
        });
      }
      return Promise.resolve(new Response(JSON.stringify({ status: "error", error: `unexpected ${url}` }), {
        headers: { "Content-Type": "application/json" },
        status: 500,
      }));
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("does not use window.prompt in registry operator UI", () => {
    expect(readFileSync("src/pages/admin/registry-page.tsx", "utf-8")).not.toContain("window.prompt");
    expect(readFileSync("src/features/admin/registry/registry-quality-tab.tsx", "utf-8")).not.toContain("window.prompt");
  });

  it("uses a bulk dialog with department picker and preview before apply", async () => {
    renderRegistry();

    fireEvent.click(await screen.findByRole("button", { name: "Устройства" }));
    fireEvent.click(await screen.findByLabelText("Select device PC-01"));
    fireEvent.click(screen.getByRole("button", { name: "Назначить подразделение" }));

    expect(screen.getByRole("heading", { name: "Массовая операция" })).toBeInTheDocument();
    expect(screen.getByText("Выберите подразделение")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Подразделение"), { target: { value: "dept-1" } });
    fireEvent.change(screen.getByLabelText("Причина"), { target: { value: "Плановая нормализация реестра" } });
    expect(screen.getByRole("button", { name: "Применить" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Предпросмотр" }));
    expect(await screen.findByText("Предпросмотр изменений")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Применить" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/admin/registry/bulk/devices/assign-department",
      expect.objectContaining({ method: "POST" })
    ));
  });

  it("manages audience group members with preview before save", async () => {
    renderRegistry();

    fireEvent.click(await screen.findByRole("button", { name: /Аудитории/ }));
    expect(await screen.findByText("ИТ сотрудники")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Тип участника"), { target: { value: "department_tree" } });
    fireEvent.change(screen.getByLabelText("Участник"), { target: { value: "dept-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Добавить участника" }));
    fireEvent.change(screen.getByLabelText("Причина изменения аудитории"), { target: { value: "Настройка видимости базы знаний" } });
    expect(screen.getByRole("button", { name: "Сохранить участников" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Предпросмотр состава" }));
    expect(await screen.findByText("Людей в аудитории: 1")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Сохранить участников" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/admin/registry/audience-groups/aud-1/members",
      expect.objectContaining({ method: "PUT" })
    ));
  });

  it("shows access groups as a registry summary with a link to the canonical RBAC editor", async () => {
    renderRegistry();

    fireEvent.click(await screen.findByRole("button", { name: /Группы доступа/ }));

    expect(await screen.findByText("Support L1")).toBeInTheDocument();
    expect(screen.getByText("Первая линия поддержки")).toBeInTheDocument();
    expect(screen.getByText("1 permissions")).toBeInTheDocument();
    expect(screen.getByText("1 members")).toBeInTheDocument();
    expect(screen.getByText("1 queues")).toBeInTheDocument();
    expect(screen.getByText("Тестовая сводка RBAC")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Открыть RBAC-редактор" })).toHaveAttribute("href", "/app/admin/access");
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/web\/admin\/access\/groups/),
      expect.objectContaining({ method: expect.stringMatching(/POST|PUT|PATCH|DELETE/) }),
    );
  });

  it("shows an approval diff for registration claims before admin actions", async () => {
    currentRegistryPayload = registryPayloadWithApprovalDiff;
    renderRegistry();

    fireEvent.click(await screen.findByRole("button", { name: "Заявки" }));

    expect(await screen.findByText("Дифф подтверждения")).toBeInTheDocument();
    expect(screen.getByText("Текущая привязка: Иван Петров · primary_user")).toBeInTheDocument();
    expect(screen.getByText("Заявлено: Анна Смирнова")).toBeInTheDocument();
    expect(screen.getByText("Подразделение: ИТ")).toBeInTheDocument();
    expect(screen.getByText("Локация: Кабинет 101")).toBeInTheDocument();
    expect(screen.getByText("Идентичность: anna@example.test / anna")).toBeInTheDocument();
    expect(screen.getByText("Тип привязки: primary_user")).toBeInTheDocument();
    expect(screen.getByText("Блокер: active_primary_user_exists")).toBeInTheDocument();
  });
});
